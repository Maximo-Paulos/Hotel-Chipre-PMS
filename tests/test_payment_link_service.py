from datetime import date
from decimal import Decimal

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction
from app.schemas.payment_link import PaymentLinkCreate
from app.services.payment_link_service import (
    PaymentLinkError,
    cancel_link,
    create_link,
    deliver_link,
    get_preference_id,
    list_links_for_reservation,
)
from app.services.payment_link_test_service import (
    PaymentLinkTestError,
    validate_mercadopago_webhook_signature,
)
from app.config import get_settings


def _enable_external_effects(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_external_effect_settings_cache():
    yield
    get_settings.cache_clear()


def _reservation(db, hotel_id: int, code: str = "RL-1") -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name="Ada", last_name="Guest", email=f"guest-{hotel_id}@test.com", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        total_amount=Decimal("200.00"),
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_create_payment_link_persists_link_without_transaction(db):
    reservation = _reservation(db, 1)

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("75.50"),
            recipient_email="guest@example.com",
            description="Deposit",
        ),
    )

    assert link.id is not None
    assert link.provider == "mercado_pago"
    assert link.link_code
    assert link.requested_amount == Decimal("75.50")
    assert link.collected_amount == Decimal("0.00")
    assert db.query(Transaction).count() == 0


def test_connections_flag_closed_forces_local_only_before_gateway(db, monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()
    reservation = _reservation(db, 1)

    def unexpected_gateway(*args, **kwargs):
        raise AssertionError("provider gateway must not be called")

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("75.50"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=unexpected_gateway,
    )

    assert link.execution_mode == "local_only"
    assert link.payable is False
    assert link.external_checkout_url is None


def test_cross_hotel_isolation_for_payment_link_service(db):
    reservation_a = _reservation(db, 1, "RL-A")
    reservation_b = _reservation(db, 2, "RL-B")
    link_b = create_link(
        db,
        2,
        PaymentLinkCreate(
            reservation_id=reservation_b.id,
            requested_amount=Decimal("20.00"),
            recipient_email="guest-b@example.com",
        ),
    )

    assert list_links_for_reservation(db, 1, reservation_a.id) == []
    assert list_links_for_reservation(db, 1, reservation_b.id) == []
    with pytest.raises(PaymentLinkError):
        cancel_link(db, 1, link_b.id)


def _fake_mp_gateway(checkout="https://mp.example/checkout/abc", preference_id="pref-123"):
    def gateway(db, hotel_id, link):
        return {"checkout_url": checkout, "preference_id": preference_id, "raw": {"id": preference_id}}

    return gateway


def test_create_link_fills_checkout_url_with_mocked_mp(db, monkeypatch):
    # §12.2 ITEM A: production link creates a (mocked) MP preference and persists
    # external_checkout_url + preference id.
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("120.00"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=_fake_mp_gateway(),
        idempotency_key="payment-link-create-1",
    )

    assert link.external_checkout_url == "https://mp.example/checkout/abc"
    assert get_preference_id(link) == "pref-123"
    assert link.last_error is None


def test_create_link_best_effort_when_gateway_fails(db, monkeypatch):
    # No MP connection / failing gateway must NOT block link creation.
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)

    def boom(db, hotel_id, link):
        raise RuntimeError("mp down")

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("50.00"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=boom,
        idempotency_key="payment-link-failure-1",
    )

    assert link.id is not None
    assert link.external_checkout_url is None
    assert "No se pudo crear la preferencia" in (link.last_error or "")


def test_deliver_link_email_records_channel(db, monkeypatch):
    # §12.2 ITEM B: email delivery (mocked) fires and records the channel.
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)
    sent = {}

    def fake_email(db, hotel_id, link):
        sent["to"] = link.recipient_email
        return "hotel@gmail.com"

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("80.00"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=_fake_mp_gateway(),
        delivery_channel="email",
        email_delivery=fake_email,
        idempotency_key="payment-link-email-1",
    )

    assert sent["to"] == "guest@example.com"
    assert link.sent_via_email is True
    assert link.gateway_response.get("delivery_status") == "sent"


def test_deliver_link_email_best_effort_on_failure(db, monkeypatch):
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)
    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("80.00"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=_fake_mp_gateway(),
        idempotency_key="payment-link-email-failure-1",
    )

    def boom_email(db, hotel_id, link):
        raise RuntimeError("smtp down")

    deliver_link(db, 1, link, channel="email", email_delivery=boom_email)
    assert link.gateway_response.get("delivery_status") == "failed"
    assert link.sent_via_email is False


def test_deliver_link_whatsapp_stub_pending(db, monkeypatch):
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)
    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("80.00"),
            recipient_email="guest@example.com",
        ),
        mp_gateway=_fake_mp_gateway(),
        idempotency_key="payment-link-whatsapp-1",
    )

    deliver_link(db, 1, link, channel="whatsapp")
    assert link.gateway_response.get("delivery_channel") == "whatsapp"
    assert link.gateway_response.get("delivery_status") == "pending"


def test_provider_link_requires_idempotency_key_before_gateway(db, monkeypatch):
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)
    gateway_called = False

    def unexpected_gateway(db, hotel_id, link):
        nonlocal gateway_called
        gateway_called = True
        raise AssertionError("gateway must not be called without idempotency")

    with pytest.raises(PaymentLinkError, match="Idempotency-Key es obligatorio"):
        create_link(
            db,
            1,
            PaymentLinkCreate(
                reservation_id=reservation.id,
                requested_amount=Decimal("50.00"),
                recipient_email="guest@example.com",
            ),
            mp_gateway=unexpected_gateway,
        )

    assert gateway_called is False


def test_provider_link_replays_same_idempotency_key_without_second_gateway(db, monkeypatch):
    _enable_external_effects(monkeypatch)
    reservation = _reservation(db, 1)
    calls = 0

    def gateway(db, hotel_id, link):
        nonlocal calls
        calls += 1
        return _fake_mp_gateway()(db, hotel_id, link)

    payload = PaymentLinkCreate(
        reservation_id=reservation.id,
        requested_amount=Decimal("50.00"),
        recipient_email="guest@example.com",
    )
    first = create_link(
        db,
        1,
        payload,
        mp_gateway=gateway,
        idempotency_key="provider-replay-key",
    )
    replay = create_link(
        db,
        1,
        payload,
        mp_gateway=gateway,
        idempotency_key="provider-replay-key",
    )

    assert replay.id == first.id
    assert calls == 1


def test_mercadopago_webhook_signature_rejects_when_secret_is_unconfigured():
    """A public webhook endpoint must fail closed without a configured secret."""
    with pytest.raises(PaymentLinkTestError, match="no esta configurado"):
        validate_mercadopago_webhook_signature(
            "",
            data_id="payment-789",
            request_id="req-123",
            signature_header="ts=1700000000,v1=deadbeef",
        )
