from __future__ import annotations

from datetime import date
import re

from sqlalchemy import event

from app.models.analytics import FactReservationDaily, FactRoomOccupancyDaily
from app.models.company import Company
from app.models.guest import Guest
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
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.analytics_service import build_home_payload, build_room_detail_payload
from app.services.analytics_facts import refresh_fact_reservation_daily


def test_analytics_home_does_not_repair_missing_facts_during_postgres_read(
    pg_session, monkeypatch
):
    monkeypatch.setenv("SYNC_FACT_REFRESH_ENABLED", "true")
    db = pg_session
    hotel = HotelConfiguration(id=981101, hotel_name="Synthetic Analytics Read")
    db.add(hotel)
    db.flush()

    category = RoomCategory(
        hotel_id=hotel.id,
        name="Synthetic",
        code="SYN",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(
        hotel_id=hotel.id,
        first_name="Synthetic",
        last_name="Guest",
        terms_accepted=True,
    )
    db.add_all([category, guest])
    db.flush()

    room = Room(
        hotel_id=hotel.id,
        room_number="SYN-01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()

    reservation = Reservation(
        hotel_id=hotel.id,
        confirmation_code="SYNTHETIC-ANALYTICS-READ",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 3),
        total_amount=200,
        subtotal_amount=200,
        net_amount=200,
        amount_paid=0,
        currency_code="ARS",
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
    assert db.query(FactReservationDaily).filter_by(hotel_id=hotel.id).count() == 0
    assert db.query(FactRoomOccupancyDaily).filter_by(hotel_id=hotel.id).count() == 0

    writes: list[str] = []

    def capture_writes(_connection, _cursor, statement, _parameters, _context, _many):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb in {"INSERT", "UPDATE", "DELETE"}:
            writes.append(verb)

    connection = db.get_bind()
    event.listen(connection, "before_cursor_execute", capture_writes)
    try:
        payload = build_home_payload(
            db,
            hotel_id=hotel.id,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )
    finally:
        event.remove(connection, "before_cursor_execute", capture_writes)

    assert payload["data_as_of"] is None
    assert writes == []
    assert db.query(FactReservationDaily).filter_by(hotel_id=hotel.id).count() == 0
    assert db.query(FactRoomOccupancyDaily).filter_by(hotel_id=hotel.id).count() == 0


def test_company_reservation_fact_refresh_persists_company_channel_on_postgres(pg_session):
    db = pg_session
    hotel = HotelConfiguration(id=981102, hotel_name="Synthetic Company Analytics")
    db.add(hotel)
    db.flush()

    category = RoomCategory(
        hotel_id=hotel.id,
        name="Corporate Synthetic",
        code="CORP",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(
        hotel_id=hotel.id,
        first_name="Synthetic",
        last_name="Corporate Guest",
        terms_accepted=True,
    )
    company = Company(
        hotel_id=hotel.id,
        legal_name="Synthetic Company SA",
        display_name="Synthetic Company",
    )
    db.add_all([category, guest, company])
    db.flush()

    room = Room(
        hotel_id=hotel.id,
        room_number="CORP-01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()

    reservation = Reservation(
        hotel_id=hotel.id,
        confirmation_code="SYNTHETIC-COMPANY-FACT",
        guest_id=guest.id,
        company_id=company.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=date(2026, 4, 1),
        check_out_date=date(2026, 4, 2),
        total_amount=100,
        subtotal_amount=100,
        net_amount=100,
        amount_paid=0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        outcome=ReservationOutcomeEnum.PENDING,
        source=ReservationSourceEnum.DIRECT,
        channel_code=ReservationChannelCodeEnum.COMPANY,
        guest_segment=ReservationGuestSegmentEnum.BUSINESS,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.NONE,
        num_adults=1,
        num_children=0,
    )
    db.add(reservation)
    db.flush()

    result = refresh_fact_reservation_daily(
        db,
        hotel_id=hotel.id,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 1),
        reservation_id=reservation.id,
    )
    fact = (
        db.query(FactReservationDaily)
        .filter_by(hotel_id=hotel.id, reservation_id=reservation.id)
        .one()
    )

    assert result.inserted == 1
    assert fact.channel_code == ReservationChannelCodeEnum.COMPANY


def test_room_detail_analytics_does_not_load_reservation_history_on_postgres(pg_session):
    db = pg_session
    hotel = HotelConfiguration(id=981103, hotel_name="Synthetic Room Detail Analytics")
    db.add(hotel)
    db.flush()

    category = RoomCategory(
        hotel_id=hotel.id,
        name="Room Detail Synthetic",
        code="RDS",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=hotel.id,
        room_number="RDS-01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()

    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement.lower())

    connection = db.get_bind()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        payload = build_room_detail_payload(
            db,
            hotel_id=hotel.id,
            room_id=room.id,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 5),
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )
    finally:
        event.remove(connection, "before_cursor_execute", capture)

    assert payload["data"]["room"]["room_number"] == "RDS-01"
    assert payload["data"]["room"]["category_name"] == "Room Detail Synthetic"
    assert not [
        statement
        for statement in statements
        if re.search(r"\b(?:from|join)\s+(?:public\.)?(?:reservations|transactions)\b", statement)
    ]
