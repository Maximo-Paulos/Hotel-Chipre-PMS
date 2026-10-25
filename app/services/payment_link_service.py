"""Production payment-link lifecycle: create, list, cancel, expire, collection refresh.

Source-of-truth rule (docs/data-foundations/transactions-vs-payments.md):
balance_due is ALWAYS computed from confirmed transactions, never from payments.
The external_reference is HMAC-signed so an inbound webhook can resolve the hotel
without trusting caller-supplied hotel_id.
"""
import hashlib
import hmac
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import quote, urlencode, urlparse
from uuid import uuid4

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.payment import Payment, PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.services.external_effects_policy import (
    ExternalEffectsDisabled,
    external_connections_enabled,
    require_external_connections,
)
from app.services.outbound_http_telemetry import observed_http_call
from app.services.payment_service import (
    PaymentError,
    calculate_base_amount_before_surcharge,
    calculate_payment_surcharge,
)
from app.services.row_locks import lock_query

logger = logging.getLogger(__name__)

# Gateway callable signature: (db, hotel_id, link) -> dict with at least
# {"checkout_url": str, "preference_id": str|None, "raw": dict}. Injectable so
# tests never hit the real Mercado Pago API.
MpGateway = Callable[[Session, int, PaymentLink], dict[str, Any]]

