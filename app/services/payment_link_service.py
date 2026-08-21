"""Production payment-link lifecycle: create, list, cancel, expire, collection refresh.

Source-of-truth rule (docs/data-foundations/transactions-vs-payments.md):
balance_due is ALWAYS computed from confirmed transactions, never from payments.
The external_reference is HMAC-signed so an inbound webhook can resolve the hotel
without trusting caller-supplied hotel_id.
"""
from datetime import datetime, timezone
from decimal import Decimal
import logging
import hashlib
import hmac
from typing import Any, Callable, Optional
from urllib.parse import urlencode, urlparse
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment import Payment, PaymentLink
from app.models.reservation import Reservation
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.services.external_effects_policy import (
    ExternalEffectsDisabled,
    external_connections_enabled,
    require_external_connections,
)
from app.services.payment_service import (
    calculate_base_amount_before_surcharge,
    calculate_payment_surcharge,
)

logger = logging.getLogger(__name__)

# Gateway callable signature: (db, hotel_id, link) -> dict with at least
# {"checkout_url": str, "preference_id": str|None, "raw": dict}. Injectable so
# tests never hit the real Mercado Pago API.
MpGateway = Callable[[Session, int, PaymentLink], dict[str, Any]]

# Delivery callable signature: (db, hotel_id, link) -> str (sender identifier).
# Injectable so tests never send real email.
EmailDelivery = Callable[[Session, int, PaymentLink], str]


class PaymentLinkError(Exception):
    pass


def _create_mercadopago_preference(db: Session, hotel_id: int, link: PaymentLink) -> dict[str, Any]:
    """Default production MP gateway: builds a checkout preference and returns the
    checkout URL + preference id. Reuses the same MP integration token + preference
    shape as the test tooling (payment_link_test_service)."""
    # The policy check intentionally precedes imports, credential lookup/decryption,
    # and construction of a network client.
    require_external_connections("Mercado Pago payment-link creation")

    # Imported lazily so the local-only path never pulls in network code.
    from app.services.payment_link_test_service import _mercadopago_access_token  # noqa: PLC0415
    import requests  # noqa: PLC0415

    access_token = _mercadopago_access_token(db, hotel_id)
    preference_payload: dict[str, Any] = {
        "items": [
            {
                "title": link.title or "Pago de Reserva",
                "quantity": 1,
                "currency_id": link.currency,
                "unit_price": float(round(Decimal(str(link.requested_amount)), 2)),
            }
        ],
        "payer": {"email": link.recipient_email},
        "external_reference": link.external_reference,
        "metadata": {"source": "hotel_chipre_pms", "hotel_id": hotel_id, "link_code": link.link_code},
        "statement_descriptor": "HOTEL CHIPRE",
    }
    if link.expires_at:
        preference_payload["expires"] = True
        preference_payload["expiration_date_to"] = link.expires_at.isoformat()

    settings = get_settings()
    webhook_base = settings.APP_BASE_URL.rstrip("/")
    if _is_safe_provider_url(webhook_base):
        preference_payload["notification_url"] = (
            f"{webhook_base}/api/payment-links/mercadopago/webhook?"
            + urlencode({"external_reference": link.external_reference or ""})
        )

    provider_idempotency_key = hashlib.sha256(
        (link.idempotency_key or link.external_reference or link.link_code).encode("utf-8")
    ).hexdigest()

    response = requests.post(
        "https://api.mercadopago.com/checkout/preferences",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": provider_idempotency_key,
        },
        json=preference_payload,
        timeout=20,
    )
    if not response.ok:
        raise PaymentLinkError("Mercado Pago rechazo la creacion del link.")
    data = response.json()
    checkout_url = data.get("init_point") or data.get("sandbox_init_point")
    if not checkout_url:
        raise PaymentLinkError("Mercado Pago no devolvio un link de pago.")
    return {"checkout_url": checkout_url, "preference_id": data.get("id"), "raw": data}


