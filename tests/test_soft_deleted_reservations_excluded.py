from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Callable

import pytest

from app.api import reports as reports_api
from app.dependencies.auth import AuthContext
from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily
from app.models.company import Company
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room_block import RoomBlockReasonEnum
from app.services.allocation_engine import build_slots_from_db
from app.services.analytics_contracts import calculate_pickup_30d_count
from app.services.analytics_facts import (
    calculate_pickup_30d,
    refresh_fact_reservation_daily,
    refresh_fact_room_occupancy_daily,
)
from app.services.analytics_service import (
    build_operations_payload,
    build_starter_summary_payload,
    get_company_fact_detail,
)
from app.services.gemma_context_service import build_gemma_hotel_context
from app.services.guest_service import quick_profile
from app.services.timezones import hotel_today
from app.services.operational_report_service import daily_report as operational_daily_report
from app.services.rate_calendar_service import get_daily_calendar
from app.services.reservation_action_service import list_pending_reservation_actions
from app.services.room_block_service import ProtectedReservationConflictError, create_block


@dataclass(frozen=True)
class Surface:
    measure: Callable
    prepare: Callable = lambda db, reservation: None


def _request_context() -> AuthContext:
    return AuthContext(
        hotel_id=1,
        user_id=1,
        user_email="owner@test.com",
        user_role="owner",
        is_verified=True,
        permissions=set(),
    )


def _make_reservation(db, sample_guest, sample_categories, sample_rooms, target: date, code: str) -> Reservation:
    reservation = Reservation(
        hotel_id=1,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code=code,
        check_in_date=target,
        check_out_date=target + timedelta(days=1),
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _reports_daily(db, reservation, target):
    return reports_api.daily_report(report_date=target, db=db, context=_request_context())["arrivals"]["count"]


def _reports_occupancy(db, reservation, target):
    payload = reports_api.occupancy_report(
        start_date=target,
        end_date=target,
        db=db,
        context=_request_context(),
    )
    return payload["daily"][0]["occupied"]


def _reports_revenue(db, reservation, target):
    payload = reports_api.revenue_report(
        start_date=target,
        end_date=target,
        db=db,
        context=_request_context(),
    )
    return payload["expected"]["reservations_count"]


def _operational_daily(db, reservation, target):
    return operational_daily_report(db, 1, target).arrivals.count


def _rate_calendar(db, reservation, target):
    return get_daily_calendar(
        db,
        hotel_id=1,
        category_id=reservation.category_id,
        date_from=target,
        date_to=target,
    )["days"][0]["reserved"]


def _fact_reservation_daily(db, reservation, target):
    refresh_fact_reservation_daily(db, hotel_id=1, date_from=target, date_to=target)
    return (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.hotel_id == 1, FactReservationDaily.stay_date == target)
        .count()
    )


def _fact_room_occupancy_daily(db, reservation, target):
    refresh_fact_room_occupancy_daily(db, hotel_id=1, date_from=target, date_to=target)
    return (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == 1,
            FactRoomOccupancyDaily.stay_date == target,
            FactRoomOccupancyDaily.is_occupied.is_(True),
        )
        .count()
    )


def _facts_pickup(db, reservation, target):
    return calculate_pickup_30d(db, hotel_id=1, date_from=target, date_to=target)


def _contracts_pickup(db, reservation, target):
    return calculate_pickup_30d_count(db, hotel_id=1, date_from=target, date_to=target)


def _prepare_company(db, reservation):
    company = Company(
        hotel_id=1,
        legal_name="Soft Delete Company",
        display_name="Soft Delete Company",
        tax_id="30-00000000-1",
        country_code="AR",
    )
    db.add(company)
    db.flush()
    reservation.company_id = company.id
    db.flush()


def _company_detail(db, reservation, target):
    payload = get_company_fact_detail(
        db,
        hotel_id=1,
        company_id=reservation.company_id,
        date_from=target,
        date_to=target,
    )
    return len(payload["reservations"])


def _card_value(payload, card_code):
    return next(card["value_count"] for card in payload["data"]["cards"] if card["card_code"] == card_code)


