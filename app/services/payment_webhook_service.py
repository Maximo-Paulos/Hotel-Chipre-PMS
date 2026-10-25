"""Production gateway webhook ingestion.

Idempotency has two layers:
  1. payment_webhook_events unique (hotel_id, provider, webhook_id) — a re-delivered
     webhook is a no-op.
  2. transactions.idempotency_key — even if two DISTINCT webhooks report the same
     completed payment, only ONE Transaction is ever written.

A completed gateway Payment writes exactly one Transaction via payment_service.process_payment
(the canonical ledger). PaymentLink collection totals are recomputed from completed Payments.
"""
import hashlib
import json
import re
from datetime import UTC, datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import requests
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification import NotificationChannelEnum, NotificationSeverityEnum
from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services.external_effects_policy import (
    ExternalEffectsDisabled,
    require_external_connections,
    require_inbound_provider_events,
)
from app.services.outbound_http_telemetry import observed_http_call
from app.services.payment_link_service import _money, refresh_link_collection
from app.services.payment_link_test_service import PaymentLinkTestError
from app.services.payment_link_test_service import (
    validate_mercadopago_webhook_signature as _validate_signature_or_raise,
)
from app.services.payment_service import (
    calculate_base_amount_before_surcharge,
    process_payment,
)
from app.services.row_locks import lock_query
from app.services.tenant_context import set_tenant_hotel_context


class PaymentWebhookError(Exception):
    pass


class RetryablePaymentWebhookError(PaymentWebhookError):
    """A provider verification failure that may succeed on webhook retry."""


# These are the provider payment fields needed to reconcile a charge and
# explain its state transition. Provider responses also contain payer, card,
# address, and arbitrary merchant metadata, so never persist the full object.
_PAYMENT_RESPONSE_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "external_reference": (
        "external_reference",
        "data.external_reference",
        "metadata.external_reference",
        "data.metadata.external_reference",
    ),
    "status": ("status", "data.status"),
    "status_detail": ("status_detail", "data.status_detail"),
    "transaction_amount": (
        "transaction_amount",
        "amount",
        "data.transaction_amount",
        "data.amount",
    ),
    "currency_id": ("currency_id", "currency", "data.currency_id", "data.currency"),
    "date_created": ("date_created", "data.date_created"),
    "date_approved": ("date_approved", "completed_at", "data.date_approved"),
    "date_last_updated": ("date_last_updated", "data.date_last_updated"),
    "collector_id": (
        "collector_id",
        "user_id",
        "data.collector_id",
        "data.user_id",
        "metadata.account_id",
        "data.metadata.account_id",
    ),
    "transaction_amount_refunded": (
        "transaction_amount_refunded",
        "data.transaction_amount_refunded",
    ),
    "amount_refunded": ("amount_refunded", "data.amount_refunded"),
}

_WEBHOOK_TYPES = frozenset({"payment"})
_WEBHOOK_ACTIONS = frozenset({"payment.created", "payment.updated"})
_WEBHOOK_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_PAYMENT_RECONCILIATION_REVIEW_CODES = frozenset(
    {
        "legacy_link_amount_exceeds_link_balance_review_required",
        "legacy_link_amount_exceeds_reservation_balance_review_required",
        "legacy_link_missing_payment_fx_snapshot_review_required",
    }
)


def _is_json_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool))