def _default_email_delivery(db: Session, hotel_id: int, link: PaymentLink) -> str:
    """Default email delivery: reuses the hotel outbound email pipeline."""
    from app.services.payment_link_test_service import _send_payment_link_email  # noqa: PLC0415

    return _send_payment_link_email(
        db,
        hotel_id,
        link.recipient_email,
        float(round(Decimal(str(link.requested_amount)), 2)),
        link.currency,
        link.external_checkout_url or "",
        link.description or link.title or "Pago de Reserva",
    )


def _money(value) -> Decimal:
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _is_safe_provider_url(value: str | None) -> bool:
    try:
        parsed = urlparse((value or "").strip())
    except ValueError:
        return False
    return parsed.scheme == "https" and bool(parsed.hostname) and not parsed.username and not parsed.password


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
        .with_for_update()
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


def _normalized_idempotency_key(value: str | None) -> str | None:
    normalized = (value or "").strip()
    if not normalized:
        return None
    if len(normalized) < 8 or len(normalized) > 100:
        raise PaymentLinkError("Idempotency-Key debe tener entre 8 y 100 caracteres")
    return normalized


def _find_idempotent_link(db: Session, hotel_id: int, idempotency_key: str | None) -> PaymentLink | None:
    if idempotency_key is None:
        return None
    return (
        db.query(PaymentLink)
        .filter(
            PaymentLink.hotel_id == hotel_id,
            PaymentLink.idempotency_key == idempotency_key,
        )
        .first()
    )


def _validate_idempotent_replay(
    link: PaymentLink,
    *,
    reservation_id: int,
    provider: str,
    requested_amount: Decimal,
    currency: str,
    recipient_email: str,
) -> PaymentLink:
    same_request = (
        link.reservation_id == reservation_id
        and link.provider == provider
        and _money(link.requested_amount) == _money(requested_amount)
        and link.currency == currency
        and link.recipient_email == recipient_email
    )
    if not same_request:
        raise PaymentLinkError("Idempotency-Key ya fue usado con otro pedido de link")
    return link


def _available_provider_balance(
    db: Session,
    *,
    hotel_id: int,
    reservation: Reservation,
    provider: str,
) -> Decimal:
    from app.services.financial_ledger import operational_balance_due  # noqa: PLC0415

    balance = _money(operational_balance_due(db, hotel_id=hotel_id, reservation=reservation))
    active_links = (
        db.query(PaymentLink)
        .filter(
            PaymentLink.hotel_id == hotel_id,
            PaymentLink.reservation_id == reservation.id,
            PaymentLink.execution_mode == "provider",
            PaymentLink.payable.is_(True),
            PaymentLink.status.in_(["active", "pending", "partially_paid"]),
        )
        .all()
    )
    reserved = Decimal("0.00")
    for active_link in active_links:
        provider_outstanding = max(
            Decimal("0.00"),
            _money(active_link.requested_amount) - _money(active_link.collected_amount),
        )
        reserved += calculate_base_amount_before_surcharge(
            db,
            hotel_id=hotel_id,
            payment_method=active_link.provider or provider,
            final_amount=provider_outstanding,
        )
    return max(Decimal("0.00"), balance - reserved).quantize(Decimal("0.01"))


