from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from app.config import Settings
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
from app.services import analytics_service
from app.services.analytics_service import build_home_payload


def test_sync_fact_refresh_defaults_to_enabled():
    assert Settings(_env_file=None).SYNC_FACT_REFRESH_ENABLED is True


def test_inline_fact_refresh_can_be_disabled(monkeypatch, db):
    monkeypatch.setattr(
        analytics_service,
        "get_settings",
        lambda: SimpleNamespace(
            SYNC_FACT_REFRESH_ENABLED=False,
            SYNC_FACT_REFRESH_MAX_DAYS=3,
        ),
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("inline fact refresh must be disabled")

    monkeypatch.setattr(analytics_service, "refresh_fact_reservation_daily", fail_if_called)
    monkeypatch.setattr(analytics_service, "refresh_fact_room_occupancy_daily", fail_if_called)

    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=1,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 10),
    )


def test_inline_fact_refresh_is_bounded_and_logged(monkeypatch, caplog, db):
    monkeypatch.setattr(
        analytics_service,
        "get_settings",
        lambda: SimpleNamespace(
            SYNC_FACT_REFRESH_ENABLED=True,
            SYNC_FACT_REFRESH_MAX_DAYS=3,
        ),
    )
    refresh_ranges = []

    def record_refresh(*_args, date_from, date_to, **_kwargs):
        refresh_ranges.append((date_from, date_to))

    monkeypatch.setattr(analytics_service, "refresh_fact_reservation_daily", record_refresh)
    monkeypatch.setattr(analytics_service, "refresh_fact_room_occupancy_daily", record_refresh)

    with caplog.at_level("WARNING", logger="app.services.analytics_service"):
        analytics_service._ensure_facts_materialized(
            db,
            hotel_id=1,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 10),
        )

    assert refresh_ranges == [
        (date(2026, 1, 8), date(2026, 1, 10)),
        (date(2026, 1, 8), date(2026, 1, 10)),
    ]
    assert sum(record.message == "analytics.sync_fact_refresh.inline" for record in caplog.records) == 1


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
    assert reservation.no_show_policy_applied == ReservationNoShowPolicyAppliedEnum.NONE
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

    statements: list[str] = []
    engine = db.get_bind()

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = refresh_fact_reservation_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 2),
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert sum("room_categories.id in" in statement.lower() for statement in statements) == 1
    assert sum("companies.id in" in statement.lower() for statement in statements) == 1

    assert result.inserted == 2
    rows = db.query(FactReservationDaily).order_by(FactReservationDaily.stay_date.asc()).all()
    assert len(rows) == 2
    assert {row.row_kind.value for row in rows} == {"occupied"}
    assert all(row.guest_segment.value == "business" for row in rows)
    assert all(row.channel_code.value == "booking" for row in rows)
    assert sum(float(row.revenue_gross_ars) for row in rows) == pytest.approx(100.0)
    assert sum(float(row.variable_cost_ars) for row in rows) == pytest.approx(25.0)
    assert sum(float(row.margin_operating_ars) for row in rows) == pytest.approx(65.0)