# Delivery callable signature: (db, hotel_id, link) -> str (sender identifier).
# Injectable so tests never send real email.
EmailDelivery = Callable[[Session, int, PaymentLink], str]
MpRevocation = Callable[[Session, int, PaymentLink], dict[str, Any]]


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
    import requests

    from app.services.payment_link_test_service import _mercadopago_connection_payload

    connection_payload = _mercadopago_connection_payload(db, hotel_id)
    access_token = str(connection_payload["access_token"])
    account_id = (
        connection_payload.get("user_id")
        or connection_payload.get("collector_id")
        or connection_payload.get("merchant_id")
    )
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
        "metadata": {
            "source": "hotel_chipre_pms",
            "hotel_id": hotel_id,
            "link_code": link.link_code,
            **({"account_id": str(account_id)} if account_id else {}),
        },
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

    response = observed_http_call("mercadopago.payment_link", requests.post,
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
    return {
        "checkout_url": checkout_url,
        "preference_id": data.get("id"),
        "account_id": str(account_id) if account_id else None,
        "raw": data,
    }


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _assert_mercadopago_preference_identity(
    data: Any,
    *,
    preference_id: str,
    external_reference: str,
    expected_account_id: str | None,
    known_account_id: str | None = None,
) -> str | None:
    if not isinstance(data, dict):
        raise PaymentLinkError("provider_revocation_unconfirmed")
    if str(data.get("id") or "") != preference_id:
        raise PaymentLinkError("provider_preference_mismatch")
    if str(data.get("external_reference") or "") != external_reference:
        raise PaymentLinkError("provider_preference_mismatch")
    account_id = data.get("collector_id") or data.get("user_id")
    normalized_account_id = str(account_id) if account_id else None
    if expected_account_id and normalized_account_id != expected_account_id:
        raise PaymentLinkError("provider_account_mismatch")
    if known_account_id and normalized_account_id != known_account_id:
        raise PaymentLinkError("provider_account_mismatch")
    return normalized_account_id


def _mercadopago_preference_expired(
    db: Session, hotel_id: int, link: PaymentLink
) -> dict[str, Any]:
    """Expire and verify a canceled Checkout Pro preference.

    Mercado Pago exposes preference update/read operations rather than a
    dedicated preference DELETE/revoke endpoint. This updates the preference's
    validity window to end at the already-persisted local cancellation time,
    then confirms `preference_expired` with Mercado Pago. It deliberately does
    not use `date_of_expiration`, which is for offline-payment deadlines and
    can cause a late payment to be returned automatically to the payer.
    """
    require_external_connections("Mercado Pago payment-link revocation")
    import requests

    from app.services.payment_link_test_service import _mercadopago_connection_payload

    preference_id = get_preference_id(link)
    if not isinstance(preference_id, str) or not preference_id or len(preference_id) > 200:
        raise PaymentLinkError("preference_id_unavailable")
    # IDs are path components supplied by the provider and persisted locally.
    # Restrict the accepted alphabet before placing one in a request URL.
    if not all(char.isalnum() or char in "-_" for char in preference_id):
        raise PaymentLinkError("preference_id_unavailable")
    if not link.external_reference:
        raise PaymentLinkError("provider_preference_mismatch")

    connection_payload = _mercadopago_connection_payload(
        db, hotel_id, seed_catalog_entries=False
    )
    # The worker has already committed its claim. Skip catalog seeding and close
    # this credential-read transaction before provider I/O so no DB connection
    # or transaction remains checked out while waiting on Mercado Pago.
    db.commit()
    access_token = str(connection_payload["access_token"])
    account_id = (
        connection_payload.get("user_id")
        or connection_payload.get("collector_id")
        or connection_payload.get("merchant_id")
    )
    stored_account_id = (link.gateway_response or {}).get("pms_account_id")
    if stored_account_id and (
        not account_id or str(stored_account_id) != str(account_id)
    ):
        raise PaymentLinkError("provider_account_mismatch")
    expected_provider_account_id = (
        str(stored_account_id or account_id) if (stored_account_id or account_id) else None
    )

    cancelled_at = _ensure_utc(link.cancelled_at or datetime.now(UTC))
    created_at = _ensure_utc(link.created_at or cancelled_at)
    if created_at >= cancelled_at:
        # Preserve an ordered window if an imported row has an unusable
        # creation timestamp. The end remains the fixed cancellation instant.
        created_at = cancelled_at - timedelta(seconds=1)

    webhook_base = get_settings().APP_BASE_URL.rstrip("/")
    payload: dict[str, Any] = {
        "items": [
            {
                "title": link.title or "Pago de Reserva",
                "quantity": 1,
                "currency_id": link.currency,
                "unit_price": float(_money(link.requested_amount)),
            }
        ],
        "payer": {"email": link.recipient_email},
        "external_reference": link.external_reference,
        "metadata": {
            "source": "hotel_chipre_pms",
            "hotel_id": hotel_id,
            "link_code": link.link_code,
            **({"account_id": str(account_id)} if account_id else {}),
        },
        "statement_descriptor": "HOTEL CHIPRE",
        "expires": True,
        "expiration_date_from": created_at.isoformat(timespec="milliseconds"),
        "expiration_date_to": cancelled_at.isoformat(timespec="milliseconds"),
    }
    if _is_safe_provider_url(webhook_base):
        payload["notification_url"] = (
            f"{webhook_base}/api/payment-links/mercadopago/webhook?"
            + urlencode({"external_reference": link.external_reference or ""})
        )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    preference_url = f"https://api.mercadopago.com/checkout/preferences/{quote(preference_id, safe='')}"
    preflight = observed_http_call(
        "mercadopago.payment_link_revoke_preflight",
        requests.get,
        preference_url,
        headers=headers,
        timeout=20,
    )
    if not preflight.ok:
        raise PaymentLinkError("provider_preference_unavailable")
    try:
        preflight_data = preflight.json()
    except (TypeError, ValueError) as exc:
        raise PaymentLinkError("provider_revocation_unconfirmed") from exc
    preflight_account_id = _assert_mercadopago_preference_identity(
        preflight_data,
        preference_id=preference_id,
        external_reference=link.external_reference,
        expected_account_id=expected_provider_account_id,
    )
    if preflight_data.get("preference_expired") is True:
        return {"preference_expired": True}

    response = observed_http_call(
        "mercadopago.payment_link_revoke",
        requests.put,
        preference_url,
        headers=headers,
        json=payload,
        timeout=20,
    )
    if not response.ok:
        raise PaymentLinkError("provider_rejected_revocation")
    try:
        response_data = response.json()
    except (TypeError, ValueError) as exc:
        raise PaymentLinkError("provider_revocation_unconfirmed") from exc
    _assert_mercadopago_preference_identity(
        response_data,
        preference_id=preference_id,
        external_reference=link.external_reference,
        expected_account_id=expected_provider_account_id,
        known_account_id=preflight_account_id,
    )
    if response_data.get("preference_expired") is True:
        return {"preference_expired": True}

    # A 2xx update is not proof that the checkout stopped accepting payments.
    # Read the provider's computed expiration flag before reporting success.
    verification = observed_http_call(
        "mercadopago.payment_link_revoke_verify",
        requests.get,
        preference_url,
        headers=headers,
        timeout=20,
    )
    if not verification.ok:
        raise PaymentLinkError("provider_revocation_unconfirmed")
    try:
        verification_data = verification.json()
    except (TypeError, ValueError) as exc:
        raise PaymentLinkError("provider_revocation_unconfirmed") from exc
    _assert_mercadopago_preference_identity(
        verification_data,
        preference_id=preference_id,
        external_reference=link.external_reference,
        expected_account_id=expected_provider_account_id,
        known_account_id=preflight_account_id,
    )
    return {"preference_expired": verification_data.get("preference_expired") is True}


def _default_email_delivery(db: Session, hotel_id: int, link: PaymentLink) -> str:
    """Default email delivery: reuses the hotel outbound email pipeline."""
    from app.services.payment_link_test_service import _send_payment_link_email

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
    reservation = lock_query(
        db.query(Reservation).filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id),
        Reservation,
    ).first()
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
    from app.services.financial_ledger import operational_balance_due

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
        link_metadata = active_link.gateway_response if isinstance(active_link.gateway_response, dict) else {}
        try:
            reserved += calculate_base_amount_before_surcharge(
                db,
                hotel_id=hotel_id,
                payment_method=active_link.provider or provider,
                final_amount=provider_outstanding,
                currency_code=active_link.currency,
                surcharge_quote_snapshot=link_metadata.get("_pms_surcharge_quote"),
            )
        except PaymentError as exc:
            raise PaymentLinkError(str(exc)) from exc
    return max(Decimal("0.00"), balance - reserved).quantize(Decimal("0.01"))


