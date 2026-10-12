"""Explicit, tenant-scoped email delivery for persisted payment receipts."""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.guest import Guest
from app.models.payment_receipt_email_delivery import PaymentReceiptEmailDelivery
from app.models.reservation import Reservation
from app.models.transaction import Transaction
from app.services.hotel_outbound_email_service import (
    ensure_hotel_gmail_ready,
    send_hotel_email,
)
from app.services.payment_service import PaymentNotFoundError, get_payment_receipt_data


class PaymentReceiptEmailError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_EMAIL_PATTERN = re.compile(r"^[^\s,;<>]+@[^\s,;<>]+\.[^\s,;<>]+$")


def _normalize_email(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or not _EMAIL_PATTERN.fullmatch(normalized):
        raise PaymentReceiptEmailError(400, "Ingresá el email registrado del huésped.")
    try:
        return validate_email(normalized, check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise PaymentReceiptEmailError(400, "Ingresá el email registrado del huésped.") from exc


def _key_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _recipient_fingerprint(value: str) -> str:
    secret = get_settings().JWT_SECRET.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _load_receipt_and_registered_email(
    db: Session,
    *,
    hotel_id: int,
    transaction_id: int,
    confirmed_email: str,
) -> tuple[dict, str]:
    transaction = (
        db.query(Transaction)
        .filter(Transaction.hotel_id == hotel_id, Transaction.id == transaction_id)
        .first()
    )
    if transaction is None:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")

    reservation = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.id == transaction.reservation_id,
        )
        .first()
    )
    if reservation is None:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")

    guest = (
        db.query(Guest)
        .filter(
            Guest.hotel_id == hotel_id,
            Guest.id == reservation.guest_id,
            Guest.deleted_at.is_(None),
        )
        .first()
    )
    if guest is None:
        raise PaymentReceiptEmailError(409, "La reserva no tiene un email de huésped disponible.")

    try:
        registered_email = _normalize_email(guest.email or "")
    except PaymentReceiptEmailError as exc:
        raise PaymentReceiptEmailError(409, "La reserva no tiene un email de huésped válido.") from exc
    if not hmac.compare_digest(registered_email, confirmed_email):
        raise PaymentReceiptEmailError(
            409,
            "El email confirmado no coincide con el email registrado del huésped.",
        )

    # This is the existing receipt source of truth and applies the completed /
    # refunded transaction rule again under the same tenant scope.
    try:
        receipt = get_payment_receipt_data(db, hotel_id, transaction_id)
    except PaymentNotFoundError:
        raise
    return receipt, registered_email


def _format_money(value, currency: str) -> str:
    amount = Decimal(str(value or 0)).copy_abs().quantize(Decimal("0.01"))
    return f"{amount:.2f} {currency}"


def _receipt_email_content(receipt: dict) -> tuple[str, str]:
    is_refund = str(getattr(receipt["type"], "value", receipt["type"])) == "refund"
    title = "Comprobante de devolución" if is_refund else "Comprobante de pago"
    subject = f"{title} - {receipt['confirmation_code']}"
    lines = [
        str(receipt["hotel_name"]),
        title,
        f"Reserva: {receipt['confirmation_code']}",
        f"Movimiento: #{receipt['id']}",
        f"Fecha (UTC): {receipt['created_at'].astimezone(timezone.utc).isoformat()}",
        f"Estado: {getattr(receipt['status'], 'value', receipt['status'])}",
        f"Medio: {getattr(receipt['method'], 'value', receipt['method'])}",
    ]
    if is_refund:
        lines.append(f"Importe devuelto: {_format_money(receipt['amount'], receipt['currency'])}")
        if receipt.get("refund_of_transaction_id") is not None:
            lines.append(f"Movimiento original: #{receipt['refund_of_transaction_id']}")
    else:
        lines.append(f"Importe: {_format_money(receipt['gross_amount'], receipt['currency'])}")
        fee = Decimal(str(receipt.get("fee_amount") or 0)).copy_abs().quantize(Decimal("0.01"))
        if fee > Decimal("0.00"):
            lines.append(f"Cargo del medio de pago: {_format_money(fee, receipt['currency'])}")
        applied_currency = receipt.get("applied_currency") or receipt["currency"]
        if applied_currency != receipt["currency"]:
            lines.append(f"Importe aplicado: {_format_money(receipt['applied_amount'], applied_currency)}")
    lines.extend(["", "Este correo contiene el comprobante generado con los datos registrados en el hotel."])
    return subject, "\n".join(lines)