def _starter_analytics(db, reservation, target):
    return _card_value(
        build_starter_summary_payload(db, hotel_id=1, date_from=target, date_to=target),
        "starter_arrivals_today",
    )


def _prepare_no_show(db, reservation):
    reservation.status = ReservationStatusEnum.NO_SHOW
    db.flush()


def _operations_analytics(db, reservation, target):
    return _card_value(
        build_operations_payload(
            db,
            hotel_id=1,
            date_from=target,
            date_to=target,
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        ),
        "operations_no_shows",
    )


def _allocation(db, reservation, target):
    slots, _rooms = build_slots_from_db(
        db,
        start_date=target,
        end_date=target + timedelta(days=1),
        hotel_id=1,
    )
    return sum(slot.reservation_id == reservation.id for slot in slots)


def _guest_quick_profile(db, reservation, target):
    return quick_profile(db, hotel_id=1, guest_id=reservation.guest_id)["total_stays"]


def _prepare_pending_action(db, reservation):
    reservation.room_id = None
    reservation.requires_manual_review = True
    reservation.allocation_status = "manual_review"
    db.flush()


def _reservation_actions(db, reservation, target):
    return int(
        any(action["reservation_id"] == reservation.id for action in list_pending_reservation_actions(db, hotel_id=1))
    )


def _gemma_context(db, reservation, target):
    payload = build_gemma_hotel_context(db, hotel_id=1, intent_type="occupancy")
    return payload["reservation_summary"]["upcoming_active_reservation_count"]


def _prepare_protected_reservation(db, reservation):
    reservation.allocation_locked = True
    db.flush()


def _room_block_conflict(db, reservation, target):
    try:
        create_block(
            db,
            hotel_id=1,
            room_id=reservation.room_id,
            starts_at=target,
            ends_at=target + timedelta(days=1),
            reason_code=RoomBlockReasonEnum.MAINTENANCE,
        )
    except ProtectedReservationConflictError:
        return 1
    return 0


SURFACES = [
    pytest.param(Surface(_reports_daily), id="reports-daily"),
    pytest.param(Surface(_reports_occupancy), id="reports-occupancy"),
    pytest.param(Surface(_reports_revenue), id="reports-revenue"),
    pytest.param(Surface(_operational_daily), id="operational-daily"),
    pytest.param(Surface(_rate_calendar), id="rate-calendar"),
    pytest.param(Surface(_fact_reservation_daily), id="fact-reservation-daily"),
    pytest.param(Surface(_fact_room_occupancy_daily), id="fact-room-occupancy-daily"),
    pytest.param(Surface(_facts_pickup), id="analytics-facts-pickup"),
    pytest.param(Surface(_contracts_pickup), id="analytics-contracts-pickup"),
    pytest.param(Surface(_company_detail, _prepare_company), id="analytics-company-detail"),
    pytest.param(Surface(_starter_analytics), id="analytics-starter"),
    pytest.param(Surface(_operations_analytics, _prepare_no_show), id="analytics-operations"),
    pytest.param(Surface(_allocation), id="allocation"),
    pytest.param(Surface(_guest_quick_profile), id="guest-quick-profile"),
    pytest.param(Surface(_reservation_actions, _prepare_pending_action), id="reservation-actions"),
    pytest.param(Surface(_gemma_context), id="gemma-context"),
    pytest.param(Surface(_room_block_conflict, _prepare_protected_reservation), id="room-block-availability"),
]


@pytest.mark.parametrize("surface", SURFACES)
def test_soft_deleted_reservation_is_excluded_from_aggregation_and_availability(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    surface: Surface,
):
    # Hotel-local, not the runner's date: the analytics pickup surfaces bucket
    # `created_at` in the hotel's timezone, so a UTC runner between 21:00 and
    # midnight in Buenos Aires would look for the reservation one day late.
    target = hotel_today(db, 1)
    reservation = _make_reservation(
        db,
        sample_guest,
        sample_categories,
        sample_rooms,
        target,
        code=f"SOFT-{surface.measure.__name__}"[:30],
    )
    surface.prepare(db, reservation)

    assert surface.measure(db, reservation, target) == 1

    reservation.deleted_at = datetime.now(timezone.utc)
    db.flush()

    assert surface.measure(db, reservation, target) == 0
