from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
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
from app.models.guest import Guest
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
    touch_reservation_fact_window,
)
from app.services import analytics_service
from app.services.analytics_service import build_home_payload


def test_sync_fact_refresh_defaults_to_enabled():
    settings = Settings(_env_file=None)
    assert settings.SYNC_FACT_REFRESH_ENABLED is True
    assert settings.SYNC_FACT_REFRESH_STALE_AFTER_SECONDS == 900


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


def test_inline_fact_refresh_is_bounded_and_logged(monkeypatch, caplog, db, hotel_config, sample_rooms):
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
            hotel_id=hotel_config.id,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 10),
        )

    assert refresh_ranges == [
        (date(2026, 1, 8), date(2026, 1, 10)),
        (date(2026, 1, 8), date(2026, 1, 10)),
    ]
    assert sum(record.message == "analytics.sync_fact_refresh.inline" for record in caplog.records) == 1


def _make_refresh_test_reservation(hotel_config, sample_guest, sample_categories, sample_rooms):
    return Reservation(
        confirmation_code="ANALYTICS-REFRESH-001",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
        total_amount=200.0,
        subtotal_amount=180.0,
        tax_amount=20.0,
        fee_amount=0.0,
        commission_amount=0.0,
        net_amount=180.0,
        amount_paid=200.0,
        deposit_amount=0.0,
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


def _enable_bounded_fact_refresh(monkeypatch):
    monkeypatch.setattr(
        analytics_service,
        "get_settings",
        lambda: SimpleNamespace(
            SYNC_FACT_REFRESH_ENABLED=True,
            SYNC_FACT_REFRESH_MAX_DAYS=31,
            SYNC_FACT_REFRESH_STALE_AFTER_SECONDS=900,
        ),
    )


def test_stale_fact_window_is_refreshed_within_31_day_cap(
    monkeypatch, db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    _enable_bounded_fact_refresh(monkeypatch)
    db.add(_make_refresh_test_reservation(hotel_config, sample_guest, sample_categories, sample_rooms))
    db.flush()
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3))
    refresh_fact_room_occupancy_daily(db, hotel_id=hotel_config.id, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3))

    stale_since = datetime.now(timezone.utc) - pytest.importorskip("datetime").timedelta(hours=2)
    db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == hotel_config.id).update(
        {FactReservationDaily.updated_at: stale_since}
    )
    db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).update(
        {FactRoomOccupancyDaily.updated_at: stale_since}
    )
    db.commit()

    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 3),
    )

    reservation_as_of = min(
        analytics_service._ensure_utc(row.updated_at)
        for row in db.query(FactReservationDaily.updated_at).filter(FactReservationDaily.hotel_id == hotel_config.id).all()
    )
    occupancy_as_of = min(
        analytics_service._ensure_utc(row.updated_at)
        for row in db.query(FactRoomOccupancyDaily.updated_at).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).all()
    )
    assert reservation_as_of > stale_since
    assert occupancy_as_of > stale_since


def test_partial_fact_window_refreshes_both_tables(
    monkeypatch, db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    _enable_bounded_fact_refresh(monkeypatch)
    db.add(_make_refresh_test_reservation(hotel_config, sample_guest, sample_categories, sample_rooms))
    db.flush()
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3))
    refresh_fact_room_occupancy_daily(db, hotel_id=hotel_config.id, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3))

    stale_since = datetime.now(timezone.utc) - pytest.importorskip("datetime").timedelta(hours=2)
    db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == hotel_config.id).update(
        {FactReservationDaily.updated_at: stale_since}
    )
    db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).delete()
    db.commit()

    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 3),
    )

    reservation_rows = db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == hotel_config.id).all()
    occupancy_rows = db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).all()
    assert len(reservation_rows) == 2
    assert min(analytics_service._ensure_utc(row.updated_at) for row in reservation_rows) > stale_since
    assert len(occupancy_rows) == len(sample_rooms) * 3


