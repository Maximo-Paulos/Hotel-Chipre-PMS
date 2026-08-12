"""Production gateway webhook ingestion.

Idempotency has two layers:
  1. payment_webhook_events unique (hotel_id, provider, webhook_id) — a re-delivered
     webhook is a no-op.
  2. transactions.idempotency_key — even if two DISTINCT webhooks report the same
     completed payment, only ONE Transaction is ever written.

A completed gateway Payment writes exactly one Transaction via payment_service.process_payment
(the canonical ledger). PaymentLink collection totals are recomputed from completed Payments.
"""
from datetime import datetime, timezone
from decimal import Decimal
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services.payment_link_service import _money, refresh_link_collection
from app.services.payment_link_test_service import PaymentLinkTestError
from app.services.payment_link_test_service import (
    validate_mercadopago_webhook_signature as _validate_signature_or_raise,
)
from app.services.payment_service import calculate_base_amount_before_surcharge, process_payment
from app.services.external_effects_policy import require_inbound_provider_events


class PaymentWebhookError(Exception):
    pass


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


def _insert_event(
    db: Session, hotel_id: int, payment_id: int, provider: str, webhook_id: str, payload: dict[str, Any]
) -> tuple[PaymentWebhookEvent, bool]:
    event = PaymentWebhookEvent(
        hotel_id=hotel_id,
        payment_id=payment_id,
        provider=provider,
        webhook_id=webhook_id,
        event_type=str(_payload_value(payload, "type", "action") or ""),
        raw_payload=payload,
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


def _ensure_completed_transaction(db: Session, payment: Payment, provider: str, payload: dict[str, Any]) -> None:
    idempotency_key = f"{provider}:{payment.external_payment_id}:completed"
    if _transaction_exists(db, payment.hotel_id, payment.reservation_id, idempotency_key):
        return
    payment_method = PaymentMethodEnum.MERCADO_PAGO if provider == "mercado_pago" else PaymentMethodEnum.PAYPAL
    base_amount = calculate_base_amount_before_surcharge(
        db,
        hotel_id=payment.hotel_id,
        payment_method=payment_method,
        final_amount=_money(payment.amount),
    )
    # Pass idempotency_key into process_payment so the Transaction is INSERTED with
    # the key already set. A concurrent duplicate delivery then collides on the unique
    # index inside process_payment's savepoint and is resolved as a replay (no 2nd row,
    # no 500) instead of leaving a race window where the key is assigned post-insert.
    process_payment(
        db,
        PaymentRequest(
            reservation_id=payment.reservation_id,
            amount=float(base_amount),
            payment_method=payment_method,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency=payment.currency,
            description=f"{provider} payment {payment.external_payment_id}",
        ),
        hotel_id=payment.hotel_id,
        gateway_response=PaymentGatewayResponse(
            success=True,
            external_payment_id=payment.external_payment_id,
            external_status=payment.status,
            gateway_response=json.dumps(payload, sort_keys=True, default=str),
        ),
        idempotency_key=idempotency_key,
    )
    db.flush()


def ingest_webhook(
    db: Session,
    *,
    hotel_id: int,
    provider: str,
    webhook_id: str,
    payload: dict[str, Any],
    payment_link_id: int | None = None,
) -> dict[str, Any]:
    # Direct service callers get the same fail-closed boundary as HTTP routes.
    # Keep this before all queries and inserts so a disabled lane cannot persist
    # even a rejected/ignored provider event.
    require_inbound_provider_events(provider or "payment provider")

    provider = (provider or "mercado_pago").strip().lower()
    if provider == "mercadopago":
        provider = "mercado_pago"

    # Re-delivery short-circuit: if this (hotel, provider, webhook_id) was already
    # ingested, return before creating/updating any Payment row.
    existing_event = _find_existing_event(db, hotel_id, provider, webhook_id)
    if existing_event is not None:
        return {"status": "ignored", "duplicate": True, "event_id": existing_event.id,
                "payment_id": existing_event.payment_id}

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

    external_payment_id = str(_payload_value(payload, "payment_id", "id", "data.id") or webhook_id)
    link_provider = (link.provider or "").strip().lower()
    if link_provider == "mercadopago":
        link_provider = "mercado_pago"
    if link_provider != provider:
        raise PaymentWebhookError("El proveedor del evento no coincide con el link de pago")
    if link.execution_mode != "provider" or not link.external_checkout_url:
        raise PaymentWebhookError("El artefacto local_only no acepta pagos de proveedor")
    if link.status in {"cancelled", "expired"}:
        raise PaymentWebhookError("El link de pago ya no acepta eventos de cobro")

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
    status = _normalize_status(provider, str(_payload_value(payload, "status", "data.status") or "pending"))

    payment = (
        db.query(Payment)
        .filter(
            Payment.hotel_id == hotel_id,
            Payment.provider == provider,
            Payment.external_payment_id == external_payment_id,
        )
        .first()
    )
    if payment is None:
        if not link.payable:
            raise PaymentWebhookError("El link de pago no esta habilitado para nuevos cobros")
        outstanding = max(
            Decimal("0.00"),
            _money(link.requested_amount) - _money(link.collected_amount),
        )
        if amount > outstanding + Decimal("0.01"):
            raise PaymentWebhookError("El monto del evento excede el saldo del link de pago")
    else:
        if payment.payment_link_id not in {None, link.id} or payment.reservation_id != link.reservation_id:
            raise PaymentWebhookError("El pago externo ya pertenece a otro link o reserva")
        if _money(payment.amount) != amount or str(payment.currency or "").strip().upper() != currency:
            raise PaymentWebhookError("El monto o la moneda de un pago externo idempotente no pueden cambiar")

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
            gateway_response=payload,
        )
        db.add(payment)
        db.flush()
    elif _is_allowed_status_transition(payment.status, status):
        payment.payment_link_id = link.id
        payment.amount = amount
        payment.currency = currency
        payment.status = status
        payment.gateway_response = payload
    else:
        # Out-of-order delivery or a rejected/failed payment "resurrected" by a
        # later webhook for the same external payment id: keep the recorded
        # (already-processed) status untouched. The event is still logged for
        # audit, just marked as not applied.
        attempted_status = status
        status = payment.status
        invalid_transition = True

    event, duplicate = _insert_event(db, hotel_id, payment.id, provider, webhook_id, payload)
    if duplicate:
        return {"status": "ignored", "duplicate": True, "event_id": event.id, "payment_id": payment.id}

    if invalid_transition:
        event.processed = False
        event.processing_error = f"invalid_status_transition:{status}->{attempted_status}"
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        return {"status": "ignored", "duplicate": False, "reason": "invalid_status_transition",
                "event_id": event.id, "payment_id": payment.id}

    try:
        if status == "completed":
            payment.processed_at = payment.processed_at or _completed_at(payload)
            _ensure_completed_transaction(db, payment, provider, payload)

        refresh_link_collection(db, link)
        event.processed = True
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        return {"status": "ok", "duplicate": False, "event_id": event.id, "payment_id": payment.id}
    except Exception as exc:
        event.processed = False
        event.processing_error = str(exc)
        event.processed_at = datetime.now(timezone.utc)
        db.flush()
        raise
