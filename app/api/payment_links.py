from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.payment_link import PaymentLinkCancel, PaymentLinkCreate, PaymentLinkRead
from app.services.payment_link_service import (
    PaymentLinkError,
    cancel_link,
    create_link,
    list_links_for_reservation,
    resolve_signed_external_reference,
)
from app.services.payment_link_test_service import PaymentLinkTestError, validate_mercadopago_webhook_signature
from app.services.payment_webhook_service import PaymentWebhookError, ingest_webhook

router = APIRouter(tags=["Payment Links"])


def _authorized_context() -> AuthContext:
    return Depends(require_roles("owner", "co_owner", "manager", "receptionist"))


@router.post("/api/payment-links", response_model=PaymentLinkRead, status_code=status.HTTP_201_CREATED)
@router.post("/payment-links", response_model=PaymentLinkRead, status_code=status.HTTP_201_CREATED)
def create_payment_link(
    payload: PaymentLinkCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    try:
        link = create_link(db, context.hotel_id, payload)
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    return list_links_for_reservation(db, context.hotel_id, reservation_id)


@router.post("/api/payment-links/{link_id}/cancel", response_model=PaymentLinkRead)
@router.post("/payment-links/{link_id}/cancel", response_model=PaymentLinkRead)
def cancel_payment_link(
    link_id: int,
    payload: PaymentLinkCancel | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
):
    try:
        link = cancel_link(db, context.hotel_id, link_id, reason=payload.reason if payload else None)
        db.commit()
        db.refresh(link)
        return link
    except PaymentLinkError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc))


async def _mercadopago_webhook_impl(request: Request, db: Session) -> dict:
    payload = {}
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    data = payload.get("data") if isinstance(payload, dict) else {}
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
        webhook_id = str(request.query_params.get("webhook_id") or data_id or payload.get("id") or "")
        if not webhook_id:
            return {"status": "ignored", "reason": "webhook_id_missing"}
        result = ingest_webhook(
            db,
            hotel_id=hotel_id,
            provider="mercado_pago",
            webhook_id=webhook_id,
            payload={**payload, "external_reference": str(external_reference)},
        )
        db.commit()
        return result
    except (PaymentLinkError, PaymentLinkTestError) as exc:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(exc))
    except PaymentWebhookError as exc:
        db.rollback()
        return {"status": "error", "reason": str(exc)}


@router.post("/api/payment-links/mercadopago/webhook")
@router.post("/payment-links/mercadopago/webhook")
async def mercadopago_payment_link_webhook(request: Request, db: Session = Depends(get_db)):
    return await _mercadopago_webhook_impl(request, db)