def test_targeted_touch_keeps_unaffected_age_visible_and_read_repairs_ttl_and_fx(
    monkeypatch,
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    _enable_bounded_fact_refresh(monkeypatch)
    date_from = date(2026, 4, 1)
    date_to = date(2026, 4, 3)
    target = _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-TOUCH-FRESHNESS-TARGET",
        check_in_date=date_from,
        check_out_date=date_to,
    )
    unaffected = _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[1].id,
        confirmation_code="FACT-TOUCH-FRESHNESS-OTHER",
        check_in_date=date_from,
        check_out_date=date_to,
    )
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )

    stale_since = datetime.now(timezone.utc) - timedelta(hours=2)
    db.query(FactReservationDaily).filter(FactReservationDaily.hotel_id == hotel_config.id).update(
        {FactReservationDaily.updated_at: stale_since},
        synchronize_session=False,
    )
    db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).update(
        {FactRoomOccupancyDaily.updated_at: stale_since},
        synchronize_session=False,
    )
    db.commit()

    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=target.id,
    )
    unaffected_fact = (
        db.query(FactReservationDaily)
        .filter_by(reservation_id=unaffected.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .first()
    )
    unaffected_room_fact = (
        db.query(FactRoomOccupancyDaily)
        .filter_by(room_id=sample_rooms[1].id, stay_date=date_from)
        .one()
    )
    assert analytics_service._ensure_utc(unaffected_fact.updated_at) == stale_since
    assert analytics_service._ensure_utc(unaffected_room_fact.updated_at) == stale_since
    db.expunge(unaffected_fact)
    db.expunge(unaffected_room_fact)

    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    refreshed_reservation_timestamps = [
        analytics_service._ensure_utc(row.updated_at)
        for row in db.query(FactReservationDaily.updated_at)
        .filter(FactReservationDaily.hotel_id == hotel_config.id)
        .all()
    ]
    refreshed_room_timestamps = [
        analytics_service._ensure_utc(row.updated_at)
        for row in db.query(FactRoomOccupancyDaily.updated_at)
        .filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id)
        .all()
    ]
    assert refreshed_reservation_timestamps
    assert refreshed_room_timestamps
    assert min(refreshed_reservation_timestamps) > stale_since
    assert min(refreshed_room_timestamps) > stale_since

    # A fresh timestamp must not hide the independent legacy-FX repair signal.
    legacy_fact = (
        db.query(FactReservationDaily)
        .filter_by(reservation_id=unaffected.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .first()
    )
    legacy_fact.revenue_net_usd = legacy_fact.revenue_net_ars
    legacy_fact.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.expunge(legacy_fact)
    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    db.expire_all()
    repaired_fact = (
        db.query(FactReservationDaily)
        .filter_by(reservation_id=unaffected.id, stay_date=date_from)
        .one()
    )
    assert repaired_fact.revenue_net_usd == Decimal("0.00")


def test_wide_fact_window_does_not_refresh_or_mask_stale_metadata(
    monkeypatch, db, hotel_config, sample_rooms
):
    _enable_bounded_fact_refresh(monkeypatch)
    date_from = date(2026, 4, 1)
    date_to = date(2026, 5, 2)  # 32 days, above the hard refresh cap.
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    refresh_fact_room_occupancy_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    stale_since = datetime.now(timezone.utc) - pytest.importorskip("datetime").timedelta(hours=2)
    db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id).update(
        {FactRoomOccupancyDaily.updated_at: stale_since}
    )
    db.commit()

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("wide analytics windows must retain honest stale metadata without a read-time rebuild")

    monkeypatch.setattr(analytics_service, "refresh_fact_reservation_daily", fail_if_called)
    monkeypatch.setattr(analytics_service, "refresh_fact_room_occupancy_daily", fail_if_called)
    analytics_service._ensure_facts_materialized(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )

    remaining_timestamps = [
        analytics_service._ensure_utc(row.updated_at)
        for row in db.query(FactRoomOccupancyDaily.updated_at)
        .filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id)
        .all()
    ]
    assert remaining_timestamps
    assert min(remaining_timestamps) == stale_since