def _existing_delivery(
    db: Session,
    *,
    hotel_id: int,
    transaction_id: int,
    key_hash: str,
    recipient_fingerprint: str,
) -> dict | None:
    existing = (
        db.query(PaymentReceiptEmailDelivery)
        .filter(
            PaymentReceiptEmailDelivery.hotel_id == hotel_id,
            PaymentReceiptEmailDelivery.idempotency_key_hash == key_hash,
        )
        .first()
    )
    if existing is not None:
        if (
            existing.transaction_id != transaction_id
            or not hmac.compare_digest(existing.recipient_fingerprint, recipient_fingerprint)
        ):
            raise PaymentReceiptEmailError(409, "La clave de idempotencia ya fue usada con otros datos.")
        if existing.status == "sent":
            return {
                "transaction_id": transaction_id,
                "status": "sent",
                "replayed": True,
            }
        raise PaymentReceiptEmailError(
            409,
            "El resultado de un envío anterior no está confirmado. Revisá el correo enviado antes de volver a intentar.",
        )

    pending = (
        db.query(PaymentReceiptEmailDelivery.id)
        .filter(
            PaymentReceiptEmailDelivery.hotel_id == hotel_id,
            PaymentReceiptEmailDelivery.transaction_id == transaction_id,
            PaymentReceiptEmailDelivery.status.in_(["sending", "unknown"]),
        )
        .first()
    )
    if pending is not None:
        raise PaymentReceiptEmailError(
            409,
            "Hay un envío previo sin resultado confirmado. Revisá el correo enviado antes de volver a intentar.",
        )
    return None


def send_payment_receipt_email(
    db: Session,
    *,
    hotel_id: int,
    transaction_id: int,
    actor_user_id: int,
    recipient_email: str,
    idempotency_key: str,
) -> dict:
    """Send one guest-confirmed receipt and persist a fail-closed outcome."""
    if hotel_id is None or hotel_id <= 0:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")
    if actor_user_id is None or actor_user_id <= 0:
        raise PaymentReceiptEmailError(403, "Se requiere un usuario autenticado para enviar el comprobante.")
    key = str(idempotency_key or "").strip()
    if not 8 <= len(key) <= 100:
        raise PaymentReceiptEmailError(400, "La clave de idempotencia no es válida.")
    confirmed_email = _normalize_email(recipient_email)
    key_hash = _key_hash(key)
    recipient_hash = _recipient_fingerprint(confirmed_email)

    # Even an idempotent replay is only available while the same transaction
    # and registered guest contact still qualify for a receipt.
    receipt, _registered_email = _load_receipt_and_registered_email(
        db,
        hotel_id=hotel_id,
        transaction_id=transaction_id,
        confirmed_email=confirmed_email,
    )
    replay = _existing_delivery(
        db,
        hotel_id=hotel_id,
        transaction_id=transaction_id,
        key_hash=key_hash,
        recipient_fingerprint=recipient_hash,
    )
    if replay is not None:
        return replay

    # Validate the hotel Gmail connection before creating an attempt. A missing
    # connection is a definite pre-send failure and leaves the key reusable.
    try:
        ensure_hotel_gmail_ready(db, hotel_id)
    except Exception:
        db.rollback()
        raise PaymentReceiptEmailError(
            503,
            "El correo del hotel no está disponible para enviar el comprobante.",
        ) from None

    # Read fresh source values after the readiness check; the guest's registered
    # email or transaction status could have changed during provider validation.
    db.expire_all()
    receipt, _registered_email = _load_receipt_and_registered_email(
        db,
        hotel_id=hotel_id,
        transaction_id=transaction_id,
        confirmed_email=confirmed_email,
    )
    replay = _existing_delivery(
        db,
        hotel_id=hotel_id,
        transaction_id=transaction_id,
        key_hash=key_hash,
        recipient_fingerprint=recipient_hash,
    )
    if replay is not None:
        return replay

    subject, body = _receipt_email_content(receipt)
    delivery = PaymentReceiptEmailDelivery(
        hotel_id=hotel_id,
        transaction_id=transaction_id,
        idempotency_key_hash=key_hash,
        recipient_fingerprint=recipient_hash,
        actor_user_id=actor_user_id,
        status="sending",
    )
    db.add(delivery)
    try:
        # Persist the idempotency claim before crossing the network boundary.
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = _existing_delivery(
            db,
            hotel_id=hotel_id,
            transaction_id=transaction_id,
            key_hash=key_hash,
            recipient_fingerprint=recipient_hash,
        )
        if replay is not None:
            return replay
        raise PaymentReceiptEmailError(
            409,
            "Hay un envío previo sin resultado confirmado. Revisá el correo enviado antes de volver a intentar.",
        ) from exc

    try:
        send_result = send_hotel_email(
            db,
            hotel_id,
            to=confirmed_email,
            subject=subject,
            body=body,
        )
    except Exception:
        # A transport exception can happen after Gmail accepted the message.
        # Persist an ambiguous outcome and require human review before retrying.
        delivery.status = "unknown"
        delivery.completed_at = datetime.now(timezone.utc)
        try:
            db.commit()
        except Exception:
            db.rollback()
        raise PaymentReceiptEmailError(
            503,
            "No se pudo confirmar el resultado del envío. Revisá el correo enviado antes de volver a intentar.",
        ) from None

    delivery.status = "sent"
    delivery.provider_message_id = getattr(send_result, "provider_message_id", None)
    delivery.completed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        # Gmail returned success but the audit update failed; the committed
        # 'sending' row remains and blocks retries for this transaction.
        db.rollback()
        raise PaymentReceiptEmailError(
            503,
            "El correo se envió, pero no se pudo confirmar el registro. Revisá el correo antes de volver a intentar.",
        ) from None

    return {
        "transaction_id": transaction_id,
        "status": "sent",
        "replayed": False,
    }
