import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.webhook_payloads import read_bounded_body
from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.payment_link import (
    PaymentLinkCancel,
    PaymentLinkCreate,
    PaymentLinkRead,
)
from app.services.external_effects_policy import (
    InboundProviderEventsDisabled,
    require_inbound_provider_events,
)
from app.services.payment_link_service import (
    PaymentLinkError,
    cancel_link,
    create_link,
    list_links_for_reservation,
    process_payment_link_revocations,
    resolve_signed_external_reference,
)
from app.services.payment_link_test_service import (
    PaymentLinkTestError,
    validate_mercadopago_webhook_signature,
)
from app.services.payment_webhook_service import (
    PaymentWebhookError,
    RetryablePaymentWebhookError,
    ingest_webhook,
    normalize_webhook_identifier,
)
from app.services.permission_service import PERMISSION_CASH_OPERATE

router = APIRouter(tags=["Payment Links"])
logger = logging.getLogger(__name__)


def _authorized_context() -> AuthContext:
    return Depends(require_permission(PERMISSION_CASH_OPERATE))


@router.post("/api/payment-links", response_model=PaymentLinkRead, status_code=status.HTTP_201_CREATED)
@router.post("/payment-links", response_model=PaymentLinkRead, status_code=status.HTTP_201_CREATED)
def create_payment_link(
    payload: PaymentLinkCreate,
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
        min_length=8,
        max_length=100,
    ),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        link = create_link(
            db,
            context.hotel_id,
            payload,
            idempotency_key=idempotency_key,
        )
        db.commit()
        db.refresh(link)
        return link
    except PaymentLinkError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/api/payment-links", response_model=list[PaymentLinkRead])
@router.get("/payment-links", response_model=list[PaymentLinkRead])
def list_payment_links(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    return list_links_for_reservation(db, context.hotel_id, reservation_id)


@router.post("/api/payment-links/{link_id}/cancel", response_model=PaymentLinkRead)
@router.post("/payment-links/{link_id}/cancel", response_model=PaymentLinkRead)
def cancel_payment_link(
    link_id: int,
    payload: PaymentLinkCancel | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        link = cancel_link(db, context.hotel_id, link_id, reason=payload.reason if payload else None)
        db.commit()
    except PaymentLinkError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))

    # Provider calls happen only after local cancellation has committed. A
    # provider/configuration failure must leave the cancellation intact.
    try:
        process_payment_link_revocations(
            db,
            context.hotel_id,
            reservation_id=link.reservation_id,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 - local cancellation is already durable
        db.rollback()
        logger.warning(
            "payment_link.revocation_attempt_unavailable hotel_id=%s payment_link_id=%s error_type=%s",
            context.hotel_id,
            link.id,
            type(exc).__name__,
        )
    db.refresh(link)
    return link


async def _mercadopago_webhook_impl(request: Request, db: Session) -> dict:
    try:
        # This must stay before request.json(), secret lookup, and every DB
        # mutation. A disabled callback lane is intentionally content-agnostic.
        require_inbound_provider_events("Mercado Pago")
    except InboundProviderEventsDisabled as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    payload = {}
    try:
        raw_body = await read_bounded_body(request, max_bytes=1024 * 1024)
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    external_reference = request.query_params.get("external_reference")
    if not external_reference and isinstance(payload, dict):
        external_reference = payload.get("external_reference")
    if not external_reference and isinstance(data, dict):
        external_reference = data.get("external_reference")
    if not external_reference:
        return {"status": "ignored", "reason": "external_reference_missing"}

    data_id = request.query_params.get("data.id") or request.query_params.get("data_id") or request.query_params.get("id")
    if not data_id and isinstance(data, dict):
        data_id = data.get("id") or data.get("id_url")

    try:
        validate_mercadopago_webhook_signature(
            get_settings().MERCADOPAGO_WEBHOOK_SECRET,
            data_id=str(data_id or ""),
            request_id=request.headers.get("x-request-id") or request.headers.get("X-Request-Id"),
            signature_header=request.headers.get("x-signature") or request.headers.get("X-Signature"),
        )
        hotel_id, _link_code = resolve_signed_external_reference(str(external_reference))
        webhook_id = ""
        for candidate in (request.query_params.get("webhook_id"), payload.get("id"), data_id):
            webhook_id = normalize_webhook_identifier(candidate) or ""
            if webhook_id:
                break
        if not webhook_id:
            return {"status": "ignored", "reason": "webhook_id_missing"}
        ingest_payload = {
            **payload,
            "external_reference": str(external_reference),
            # The signature authenticates data_id. Never let an unsigned
            # payment_id value from the body override that resource ID.
            "payment_id": str(data_id or ""),
        }
        if isinstance(payload.get("data"), dict):
            ingest_payload["data"] = {
                **payload["data"],
                # The notification body is not fully authenticated. Replace
                # nested correlation fields with the verified values before
                # the service can retain its audit projection.
                "external_reference": str(external_reference),
                **({"id": str(data_id)} if data_id else {}),
            }
        result = ingest_webhook(
            db,
            hotel_id=hotel_id,
            provider="mercado_pago",
            webhook_id=webhook_id,
            payload=ingest_payload,
        )
        db.commit()
        return result
    except (PaymentLinkError, PaymentLinkTestError) as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(exc))
    except RetryablePaymentWebhookError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No se pudo verificar el pago temporalmente; el webhook puede reintentarse.",
        ) from exc
    except PaymentWebhookError as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}


@router.post("/api/payment-links/mercadopago/webhook")
@router.post("/payment-links/mercadopago/webhook")
async def mercadopago_payment_link_webhook(request: Request, db: Session = Depends(get_db)):
    return await _mercadopago_webhook_impl(request, db)
