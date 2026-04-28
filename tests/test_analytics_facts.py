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
    assert "analytics.refresh_fact_reservation_daily" in celery_app.tasks
    assert "analytics.refresh_fact_room_occupancy_daily" in celery_app.tasks
