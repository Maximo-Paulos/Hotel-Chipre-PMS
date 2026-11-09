"""PostgreSQL regressions for stay-extension pricing."""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.schemas.reservation import ReservationUpdate
from app.services import reservation_operations_service, reservation_service
from app.services.collaboration import apply_resource_changes
from app.services.reservation_operations_service import (
    extend_reservation_stay,
    preview_reservation_stay_extension,
)
from app.services.reservation_service import ReservationError
from app.services.tenant_context import set_tenant_hotel_context


def _paid_reservation(pg_session) -> Reservation:
    suffix = uuid4().hex[:10].upper()
    hotel_id = 160_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(
        id=hotel_id,
        hotel_name=f"Synthetic extension pricing {suffix}",
        deposit_policy_configured=True,
    )
    pg_session.add(hotel)
    pg_session.flush()

    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic extension category {suffix}",
        code=f"EX{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Extension guest")
    pg_session.add_all([category, guest])
    pg_session.flush()

    room = Room(
        hotel_id=hotel_id,
        room_number=f"E{suffix[:8]}",
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
    )
    pg_session.add(room)
    pg_session.flush()

    check_in = date.today() + timedelta(days=30)
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"EXT-{suffix}",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_in + timedelta(days=2),
        total_amount=Decimal("200.00"),
        subtotal_amount=Decimal("200.00"),
        net_amount=Decimal("200.00"),
        amount_paid=Decimal("200.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
    )
    pg_session.add(reservation)
    pg_session.flush()
    return reservation


def test_postgres_paid_extension_preserves_booked_nightly_rate_when_no_active_rate(
    pg_session, monkeypatch
):
    reservation = _paid_reservation(pg_session)
    hotel_id = reservation.hotel_id
    new_checkout = reservation.check_out_date + timedelta(days=1)

    def no_active_rate(*args, **kwargs):
        raise ReservationError("No active prices found for rate plan")

    monkeypatch.setattr(reservation_operations_service, "calculate_reservation_pricing", no_active_rate)

    preview_amount = preview_reservation_stay_extension(
        pg_session,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout,
    )
    assert preview_amount == Decimal("100.00")

    result = extend_reservation_stay(
        pg_session,
        reservation=reservation,
        hotel_id=hotel_id,
        new_checkout_date=new_checkout,
        client_version=reservation.version,
        pricing_mode="current_rate",
        payment_action="pending_balance",
    )

    assert result.success is True
    assert result.extension_amount == Decimal("100.00")
    assert reservation.check_out_date == new_checkout
    assert reservation.total_amount == Decimal("300.00")
    assert reservation.subtotal_amount == Decimal("300.00")
    assert reservation.net_amount == Decimal("300.00")
    assert reservation.amount_paid == Decimal("200.00")
    assert (reservation.total_amount / Decimal((new_checkout - reservation.check_in_date).days)) == Decimal("100.00")


def test_postgres_paid_extension_still_rejects_other_pricing_errors(pg_session, monkeypatch):
    reservation = _paid_reservation(pg_session)

    def invalid_policy(*args, **kwargs):
        raise ReservationError("La configuración fiscal no es válida")

    monkeypatch.setattr(reservation_operations_service, "calculate_reservation_pricing", invalid_policy)

    with pytest.raises(ReservationError, match="configuración fiscal"):
        preview_reservation_stay_extension(
            pg_session,
            reservation=reservation,
            hotel_id=reservation.hotel_id,
            new_checkout_date=reservation.check_out_date + timedelta(days=1),
        )


@pytest.mark.parametrize(
    ("checkout_delta", "expected_total"),
    [(1, Decimal("300.00")), (-1, Decimal("100.00"))],
    ids=["extension", "shortening"],
)
def test_postgres_paid_edit_keeps_booked_nightly_rate_when_no_active_rate(
    pg_session, monkeypatch, checkout_delta, expected_total
):
    reservation = _paid_reservation(pg_session)
    reservation.pricing_snapshot = json.dumps(
        {"pricing_source": "rate_plan_quote", "nightly_rate": "100.00"}
    )
    pg_session.flush()
    new_checkout = reservation.check_out_date + timedelta(days=checkout_delta)

    def no_active_rate(*args, **kwargs):
        raise ReservationError("No active prices found for rate plan")

    monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", no_active_rate)

    reservation_service.update_reservation_fields(
        pg_session,
        reservation,
        ReservationUpdate(check_out_date=new_checkout, client_version=reservation.version),
        reservation.hotel_id,
        actor_role="manager",
        preserve_unclassified_price=True,
    )
    pg_session.flush()

    assert reservation.check_out_date == new_checkout
    assert reservation.total_amount == expected_total
    assert reservation.amount_paid == Decimal("200.00")
    assert Decimal(str(reservation.total_amount)) / Decimal(
        (reservation.check_out_date - reservation.check_in_date).days
    ) == Decimal("100.00")
    assert json.loads(reservation.pricing_snapshot)["nightly_rate"] == 100.0


def test_postgres_collaborative_edit_recalculates_manual_total_for_shortened_stay(
    pg_session, monkeypatch
):
    reservation = _paid_reservation(pg_session)
    reservation.pricing_snapshot = json.dumps(
        {"pricing_source": "manual_total_override", "nightly_rate": "100.00"}
    )
    pg_session.flush()
    new_checkout = reservation.check_out_date - timedelta(days=1)

    def unexpected_rate_lookup(*args, **kwargs):
        raise AssertionError("manual nightly pricing must not query an active rate")

    monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", unexpected_rate_lookup)

    apply_resource_changes(
        pg_session,
        "reservation",
        reservation,
        {"check_out_date": new_checkout},
        hotel_id=reservation.hotel_id,
        actor_role="owner",
    )
    pg_session.flush()

    assert reservation.check_out_date == new_checkout
    assert reservation.total_amount == Decimal("100.00")
    assert reservation.amount_paid == Decimal("200.00")
    assert json.loads(reservation.pricing_snapshot)["nightly_rate"] == 100.0


def test_postgres_paid_edit_keeps_dates_and_total_when_pricing_error_is_not_missing_rate(
    pg_session, monkeypatch
):
    reservation = _paid_reservation(pg_session)
    reservation.pricing_snapshot = json.dumps(
        {"pricing_source": "rate_plan_quote", "nightly_rate": "100.00"}
    )
    pg_session.flush()
    original_checkout = reservation.check_out_date
    original_total = reservation.total_amount
    new_checkout = original_checkout - timedelta(days=1)

    def invalid_pricing_policy(*args, **kwargs):
        raise ReservationError("La configuración fiscal no es válida")

    monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", invalid_pricing_policy)

    with pytest.raises(ReservationError, match="configuración fiscal"):
        reservation_service.update_reservation_fields(
            pg_session,
            reservation,
            ReservationUpdate(check_out_date=new_checkout, client_version=reservation.version),
            reservation.hotel_id,
            actor_role="manager",
            preserve_unclassified_price=True,
        )

    pg_session.expire(reservation)
    assert reservation.check_out_date == original_checkout
    assert reservation.total_amount == original_total
    assert reservation.amount_paid == Decimal("200.00")