def normalize_webhook_identifier(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        value = str(value)
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized if _WEBHOOK_IDENTIFIER_RE.fullmatch(normalized) else None


def _safe_webhook_event_type(payload: dict[str, Any]) -> str:
    event_type = _payload_value(payload, "type")
    if isinstance(event_type, str) and event_type.strip().lower() in _WEBHOOK_TYPES:
        return event_type.strip().lower()
    action = _payload_value(payload, "action")
    if isinstance(action, str) and action.strip().lower() in _WEBHOOK_ACTIONS:
        return action.strip().lower()
    return ""


def _payment_response_projection(payload: dict[str, Any], external_payment_id: str) -> dict[str, Any]:
    """Return the small, non-PII subset needed to reconcile a provider payment."""
    projection: dict[str, Any] = {"id": external_payment_id}
    for field, aliases in _PAYMENT_RESPONSE_FIELD_ALIASES.items():
        value = _payload_value(payload, *aliases)
        if _is_json_scalar(value):
            projection[field] = value
    return projection


def _webhook_event_payload_projection(payload: dict[str, Any]) -> dict[str, Any]:
    """Retain bounded event identifiers and a validated, non-sensitive envelope."""
    projection: dict[str, Any] = {}
    event_id = normalize_webhook_identifier(payload.get("id"))
    if event_id:
        projection["id"] = event_id

    event_type = payload.get("type")
    if isinstance(event_type, str) and event_type.strip().lower() in _WEBHOOK_TYPES:
        projection["type"] = event_type.strip().lower()
    action = payload.get("action")
    if isinstance(action, str) and action.strip().lower() in _WEBHOOK_ACTIONS:
        projection["action"] = action.strip().lower()

    api_version = payload.get("api_version")
    if api_version == "v1":
        projection["api_version"] = "v1"
    if isinstance(payload.get("live_mode"), bool):
        projection["live_mode"] = payload["live_mode"]

    external_reference = payload.get("external_reference")
    if isinstance(external_reference, str) and len(external_reference) <= 256:
        projection["external_reference"] = external_reference
    payment_id = normalize_webhook_identifier(payload.get("payment_id"))
    if payment_id:
        projection["payment_id"] = payment_id

    data = payload.get("data")
    if isinstance(data, dict):
        resource_id = normalize_webhook_identifier(data.get("id"))
        if resource_id:
            projection["data"] = {"id": resource_id}
    return projection


def fetch_mercadopago_payment(
    db: Session,
    hotel_id: int,
    external_payment_id: str,
    *,
    commit_before_network: bool = False,
) -> dict[str, Any]:
    """Verify a signed notification against the active hotel's MP account."""
    require_external_connections("Mercado Pago payment verification")
    from app.services.integration_service import get_connection_payload  # noqa: PLC0415

    connection_payload = get_connection_payload(db, hotel_id, "mercadopago")
    access_token = str(connection_payload.get("access_token") or "").strip()
    if not access_token:
        raise PaymentWebhookError("El hotel no tiene una cuenta de Mercado Pago conectada")
    if commit_before_network:
        # PaymentLinkTest has only read this session so far. Release its tenant
        # scoped transaction before waiting on Mercado Pago's network response.
        db.commit()
    try:
        response = observed_http_call("mercadopago.payment_verify", requests.get,
            f"https://api.mercadopago.com/v1/payments/{external_payment_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20,
        )
    except requests.RequestException as exc:
        raise RetryablePaymentWebhookError("No se pudo consultar el pago en Mercado Pago") from exc
    if not response.ok:
        if response.status_code in {408, 425, 429} or response.status_code >= 500:
            raise RetryablePaymentWebhookError("Mercado Pago no pudo verificar el pago informado")
        raise PaymentWebhookError("Mercado Pago no pudo verificar el pago informado")
    try:
        data = response.json()
    except ValueError as exc:
        raise RetryablePaymentWebhookError("Mercado Pago devolvio una respuesta de pago invalida") from exc
    if not isinstance(data, dict):
        raise RetryablePaymentWebhookError("Mercado Pago devolvio una respuesta de pago invalida")
    return data


def validate_mercadopago_webhook_signature(
    secret: str,
    *,
    data_id: str,
    request_id: str | None,
    signature_header: str | None,
) -> bool:
    """Bool-returning shim over the canonical (raising, replay-protected)
    validator in payment_link_test_service — the one every real webhook route
    actually calls. Kept only so existing callers of this bool API don't need
    to change; there is exactly ONE signature-checking implementation now.
    """
    try:
        _validate_signature_or_raise(
            secret, data_id=data_id, request_id=request_id, signature_header=signature_header
        )
        return True
    except PaymentLinkTestError:
        return False


def _payload_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        current: Any = payload
        found = True
        for part in key.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                found = False
                break
        if found and current not in (None, ""):
            return current
    return None


def _normalize_status(provider: str, status: str | None) -> str:
    normalized = (status or "").strip().lower()
    if provider == "mercado_pago" and normalized == "approved":
        return "completed"
    if normalized in {"completed", "paid", "succeeded", "success"}:
        return "completed"
    if normalized in {"rejected", "failed", "cancelled", "canceled", "charged_back"}:
        return "failed"
    if normalized in {"refunded", "partially_refunded"}:
        return normalized
    return "pending"


def _completed_at(payload: dict[str, Any]) -> datetime:
    for key in ("date_approved", "completed_at", "date_last_updated"):
        raw = _payload_value(payload, key)
        if raw:
            try:
                return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            except ValueError:
                pass
    return datetime.now(timezone.utc)


# Payment status state machine. A later-arriving webhook (out-of-order delivery,
# or a stale retry) must never regress a payment past a terminal state, and a
# rejected/failed payment must never become completed except through a brand
# new payment id (that is a distinct, correctly-approved payment).
_ALLOWED_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"pending", "completed", "failed", "refunded", "partially_refunded"},
    "completed": {"completed", "refunded", "partially_refunded"},
    "failed": {"failed"},
    "refunded": {"refunded"},
    "partially_refunded": {"partially_refunded", "refunded"},
}