def test_fact_refresh_guard_is_nonblocking_per_hotel(db):
    with analytics_service._analytics_fact_refresh_guard(db, hotel_id=1) as first:
        assert first is True
        with analytics_service._analytics_fact_refresh_guard(db, hotel_id=1) as second:
            assert second is False


def test_missing_fact_window_skips_refresh_while_another_request_holds_lock(
    monkeypatch, db, hotel_config, sample_rooms
):
    monkeypatch.setattr(
        analytics_service,
        "get_settings",
        lambda: SimpleNamespace(
            SYNC_FACT_REFRESH_ENABLED=True,
            SYNC_FACT_REFRESH_MAX_DAYS=31,
            SYNC_FACT_REFRESH_STALE_AFTER_SECONDS=900,
        ),
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("a concurrent request already owns this hotel's refresh guard")

    monkeypatch.setattr(analytics_service, "refresh_fact_reservation_daily", fail_if_called)
    monkeypatch.setattr(analytics_service, "refresh_fact_room_occupancy_daily", fail_if_called)

    with analytics_service._analytics_fact_refresh_guard(db, hotel_config.id) as acquired:
        assert acquired is True
        analytics_service._ensure_facts_materialized(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 3),
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


def test_reservation_update_fact_field_classification_is_exhaustive():
    from app.services.reservation_service import _ANALYTICS_FACT_AFFECTING_RESERVATION_UPDATE_FIELDS

    metadata_or_control_fields = {
        "paid_total_change_reason",
        "num_adults",
        "num_children",
        "notes",
        "arrival_time_hint",
        "reservation_comment",
        "mobility_restriction",
        "client_version",
        "restriction_override",
    }

    assert set(ReservationUpdate.model_fields) == (
        _ANALYTICS_FACT_AFFECTING_RESERVATION_UPDATE_FIELDS | metadata_or_control_fields
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


@pytest.mark.parametrize(
    "update_fields",
    [
        {"notes": "Updated operator note"},
        {"arrival_time_hint": "18:30"},
        {"reservation_comment": "Guest requested a quiet room"},
        {"mobility_restriction": True},
        {"num_adults": 2},
        {"num_children": 1},
    ],
)
def test_metadata_only_reservation_update_skips_analytical_fact_refresh(
    db, hotel_config, sample_guest, sample_categories, sample_rooms, monkeypatch, update_fields
):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 3),
        ),
        hotel_id=hotel_config.id,
    )
    version_before_update = reservation.version
    facts_before_update = db.query(FactReservationDaily).filter(
        FactReservationDaily.reservation_id == reservation.id
    ).count()

    def fail_if_refreshed(*_args, **_kwargs):
        pytest.fail("metadata-only reservation update must not rebuild analytical facts")

    monkeypatch.setattr("app.services.reservation_service._touch_facts", fail_if_refreshed)

    update_reservation_fields(
        db,
        reservation,
        ReservationUpdate(**update_fields),
        hotel_id=hotel_config.id,
        client_version=version_before_update,
    )

    assert reservation.version == version_before_update + 1
    assert db.query(FactReservationDaily).filter(
        FactReservationDaily.reservation_id == reservation.id
    ).count() == facts_before_update == 2


def test_update_reservation_total_refreshes_analytical_revenue_immediately(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 3),
        ),
        hotel_id=hotel_config.id,
    )
    corrected_total = Decimal(str(reservation.total_amount)).quantize(Decimal("0.01")) + Decimal("50.00")

    update_reservation_fields(
        db,
        reservation,
        ReservationUpdate(
            total_amount=corrected_total,
            paid_total_change_reason="Corrected negotiated reservation total",
        ),
        hotel_id=hotel_config.id,
        client_version=reservation.version,
    )

    facts = db.query(FactReservationDaily).filter(
        FactReservationDaily.reservation_id == reservation.id
    ).all()
    recognized_total = sum((Decimal(str(row.revenue_gross_ars)) for row in facts), Decimal("0"))
    assert len(facts) == 2
    assert recognized_total == corrected_total


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