def create_link(
    db: Session,
    hotel_id: int,
    payload: PaymentLinkCreate,
    *,
    mp_gateway: Optional[MpGateway] = None,
    delivery_channel: Optional[str] = None,
    email_delivery: Optional[EmailDelivery] = None,
    idempotency_key: str | None = None,
) -> PaymentLink:
    reservation = _get_reservation_for_hotel(db, hotel_id, payload.reservation_id)
    provider = payload.provider or "mercado_pago"
    if provider != "mercado_pago":
        raise PaymentLinkError("Solo mercado_pago esta habilitado para links de pago")

    currency = (payload.currency or reservation.currency_code or "ARS").strip().upper()
    recipient_email = str(payload.recipient_email).strip().lower()
    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=provider,
        base_amount=payload.requested_amount,
    )
    normalized_idempotency_key = _normalized_idempotency_key(idempotency_key)
    existing = _find_idempotent_link(db, hotel_id, normalized_idempotency_key)
    if existing is not None:
        return _validate_idempotent_replay(
            existing,
            reservation_id=reservation.id,
            provider=provider,
            requested_amount=surcharge_info["final_amount"],
            currency=currency,
            recipient_email=recipient_email,
        )

    provider_mode_requested = external_connections_enabled()
    if provider_mode_requested:
        if normalized_idempotency_key is None:
            raise PaymentLinkError(
                "Idempotency-Key es obligatorio para crear un link con proveedor"
            )
        reservation_currency = (reservation.currency_code or "ARS").strip().upper()
        if currency != reservation_currency:
            raise PaymentLinkError(
                f"La moneda del link ({currency}) debe coincidir con la reserva ({reservation_currency})"
            )
        available_balance = _available_provider_balance(
            db,
            hotel_id=hotel_id,
            reservation=reservation,
            provider=provider,
        )
        if _money(payload.requested_amount) > available_balance + Decimal("0.01"):
            raise PaymentLinkError(
                f"El monto del link excede el saldo disponible ({available_balance:.2f} {currency})"
            )

    link_code = _unique_link_code(db)
    link = PaymentLink(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        provider=provider,
        link_code=link_code,
        requested_amount=surcharge_info["final_amount"],
        collected_amount=Decimal("0.00"),
        currency=currency,
        recipient_email=recipient_email,
        recipient_name=(payload.recipient_name or "").strip() or None,
        recipient_phone=(payload.recipient_phone or "").strip() or None,
        title=(payload.title or "").strip() or "Pago de Reserva",
        description=(payload.description or "").strip() or None,
        status="pending",
        execution_mode="local_only",
        payable=False,
        idempotency_key=normalized_idempotency_key,
        external_reference=sign_external_reference(hotel_id, link_code),
        expires_at=payload.expires_at,
    )
    if normalized_idempotency_key is None:
        db.add(link)
        db.flush()
    else:
        try:
            with db.begin_nested():
                db.add(link)
                db.flush()
        except IntegrityError:
            concurrent = _find_idempotent_link(db, hotel_id, normalized_idempotency_key)
            if concurrent is None:
                raise
            return _validate_idempotent_replay(
                concurrent,
                reservation_id=reservation.id,
                provider=provider,
                requested_amount=surcharge_info["final_amount"],
                currency=currency,
                recipient_email=recipient_email,
            )

    if provider_mode_requested:
        gateway = mp_gateway or _create_mercadopago_preference
        try:
            # Re-check at the actual sink so a changed/reloaded policy cannot
            # race the earlier decision.
            require_external_connections("Mercado Pago payment-link creation")
            result = gateway(db, hotel_id, link)
            checkout_url = str(result.get("checkout_url") or "").strip()
            preference_id = str(result.get("preference_id") or "").strip()
            if not _is_safe_provider_url(checkout_url) or not preference_id:
                raise PaymentLinkError("Mercado Pago no devolvio una preferencia pagable valida")
            link.external_checkout_url = checkout_url
            link.execution_mode = "provider"
            link.payable = True
            link.gateway_response = {
                **(result.get("raw") or {}),
                "preference_id": preference_id,
            }
            link.last_error = None
        except Exception as exc:  # noqa: BLE001 - persist a safe local artifact
            logger.warning(
                "payment-link MP preference failed link=%s error_type=%s",
                link.link_code,
                type(exc).__name__,
            )
            link.external_checkout_url = None
            link.execution_mode = "local_only"
            link.payable = False
            link.last_error = "No se pudo crear la preferencia de pago con el proveedor."
        db.flush()

    if delivery_channel:
        if link.payable:
            deliver_link(db, hotel_id, link, channel=delivery_channel, email_delivery=email_delivery)
        else:
            link.last_error = link.last_error or "El artefacto local_only no se puede enviar como link pagable"
            db.flush()

    return link


def get_preference_id(link: PaymentLink) -> str | None:
    """Convenience accessor for the persisted MP preference id."""
    if isinstance(link.gateway_response, dict):
        return link.gateway_response.get("preference_id")
    return None


