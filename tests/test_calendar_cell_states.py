from __future__ import annotations

from datetime import date, timedelta

from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationOutcomeEnum,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.services.rate_calendar_service import get_daily_calendar

from tests.test_rate_calendar_service import (
    _seed_category,
    _seed_rooms,
    _seed_user_and_guest,
)


def _make_reservation(
    db,
    *,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int,
    check_in: date,
    check_out: date,
    code: str,
    total: float = 100.0,
    paid: float = 0.0,
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT,
    requires_manual_review: bool = False,
) -> Reservation:
    reservation = Reservation(
        confirmation_code=code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=total,
        subtotal_amount=total,
        net_amount=total,
        amount_paid=paid,
        deposit_amount=0.0,
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        source=source,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        requires_manual_review=requires_manual_review,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _states_for_first_day(db, category, target: date) -> list[str]:
    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=target,
        date_to=target,
    )
    return result["days"][0]["cell_states"]


def test_pending_payment_marks_cell(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 2)
    _user, guest = _seed_user_and_guest(db, category.hotel_id)
    target = date(2026, 7, 2)
    _make_reservation(
        db,
        hotel_id=category.hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=target,
        check_out=target + timedelta(days=1),
        code="RES-PEND",
        total=100.0,
        paid=40.0,  # balance_due = 60 > 0
        source=ReservationSourceEnum.DIRECT,
    )

    states = _states_for_first_day(db, category, target)
    assert "pending_payment" in states
    assert "ota_unpaid" not in states
    assert "available_with_review" not in states


def test_ota_with_balance_marks_ota_unpaid(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 2)
    _user, guest = _seed_user_and_guest(db, category.hotel_id)
    target = date(2026, 7, 3)
    _make_reservation(
        db,
        hotel_id=category.hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=target,
        check_out=target + timedelta(days=1),
        code="RES-OTA",
        total=100.0,
        paid=0.0,  # balance_due = 100 > 0
        source=ReservationSourceEnum.BOOKING,
    )

    result = get_daily_calendar(
        db,
        hotel_id=category.hotel_id,
        category_id=category.id,
        date_from=target,
        date_to=target,
    )
    day = result["days"][0]
    assert "ota_unpaid" in day["cell_states"]
    # OTA with balance is also pending_payment (§13.1 superset).
    assert "pending_payment" in day["cell_states"]
    # severity suggestion is exposed and aligned with states
    assert len(day["cell_state_severities"]) == len(day["cell_states"])
    assert "yellow" in day["cell_state_severities"]


def test_requires_manual_review_marks_available_with_review(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 2)
    _user, guest = _seed_user_and_guest(db, category.hotel_id)
    target = date(2026, 7, 4)
    _make_reservation(
        db,
        hotel_id=category.hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=target,
        check_out=target + timedelta(days=1),
        code="RES-REVIEW",
        total=100.0,
        paid=100.0,  # fully paid, no balance
        source=ReservationSourceEnum.DIRECT,
        requires_manual_review=True,
    )

    states = _states_for_first_day(db, category, target)
    assert "available_with_review" in states
    assert "pending_payment" not in states
    assert "ota_unpaid" not in states


def test_fully_paid_direct_marks_nothing(db):
    category = _seed_category(db)
    rooms = _seed_rooms(db, category, 2)
    _user, guest = _seed_user_and_guest(db, category.hotel_id)
    target = date(2026, 7, 5)
    _make_reservation(
        db,
        hotel_id=category.hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=rooms[0].id,
        check_in=target,
        check_out=target + timedelta(days=1),
        code="RES-PAID",
        total=100.0,
        paid=100.0,
        source=ReservationSourceEnum.DIRECT,
        requires_manual_review=False,
    )

    states = _states_for_first_day(db, category, target)
    assert states == []


def test_cell_states_isolated_per_hotel(db):
    # Hotel 1 has a pending-payment reservation; hotel 2's calendar must be clean.
    cat1 = _seed_category(db, hotel_id=1, code="STD1")
    rooms1 = _seed_rooms(db, cat1, 2)
    _u1, g1 = _seed_user_and_guest(db, 1)
    cat2 = _seed_category(db, hotel_id=2, code="STD2")
    _seed_rooms(db, cat2, 2)

    target = date(2026, 7, 6)
    _make_reservation(
        db,
        hotel_id=1,
        guest_id=g1.id,
        category_id=cat1.id,
        room_id=rooms1[0].id,
        check_in=target,
        check_out=target + timedelta(days=1),
        code="RES-H1",
        total=100.0,
        paid=0.0,
        source=ReservationSourceEnum.BOOKING,
    )

    states_h1 = _states_for_first_day(db, cat1, target)
    states_h2 = _states_for_first_day(db, cat2, target)
    assert "ota_unpaid" in states_h1
    assert states_h2 == []
