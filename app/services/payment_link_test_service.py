from datetime import datetime, timedelta, timezone
import ipaddress
import hmac
import hashlib
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.hotel_config import HotelConfiguration
from app.models.payment_link_test import PaymentLinkTest
from app.schemas.payment_link_test import PaymentLinkTestCreate
from app.services.hotel_outbound_email_service import HotelOutboundEmailError, ensure_hotel_gmail_ready, send_hotel_email
from app.services.integration_service import get_connection_payload, redact_integration_error
from app.services.external_effects_policy import (
    ExternalEffectsDisabled,
    InboundProviderEventsDisabled,
    require_external_connections,
    require_inbound_provider_events,
)


class PaymentLinkTestError(Exception):
    pass


def _validate_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise PaymentLinkTestError("Ingresa un email valido para enviar el link.")
    return normalized


def _mercadopago_access_token(db: Session, hotel_id: int) -> str:
    # Keep this before get_connection_payload(), which decrypts credentials.
    try:
        require_external_connections("Mercado Pago payment-link test")
    except ExternalEffectsDisabled as exc:
        raise PaymentLinkTestError(str(exc)) from exc
    try:
        payload = get_connection_payload(db, hotel_id, "mercadopago")
    except ValueError as exc:
        raise PaymentLinkTestError(str(exc))
    access_token = payload.get("access_token")
    if not access_token:
        raise PaymentLinkTestError("Conecta Mercado Pago primero desde Configuracion > Conexiones.")
    return str(access_token)


def _friendly_mercadopago_error(detail: object, status_code: int | None = None) -> str:
    if isinstance(detail, dict):
        code = detail.get("code")
        blocked_by = detail.get("blocked_by")
        message = str(detail.get("message") or detail.get("error") or "").strip()
        if status_code in {401, 403} and (
            blocked_by == "PolicyAgent" or code == "PA_UNAUTHORIZED_RESULT_FROM_POLICIES"
        ):
            return (
                "Mercado Pago rechazo la prueba porque el Access Token conectado para este hotel no tiene permisos "
                "validos. Vuelve a conectar Mercado Pago con un Access Token real de la cuenta que va a cobrar la seña."
            )
        return redact_integration_error(message, fallback="Mercado Pago rechazo la prueba.")
    return "Mercado Pago rechazo la prueba."


def _status_from_payment(status: str | None) -> str:
    normalized = (status or "").lower()
    if normalized == "approved":
        return "approved"
    if normalized in {"pending", "authorized", "in_process", "in_mediation"}:
        return "pending"
    if normalized in {"cancelled"}:
        return "cancelled"
    if normalized in {"refunded"}:
        return "refunded"
    if normalized in {"rejected", "charged_back"}:
        return "failed"
    return "pending"


def _send_payment_link_email(db: Session, hotel_id: int, recipient_email: str, amount: float, currency: str, payment_url: str, description: str) -> str:
    hotel = db.get(HotelConfiguration, hotel_id)
    hotel_name = hotel.hotel_name if hotel and hotel.hotel_name else "tu hotel"
    subject = f"Link de pago - {hotel_name}"
    body = (
        "Hola,\n\n"
        f"Te enviamos un link de pago de prueba por {amount:.2f} {currency}.\n\n"
        f"Concepto: {description}\n"
        f"Link de pago: {payment_url}\n\n"
        f"Este correo fue enviado desde la cuenta conectada del hotel {hotel_name}.\n"
        "Una vez abonado, el hotel podra verificar el estado desde el PMS.\n"
    )
    result = send_hotel_email(
        db,
        hotel_id,
        to=recipient_email,
        subject=subject,
        body=body,
    )
    return result.sender_email


def _notification_url(external_reference: str, hotel_id: int) -> str:
    base_url = get_settings().APP_BASE_URL.rstrip("/")
    return (
        f"{base_url}/api/payment-link-tests/mercadopago/webhook"
        f"?external_reference={external_reference}&hotel_id={hotel_id}"
    )


