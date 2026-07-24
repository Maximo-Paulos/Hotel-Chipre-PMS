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
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment import Payment, PaymentLink
from app.models.reservation import Reservation
from app.models.transaction import Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.services.payment_service import calculate_payment_surcharge

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
    # Imported lazily so the test gateway never pulls in requests / network code.
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
        raise PaymentLinkError(f"Mercado Pago rechazo la creacion del link: {detail}")
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


def create_link(
    db: Session,
    hotel_id: int,
    payload: PaymentLinkCreate,
    *,
    mp_gateway: Optional[MpGateway] = None,
    delivery_channel: Optional[str] = None,
    email_delivery: Optional[EmailDelivery] = None,
) -> PaymentLink:
    reservation = _get_reservation_for_hotel(db, hotel_id, payload.reservation_id)
    provider = payload.provider or "mercado_pago"
    if provider != "mercado_pago":
        raise PaymentLinkError("Solo mercado_pago esta habilitado para links de pago")

    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=provider,
        base_amount=payload.requested_amount,
    )
    link_code = _unique_link_code(db)
    link = PaymentLink(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        provider=provider,
        link_code=link_code,
        requested_amount=surcharge_info["final_amount"],
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

    # §12.2: in production, fill external_checkout_url + preference id by creating a
    # real Mercado Pago preference. Best-effort: if MP is not connected / fails, the
    # link is still created (with last_error recorded) so the operator can retry.
    gateway = mp_gateway or _create_mercadopago_preference
    try:
        result = gateway(db, hotel_id, link)
        link.external_checkout_url = result.get("checkout_url")
        preference_id = result.get("preference_id")
        link.gateway_response = {
            **(result.get("raw") or {}),
            "preference_id": preference_id,
        }
        link.last_error = None
    except Exception as exc:  # noqa: BLE001 - best-effort gateway
        logger.warning("payment-link MP preference failed link=%s: %s", link.link_code, exc)
        link.last_error = f"No se pudo crear la preferencia de pago: {exc}"
    db.flush()

    if delivery_channel:
        deliver_link(db, hotel_id, link, channel=delivery_channel, email_delivery=email_delivery)

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
            logger.warning("payment-link email delivery failed link=%s: %s", link.link_code, exc)
            link.gateway_response = {
                **(link.gateway_response or {}),
                "delivery_channel": "email",
                "delivery_status": "failed",
            }
            link.last_error = f"No se pudo enviar el link por email: {exc}"
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
    from app.services.financial_ledger import operational_balance_due

    return operational_balance_due(db, hotel_id=hotel_id, reservation=reservation)