def _is_allowed_status_transition(current: str, new: str) -> bool:
    return new in _ALLOWED_STATUS_TRANSITIONS.get(current, {new})


def _find_existing_event(db: Session, hotel_id: int, provider: str, webhook_id: str) -> PaymentWebhookEvent | None:
    return (
        db.query(PaymentWebhookEvent)
        .filter(
            PaymentWebhookEvent.hotel_id == hotel_id,
            PaymentWebhookEvent.provider == provider,
            PaymentWebhookEvent.webhook_id == webhook_id,
        )
        .first()
    )


def _acquire_postgres_webhook_lock(
    db: Session,
    *,
    hotel_id: int,
    provider: str,
    scope: str,
    identifier: str,
) -> None:
    """Serialize webhook idempotency checks for the current PostgreSQL transaction.

    The event lock handles the same provider notification arriving concurrently;
    the payment lock handles separate notifications for the same provider payment.
    PostgreSQL owns both locks until the caller commits or rolls back. Other test
    dialects continue to rely on the database uniqueness constraints.
    """
    if db.get_bind().dialect.name != "postgresql":
        return

    lock_material = "\0".join(("hotel-chipre-payment-webhook", scope, str(hotel_id), provider, identifier))
    lock_id = int.from_bytes(
        hashlib.blake2b(lock_material.encode("utf-8"), digest_size=8).digest(),
        byteorder="big",
        signed=True,
    )
    db.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})


def _insert_event(
    db: Session, hotel_id: int, payment_id: int, provider: str, webhook_id: str, payload: dict[str, Any]
) -> tuple[PaymentWebhookEvent, bool]:
    event = PaymentWebhookEvent(
        hotel_id=hotel_id,
        payment_id=payment_id,
        provider=provider,
        webhook_id=webhook_id,
        event_type=_safe_webhook_event_type(payload),
        raw_payload=_webhook_event_payload_projection(payload),
        processed=False,
    )
    try:
        # Savepoint so a concurrent-insert IntegrityError rolls back ONLY this event,
        # never the outer transaction (which holds the already-created Payment).
        # The db.add() MUST happen inside begin_nested() so the pending INSERT is
        # owned by the savepoint; otherwise an autoflush could emit it outside the
        # savepoint and a concurrent duplicate would poison the outer transaction.
        with db.begin_nested():
            db.add(event)
            db.flush()
    except IntegrityError:
        existing = _find_existing_event(db, hotel_id, provider, webhook_id)
        if existing is not None:
            return existing, True
        raise
    return event, False


def _transaction_exists(db: Session, hotel_id: int, reservation_id: int, idempotency_key: str) -> bool:
    return (
        db.query(Transaction.id)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation_id,
            Transaction.idempotency_key == idempotency_key,
        )
        .first()
        is not None
    )


def _enqueue_completed_payment_failure_alert(
    db: Session,
    *,
    payment: Payment,
    event: PaymentWebhookEvent,
) -> list[Any]:
    """Persist one management-only in-app alert for a verified late failure.

    The notification points to the reservation and carries internal IDs only;
    provider payloads, external payment IDs, and guest data are not retained.
    The stable payment-based dedupe key collapses distinct provider replays.
    """
    from app.services.notification_service import enqueue_notifications_for_event

    return enqueue_notifications_for_event(
        db,
        hotel_id=payment.hotel_id,
        event_type="payment.completed_status_discrepancy",
        dedupe_key=f"payment:completed_status_discrepancy:{payment.id}",
        title="Pago previamente aprobado requiere revisión",
        body=(
            "Mercado Pago informó un rechazo o una reversión de un pago ya registrado. "
            "La reserva y el libro contable no se modificaron; requiere revisión manual."
        ),
        severity=NotificationSeverityEnum.CRITICAL,
        entity_type="reservation",
        entity_id=payment.reservation_id,
        payload={
            "reservation_id": payment.reservation_id,
            "payment_id": payment.id,
            "payment_link_id": payment.payment_link_id,
            "event_id": event.id,
            "status": "failed",
        },
        recipient_roles=("owner", "co_owner", "manager"),
        channels=(NotificationChannelEnum.IN_APP,),
        force_in_app=True,
    )


