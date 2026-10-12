from __future__ import annotations

from datetime import date, datetime, timezone

from app.config import get_settings
from app.models.analytics import AnalyticsFactRefreshJob, FactReservationDaily, FactRoomOccupancyDaily
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.services.analytics_fact_refresh_queue import (
    enqueue_analytics_fact_refresh,
    process_analytics_fact_refresh_queue_for_hotel,
)
from app.services.analytics_facts import touch_reservation_fact_window


def _reservation(db, *, hotel_id, guest_id, category_id, room_id, confirmation_code):
    reservation = Reservation(
        confirmation_code=confirmation_code,
        hotel_id=hotel_id,
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
        total_amount=100,
        subtotal_amount=100,
        net_amount=100,
        amount_paid=0,
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


def test_reservation_fact_touch_enqueues_and_coalesces_without_materializing(
    db, hotel_config, sample_guest, sample_categories, sample_rooms, monkeypatch
):
    reservation = _reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-QUEUE-COALESCE",
    )
    monkeypatch.setattr(get_settings(), "ANALYTICS_FACTS_SYNC_ON_WRITE", False)

    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 2),
    )
    touch_reservation_fact_window(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        date_from=date(2026, 5, 31),
        date_to=date(2026, 6, 3),
    )

    jobs = db.query(AnalyticsFactRefreshJob).filter_by(hotel_id=hotel_config.id).all()
    assert len(jobs) == 1
    assert jobs[0].date_from == date(2026, 5, 31)
    assert jobs[0].date_to == date(2026, 6, 3)
    assert jobs[0].attempts == 0
    assert db.query(FactReservationDaily).filter_by(hotel_id=hotel_config.id).count() == 0
    assert db.query(FactRoomOccupancyDaily).filter_by(hotel_id=hotel_config.id).count() == 0


def test_hotel_cron_materializes_and_deletes_only_that_hotels_jobs(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = _reservation(
        db,
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        confirmation_code="FACT-QUEUE-DRAIN",
    )
    db.add(HotelConfiguration(id=2, subscription_active=True))
    db.flush()
    enqueue_analytics_fact_refresh(
        db,
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 2),
    )
    enqueue_analytics_fact_refresh(
        db,
        hotel_id=2,
        reservation_id=90001,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 2),
    )

    result = process_analytics_fact_refresh_queue_for_hotel(
        db,
        hotel_id=hotel_config.id,
        batch_size=10,
    )

    assert result == {"processed": 1, "deferred": 0}
    assert db.query(AnalyticsFactRefreshJob).filter_by(hotel_id=hotel_config.id).count() == 0
    assert db.query(AnalyticsFactRefreshJob).filter_by(hotel_id=2).count() == 1
    assert db.query(FactReservationDaily).filter_by(
        hotel_id=hotel_config.id,
        reservation_id=reservation.id,
    ).count() == 2
    assert db.query(FactRoomOccupancyDaily).filter_by(
        hotel_id=hotel_config.id,
        room_id=sample_rooms[0].id,
    ).count() == 2


def test_failed_fact_refresh_is_retained_with_bounded_backoff(
    db, hotel_config, monkeypatch
):
    import app.services.analytics_facts as analytics_facts

    enqueue_analytics_fact_refresh(
        db,
        hotel_id=hotel_config.id,
        reservation_id=90002,
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 2),
    )

    def fail_refresh(*_args, **_kwargs):
        raise RuntimeError("synthetic refresh failure")

    monkeypatch.setattr(analytics_facts, "touch_reservation_fact_window", fail_refresh)
    first_result = process_analytics_fact_refresh_queue_for_hotel(db, hotel_id=hotel_config.id)
    job = db.query(AnalyticsFactRefreshJob).filter_by(reservation_id=90002).one()

    assert first_result == {"processed": 0, "deferred": 1}
    assert job.attempts == 1
    assert job.last_error_type == "RuntimeError"
    assert job.available_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)
    assert process_analytics_fact_refresh_queue_for_hotel(db, hotel_id=hotel_config.id) == {
        "processed": 0,
        "deferred": 0,
    }