@pytest.mark.parametrize("change_path", ["edit", "room_move"])
def test_room_change_repairs_missing_prior_room_facts_without_rebuilding_other_rooms(
    change_path,
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    monkeypatch,
):
    from app.services import analytics_facts
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
    unaffected_room_id = sample_rooms[2].id
    date_from, date_to = reservation.check_in_date, reservation.check_out_date

    # Seed complete room facts, then simulate a missing prior-room partition
    # while preserving a known-unaffected room for a no-rebuild assertion.
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    unaffected_before = [
        (row.stay_date, row.status_at_night, row.is_occupied, row.reservation_id)
        for row in (
            db.query(FactRoomOccupancyDaily)
            .filter(
                FactRoomOccupancyDaily.hotel_id == hotel_config.id,
                FactRoomOccupancyDaily.room_id == unaffected_room_id,
            )
            .order_by(FactRoomOccupancyDaily.stay_date)
            .all()
        )
    ]
    assert len(unaffected_before) == 3

    db.query(FactRoomOccupancyDaily).filter(
        FactRoomOccupancyDaily.hotel_id == hotel_config.id,
        FactRoomOccupancyDaily.room_id == old_room_id,
        FactRoomOccupancyDaily.stay_date >= date_from,
        FactRoomOccupancyDaily.stay_date <= date_to,
    ).delete(synchronize_session=False)
    db.flush()

    original_room_refresh = analytics_facts.refresh_fact_room_occupancy_daily
    observed_refreshes = []

    def record_room_refresh(*args, **kwargs):
        result = original_room_refresh(*args, **kwargs)
        observed_refreshes.append((kwargs.get("room_ids"), result.inserted))
        return result

    monkeypatch.setattr(analytics_facts, "refresh_fact_room_occupancy_daily", record_room_refresh)
    if change_path == "edit":
        update_reservation_fields(
            db,
            reservation,
            ReservationUpdate(room_id=new_room_id),
            hotel_id=hotel_config.id,
            client_version=reservation.version,
        )
    else:
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

    assert observed_refreshes == [({old_room_id, new_room_id}, 6)]

    old_room_rows = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_config.id,
            FactRoomOccupancyDaily.room_id == old_room_id,
            FactRoomOccupancyDaily.stay_date >= date_from,
            FactRoomOccupancyDaily.stay_date <= date_to,
        )
        .order_by(FactRoomOccupancyDaily.stay_date)
        .all()
    )
    assert len(old_room_rows) == 3
    assert all(not row.is_occupied and row.reservation_id is None for row in old_room_rows)
    assert all(row.status_at_night.value == "available" for row in old_room_rows)

    new_room_occupied_rows = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_config.id,
            FactRoomOccupancyDaily.room_id == new_room_id,
            FactRoomOccupancyDaily.is_occupied.is_(True),
        )
        .order_by(FactRoomOccupancyDaily.stay_date)
        .all()
    )
    assert len(new_room_occupied_rows) == 2
    assert all(row.reservation_id == reservation.id for row in new_room_occupied_rows)

    unaffected_after = [
        (row.stay_date, row.status_at_night, row.is_occupied, row.reservation_id)
        for row in (
            db.query(FactRoomOccupancyDaily)
            .filter(
                FactRoomOccupancyDaily.hotel_id == hotel_config.id,
                FactRoomOccupancyDaily.room_id == unaffected_room_id,
            )
            .order_by(FactRoomOccupancyDaily.stay_date)
            .all()
        )
    ]
    assert unaffected_after == unaffected_before


def _make_fact_refresh_reservation(
    db,
    *,
    hotel_id,
    guest_id,
    category_id,
    room_id,
    confirmation_code,
    check_in_date=date(2026, 6, 1),
    check_out_date=date(2026, 6, 3),
):
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        total_amount=Decimal("100.00"),
        subtotal_amount=Decimal("100.00"),
        net_amount=Decimal("100.00"),
        amount_paid=Decimal("0.00"),
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
    return reservation


