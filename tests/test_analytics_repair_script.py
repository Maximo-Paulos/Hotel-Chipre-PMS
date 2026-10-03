from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.analytics import (
    FactReservationDaily,
    FactRoomOccupancyDaily,
    FactRoomOccupancyStatusAtNightEnum,
)
from app.models.reservation import Reservation, ReservationStatusEnum
from scripts.repair_analytics_facts import _hotel_ranges
from app.services.analytics_facts import refresh_fact_reservation_daily, refresh_fact_room_occupancy_daily


def test_unbounded_repair_includes_stale_fact_dates_outside_current_stays(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = Reservation(
        confirmation_code="REPAIR-FACT-RANGE",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 5, 10),
        check_out_date=date(2026, 5, 12),
        total_amount=Decimal("200.00"),
        subtotal_amount=Decimal("200.00"),
        net_amount=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()

    for stale_fact_date in (date(2026, 1, 2), date(2026, 8, 3)):
        db.add(
            FactRoomOccupancyDaily(
                hotel_id=hotel_config.id,
                room_id=sample_rooms[0].id,
                stay_date=stale_fact_date,
                category_id=sample_categories[0].id,
                status_at_night=FactRoomOccupancyStatusAtNightEnum.AVAILABLE,
                is_sellable_night=True,
                is_occupied=False,
                revenue_net_ars=Decimal("0.00"),
                revenue_net_usd=Decimal("0.00"),
                margin_operating_ars=Decimal("0.00"),
                margin_operating_usd=Decimal("0.00"),
            )
        )
    db.flush()

    ranges = _hotel_ranges(db, SimpleNamespace(hotel_id=None, date_from=None, date_to=None))

    assert ranges == [(hotel_config.id, date(2026, 1, 2), date(2026, 8, 3))]


def test_rebuilding_the_same_historical_fact_range_is_idempotent(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = Reservation(
        confirmation_code="REPAIR-FACT-IDEMPOTENT",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 5, 10),
        check_out_date=date(2026, 5, 12),
        total_amount=Decimal("200.00"),
        subtotal_amount=Decimal("200.00"),
        net_amount=Decimal("200.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("0.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()

    for _ in range(2):
        refresh_fact_reservation_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 5, 10),
            date_to=date(2026, 5, 11),
        )
        refresh_fact_room_occupancy_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 5, 10),
            date_to=date(2026, 5, 11),
        )
        db.flush()

    reservation_facts = (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.hotel_id == hotel_config.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    occupancy_facts = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_config.id,
            FactRoomOccupancyDaily.stay_date >= date(2026, 5, 10),
            FactRoomOccupancyDaily.stay_date <= date(2026, 5, 11),
        )
        .order_by(FactRoomOccupancyDaily.stay_date.asc())
        .all()
    )
    assert len(reservation_facts) == 2
    assert len(occupancy_facts) == len(sample_rooms) * 2
    reservation_occupancy_facts = [row for row in occupancy_facts if row.reservation_id == reservation.id]
    assert len(reservation_occupancy_facts) == 2
    assert sum(
        (Decimal(str(row.revenue_gross_ars)) for row in reservation_facts), Decimal("0.00")
    ) == Decimal("200.00")
    assert [row.stay_date for row in reservation_facts] == [date(2026, 5, 10), date(2026, 5, 11)]


def test_single_night_refresh_keeps_full_stay_revenue_distribution(
    db, hotel_config, sample_guest, sample_categories, sample_rooms
):
    reservation = Reservation(
        confirmation_code="REPAIR-FACT-PARTIAL",
        hotel_id=hotel_config.id,
        guest_id=sample_guest.id,
        room_id=sample_rooms[0].id,
        category_id=sample_categories[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
        total_amount=Decimal("201.00"),
        subtotal_amount=Decimal("201.00"),
        net_amount=Decimal("201.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("0.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()

    for date_from in (date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 1)):
        refresh_fact_reservation_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date_from,
            date_to=date_from,
        )
        refresh_fact_room_occupancy_daily(
            db,
            hotel_id=hotel_config.id,
            date_from=date_from,
            date_to=date_from,
        )

    rows = (
        db.query(FactReservationDaily)
        .filter(FactReservationDaily.hotel_id == hotel_config.id)
        .order_by(FactReservationDaily.stay_date.asc())
        .all()
    )
    assert len(rows) == 2
    assert [row.revenue_gross_ars for row in rows] == [Decimal("100.50"), Decimal("100.50")]
    occupancy_rows = (
        db.query(FactRoomOccupancyDaily)
        .filter(
            FactRoomOccupancyDaily.hotel_id == hotel_config.id,
            FactRoomOccupancyDaily.reservation_id == reservation.id,
        )
        .order_by(FactRoomOccupancyDaily.stay_date.asc())
        .all()
    )
    assert len(occupancy_rows) == 2
    assert [row.revenue_net_ars for row in occupancy_rows] == [Decimal("100.50"), Decimal("100.50")]