def deliver_link(
    db: Session,
    hotel_id: int,
    link: PaymentLink,
    *,
    channel: str,
    email_delivery: Optional[EmailDelivery] = None,
) -> PaymentLink:
    """§12.2 best-effort delivery of a payment link.

    - email: reuses the hotel outbound email pipeline. On success records the channel.
    - whatsapp / sms: stubbed with status 'pending' (no provider wired yet).
    A delivery failure never raises: the link stays created, the error is recorded.
    """
    normalized = (channel or "").strip().lower()
    if link.execution_mode != "provider" or not link.payable or not link.external_checkout_url:
        raise PaymentLinkError("El artefacto local_only no es pagable ni se puede enviar al huesped")
    try:
        require_external_connections(f"payment-link {normalized} delivery")
    except ExternalEffectsDisabled as exc:
        raise PaymentLinkError(str(exc)) from exc
    if normalized == "email":
        deliver = email_delivery or _default_email_delivery
        try:
            sender = deliver(db, hotel_id, link)
            link.sent_via_email = True
            link.gateway_response = {
                **(link.gateway_response or {}),
                "delivery_channel": "email",
                "delivery_status": "sent",
                "delivery_sender": sender,
            }
            link.last_error = None
        except Exception as exc:  # noqa: BLE001 - best-effort delivery
            logger.warning(
                "payment-link email delivery failed link=%s error_type=%s",
                link.link_code,
                type(exc).__name__,
            )
            link.gateway_response = {
                **(link.gateway_response or {}),
                "delivery_channel": "email",
                "delivery_status": "failed",
            }
            link.last_error = "No se pudo enviar el link por email."
    elif normalized in {"whatsapp", "sms"}:
        # No provider wired yet (§12.2 future): record intent as pending, do not fail.
        link.gateway_response = {
            **(link.gateway_response or {}),
            "delivery_channel": normalized,
            "delivery_status": "pending",
        }
    else:
        raise PaymentLinkError(f"Canal de envio no soportado: {channel}")
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
    link.payable = False
    link.cancelled_at = datetime.now(timezone.utc)
    if reason:
        # No dedicated column; record the operator reason in last_error for traceability.
        link.last_error = f"cancelled: {reason}"
    db.flush()
    return link


def cancel_active_links_for_reservation(
    db: Session, hotel_id: int, reservation_id: int, reason: str | None = None
) -> int:
    """Cancel every non-terminal payment link of a reservation (e.g. on cancellation),
    so a guest can no longer pay a stale seña link. Completed/expired/cancelled links
    are left untouched. Returns the number of links cancelled."""
    links = list_links_for_reservation(db, hotel_id, reservation_id)
    cancelled = 0
    for link in links:
        if link.status in {"pending", "partially_paid"}:
            link.status = "cancelled"
            link.payable = False
            link.cancelled_at = datetime.now(timezone.utc)
            if reason:
                link.last_error = f"cancelled: {reason}"
            cancelled += 1
    if cancelled:
        db.flush()
    return cancelled


def expire_link(db: Session, hotel_id: int, link_id: int) -> PaymentLink:
    link = db.query(PaymentLink).filter(PaymentLink.id == link_id, PaymentLink.hotel_id == hotel_id).first()
    if not link:
        raise PaymentLinkError("Link de pago no encontrado para este hotel")
    if link.status not in {"completed", "cancelled"}:
        link.status = "expired"
        link.payable = False
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
        link.payable = False
    elif link.collected_amount > Decimal("0.00"):
        link.status = "partially_paid"
        link.payable = link.execution_mode == "provider" and bool(link.external_checkout_url)
    elif link.status not in {"cancelled", "expired"}:
        link.status = "pending"
    db.flush()
    return link


def balance_due_from_transactions(db: Session, hotel_id: int, reservation_id: int) -> Decimal:
    reservation = _get_reservation_for_hotel(db, hotel_id, reservation_id)
    from app.services.financial_ledger import operational_balance_due

    return operational_balance_due(db, hotel_id=hotel_id, reservation=reservation)