def _fact_business_snapshot(
    db,
    model,
    *,
    hotel_id,
    date_from,
    date_to,
    room_id=None,
    reservation_id=None,
):
    fields = [
        column.name
        for column in model.__table__.columns
        if column.name not in {"id", "created_at", "updated_at"}
    ]
    query = db.query(*(getattr(model, field) for field in fields)).filter(
        model.hotel_id == hotel_id,
        model.stay_date >= date_from,
        model.stay_date <= date_to,
    )
    if room_id is not None and hasattr(model, "room_id"):
        query = query.filter(model.room_id == room_id)
    if reservation_id is not None and hasattr(model, "reservation_id"):
        query = query.filter(model.reservation_id == reservation_id)
    rows = query.all()
    return tuple(sorted((tuple(row) for row in rows), key=repr))


@pytest.mark.parametrize(
    ("scenario", "expected_room_indexes"),
    [
        ("create", {0}),
        ("cancel", {0}),
        ("date_move", {0}),
        ("room_move", {0, 2}),
        ("unassigned", {0}),
        ("no_show", {0}),
        ("soft_delete", {0}),
    ],
)
def test_targeted_reservation_fact_touch_matches_full_refresh(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    monkeypatch,
    scenario,
    expected_room_indexes,
):
    date_from = date(2026, 6, 1)
    date_to = date(2026, 6, 4)
    _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[1].id,
        confirmation_code=f"FACT-TOUCH-STABLE-{scenario}",
        check_in_date=date_from,
        check_out_date=date(2026, 6, 5),
    )

    target = None
    if scenario != "create":
        target = _make_fact_refresh_reservation(
            db,
            hotel_id=hotel_config.id,
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            confirmation_code=f"FACT-TOUCH-TARGET-{scenario}",
        )

    # Materialize the pre-change state so room moves and removals have stale
    # occupancy rows from which the targeted refresh must discover old rooms.
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    refresh_fact_room_occupancy_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)

    if scenario == "create":
        target = _make_fact_refresh_reservation(
            db,
            hotel_id=hotel_config.id,
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            confirmation_code="FACT-TOUCH-TARGET-create",
        )
    elif scenario == "cancel":
        target.status = ReservationStatusEnum.CANCELLED
        target.outcome = ReservationOutcomeEnum.CANCELLED
    elif scenario == "date_move":
        target.check_in_date = date(2026, 6, 3)
        target.check_out_date = date(2026, 6, 5)
    elif scenario == "room_move":
        target.room_id = sample_rooms[2].id
    elif scenario == "unassigned":
        # The previously materialized occupancy rows are now the only source
        # from which the targeted refresh can discover the old room.
        target.room_id = None
    elif scenario == "no_show":
        target.status = ReservationStatusEnum.NO_SHOW
        target.outcome = ReservationOutcomeEnum.NO_SHOW
        target.no_show_confirmed_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    elif scenario == "soft_delete":
        target.deleted_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    db.flush()

    import app.services.analytics_facts as analytics_facts

    original_room_refresh = analytics_facts.refresh_fact_room_occupancy_daily
    observed_room_refreshes = []

    def record_room_refresh(*args, **kwargs):
        result = original_room_refresh(*args, **kwargs)
        observed_room_refreshes.append((kwargs.get("room_ids"), result.inserted))
        return result

    monkeypatch.setattr(analytics_facts, "refresh_fact_room_occupancy_daily", record_room_refresh)
    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=target.id,
    )

    assert len(observed_room_refreshes) == 1
    affected_room_ids, inserted_room_rows = observed_room_refreshes[0]
    assert affected_room_ids == {sample_rooms[index].id for index in expected_room_indexes}
    assert inserted_room_rows == len(expected_room_indexes) * ((date_to - date_from).days + 1)

    targeted_reservation_snapshot = _fact_business_snapshot(
        db,
        FactReservationDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    targeted_occupancy_snapshot = _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )

    # A legacy full-window refresh is the correctness oracle for the optimized
    # write-time path; compare business columns, excluding surrogate ids/times.
    refresh_fact_reservation_daily(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    original_room_refresh(db, hotel_id=hotel_config.id, date_from=date_from, date_to=date_to)
    assert targeted_reservation_snapshot == _fact_business_snapshot(
        db,
        FactReservationDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    assert targeted_occupancy_snapshot == _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )


def test_targeted_refresh_preserves_facts_outside_union_window(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    target = _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-TOUCH-OUTSIDE-TARGET",
        check_in_date=date(2026, 6, 3),
        check_out_date=date(2026, 6, 5),
    )
    _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[1].id,
        confirmation_code="FACT-TOUCH-OUTSIDE-STABLE",
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 11),
    )
    outer_from = date(2026, 6, 1)
    outer_to = date(2026, 6, 10)
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=outer_from,
        date_to=outer_to,
    )
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=outer_from,
        date_to=outer_to,
    )

    old_check_in = target.check_in_date
    old_check_out = target.check_out_date
    target.check_in_date = date(2026, 6, 6)
    target.check_out_date = date(2026, 6, 8)
    db.flush()

    left_range = (outer_from, old_check_in - timedelta(days=1))
    right_range = (target.check_out_date + timedelta(days=1), outer_to)
    outside_before = tuple(
        (
            _fact_business_snapshot(
                db,
                FactReservationDaily,
                hotel_id=hotel_config.id,
                date_from=start,
                date_to=end,
            ),
            _fact_business_snapshot(
                db,
                FactRoomOccupancyDaily,
                hotel_id=hotel_config.id,
                date_from=start,
                date_to=end,
            ),
        )
        for start, end in (left_range, right_range)
    )

    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=old_check_in,
        date_to=max(old_check_out, target.check_out_date),
        reservation_id=target.id,
    )

    outside_after = tuple(
        (
            _fact_business_snapshot(
                db,
                FactReservationDaily,
                hotel_id=hotel_config.id,
                date_from=start,
                date_to=end,
            ),
            _fact_business_snapshot(
                db,
                FactRoomOccupancyDaily,
                hotel_id=hotel_config.id,
                date_from=start,
                date_to=end,
            ),
        )
        for start, end in (left_range, right_range)
    )
    assert outside_after == outside_before


