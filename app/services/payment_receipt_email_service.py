"""Explicit, tenant-scoped email delivery for persisted payment receipts."""
from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime, timezone
from decimal import Decimal
from email_validator import EmailNotValidError, validate_email
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment_receipt_email_delivery import PaymentReceiptEmailDelivery
from app.services.hotel_outbound_email_service import (
    HotelEmailAttachment,
    capture_hotel_email,
    ensure_hotel_gmail_ready,
    send_hotel_email,
)
from app.services.payment_service import PaymentNotFoundError, get_payment_receipt_data
from app.services.timezones import business_clock_enabled_for_hotel
from app.services.payment_receipt_pdf import generate_payment_receipt_pdf


class PaymentReceiptEmailError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


_EMAIL_PATTERN = re.compile(r"^[^\s,;<>]+@[^\s,;<>]+\.[^\s,;<>]+$")


def _normalize_email(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized or not _EMAIL_PATTERN.fullmatch(normalized):
        raise PaymentReceiptEmailError(400, "Ingresá una dirección de correo válida.")
    try:
        allow_reserved_test = normalized.rsplit("@", maxsplit=1)[-1].rstrip(".").endswith(".test")
        return validate_email(
            normalized,
            check_deliverability=False,
            test_environment=allow_reserved_test,
        ).normalized.lower()
    except EmailNotValidError as exc:
        raise PaymentReceiptEmailError(400, "Ingresá una dirección de correo válida.") from exc


def _key_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _recipient_fingerprint(value: str) -> str:
    secret = get_settings().JWT_SECRET.encode("utf-8")
    return hmac.new(secret, value.encode("utf-8"), hashlib.sha256).hexdigest()


def _load_receipt(
    db: Session,
    *,
    hotel_id: int,
    transaction_id: int,
) -> dict:
    try:
        return get_payment_receipt_data(db, hotel_id, transaction_id)
    except PaymentNotFoundError:
        raise


def _local_simulation_enabled(db: Session, hotel_id: int) -> bool:
    """Identify the one local clock-enabled hotel, failing closed if misconfigured."""
    settings = get_settings()
    if settings.LOCAL_SIMULATION_CLOCK_ENABLED is not True:
        return False

    fields_set = getattr(settings, "model_fields_set", set())
    try:
        configured_database_is_sqlite = make_url(settings.DATABASE_URL).get_backend_name() == "sqlite"
        actual_database_is_sqlite = db.get_bind().dialect.name == "sqlite"
    except Exception:
        configured_database_is_sqlite = False
        actual_database_is_sqlite = False
    enabled = (
        settings.APP_ENV == "development"
        and "APP_ENV" in fields_set
        and settings.EXTERNAL_EFFECTS_ENABLED is False
        and "EXTERNAL_EFFECTS_ENABLED" in fields_set
        and "LOCAL_SIMULATION_CLOCK_ENABLED" in fields_set
        and settings.LOCAL_SIMULATION_CLOCK_HOTEL_ID == hotel_id
        and business_clock_enabled_for_hotel(hotel_id)
        and configured_database_is_sqlite
        and actual_database_is_sqlite
    )
    if not enabled:
        raise PaymentReceiptEmailError(
            503,
            "La captura local de comprobantes no está habilitada para este entorno.",
        )
    return True


def _is_reserved_test_recipient(value: str) -> bool:
    domain = value.rsplit("@", maxsplit=1)[-1].rstrip(".").lower()
    return domain.endswith(".test")


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
            local_capture = (existing.provider_message_id or "").startswith("local-simulation:")
            return {
                "transaction_id": transaction_id,
                "status": "captured" if local_capture else "sent",
                "delivery_mode": "local_simulation" if local_capture else "provider",
                "replayed": True,
            }
        raise PaymentReceiptEmailError(
            409,
            "El resultado de un intento anterior no está confirmado. Revisá el correo o la captura local antes de volver a intentar.",
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
            "Hay un intento previo sin resultado confirmado. Revisá el correo o la captura local antes de volver a intentar.",
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
    """Send or capture one operator-addressed receipt with a fail-closed outcome."""
    if hotel_id is None or hotel_id <= 0:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")
    if actor_user_id is None or actor_user_id <= 0:
        raise PaymentReceiptEmailError(403, "Se requiere un usuario autenticado para enviar el comprobante.")
    key = str(idempotency_key or "").strip()
    if not 8 <= len(key) <= 100:
        raise PaymentReceiptEmailError(400, "La clave de idempotencia no es válida.")
    confirmed_email = _normalize_email(recipient_email)
    local_simulation = _local_simulation_enabled(db, hotel_id)
    if local_simulation and not _is_reserved_test_recipient(confirmed_email):
        raise PaymentReceiptEmailError(
            400,
            "La simulación local solo permite destinatarios del dominio reservado .test.",
        )
    if not local_simulation and _is_reserved_test_recipient(confirmed_email):
        raise PaymentReceiptEmailError(
            400,
            "Las direcciones .test solo se permiten en la simulación local aislada.",
        )
    key_hash = _key_hash(key)
    recipient_hash = _recipient_fingerprint(confirmed_email)

    receipt = _load_receipt(
        db,
        hotel_id=hotel_id,
        transaction_id=transaction_id,
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

    if not local_simulation:
        # Validate Gmail before creating an attempt. A missing connection is a
        # definite pre-send failure and leaves the key reusable.
        try:
            ensure_hotel_gmail_ready(db, hotel_id)
        except Exception:
            db.rollback()
            raise PaymentReceiptEmailError(
                503,
                "El correo del hotel no está disponible para enviar el comprobante.",
            ) from None

        # Re-read the receipt after the provider readiness check so a changed
        # transaction status cannot cross the network boundary unnoticed.
        db.expire_all()
        receipt = _load_receipt(
            db,
            hotel_id=hotel_id,
            transaction_id=transaction_id,
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
    pdf_bytes = generate_payment_receipt_pdf(receipt)
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
            "Hay un intento previo sin resultado confirmado. Revisá el correo o la captura local antes de volver a intentar.",
        ) from exc

    try:
        attachment = HotelEmailAttachment(
            filename=f"comprobante-pago-{transaction_id}.pdf",
            content_type="application/pdf",
            content=pdf_bytes,
        )
        if local_simulation:
            send_result = capture_hotel_email(
                db,
                hotel_id,
                to=confirmed_email,
                subject=subject,
                body=body,
                attachments=(attachment,),
            )
        else:
            send_result = send_hotel_email(
                db,
                hotel_id,
                to=confirmed_email,
                subject=subject,
                body=body,
                attachments=(attachment,),
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
            "No se pudo confirmar el resultado. Revisá el correo o la captura local antes de volver a intentar.",
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
            "El resultado no se pudo confirmar en el registro. Revisá el correo o la captura local antes de volver a intentar.",
        ) from None

    return {
        "transaction_id": transaction_id,
        "status": "captured" if local_simulation else "sent",
        "delivery_mode": "local_simulation" if local_simulation else "provider",
        "replayed": False,
    }