def _ensure_completed_transaction(
    db: Session,
    payment: Payment,
    provider: str,
    gateway_response_payload: dict[str, Any],
    *,
    allow_verified_cancelled_settlement: bool = False,
) -> None:
    idempotency_key = f"{provider}:{payment.external_payment_id}:completed"
    if _transaction_exists(db, payment.hotel_id, payment.reservation_id, idempotency_key):
        return
    payment_method = PaymentMethodEnum.MERCADO_PAGO if provider == "mercado_pago" else PaymentMethodEnum.PAYPAL
    linked_payment = None
    if payment.payment_link_id is not None:
        linked_payment = (
            db.query(PaymentLink)
            .filter(
                PaymentLink.hotel_id == payment.hotel_id,
                PaymentLink.id == payment.payment_link_id,
            )
            .first()
        )
    link_metadata = linked_payment.gateway_response if linked_payment and isinstance(linked_payment.gateway_response, dict) else {}
    surcharge_quote_snapshot = link_metadata.get("_pms_surcharge_quote")
    payment_currency = str(payment.currency or (linked_payment.currency if linked_payment else "ARS")).strip().upper()
    if provider == "mercado_pago" and surcharge_quote_snapshot is None:
        # A legacy link without its issue-time quote has no trustworthy way to
        # split the provider-confirmed total into principal and surcharge.
        # Treat the exact captured amount as the tender, and never query today's
        # surcharge configuration or FX quote to reconstruct a historical fact.
        base_amount = _money(payment.amount)
        apply_surcharge = False
    else:
        base_amount = calculate_base_amount_before_surcharge(
            db,
            hotel_id=payment.hotel_id,
            payment_method=payment_method,
            final_amount=_money(payment.amount),
            currency_code=payment_currency,
            surcharge_quote_snapshot=surcharge_quote_snapshot,
        )
        apply_surcharge = True
    # Pass idempotency_key into process_payment so the Transaction is INSERTED with
    # the key already set. A concurrent duplicate delivery then collides on the unique
    # index inside process_payment's savepoint and is resolved as a replay (no 2nd row,
    # no 500) instead of leaving a race window where the key is assigned post-insert.
    process_payment(
        db,
        PaymentRequest(
            reservation_id=payment.reservation_id,
            amount=base_amount,
            payment_method=payment_method,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency=payment_currency,
            description=f"{provider} payment {payment.external_payment_id}",
        ),
        hotel_id=payment.hotel_id,
        gateway_response=PaymentGatewayResponse(
            success=True,
            external_payment_id=payment.external_payment_id,
            external_status=payment.status,
            gateway_response=json.dumps(gateway_response_payload, sort_keys=True, default=str),
        ),
        idempotency_key=idempotency_key,
        apply_surcharge=apply_surcharge,
        allow_verified_cancelled_settlement=allow_verified_cancelled_settlement,
        surcharge_quote_snapshot=surcharge_quote_snapshot,
    )
    db.flush()


def _existing_reconciliation_review_code(
    db: Session,
    *,
    payment: Payment | None,
) -> str | None:
    if payment is None:
        return None
    prior_review = (
        db.query(PaymentWebhookEvent.processing_error)
        .filter(
            PaymentWebhookEvent.hotel_id == payment.hotel_id,
            PaymentWebhookEvent.payment_id == payment.id,
            PaymentWebhookEvent.processing_error.in_(_PAYMENT_RECONCILIATION_REVIEW_CODES),
        )
        .order_by(PaymentWebhookEvent.id.asc())
        .first()
    )
    return str(prior_review[0]) if prior_review else None


