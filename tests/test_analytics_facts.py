from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.analytics import (
    FactReservationDaily,
    FactRoomOccupancyDaily,
    HotelAuditEvent,
    RoomStateEvent,
    RoomStateEventReasonCodeEnum,
    RoomStateEventTypeEnum,
)
from app.models.company import Company
from app.models.hotel_membership import HotelMembership
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
    ReservationSourceEnum,
)
from app.models.user import User
from app.services.analytics_facts import (
    detect_no_shows,
    refresh_fact_reservation_daily,
    refresh_fact_room_occupancy_daily,
)


def test_detect_no_shows_marks_reservation(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    owner = User(email="owner@example.com", password_hash="x", role="owner", is_verified=True, is_active=True)
    db.add(owner)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_config.id, user_id=owner.id, role="owner", status="active"))

    reservation = Reservation(
        confirmation_code="NS-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=180.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    result = detect_no_shows(
        db,
        hotel_id=hotel_config.id,
        now=datetime(2026, 4, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert result.marked == 1
    db.refresh(reservation)
    assert reservation.status == ReservationStatusEnum.NO_SHOW
    assert reservation.outcome == ReservationOutcomeEnum.NO_SHOW
    assert reservation.no_show_policy_applied == ReservationNoShowPolicyAppliedEnum.FULL_CHARGE
    assert reservation.no_show_confirmed_at is not None
    assert db.query(HotelAuditEvent).filter(HotelAuditEvent.action_code == "analytics.reservation.no_show_marked").count() == 1


def test_refresh_fact_reservation_daily_materializes_rows(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Acme SRL",
        display_name="Acme",
        tax_id="30-12345678-9",
        country_code="AR",
    )
    db.add(company)
    db.flush()
    sample_categories[0].variable_cost_per_night = 12.50

    reservation = Reservation(
        confirmation_code="FACT-RES-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        company_id=company.id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
        total_amount=100.0,
        subtotal_amount=80.0,
        tax_amount=15.0,
        fee_amount=5.0,
        commission_amount=10.0,
        net_amount=90.0,
        amount_paid=100.0,
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        channel_code=ReservationChannelCodeEnum.BOOKING,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    result = refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
    )

    assert result.inserted == 2
    rows = db.query(FactReservationDaily).order_by(FactReservationDaily.stay_date.asc()).all()
    assert len(rows) == 2
    assert {row.row_kind.value for row in rows} == {"occupied"}
    assert all(row.guest_segment.value == "business" for row in rows)
    assert all(row.channel_code.value == "booking" for row in rows)
    assert sum(float(row.revenue_gross_ars) for row in rows) == pytest.approx(100.0)
    assert sum(float(row.variable_cost_ars) for row in rows) == pytest.approx(25.0)
    assert sum(float(row.margin_operating_ars) for row in rows) == pytest.approx(65.0)


def test_refresh_fact_room_occupancy_daily_handles_blocking_events(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    reservation = Reservation(
        confirmation_code="FACT-ROOM-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=90.0,
        amount_paid=100.0,
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=2,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    db.add(
        User(
            email="audit@example.com",
            password_hash="x",
            role="owner",
            is_verified=True,
            is_active=True,
        )
    )
    db.flush()
    db.add(
        RoomStateEvent(
            hotel_id=hotel_config.id,
            room_id=sample_rooms[0].id,
            event_type=RoomStateEventTypeEnum.MAINTENANCE,
            reason_code=RoomStateEventReasonCodeEnum.INSPECTION,
            reason_note="Inspection programada",
            started_at=datetime(2026, 4, 2, 0, 0, tzinfo=timezone.utc),
            ended_at=datetime(2026, 4, 3, 0, 0, tzinfo=timezone.utc),
            created_by_user_id=1,
        )
    )
    db.flush()

    result = refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 2),
    )

    assert result.inserted == len(sample_rooms) * 2
    rows = (
        db.query(FactRoomOccupancyDaily)
        .filter(FactRoomOccupancyDaily.room_id == sample_rooms[0].id)
        .order_by(FactRoomOccupancyDaily.stay_date.asc())
        .all()
    )
    assert len(rows) == 2
    assert rows[0].stay_date == date(2026, 4, 1)
    assert rows[0].status_at_night.value == "occupied"
    assert rows[0].is_occupied is True
    assert float(rows[0].revenue_net_ars) == pytest.approx(45.0)
    assert rows[1].stay_date == date(2026, 4, 2)
    assert rows[1].status_at_night.value == "maintenance"
    assert rows[1].is_occupied is False
    assert float(rows[1].revenue_net_ars) == pytest.approx(0.0)


def test_celery_tasks_are_registered():
    from app.tasks.celery_app import celery_app

    assert "analytics.detect_no_shows" in celery_app.tasks


# ── Write-time incremental fact touch (no read/self-heal involved) ──
#
# These reproduce the owner's actual ask: fact rows must reflect a new
# reservation/edit/cancellation *immediately*, without waiting for anyone to
# hit an /api/analytics/* endpoint first. None of these tests call
# _ensure_facts_materialized, refresh_fact_*, or any analytics builder --
# they only call the reservation-mutating service functions and then read
# FactReservationDaily/FactRoomOccupancyDaily directly.

from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.reservation_service import (
    create_reservation,
    mark_reservation_no_show,
    transition_reservation_status,
    update_reservation_fields,
)


def test_create_reservation_materializes_fact_rows_immediately(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    assert db.query(FactReservationDaily).count() == 0

    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data, hotel_id=hotel_config.id)

    rows = (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.reservation_id == reservation.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    assert [row.stay_date for row in rows] == [date(2026, 6, 1), date(2026, 6, 2)]
    assert all(row.row_kind.value == "occupied" for row in rows)
    assert sum(float(row.revenue_gross_ars) for row in rows) == pytest.approx(float(reservation.total_amount))


def test_cancel_reservation_removes_fact_rows_immediately(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data, hotel_id=hotel_config.id)
    assert db.query(FactReservationDaily).filter(FactReservationDaily.reservation_id == reservation.id).count() == 2

    transition_reservation_status(db, reservation, ReservationStatusEnum.CANCELLED, hotel_config.id, reason_code="cancelled_by_user")

    # refresh_fact_reservation_daily excludes CANCELLED reservations entirely
    # -- a cancellation must zero out its revenue in the fact table right
    # away, not just on the next Analytics read.
    assert db.query(FactReservationDaily).filter(FactReservationDaily.reservation_id == reservation.id).count() == 0


def test_update_reservation_fields_date_move_touches_old_and_new_windows(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data, hotel_id=hotel_config.id)
    assert {
        row.stay_date
        for row in db.query(FactReservationDaily).filter(FactReservationDaily.reservation_id == reservation.id).all()
    } == {date(2026, 6, 1), date(2026, 6, 2)}

    update_reservation_fields(
        db,
        reservation,
        ReservationUpdate(check_in_date=date(2026, 7, 10), check_out_date=date(2026, 7, 12)),
        hotel_id=hotel_config.id,
        client_version=reservation.version,
    )

    # Old June window must no longer carry this reservation's revenue...
    assert db.query(FactReservationDaily).filter(
        FactReservationDaily.reservation_id == reservation.id,
        FactReservationDaily.stay_date < date(2026, 7, 1),
    ).count() == 0
    # ...and the new July window must already have it, without any read.
    assert {
        row.stay_date
        for row in db.query(FactReservationDaily).filter(FactReservationDaily.reservation_id == reservation.id).all()
    } == {date(2026, 7, 10), date(2026, 7, 11)}


def test_mark_reservation_no_show_flips_fact_row_kind_immediately(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data, hotel_id=hotel_config.id)
    reservation.status = ReservationStatusEnum.FULLY_PAID  # satisfies no_show precondition path used in prod
    db.flush()

    mark_reservation_no_show(db, reservation, hotel_id=hotel_config.id, client_version=reservation.version)

    rows = db.query(FactReservationDaily).filter(FactReservationDaily.reservation_id == reservation.id).all()
    assert len(rows) == 2
    assert all(row.row_kind.value == "no_show_chargeable" for row in rows)


def test_move_reservation_room_moves_occupancy_fact_rows_immediately(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    from app.services.reservation_operations_service import move_reservation_room

    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data, hotel_id=hotel_config.id)
    old_room_id = sample_rooms[0].id
    new_room_id = sample_rooms[1].id
    assert db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.room_id == old_room_id, FactRoomOccupancyDaily.is_occupied.is_(True)
    ).count() == 2

    move_reservation_room(
        db,
        reservation=reservation,
        to_room_id=new_room_id,
        hotel_id=hotel_config.id,
        reason_code="guest_request",
        price_action="keep",
    )

    assert db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.room_id == old_room_id, FactRoomOccupancyDaily.is_occupied.is_(True)
    ).count() == 0
    assert db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.room_id == new_room_id, FactRoomOccupancyDaily.is_occupied.is_(True)
    ).count() == 2