def test_targeted_room_refresh_reapplies_events_only_for_affected_rooms(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    monkeypatch,
):
    import app.services.analytics_facts as analytics_facts

    date_from = date(2026, 6, 1)
    date_to = date(2026, 6, 3)
    target = _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-TOUCH-ROOM-EVENTS",
        check_in_date=date_from,
        check_out_date=date(2026, 6, 4),
    )
    event_actor = User(
        email="room-event-owner@example.com",
        password_hash="x",
        role="owner",
        is_verified=True,
        is_active=True,
    )
    db.add(event_actor)
    db.flush()
    event_start = datetime(2026, 6, 2, 0, 0, tzinfo=timezone.utc)
    event_end = datetime(2026, 6, 3, 0, 0, tzinfo=timezone.utc)
    db.add_all(
        [
            RoomStateEvent(
                hotel_id=hotel_config.id,
                room_id=sample_rooms[0].id,
                event_type=RoomStateEventTypeEnum.MAINTENANCE,
                reason_code=RoomStateEventReasonCodeEnum.INSPECTION,
                started_at=event_start,
                ended_at=event_end,
                created_by_user_id=event_actor.id,
            ),
            RoomStateEvent(
                hotel_id=hotel_config.id,
                room_id=sample_rooms[2].id,
                event_type=RoomStateEventTypeEnum.OUT_OF_SERVICE,
                reason_code=RoomStateEventReasonCodeEnum.PLUMBING,
                started_at=event_start,
                ended_at=event_end,
                created_by_user_id=event_actor.id,
            ),
            RoomStateEvent(
                hotel_id=hotel_config.id,
                room_id=sample_rooms[1].id,
                event_type=RoomStateEventTypeEnum.RENOVATION,
                reason_code=RoomStateEventReasonCodeEnum.OTHER,
                started_at=datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc),
                ended_at=event_start,
                created_by_user_id=event_actor.id,
            ),
        ]
    )
    db.flush()
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    unaffected_before = _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        room_id=sample_rooms[1].id,
    )

    target.room_id = sample_rooms[2].id
    db.flush()
    original_room_refresh = analytics_facts.refresh_fact_room_occupancy_daily
    observed_refreshes = []

    def record_room_refresh(*args, **kwargs):
        result = original_room_refresh(*args, **kwargs)
        observed_refreshes.append((kwargs.get("room_ids"), result.inserted))
        return result

    monkeypatch.setattr(analytics_facts, "refresh_fact_room_occupancy_daily", record_room_refresh)
    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=target.id,
    )

    assert observed_refreshes == [({sample_rooms[0].id, sample_rooms[2].id}, 2 * 3)]
    old_room_event_row = (
        db.query(FactRoomOccupancyDaily)
        .filter_by(room_id=sample_rooms[0].id, stay_date=date(2026, 6, 2))
        .one()
    )
    new_room_event_row = (
        db.query(FactRoomOccupancyDaily)
        .filter_by(room_id=sample_rooms[2].id, stay_date=date(2026, 6, 2))
        .one()
    )
    assert old_room_event_row.status_at_night.value == "maintenance"
    assert old_room_event_row.is_occupied is False
    assert new_room_event_row.status_at_night.value == "out_of_service"
    assert new_room_event_row.is_occupied is False
    assert new_room_event_row.reservation_id == target.id
    assert unaffected_before == _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        room_id=sample_rooms[1].id,
    )

    targeted_reservations = _fact_business_snapshot(
        db,
        FactReservationDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    targeted_occupancy = _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    refresh_fact_reservation_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    original_room_refresh(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    assert targeted_reservations == _fact_business_snapshot(
        db,
        FactReservationDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )
    assert targeted_occupancy == _fact_business_snapshot(
        db,
        FactRoomOccupancyDaily,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
    )


def test_targeted_reservation_fact_touch_isolated_by_hotel(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
    sample_categories_hotel2,
    sample_rooms_hotel2,
):
    from app.services import analytics_facts

    date_from = date(2026, 6, 1)
    date_to = date(2026, 6, 2)
    target = _make_fact_refresh_reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-TOUCH-HOTEL-1",
    )
    guest_hotel2 = Guest(hotel_id=2, first_name="QA", last_name="Hotel Two")
    db.add(guest_hotel2)
    db.flush()
    other_hotel_reservation = _make_fact_refresh_reservation(
        db,
        hotel_id=2,
        guest_id=guest_hotel2.id,
        category_id=sample_categories_hotel2[0].id,
        room_id=sample_rooms_hotel2[0].id,
        confirmation_code="FACT-TOUCH-HOTEL-2",
    )

    for hotel_id in (hotel_config.id, 2):
        refresh_fact_reservation_daily(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)
        refresh_fact_room_occupancy_daily(db, hotel_id=hotel_id, date_from=date_from, date_to=date_to)

    other_hotel_before = (
        _fact_business_snapshot(db, FactReservationDaily, hotel_id=2, date_from=date_from, date_to=date_to),
        _fact_business_snapshot(db, FactRoomOccupancyDaily, hotel_id=2, date_from=date_from, date_to=date_to),
    )
    target.room_id = sample_rooms[2].id
    db.flush()

    analytics_facts.touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=target.id,
    )
    # A mismatched id must be a no-op and must never cross hotel boundaries.
    analytics_facts.touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        date_from=date_from,
        date_to=date_to,
        reservation_id=other_hotel_reservation.id,
        previous_room_id=sample_rooms_hotel2[0].id,
    )

    assert other_hotel_before == (
        _fact_business_snapshot(db, FactReservationDaily, hotel_id=2, date_from=date_from, date_to=date_to),
        _fact_business_snapshot(db, FactRoomOccupancyDaily, hotel_id=2, date_from=date_from, date_to=date_to),
    )