def _is_public_webhook_base(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in {"https"}:
        return False

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname in {"localhost"}:
        return False

    try:
        ip = ipaddress.ip_address(hostname)
        return not (ip.is_private or ip.is_loopback or ip.is_link_local)
    except ValueError:
        # Domain name: accept it for webhook usage.
        return True


def _notification_url_if_public(external_reference: str, hotel_id: int) -> str | None:
    base_url = get_settings().APP_BASE_URL.rstrip("/")
    if not _is_public_webhook_base(base_url):
        return None
    return _notification_url(external_reference, hotel_id)


def parse_mercadopago_signature_header(signature_header: str | None) -> dict[str, str]:
    if not signature_header:
        return {}
    pairs: dict[str, str] = {}
    for chunk in signature_header.split(","):
        if "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            pairs[key] = value
    return pairs


def validate_mercadopago_webhook_signature(
    secret: str,
    *,
    data_id: str,
    request_id: str | None,
    signature_header: str | None,
    max_age_seconds: int = 300,
) -> None:
    if not secret:
        raise PaymentLinkTestError("El webhook de Mercado Pago no esta configurado.")
    signature_parts = parse_mercadopago_signature_header(signature_header)
    if not request_id or not signature_parts:
        raise PaymentLinkTestError("Faltan headers de firma de Mercado Pago para validar el webhook.")
    ts = signature_parts.get("ts")
    v1 = signature_parts.get("v1")
    if not ts or not v1 or not data_id:
        raise PaymentLinkTestError("El webhook de Mercado Pago no trajo firma valida.")

    try:
        ts_int = int(ts)
    except ValueError as exc:
        raise PaymentLinkTestError("El timestamp de firma de Mercado Pago no es valido.") from exc

    now_seconds = int(datetime.now(timezone.utc).timestamp())
    if abs(now_seconds - ts_int) > max_age_seconds:
        raise PaymentLinkTestError("La firma de Mercado Pago expiro.")

    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    expected = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        raise PaymentLinkTestError("La firma de Mercado Pago no coincide.")


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_provider_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _money(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _status_from_payment_payload(payment: dict[str, Any], record: PaymentLinkTest) -> tuple[str, float]:
    normalized = _status_from_payment(payment.get("status"))
    status_detail = str(payment.get("status_detail") or "").lower()
    refunded_amount = _money(
        payment.get("transaction_amount_refunded")
        or payment.get("amount_refunded")
    )
    transaction_amount = _money(payment.get("transaction_amount")) or record.amount

    if refunded_amount > 0:
        if refunded_amount >= transaction_amount or normalized == "refunded" or status_detail == "refunded":
            return "refunded", refunded_amount
        return "partially_refunded", refunded_amount

    if normalized == "approved" and status_detail == "partially_refunded":
        return "partially_refunded", refunded_amount

    return normalized, refunded_amount


def _apply_terminal_dates(record: PaymentLinkTest, status: str, payment: dict[str, Any]) -> None:
    if status == "approved":
        paid_date = payment.get("date_approved") or payment.get("date_last_updated")
        parsed = _parse_provider_datetime(paid_date)
        if parsed:
            record.paid_at = parsed
        elif not record.paid_at:
            record.paid_at = datetime.now(timezone.utc)
        record.refunded_at = None
        record.cancelled_at = None
    elif status in {"refunded", "partially_refunded"}:
        refunded_date = payment.get("date_last_updated") or payment.get("date_approved")
        parsed = _parse_provider_datetime(refunded_date)
        record.refunded_at = parsed or datetime.now(timezone.utc)
    elif status == "cancelled" and not record.cancelled_at:
        record.cancelled_at = datetime.now(timezone.utc)
    elif status in {"pending", "expired", "failed"}:
        record.refunded_at = None


def create_mercadopago_payment_link_test(db: Session, hotel_id: int, payload: PaymentLinkTestCreate) -> PaymentLinkTest:
    # No record, credential decryption, Gmail validation, or provider traffic
    # may happen unless the operator explicitly opened the outbound lane.
    try:
        require_external_connections("Mercado Pago payment-link test creation")
    except ExternalEffectsDisabled as exc:
        raise PaymentLinkTestError(str(exc)) from exc
    access_token = _mercadopago_access_token(db, hotel_id)
    recipient_email = _validate_email(payload.recipient_email)
    try:
        ensure_hotel_gmail_ready(db, hotel_id)
    except HotelOutboundEmailError as exc:
        raise PaymentLinkTestError(str(exc)) from exc
    external_reference = f"mp-test-{hotel_id}-{uuid4().hex[:18]}"
    description = (payload.description or "Senia de prueba").strip()
    expires_at = None
    preference_payload = {
        "items": [
            {
                "title": description,
                "quantity": 1,
                "currency_id": payload.currency,
                "unit_price": round(payload.amount, 2),
            }
        ],
        "payer": {"email": recipient_email},
        "external_reference": external_reference,
        "metadata": {"source": "hotel_chipre_pms_test", "hotel_id": hotel_id},
        "statement_descriptor": "HOTEL CHIPRE",
    }
    if payload.expires_in_minutes:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=int(payload.expires_in_minutes))
        preference_payload["expires"] = True
        preference_payload["expiration_date_from"] = now.isoformat()
        preference_payload["expiration_date_to"] = expires_at.isoformat()
    notification_url = _notification_url_if_public(external_reference, hotel_id)
    if notification_url:
        preference_payload["notification_url"] = notification_url

    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": hashlib.sha256(external_reference.encode("utf-8")).hexdigest(),
        },
        json=preference_payload,
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = None
        raise PaymentLinkTestError(_friendly_mercadopago_error(detail, response.status_code))

    data = response.json()
    payment_url = data.get("init_point") or data.get("sandbox_init_point")
    if not payment_url:
        raise PaymentLinkTestError("Mercado Pago no devolvio un link de pago.")

    record = PaymentLinkTest(
        hotel_id=hotel_id,
        provider="mercadopago",
        recipient_email=recipient_email,
        amount=payload.amount,
        currency=payload.currency,
        description=description,
        external_reference=external_reference,
        preference_id=data.get("id"),
        payment_link=payment_url,
        status="pending",
        external_status="preference_created",
        expires_at=expires_at,
        gateway_response=data,
    )
    db.add(record)
    db.flush()

    try:
        sender_email = _send_payment_link_email(db, hotel_id, recipient_email, payload.amount, payload.currency, payment_url, description)
        record.email_sent_at = datetime.now(timezone.utc)
        record.sender_channel = "gmail_hotel"
        record.sender_email = sender_email
        record.last_error = None
        record.gateway_response = {
            **(record.gateway_response or {}),
            "email_delivery_channel": "gmail_hotel",
            "email_sender": sender_email,
        }
    except Exception as exc:
        record.sender_channel = "not_sent"
        record.sender_email = None
        record.last_error = "No se pudo enviar el email"

    db.flush()
    return record


