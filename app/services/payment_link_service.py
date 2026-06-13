"""Production payment-link lifecycle: create, list, cancel, expire, collection refresh.

Source-of-truth rule (docs/data-foundations/transactions-vs-payments.md):
balance_due is ALWAYS computed from confirmed transactions, never from payments.
The external_reference is HMAC-signed so an inbound webhook can resolve the hotel
without trusting caller-supplied hotel_id.
"""
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment import Payment, PaymentLink
from app.models.reservation import Reservation
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate


class PaymentLinkError(Exception):
    pass


def _money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _signing_secret() -> str:
    settings = get_settings()
    return getattr(settings, "SIGNED_TOKEN_SECRET", None) or settings.JWT_SECRET or "change-me"


def _signature(message: str) -> str:
    return hmac.new(_signing_secret().encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()[:24]


def sign_external_reference(hotel_id: int, link_code: str) -> str:
    body = f"payment-link:{hotel_id}:{link_code}"
    return f"{body}:{_signature(body)}"


def resolve_signed_external_reference(external_reference: str) -> tuple[int, str]:
    parts = (external_reference or "").split(":")
    if len(parts) != 4 or parts[0] != "payment-link":
        raise PaymentLinkError("external_reference invalido")
    body = ":".join(parts[:3])
    expected = _signature(body)
    if not hmac.compare_digest(expected, parts[3]):
        raise PaymentLinkError("external_reference no esta firmado por el PMS")
    try:
        hotel_id = int(parts[1])
    except ValueError as exc:
        raise PaymentLinkError("external_reference invalido") from exc
    return hotel_id, parts[2]


def _get_reservation_for_hotel(db: Session, hotel_id: int, reservation_id: int) -> Reservation:
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )
    if not reservation:
        raise PaymentLinkError("Reserva no encontrada para este hotel")
    return reservation


def _unique_link_code(db: Session) -> str:
    for _ in range(10):
        code = f"pl_{uuid4().hex[:20]}"
        if not db.query(PaymentLink.id).filter(PaymentLink.link_code == code).first():
            return code
    raise PaymentLinkError("No se pudo generar un codigo unico de link")


def create_link(db: Session, hotel_id: int, payload: PaymentLinkCreate) -> PaymentLink:
    reservation = _get_reservation_for_hotel(db, hotel_id, payload.reservation_id)
    provider = payload.provider or "mercado_pago"
    if provider != "mercado_pago":
        raise PaymentLinkError("Solo mercado_pago esta habilitado para links de pago")

    link_code = _unique_link_code(db)
    link = PaymentLink(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        provider=provider,
        link_code=link_code,
        requested_amount=_money(payload.requested_amount),
        collected_amount=Decimal("0.00"),
        currency=payload.currency or reservation.currency_code or "ARS",
        recipient_email=str(payload.recipient_email).strip().lower(),
        recipient_name=(payload.recipient_name or "").strip() or None,
        recipient_phone=(payload.recipient_phone or "").strip() or None,
        title=(payload.title or "").strip() or "Pago de Reserva",
        description=(payload.description or "").strip() or None,
        status="pending",
        external_reference=sign_external_reference(hotel_id, link_code),
        expires_at=payload.expires_at,
    )
    db.add(link)
    db.flush()
    return link


def list_links_for_reservation(db: Session, hotel_id: int, reservation_id: int) -> list[PaymentLink]:
    return (
        db.query(PaymentLink)
        .filter(PaymentLink.hotel_id == hotel_id, PaymentLink.reservation_id == reservation_id)
        .order_by(PaymentLink.created_at.desc(), PaymentLink.id.desc())
        .all()
    )


def cancel_link(db: Session, hotel_id: int, link_id: int, reason: str | None = None) -> PaymentLink:
    link = db.query(PaymentLink).filter(PaymentLink.id == link_id, PaymentLink.hotel_id == hotel_id).first()
    if not link:
        raise PaymentLinkError("Link de pago no encontrado para este hotel")
    if link.status in {"cancelled", "expired"}:
        return link
    if link.status == "completed":
        raise PaymentLinkError("No se puede cancelar un link ya completado")
    link.status = "cancelled"
    link.cancelled_at = datetime.now(timezone.utc)
    if reason:
        # No dedicated column; record the operator reason in last_error for traceability.
        link.last_error = f"cancelled: {reason}"
    db.flush()
    return link


def expire_link(db: Session, hotel_id: int, link_id: int) -> PaymentLink:
    link = db.query(PaymentLink).filter(PaymentLink.id == link_id, PaymentLink.hotel_id == hotel_id).first()
    if not link:
        raise PaymentLinkError("Link de pago no encontrado para este hotel")
    if link.status not in {"completed", "cancelled"}:
        link.status = "expired"
    db.flush()
    return link


def refresh_link_collection(db: Session, link: PaymentLink) -> PaymentLink:
    completed = (
        db.query(Payment)
        .filter(Payment.payment_link_id == link.id, Payment.hotel_id == link.hotel_id, Payment.status == "completed")
        .order_by(Payment.processed_at.asc(), Payment.id.asc())
        .all()
    )
    link.collected_amount = sum((_money(payment.amount) for payment in completed), Decimal("0.00"))
    completed_dates = [payment.processed_at for payment in completed if payment.processed_at]
    link.first_payment_at = min(completed_dates) if completed_dates else None
    link.last_payment_at = max(completed_dates) if completed_dates else None
    if link.collected_amount >= _money(link.requested_amount):
        link.status = "completed"
    elif link.collected_amount > Decimal("0.00"):
        link.status = "partially_paid"
    elif link.status not in {"cancelled", "expired"}:
        link.status = "pending"
    db.flush()
    return link


def balance_due_from_transactions(db: Session, hotel_id: int, reservation_id: int) -> Decimal:
    reservation = _get_reservation_for_hotel(db, hotel_id, reservation_id)
    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation_id,
            Transaction.status == TransactionStatusEnum.COMPLETED,
        )
        .all()
    )
    paid = Decimal("0.00")
    for transaction in transactions:
        amount = _money(transaction.amount)
        paid += -amount if transaction.transaction_type == TransactionTypeEnum.REFUND else amount
    return max(Decimal("0.00"), _money(reservation.total_amount) - paid)
