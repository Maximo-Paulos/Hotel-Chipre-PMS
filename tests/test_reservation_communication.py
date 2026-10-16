from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.config import get_settings
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.reservation_communication import (
    ReservationEmailKindEnum,
    ReservationEmailStatusEnum,
)
from app.models.room import RoomCategory
from app.schemas.reservation_communication import (
    ReservationEmailDeliveryRead,
    ReservationEmailSendRequest,
)
from app.services.hotel_outbound_email_service import (
    HotelOutboundEmailError,
    HotelOutboundSendResult,
)
from app.services.reservation_communication_service import (
    ReservationCommunicationError,
    list_reservation_email_deliveries,
    send_reservation_email,
)


def _reservation(db, *, hotel_id: int = 1, guest_email: str | None = "guest@example.com") -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, hotel_name="Hotel Demo", subscription_active=True))
    db.flush()
    guest = Guest(first_name="Ada", last_name="Lovelace", email=guest_email, hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code=f"STD-{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"COM-{hotel_id}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 9, 20),
        check_out_date=date(2026, 9, 22),
        total_amount=Decimal("200.00"),
        amount_paid=Decimal("60.00"),
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.DEPOSIT_PAID,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_confirmation_is_accepted_and_second_click_is_deduplicated(db):
    reservation = _reservation(db)
    calls = []

    def sender(*args, **kwargs):
        calls.append(kwargs)
        return HotelOutboundSendResult(channel="gmail_hotel", sender_email="hotel@example.com", provider_message_id="m-1")

    first = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind=ReservationEmailKindEnum.CONFIRMATION,
        requested_by_user_id=None,
        sender=sender,
    )
    second = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind=ReservationEmailKindEnum.CONFIRMATION,
        requested_by_user_id=None,
        sender=sender,
    )

    assert first.delivery.status == ReservationEmailStatusEnum.ACCEPTED
    assert first.delivery.provider_message_id == "m-1"
    assert second.deduplicated is True
    assert second.delivery.id == first.delivery.id
    assert len(calls) == 1


def test_provider_failure_is_visible_and_explicit_resend_creates_attempt(db):
    reservation = _reservation(db)
    calls = 0

    def sender(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HotelOutboundEmailError("Gmail no está conectado")
        return HotelOutboundSendResult(channel="gmail_hotel", sender_email="hotel@example.com", provider_message_id="m-2")

    first = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="voucher",
        requested_by_user_id=None,
        sender=sender,
    )
    retry = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="voucher",
        requested_by_user_id=None,
        resend=True,
        sender=sender,
    )

    assert first.delivery.status == ReservationEmailStatusEnum.FAILED
    assert retry.delivery.status == ReservationEmailStatusEnum.ACCEPTED
    assert retry.delivery.is_resend is True
    assert [item.status for item in list_reservation_email_deliveries(db, hotel_id=1, reservation_id=reservation.id)] == [
        ReservationEmailStatusEnum.ACCEPTED,
        ReservationEmailStatusEnum.FAILED,
    ]


def test_unknown_provider_result_is_not_retried_implicitly(db):
    reservation = _reservation(db)

    def sender(*args, **kwargs):
        raise TimeoutError("provider timeout")

    first = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="confirmation",
        requested_by_user_id=None,
        sender=sender,
    )
    second = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="confirmation",
        requested_by_user_id=9,
        sender=sender,
    )

    assert first.delivery.status == ReservationEmailStatusEnum.UNKNOWN
    assert second.deduplicated is True
    assert second.delivery.id == first.delivery.id


def test_invalid_recipient_is_rejected_before_provider(db):
    reservation = _reservation(db, guest_email=None)
    called = False

    def sender(*args, **kwargs):
        nonlocal called
        called = True
        return HotelOutboundSendResult(channel="gmail_hotel", sender_email="hotel@example.com")

    try:
        send_reservation_email(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            kind="confirmation",
            requested_by_user_id=None,
            sender=sender,
        )
    except ReservationCommunicationError as exc:
        assert "email" in str(exc).lower()
    else:
        raise AssertionError("an absent recipient must be rejected")
    assert called is False


def test_local_example_test_address_is_accepted_but_never_forwarded(db, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("EMAIL_PROVIDER", "null")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    payload = ReservationEmailSendRequest(recipient_email="Guest+Sim@EXAMPLE.TEST")
    assert payload.recipient_email == "Guest+Sim@example.test"

    reservation = _reservation(db, guest_email="guest@example.test")
    calls = []

    def sender(*args, **kwargs):
        calls.append(kwargs)
        return HotelOutboundSendResult(channel="gmail_hotel", sender_email="hotel@example.com")

    outcome = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="confirmation",
        requested_by_user_id=None,
        sender=sender,
    )

    assert outcome.delivery.status == ReservationEmailStatusEnum.FAILED
    assert outcome.delivery.last_error == "Dirección sintética local; no se envió ningún correo"
    assert calls == []
    validated_delivery = ReservationEmailDeliveryRead.model_validate(outcome.delivery)
    assert validated_delivery.recipient_email == "guest@example.test"


def test_production_rejects_example_test_recipient(db, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("EMAIL_PROVIDER", "null")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    with pytest.raises(ValidationError):
        ReservationEmailSendRequest(recipient_email="guest@example.test")

    reservation = _reservation(db, guest_email="guest@example.test")
    calls = []
    with pytest.raises(ReservationCommunicationError, match="formato válido"):
        send_reservation_email(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            kind="confirmation",
            requested_by_user_id=None,
            sender=lambda *args, **kwargs: calls.append(kwargs),
        )
    assert calls == []


def test_synthetic_email_does_not_expand_reservation_tenant_scope(db, monkeypatch):
    monkeypatch.delenv("TESTING", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("EMAIL_PROVIDER", "null")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    reservation = _reservation(db, guest_email="guest@example.test")
    calls = []
    with pytest.raises(ReservationCommunicationError, match="Reserva no encontrada"):
        send_reservation_email(
            db,
            hotel_id=2,
            reservation_id=reservation.id,
            kind="confirmation",
            requested_by_user_id=None,
            sender=lambda *args, **kwargs: calls.append(kwargs),
        )
    assert calls == []


def test_test_mode_never_sends_example_test_even_if_provider_flags_are_enabled(db, monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()

    reservation = _reservation(db, guest_email="guest@example.test")
    calls = []
    outcome = send_reservation_email(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        kind="confirmation",
        requested_by_user_id=None,
        sender=lambda *args, **kwargs: calls.append(kwargs),
    )

    assert outcome.delivery.status == ReservationEmailStatusEnum.FAILED
    assert "no se envió" in outcome.delivery.last_error
    assert calls == []