def create_link(
    db: Session,
    hotel_id: int,
    payload: PaymentLinkCreate,
    *,
    mp_gateway: MpGateway | None = None,
    delivery_channel: str | None = None,
    email_delivery: EmailDelivery | None = None,
    idempotency_key: str | None = None,
) -> PaymentLink:
    reservation = _get_reservation_for_hotel(db, hotel_id, payload.reservation_id)
    if reservation.status in (ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT):
        raise PaymentLinkError(
            f"Cannot create a payment link for a reservation in status '{reservation.status.value}'"
        )
    provider = payload.provider or "mercado_pago"
    if provider != "mercado_pago":
        raise PaymentLinkError("Solo mercado_pago esta habilitado para links de pago")

    currency = (payload.currency or reservation.currency_code or "ARS").strip().upper()
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    if (
        len(currency) != 3
        or not currency.isascii()
        or not currency.isalpha()
        or currency != reservation_currency
    ):
        raise PaymentLinkError(
            f"La moneda del link ({currency}) debe coincidir con la reserva ({reservation_currency})"
        )
    recipient_email = str(payload.recipient_email).strip().lower()
    try:
        surcharge_info = calculate_payment_surcharge(
            db,
            hotel_id=hotel_id,
            payment_method=provider,
            base_amount=payload.requested_amount,
            currency_code=currency,
        )
    except PaymentError as exc:
        raise PaymentLinkError(str(exc)) from exc
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
        gateway_response={"_pms_surcharge_quote": surcharge_info["surcharge_quote_snapshot"]},
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
            account_id = result.get("account_id")
            if not account_id and isinstance(result.get("raw"), dict):
                account_id = (
                    result["raw"].get("collector_id")
                    or result["raw"].get("user_id")
                    or (result["raw"].get("metadata") or {}).get("account_id")
                )
            link.gateway_response = {
                **(result.get("raw") or {}),
                **(link.gateway_response or {}),
                "preference_id": preference_id,
                **({"pms_account_id": str(account_id)} if account_id else {}),
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
    email_delivery: EmailDelivery | None = None,
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
    _queue_provider_revocation(link)
    link.status = "cancelled"
    link.payable = False
    link.cancelled_at = datetime.now(UTC)
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
        if link.status in {"active", "pending", "partially_paid"}:
            _queue_provider_revocation(link)
            link.status = "cancelled"
            link.payable = False
            link.cancelled_at = datetime.now(UTC)
            if reason:
                link.last_error = f"cancelled: {reason}"
            cancelled += 1
    if cancelled:
        db.flush()
    return cancelled


def _queue_provider_revocation(link: PaymentLink) -> None:
    """Persist a same-transaction request for canceling an MP checkout."""
    provider = (link.provider or "").strip().lower().replace("mercadopago", "mercado_pago")
    preference_id = get_preference_id(link)
    if (
        provider == "mercado_pago"
        and link.execution_mode == "provider"
        and link.payable
        and isinstance(preference_id, str)
        and bool(preference_id.strip())
    ):
        link.provider_revocation_status = "pending"
        link.provider_revocation_error = None
    else:
        link.provider_revocation_status = "not_required"
        link.provider_revocation_error = None


def _revocation_error_code(exc: Exception) -> str:
    if isinstance(exc, ExternalEffectsDisabled):
        return "external_connections_disabled"
    safe_codes = {
        "preference_id_unavailable",
        "provider_preference_unavailable",
        "provider_account_mismatch",
        "provider_preference_mismatch",
        "provider_rejected_revocation",
        "provider_revocation_unconfirmed",
    }
    if isinstance(exc, PaymentLinkError) and str(exc) in safe_codes:
        return str(exc)
    return "provider_unconfirmed"


def _enqueue_provider_revocation_failure(db: Session, link: PaymentLink) -> None:
    from app.models.notification import (
        NotificationChannelEnum,
        NotificationSeverityEnum,
    )
    from app.services.notification_service import enqueue_notifications_for_event

    enqueue_notifications_for_event(
        db,
        hotel_id=link.hotel_id,
        event_type="payment_link.revocation_failed",
        dedupe_key=f"payment-link-revocation-failed:{link.id}",
        title="No se pudo confirmar la baja del link de Mercado Pago",
        body=(
            "La reserva quedó cancelada en el PMS, pero Mercado Pago no confirmó que el link de checkout "
            "haya dejado de aceptar pagos. Revisá el estado del link en Mercado Pago. No se realizó ninguna devolución."
        ),
        severity=NotificationSeverityEnum.CRITICAL,
        entity_type="reservation",
        entity_id=link.reservation_id,
        payload={
            "reservation_id": link.reservation_id,
            "payment_link_id": link.id,
        },
        recipient_roles=("owner", "co_owner", "manager"),
        channels=(NotificationChannelEnum.IN_APP,),
        force_in_app=True,
    )


def process_payment_link_revocations(
    db: Session,
    hotel_id: int,
    *,
    reservation_id: int | None = None,
    limit: int = 50,
    revoke_gateway: MpRevocation | None = None,
) -> dict[str, int]:
    """Attempt pending provider revocations after the local cancellation commits.

    Claim one pending row in a short transaction immediately before its network
    call. This keeps unstarted rows out of the stale-claim window while a batch
    is processed sequentially. The attempt count fences a late worker from
    overwriting a newer attempt after a stale claim is recovered. Claims older
    than five minutes are reclaimed after a process crash. A failed/ambiguous
    attempt is terminal and gets one deduplicated manager alert. No payment,
    ledger transaction, or refund state is changed.
    """
    # Cancellation routes also call this processor immediately after their
    # local commit. Keep queued work pending while provider traffic is closed;
    # otherwise the adapter's later guard would turn a configuration skip into
    # a terminal failure that the scheduled worker cannot recover.
    if not external_connections_enabled():
        logger.info(
            "payment_link.provider_revocation_deferred hotel_id=%s reason=external_connections_disabled",
            hotel_id,
        )
        return {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 1}

    bounded_limit = max(1, min(int(limit), 100))
    counts = {"processed": 0, "succeeded": 0, "failed": 0, "skipped": 0}
    gateway = revoke_gateway or _mercadopago_preference_expired
    claim_count = 0
    while claim_count < bounded_limit:
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_before = now - timedelta(minutes=5)
        stale_claims = db.query(PaymentLink).filter(
            PaymentLink.hotel_id == hotel_id,
            PaymentLink.provider_revocation_status == "processing",
            or_(
                PaymentLink.provider_revocation_last_attempt_at.is_(None),
                PaymentLink.provider_revocation_last_attempt_at <= stale_before,
            ),
        )
        if reservation_id is not None:
            stale_claims = stale_claims.filter(PaymentLink.reservation_id == reservation_id)
        stale_claims.update(
            {PaymentLink.provider_revocation_status: "pending"},
            synchronize_session="fetch",
        )

        candidates = db.query(PaymentLink).filter(
            PaymentLink.hotel_id == hotel_id,
            PaymentLink.status == "cancelled",
            PaymentLink.provider_revocation_status == "pending",
            PaymentLink.execution_mode == "provider",
            PaymentLink.provider.in_(("mercado_pago", "mercadopago")),
        )
        if reservation_id is not None:
            candidates = candidates.filter(PaymentLink.reservation_id == reservation_id)
        link = (
            candidates.order_by(PaymentLink.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
            .first()
        )
        if link is None:
            # Release any stale-claim update even when there was no work to claim.
            db.commit()
            break

        payment_link_id = link.id
        claimed_attempt = int(link.provider_revocation_attempts or 0) + 1
        link.provider_revocation_status = "processing"
        link.provider_revocation_attempts = claimed_attempt
        link.provider_revocation_last_attempt_at = now
        # This service is called only after the local cancellation transaction
        # commits. Persist and release the single claim before provider I/O.
        db.commit()
        claim_count += 1

        link = (
            db.query(PaymentLink)
            .filter(
                PaymentLink.id == payment_link_id,
                PaymentLink.hotel_id == hotel_id,
                PaymentLink.provider_revocation_status == "processing",
                PaymentLink.provider_revocation_attempts == claimed_attempt,
            )
            .first()
        )
        if link is None:
            counts["skipped"] += 1
            db.commit()
            continue
        # Keep an immutable ORM snapshot for the gateway and end this read
        # transaction before external I/O. The detached object is read-only.
        db.expunge(link)
        db.commit()
        gateway_error: Exception | None = None
        gateway_succeeded = False
        try:
            result = gateway(db, hotel_id, link)
            if not isinstance(result, dict) or result.get("preference_expired") is not True:
                raise PaymentLinkError("provider_revocation_unconfirmed")
            gateway_succeeded = True
        except Exception as exc:  # noqa: BLE001 - cancellation remains local and durable
            gateway_error = exc
            # A provider adapter may have failed while using this Session.
            # Clear any failed read transaction before persisting its outcome.
            db.rollback()

        current_link = (
            db.query(PaymentLink)
            .filter(
                PaymentLink.id == payment_link_id,
                PaymentLink.hotel_id == hotel_id,
                PaymentLink.provider_revocation_status == "processing",
                PaymentLink.provider_revocation_attempts == claimed_attempt,
            )
            .with_for_update(skip_locked=True)
            .first()
        )
        if current_link is None:
            db.rollback()
            counts["skipped"] += 1
            continue

        if gateway_succeeded:
            current_link.provider_revocation_status = "succeeded"
            current_link.provider_revocation_error = None
            counts["succeeded"] += 1
        else:
            error = gateway_error or PaymentLinkError("provider_revocation_unconfirmed")
            current_link.provider_revocation_status = "failed"
            current_link.provider_revocation_error = _revocation_error_code(error)
            _enqueue_provider_revocation_failure(db, current_link)
            logger.warning(
                "payment_link.provider_revocation_failed hotel_id=%s payment_link_id=%s error_type=%s",
                hotel_id,
                current_link.id,
                type(error).__name__,
            )
            counts["failed"] += 1
        counts["processed"] += 1
        db.commit()
    return counts


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