def test_partial_refresh_allocates_money_across_the_full_stay_idempotently(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    sample_categories[0].variable_cost_per_night = Decimal("5.13")
    reservation = Reservation(
        confirmation_code="FACT-PARTIAL-WINDOW",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 30),
        check_out_date=date(2026, 5, 5),
        total_amount=Decimal("100.01"),
        subtotal_amount=Decimal("90.01"),
        tax_amount=Decimal("10.00"),
        net_amount=Decimal("90.01"),
        amount_paid=Decimal("100.01"),
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

    # Refresh a middle slice first, then the earlier and later slices. Each
    # row must keep the nightly allocation from the complete five-night stay.
    for date_from, date_to in (
        (date(2026, 5, 1), date(2026, 5, 2)),
        (date(2026, 4, 30), date(2026, 4, 30)),
        (date(2026, 5, 3), date(2026, 5, 4)),
    ):
        refresh_fact_reservation_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date_from,
            date_to=date_to,
        )

    rows = (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.hotel_id == hotel_config.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    assert [row.stay_date for row in rows] == [
        date(2026, 4, 30),
        date(2026, 5, 1),
        date(2026, 5, 2),
        date(2026, 5, 3),
        date(2026, 5, 4),
    ]
    assert sum((Decimal(str(row.revenue_gross_ars)) for row in rows), Decimal("0")) == Decimal("100.01")
    assert sum((Decimal(str(row.revenue_net_ars)) for row in rows), Decimal("0")) == Decimal("90.01")
    assert all(Decimal(str(row.revenue_gross_ars)) == Decimal("20.00") for row in rows[1:])
    assert Decimal(str(rows[0].revenue_gross_ars)) == Decimal("20.01")

    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 2),
    )
    repeated_rows = (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.hotel_id == hotel_config.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    assert len(repeated_rows) == 5
    assert sum((Decimal(str(row.revenue_gross_ars)) for row in repeated_rows), Decimal("0")) == Decimal("100.01")


def test_partial_cross_month_refresh_home_metrics_use_only_selected_local_nights(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = Reservation(
        confirmation_code="FACT-PARTIAL-HOME-METRICS",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 30),
        check_out_date=date(2026, 5, 3),
        total_amount=Decimal("100.01"),
        subtotal_amount=Decimal("90.01"),
        net_amount=Decimal("90.01"),
        amount_paid=Decimal("100.01"),
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

    # Rebuild only the May 1 local night for an Apr 30–May 3 stay. The
    # selected night must keep its full-stay nightly allocation, and all
    # home KPIs must use that same local-night window.
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 1),
    )
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 1),
    )

    payload = build_home_payload(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 1),
        compare_previous=False,
        compare_yoy=False,
        currency_display="ARS",
    )
    cards = {card["card_code"]: card for card in payload["data"]["cards"]}

    assert payload["date_from"] == date(2026, 5, 1)
    assert payload["date_to"] == date(2026, 5, 1)
    assert Decimal(cards["home_revenue_gross"]["value_ars"]) == Decimal("33.34")
    assert Decimal(cards["home_revenue_net"]["value_ars"]) == Decimal("30.00")
    assert Decimal(cards["home_adr"]["value_ars"]) == Decimal("30.00")
    assert Decimal(cards["home_revpar"]["value_ars"]) == Decimal("0.79")
    assert cards["home_occupancy"]["value_pct"] == pytest.approx(100 / len(sample_rooms), abs=0.01)
    assert cards["home_physical_room_nights"]["value_count"] == len(sample_rooms)


def test_analytics_read_rebuilds_legacy_one_to_one_currency_facts(
    db, hotel_config, sample_guest, sample_categories, sample_rooms, monkeypatch
):
    reservation = Reservation(
        confirmation_code="FX-LEGACY-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 2),
        total_amount=100.0,
        subtotal_amount=100.0,
        net_amount=90.0,
        amount_paid=0.0,
        currency_code="ARS",
        fx_rate_snapshot=None,
        status=ReservationStatusEnum.PENDING,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.flush()
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 1),
    )
    fact = db.query(FactReservationDaily).filter_by(reservation_id=reservation.id).one()
    assert float(fact.revenue_net_usd) == pytest.approx(0.0)

    # Simulate a materialized fact written by the previous 1:1 fallback.
    fact.revenue_net_usd = fact.revenue_net_ars
    db.flush()
    db.expunge(fact)
    monkeypatch.setattr(db, "commit", lambda: db.flush())
    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 1),
    )

    refreshed = db.query(FactReservationDaily).filter_by(reservation_id=reservation.id).one()
    assert float(refreshed.revenue_net_ars) == pytest.approx(90.0)
    assert float(refreshed.revenue_net_usd) == pytest.approx(0.0)


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

    statements: list[str] = []
    engine = db.get_bind()

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        result = refresh_fact_room_occupancy_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 2),
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert sum("room_categories.id in" in statement.lower() for statement in statements) == 1
    assert sum("companies.id in" in statement.lower() for statement in statements) == 0

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
        client_version=reservation.version,
        actor_role="owner",
        reason_code="guest_request",
        price_action="keep",
    )

    assert db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.room_id == old_room_id, FactRoomOccupancyDaily.is_occupied.is_(True)
    ).count() == 0
    assert db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.room_id == new_room_id, FactRoomOccupancyDaily.is_occupied.is_(True)
    ).count() == 2
