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
import hashlib
import hmac
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.payment import Payment, PaymentLink, PaymentWebhookEvent
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services.payment_link_service import _money, refresh_link_collection
from app.services.payment_service import calculate_base_amount_before_surcharge, process_payment


class PaymentWebhookError(Exception):
    pass


def _parse_mercadopago_signature_header(signature_header: str | None) -> dict[str, str]:
    if not signature_header:
        return {}
    parts: dict[str, str] = {}
    for chunk in signature_header.split(","):
        key, separator, value = chunk.strip().partition("=")
        if separator and key:
            parts[key.strip()] = value.strip()
    return parts


def validate_mercadopago_webhook_signature(
    secret: str,
    *,
    data_id: str,
    request_id: str | None,
    signature_header: str | None,
) -> bool:
    signature_parts = _parse_mercadopago_signature_header(signature_header)
    ts = signature_parts.get("ts")
    v1 = signature_parts.get("v1")
    if not secret or not data_id or not request_id or not ts or not v1:
        return False

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, v1)


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
    provider = (provider or "mercado_pago").strip().lower()

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
    amount = _money(_payload_value(payload, "amount", "transaction_amount", "data.amount") or link.requested_amount)
    currency = str(_payload_value(payload, "currency", "currency_id", "data.currency") or link.currency or "ARS").upper()[:3]
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
    else:
        payment.payment_link_id = link.id
        payment.amount = amount
        payment.currency = currency
        payment.status = status
        payment.gateway_response = payload

    event, duplicate = _insert_event(db, hotel_id, payment.id, provider, webhook_id, payload)
    if duplicate:
        return {"status": "ignored", "duplicate": True, "event_id": event.id, "payment_id": payment.id}

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