def _enqueue_provider_payment_reconciliation_alert(
    db: Session,
    *,
    payment: Payment,
    event: PaymentWebhookEvent,
) -> list[Any]:
    """Create one durable, in-app alert for a captured payment awaiting review."""
    from app.services.notification_service import enqueue_notifications_for_event

    return enqueue_notifications_for_event(
        db,
        hotel_id=payment.hotel_id,
        event_type="payment.provider_reconciliation_review_required",
        dedupe_key=f"payment:provider_reconciliation_review:{payment.id}",
        title="Pago confirmado pendiente de conciliación",
        body=(
            "Mercado Pago confirmó un pago que no se imputó automáticamente a la reserva. "
            "Requiere revisión manual antes de afectar el saldo."
        ),
        severity=NotificationSeverityEnum.CRITICAL,
        entity_type="reservation",
        entity_id=payment.reservation_id,
        payload={
            "reservation_id": payment.reservation_id,
            "payment_id": payment.id,
            "payment_link_id": payment.payment_link_id,
            "event_id": event.id,
            "status": "review_required",
        },
        recipient_roles=("owner", "co_owner", "manager"),
        channels=(NotificationChannelEnum.IN_APP,),
        force_in_app=True,
    )


def _record_payment_reconciliation_review(
    db: Session,
    *,
    payment: Payment,
    event: PaymentWebhookEvent,
    link: PaymentLink,
    closed_link_status: str | None,
    reason: str,
) -> dict[str, Any]:
    """Persist provider evidence and a review marker without inventing ledger money."""
    alert_rows = _enqueue_provider_payment_reconciliation_alert(db, payment=payment, event=event)
    refresh_link_collection(db, link)
    if closed_link_status is not None:
        link.status = closed_link_status
        link.payable = False
    event.processed = True
    event.processing_error = reason
    event.processed_at = datetime.now(UTC)
    db.flush()
    return {
        "status": "review_required",
        "duplicate": False,
        "reason": reason,
        "alert_queued": bool(alert_rows),
        "event_id": event.id,
        "payment_id": payment.id,
    }


def _duplicate_webhook_result(event: PaymentWebhookEvent) -> dict[str, Any]:
    if event.processing_error in _PAYMENT_RECONCILIATION_REVIEW_CODES:
        return {
            "status": "review_required",
            "duplicate": True,
            "reason": event.processing_error,
            "event_id": event.id,
            "payment_id": event.payment_id,
        }
    return {"status": "ignored", "duplicate": True, "event_id": event.id,
            "payment_id": event.payment_id}


