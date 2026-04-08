from datetime import datetime, timedelta, timezone
import ipaddress
from typing import Any
from uuid import uuid4
from urllib.parse import urlparse

import requests
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment_link_test import PaymentLinkTest
from app.schemas.payment_link_test import PaymentLinkTestCreate
from app.services.email_service import mailer
from app.services.integration_service import get_connection_payload


class PaymentLinkTestError(Exception):
    pass


def _validate_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise PaymentLinkTestError("Ingresa un email valido para enviar el link.")
    return normalized


def _mercadopago_access_token(db: Session, hotel_id: int) -> str:
    payload = get_connection_payload(db, hotel_id, "mercadopago")
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
        return message or "Mercado Pago rechazo la prueba."
    return str(detail)


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


def _send_payment_link_email(recipient_email: str, amount: float, currency: str, payment_url: str, description: str) -> None:
    subject = "Link de pago de prueba - Hotel PMS"
    body = (
        "Hola,\n\n"
        f"Te enviamos un link de pago de prueba por {amount:.2f} {currency}.\n\n"
        f"Concepto: {description}\n"
        f"Link de pago: {payment_url}\n\n"
        "Una vez abonado, el hotel podra verificar el estado desde el PMS.\n"
    )
    mailer.send(recipient_email, subject, body)


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
    access_token = _mercadopago_access_token(db, hotel_id)
    recipient_email = _validate_email(payload.recipient_email)
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
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=preference_payload,
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
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
        _send_payment_link_email(recipient_email, payload.amount, payload.currency, payment_url, description)
        record.email_sent_at = datetime.now(timezone.utc)
    except Exception as exc:
        record.last_error = f"No se pudo enviar el email: {exc}"

    db.flush()
    return record


def list_payment_link_tests(db: Session, hotel_id: int, provider: str = "mercadopago") -> list[PaymentLinkTest]:
    sync_pending_payment_link_tests(db, hotel_id, provider=provider)
    return (
        db.query(PaymentLinkTest)
        .filter(PaymentLinkTest.hotel_id == hotel_id, PaymentLinkTest.provider == provider)
        .order_by(PaymentLinkTest.created_at.desc())
        .all()
    )


def refresh_mercadopago_payment_link_test(db: Session, hotel_id: int, test_id: int) -> PaymentLinkTest:
    record = (
        db.query(PaymentLinkTest)
        .filter(PaymentLinkTest.id == test_id, PaymentLinkTest.hotel_id == hotel_id, PaymentLinkTest.provider == "mercadopago")
        .first()
    )
    if not record:
        raise PaymentLinkTestError("Prueba no encontrada para este hotel.")

    access_token = _mercadopago_access_token(db, hotel_id)
    response = requests.get(
        "https://api.mercadopago.com/v1/payments/search",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"external_reference": record.external_reference, "sort": "date_created", "criteria": "desc"},
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise PaymentLinkTestError(
            f"No se pudo consultar el estado en Mercado Pago: {_friendly_mercadopago_error(detail, response.status_code)}"
        )

    data = response.json()
    results = data.get("results") or []
    record.last_checked_at = datetime.now(timezone.utc)

    if not results:
        expires_at = _ensure_utc(record.expires_at)
        if record.cancelled_at:
            record.status = "cancelled"
            record.external_status = "cancelled_by_user"
        elif expires_at and expires_at <= datetime.now(timezone.utc):
            record.status = "expired"
            record.external_status = "expired"
        else:
            record.status = "pending"
            record.external_status = "waiting_payment"
        record.last_error = None
        record.refunded_amount = None
        if record.status != "approved":
            record.paid_at = None
        record.refunded_at = None
        record.gateway_response = data
        db.flush()
        return record

    payment = results[0]
    record.external_status = payment.get("status_detail") or payment.get("status")
    record.external_payment_id = str(payment.get("id")) if payment.get("id") else None
    record.status, record.refunded_amount = _status_from_payment_payload(payment, record)
    record.gateway_response = payment
    record.last_error = None
    _apply_terminal_dates(record, record.status, payment)

    db.flush()
    return record


def refresh_mercadopago_payment_link_test_by_reference(
    db: Session,
    external_reference: str,
    hotel_id: int | None = None,
) -> PaymentLinkTest | None:
    query = db.query(PaymentLinkTest).filter(
        PaymentLinkTest.external_reference == external_reference,
        PaymentLinkTest.provider == "mercadopago",
    )
    if hotel_id is not None:
        query = query.filter(PaymentLinkTest.hotel_id == hotel_id)
    record = query.first()
    if not record:
        return None
    return refresh_mercadopago_payment_link_test(db, record.hotel_id, record.id)


def sync_pending_payment_link_tests(
    db: Session,
    hotel_id: int,
    provider: str = "mercadopago",
    stale_after_seconds: int = 20,
) -> None:
    if provider != "mercadopago":
        return

    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(seconds=stale_after_seconds)
    syncable_tests = (
        db.query(PaymentLinkTest)
        .filter(
            PaymentLinkTest.hotel_id == hotel_id,
            PaymentLinkTest.provider == provider,
            PaymentLinkTest.status.in_(["pending", "approved", "partially_refunded"]),
        )
        .order_by(PaymentLinkTest.created_at.desc())
        .all()
    )

    for test in syncable_tests:
        last_checked_at = _ensure_utc(test.last_checked_at)
        if last_checked_at and last_checked_at > stale_before:
            continue
        try:
            refresh_mercadopago_payment_link_test(db, hotel_id, test.id)
        except PaymentLinkTestError as exc:
            test.last_error = str(exc)
            test.last_checked_at = now
        except Exception as exc:
            test.last_error = f"No se pudo sincronizar automaticamente: {exc}"
            test.last_checked_at = now
    db.flush()


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
    if not record.preference_id:
        raise PaymentLinkTestError("Este link no tiene una preferencia valida para cancelar.")

    access_token = _mercadopago_access_token(db, hotel_id)
    now = datetime.now(timezone.utc)
    response = requests.put(
        f"https://api.mercadopago.com/checkout/preferences/{record.preference_id}",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "expires": True,
            "expiration_date_from": (now - timedelta(minutes=5)).isoformat(),
            "expiration_date_to": now.isoformat(),
        },
        timeout=20,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise PaymentLinkTestError(
            f"No se pudo cancelar el link en Mercado Pago: {_friendly_mercadopago_error(detail, response.status_code)}"
        )

    record.cancelled_at = now
    record.expires_at = now
    record.gateway_response = response.json()
    record.last_error = None
    if record.status == "pending":
        record.status = "cancelled"
        record.external_status = "cancelled_by_user"
    db.flush()
    return record