def list_payment_link_tests(db: Session, hotel_id: int, provider: str = "mercadopago") -> list[PaymentLinkTest]:
    return (
        db.query(PaymentLinkTest)
        .filter(PaymentLinkTest.hotel_id == hotel_id, PaymentLinkTest.provider == provider)
        .order_by(PaymentLinkTest.created_at.desc())
        .all()
    )


def refresh_mercadopago_payment_link_test(db: Session, hotel_id: int, test_id: int) -> PaymentLinkTest:
    # Polling provider state is intentionally unsupported. Status changes arrive
    # through the signed callback lane when that lane is explicitly enabled.
    raise PaymentLinkTestError(
        "La consulta externa de estado esta deshabilitada; espera un webhook firmado del proveedor."
    )


def refresh_mercadopago_payment_link_test_by_reference(
    db: Session,
    external_reference: str,
    hotel_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> PaymentLinkTest | None:
    try:
        require_inbound_provider_events("Mercado Pago")
    except InboundProviderEventsDisabled as exc:
        raise PaymentLinkTestError(str(exc)) from exc
    query = db.query(PaymentLinkTest).filter(
        PaymentLinkTest.external_reference == external_reference,
        PaymentLinkTest.provider == "mercadopago",
    )
    if hotel_id is not None:
        query = query.filter(PaymentLinkTest.hotel_id == hotel_id)
    record = query.first()
    if not record:
        return None

    # Never poll the provider from a callback. Persist only fields delivered in
    # the already signature-verified event and reject financial mismatches.
    event = payload if isinstance(payload, dict) else {}
    data = event.get("data") if isinstance(event.get("data"), dict) else {}
    payment = {**event, **data}
    incoming_currency = str(payment.get("currency_id") or payment.get("currency") or "").strip().upper()
    if incoming_currency and incoming_currency != record.currency.upper():
        raise PaymentLinkTestError("La moneda del webhook no coincide con el link de prueba.")
    incoming_amount = payment.get("transaction_amount") or payment.get("amount")
    if incoming_amount not in (None, "") and abs(_money(incoming_amount) - _money(record.amount)) > 0.01:
        raise PaymentLinkTestError("El monto del webhook no coincide con el link de prueba.")

    record.last_checked_at = datetime.now(timezone.utc)
    record.external_payment_id = str(payment.get("id") or "").strip() or record.external_payment_id
    provider_status = payment.get("status")
    if provider_status:
        record.external_status = str(payment.get("status_detail") or provider_status)
        record.status, record.refunded_amount = _status_from_payment_payload(payment, record)
        _apply_terminal_dates(record, record.status, payment)
    else:
        record.external_status = "signed_callback_received"
    record.gateway_response = event
    record.last_error = None
    db.flush()
    return record


def sync_pending_payment_link_tests(
    db: Session,
    hotel_id: int,
    provider: str = "mercadopago",
    stale_after_seconds: int = 20,
) -> None:
    # Backward-compatible no-op: listing tests must never poll a provider.
    return None


def cancel_mercadopago_payment_link_test(db: Session, hotel_id: int, test_id: int) -> PaymentLinkTest:
    record = (
        db.query(PaymentLinkTest)
        .filter(PaymentLinkTest.id == test_id, PaymentLinkTest.hotel_id == hotel_id, PaymentLinkTest.provider == "mercadopago")
        .first()
    )
    if not record:
        raise PaymentLinkTestError("Prueba no encontrada para este hotel.")
    if record.status in {"cancelled", "expired"}:
        raise PaymentLinkTestError("Este link ya no esta activo.")
    # Cancellation is local only. We deliberately do not decrypt credentials or
    # invoke the provider cancellation API; this preserves the credential record
    # while making the PMS artifact visibly terminal.
    now = datetime.now(timezone.utc)
    record.cancelled_at = now
    record.expires_at = now
    record.gateway_response = {
        **(record.gateway_response or {}),
        "local_cancellation": True,
    }
    record.last_error = None
    if record.status == "pending":
        record.status = "cancelled"
        record.external_status = "cancelled_by_user"
    db.flush()
    return record