def ingest_webhook(
    db: Session,
    *,
    hotel_id: int,
    provider: str,
    webhook_id: str,
    payload: dict[str, Any],
    payment_link_id: int | None = None,
    provider_fetcher: Callable[[Session, int, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    # Direct service callers get the same fail-closed boundary as HTTP routes.
    # Keep this before all queries and inserts so a disabled lane cannot persist
    # even a rejected/ignored provider event.
    require_inbound_provider_events(provider or "payment provider")

    provider = (provider or "mercado_pago").strip().lower()
    if provider == "mercadopago":
        provider = "mercado_pago"
    if hotel_id <= 0:
        raise PaymentWebhookError("Hotel invalido para el webhook de pago")
    # The HTTP edge supplies this ID only after validating the provider
    # signature and the PMS-signed external reference. Bind the tenant before
    # idempotency, link, integration, or ledger queries rely on forced RLS.
    set_tenant_hotel_context(db, hotel_id)

    # Fast path for already committed deliveries. This read can race, so the
    # event identity is checked again after acquiring its transaction lock.
    existing_event = _find_existing_event(db, hotel_id, provider, webhook_id)
    if existing_event is not None:
        return _duplicate_webhook_result(existing_event)

    # Resolve the link first so a new Payment row can be created before the event log.
    link = None
    if payment_link_id is not None:
        link = db.query(PaymentLink).filter(PaymentLink.id == payment_link_id, PaymentLink.hotel_id == hotel_id).first()
    if not link:
        reference = _payload_value(payload, "external_reference", "data.external_reference", "metadata.external_reference")
        if reference:
            link = (
                db.query(PaymentLink)
                .filter(PaymentLink.hotel_id == hotel_id, PaymentLink.external_reference == str(reference))
                .first()
            )
    if not link:
        raise PaymentWebhookError("Link de pago no encontrado para el webhook")

    external_payment_id = str(_payload_value(payload, "payment_id", "data.id", "id") or webhook_id)
    link_provider = (link.provider or "").strip().lower()
    if link_provider == "mercadopago":
        link_provider = "mercado_pago"
    if link_provider != provider:
        raise PaymentWebhookError("El proveedor del evento no coincide con el link de pago")
    if link.execution_mode != "provider" or not link.external_checkout_url:
        raise PaymentWebhookError("El artefacto local_only no acepta pagos de proveedor")
    event_reference = _payload_value(
        payload,
        "external_reference",
        "data.external_reference",
        "metadata.external_reference",
    )
    if event_reference and link.external_reference and str(event_reference) != str(link.external_reference):
        raise PaymentWebhookError("La referencia del evento no coincide con el link de pago")

    required_fields = (
        _payload_value(payload, "amount", "transaction_amount", "data.amount"),
        _payload_value(payload, "currency", "currency_id", "data.currency"),
        _payload_value(payload, "status", "data.status"),
    )
    event_payload = payload
    # Mercado Pago's signature authenticates the payment resource ID, not the
    # notification's amount, currency, status, or external reference. Always
    # reconcile MP notifications against the canonical provider response before
    # allowing them to affect payment or ledger state, even when the signed
    # notification contains every field we need.
    must_verify_with_provider = provider == "mercado_pago"
    if must_verify_with_provider or any(value in (None, "") for value in required_fields):
        fetcher = provider_fetcher or (
            fetch_mercadopago_payment if must_verify_with_provider else None
        )
        if fetcher is None:
            raise PaymentWebhookError(
                "El evento no trae datos suficientes y la consulta a Mercado Pago esta deshabilitada"
            )
        try:
            verified_payload = fetcher(db, hotel_id, external_payment_id)
        except ExternalEffectsDisabled as exc:
            raise RetryablePaymentWebhookError(
                "No se puede consultar Mercado Pago para verificar el pago porque "
                "las conexiones salientes estan deshabilitadas"
            ) from exc
        if not isinstance(verified_payload, dict):
            raise PaymentWebhookError("El proveedor devolvio una respuesta de pago invalida")
        if provider == "mercado_pago" and must_verify_with_provider:
            canonical_reference = _payload_value(
                verified_payload,
                *_PAYMENT_RESPONSE_FIELD_ALIASES["external_reference"],
            )
            expected_reference = link.external_reference
            if (
                not isinstance(expected_reference, str)
                or not expected_reference
                or not isinstance(canonical_reference, str)
                or canonical_reference != expected_reference
            ):
                # The webhook signature authenticates the payment ID, not the
                # notification's external_reference. Bind the canonical
                # provider payment to the link selected from the signed ref
                # before creating Payment, ledger, or event rows.
                raise PaymentWebhookError(
                    "La referencia del pago verificado no coincide con el link de pago"
                )
        original_data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        payload = {**payload, **verified_payload, "data": {**original_data, **verified_payload}}
        provider_response = verified_payload
    else:
        provider_response = payload

    # Keep the verified provider projection separate from the event envelope.
    # The envelope can contain user-controlled or unnecessary nested fields.
    payment_response = _payment_response_projection(provider_response, external_payment_id)

    expected_account = _payload_value(
        link.gateway_response or {},
        "pms_account_id",
        "collector_id",
        "metadata.account_id",
    )
    incoming_account = _payload_value(
        payload,
        "collector_id",
        "user_id",
        "data.collector_id",
        "metadata.account_id",
    )
    if expected_account and incoming_account and str(expected_account) != str(incoming_account):
        raise PaymentWebhookError("El pago proviene de una cuenta de Mercado Pago distinta a la del hotel")

    raw_amount = _payload_value(payload, "amount", "transaction_amount", "data.amount")
    raw_currency = _payload_value(payload, "currency", "currency_id", "data.currency")
    if raw_amount in (None, ""):
        raise PaymentWebhookError("El evento del proveedor no informa el monto cobrado")
    if raw_currency in (None, ""):
        raise PaymentWebhookError("El evento del proveedor no informa la moneda")
    amount = _money(raw_amount)
    if amount <= Decimal("0.00"):
        raise PaymentWebhookError("El evento del proveedor informa un monto invalido")
    currency = str(raw_currency).strip().upper()
    if currency != str(link.currency or "ARS").strip().upper():
        raise PaymentWebhookError("La moneda del evento no coincide con el link de pago")
    # Once a provider lookup has been performed, its status is authoritative.
    # A signed notification envelope alone must not create a rejection alert or
    # change payment state when the canonical response omits/contradicts it.
    status_source = provider_response if must_verify_with_provider else payload
    reported_provider_status = str(
        _payload_value(status_source, "status", "data.status") or "pending"
    ).strip().lower()
    status = _normalize_status(provider, reported_provider_status)
    verified_late_failure = (
        must_verify_with_provider
        and provider == "mercado_pago"
        and status == "failed"
    )

    # Do not hold an advisory lock while asking the external provider to verify
    # the payment. Serialize the write path after provider validation, then
    # recheck the event because another delivery may have committed meanwhile.
    _acquire_postgres_webhook_lock(
        db,
        hotel_id=hotel_id,
        provider=provider,
        scope="event",
        identifier=webhook_id,
    )
    existing_event = _find_existing_event(db, hotel_id, provider, webhook_id)
    if existing_event is not None:
        return _duplicate_webhook_result(existing_event)

    # Different provider events can report the same payment. Serialize on the
    # stable external payment identity before reading or creating its Payment
    # row, so the second transaction observes the first instead of colliding on
    # uq_payment_external_per_hotel_provider.
    _acquire_postgres_webhook_lock(
        db,
        hotel_id=hotel_id,
        provider=provider,
        scope="payment",
        identifier=external_payment_id,
    )

    # Cancellation can commit while provider verification is in flight. Lock
    # reservation then link (the same order used by reservation cancellation)
    # and refresh both rows before deciding whether a late payment is eligible.
    reservation = lock_query(
        db.query(Reservation)
        .filter(
            Reservation.id == link.reservation_id,
            Reservation.hotel_id == hotel_id,
        )
        .populate_existing(),
        Reservation,
    ).first()
    if reservation is None:
        raise PaymentWebhookError("La reserva del link de pago ya no existe")
    link = lock_query(
        db.query(PaymentLink)
        .filter(PaymentLink.id == link.id, PaymentLink.hotel_id == hotel_id)
        .populate_existing(),
        PaymentLink,
    ).first()
    if link is None:
        raise PaymentWebhookError("Link de pago no encontrado para el webhook")
    if (link.provider or "").strip().lower().replace("mercadopago", "mercado_pago") != provider:
        raise PaymentWebhookError("El proveedor del evento no coincide con el link de pago")
    if link.execution_mode != "provider" or not link.external_checkout_url:
        raise PaymentWebhookError("El artefacto local_only no acepta pagos de proveedor")
    link_metadata = link.gateway_response if isinstance(link.gateway_response, dict) else {}
    surcharge_quote_snapshot = link_metadata.get("_pms_surcharge_quote")
    legacy_link_without_surcharge_snapshot = (
        provider == "mercado_pago" and surcharge_quote_snapshot is None
    )
    closed_link_status = (
        "cancelled"
        if reservation.status == ReservationStatusEnum.CANCELLED
        else link.status if link.status in {"cancelled", "expired"} else None
    )
    if closed_link_status == "cancelled" and link.status != "cancelled":
        # A cancellation path that committed despite failing to close the
        # local link must not let the webhook reopen it or accept an unverified
        # provider envelope as a new charge.
        link.status = "cancelled"
        link.payable = False

    payment = (
        db.query(Payment)
        .filter(
            Payment.hotel_id == hotel_id,
            Payment.provider == provider,
            Payment.external_payment_id == external_payment_id,
        )
        .first()
    )
    review_reason = _existing_reconciliation_review_code(db, payment=payment)
    if payment is None:
        if not link.payable and closed_link_status is None:
            raise PaymentWebhookError("El link de pago no esta habilitado para nuevos cobros")
        outstanding = max(
            Decimal("0.00"),
            _money(link.requested_amount) - _money(link.collected_amount),
        )
        if amount > outstanding + Decimal("0.01"):
            if status == "completed" and legacy_link_without_surcharge_snapshot:
                # The provider has already confirmed the capture. Keep its
                # exact amount/evidence for management instead of rolling back
                # the Payment row, but do not infer an allocation above the
                # original legacy link balance.
                review_reason = "legacy_link_amount_exceeds_link_balance_review_required"
            else:
                raise PaymentWebhookError("El monto del evento excede el saldo del link de pago")
    else:
        if payment.payment_link_id not in {None, link.id} or payment.reservation_id != link.reservation_id:
            raise PaymentWebhookError("El pago externo ya pertenece a otro link o reserva")
        if _money(payment.amount) != amount or str(payment.currency or "").strip().upper() != currency:
            raise PaymentWebhookError("El monto o la moneda de un pago externo idempotente no pueden cambiar")

    if closed_link_status is not None:
        # Cancellation cannot revoke an open provider checkout. Reconcile a
        # verified late success, and accept a verified rejection only for a
        # payment already recorded as completed so it can be surfaced for
        # manual review. Neither path reopens the closed link.
        verified_late_failure_for_completed_payment = (
            verified_late_failure and payment is not None and payment.status == "completed"
        )
        verified_late_success = must_verify_with_provider and status == "completed"
        if not verified_late_success and not verified_late_failure_for_completed_payment:
            raise PaymentWebhookError("El link cerrado requiere verificar un pago ya completado con el proveedor")

    late_failure_requires_review = (
        payment is not None
        and payment.status == "completed"
        and status == "failed"
        and verified_late_failure
    )

    invalid_transition = False
    if not payment:
        payment = Payment(
            hotel_id=hotel_id,
            reservation_id=link.reservation_id,
            payment_link_id=link.id,
            provider=provider,
            external_payment_id=external_payment_id,
            amount=amount,
            currency=currency,
            status=status,
            gateway_response=payment_response,
        )
        db.add(payment)
        db.flush()
    elif _is_allowed_status_transition(payment.status, status):
        payment.payment_link_id = link.id
        payment.amount = amount
        payment.currency = currency
        payment.status = status
        payment.gateway_response = payment_response
    else:
        # Out-of-order delivery or a rejected/failed payment "resurrected" by a
        # later webhook for the same external payment id: keep the recorded
        # (already-processed) status untouched. The event is still logged for
        # audit, just marked as not applied.
        attempted_status = status
        status = payment.status
        invalid_transition = True

    event, duplicate = _insert_event(db, hotel_id, payment.id, provider, webhook_id, event_payload)
    if duplicate:
        return _duplicate_webhook_result(event)

    if invalid_transition:
        if late_failure_requires_review:
            alert_rows = _enqueue_completed_payment_failure_alert(db, payment=payment, event=event)
            event.processed = True
            event.processing_error = None
            event.processed_at = datetime.now(timezone.utc)
            db.flush()
            return {
                "status": "review_required",
                "duplicate": False,
                "reason": "completed_payment_reported_failed",
                "alert_queued": bool(alert_rows),
                "event_id": event.id,
                "payment_id": payment.id,
            }

        event.processed = False
        event.processing_error = f"invalid_status_transition:{status}->{attempted_status}"
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        return {"status": "ignored", "duplicate": False, "reason": "invalid_status_transition",
                "event_id": event.id, "payment_id": payment.id}

    try:
        if status == "completed":
            payment.processed_at = payment.processed_at or _completed_at(payload)
            if provider == "mercado_pago":
                reservation_currency = str(reservation.currency_code or "ARS").strip().upper()
                if currency != reservation_currency:
                    # Payment links have no persisted reservation-to-tender FX
                    # quote. A surcharge quote can only explain that surcharge;
                    # it is not a historical payment FX snapshot. Preserve the
                    # provider-confirmed Payment, but do not convert it at today's rate.
                    review_reason = review_reason or (
                        "legacy_link_missing_payment_fx_snapshot_review_required"
                    )
                elif legacy_link_without_surcharge_snapshot and review_reason is None:
                    from app.services.financial_ledger import operational_balance_due

                    balance = Decimal(
                        str(operational_balance_due(db, hotel_id=hotel_id, reservation=reservation))
                    ).quantize(Decimal("0.01"))
                    if amount > balance:
                        # No ledger entry is created until the owner decides how
                        # to reconcile a provider capture above the remaining
                        # reservation balance.
                        review_reason = (
                            "legacy_link_amount_exceeds_reservation_balance_review_required"
                        )
            if review_reason in _PAYMENT_RECONCILIATION_REVIEW_CODES:
                return _record_payment_reconciliation_review(
                    db,
                    payment=payment,
                    event=event,
                    link=link,
                    closed_link_status=closed_link_status,
                    reason=review_reason,
                )
            _ensure_completed_transaction(
                db,
                payment,
                provider,
                payment_response,
                allow_verified_cancelled_settlement=(
                    closed_link_status is not None and must_verify_with_provider
                ),
            )

        refresh_link_collection(db, link)
        if closed_link_status is not None and link.status != "completed":
            link.status = closed_link_status
            link.payable = False
        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        return {"status": "ok", "duplicate": False, "event_id": event.id, "payment_id": payment.id}
    except Exception:
        event.processed = False
        event.processing_error = "payment_webhook_processing_failed"
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        raise
