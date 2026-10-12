from __future__ import annotations

from datetime import date

from sqlalchemy import event as sqlalchemy_event

from app.models.allocation import AllocationRun
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.allocation_runtime_service import run_persisted_allocation
from app.services.tenant_context import set_tenant_hotel_context


def test_postgres_reoptimization_batches_reservation_reads_and_invalidations(pg_session):
    hotel = HotelConfiguration(id=91001, subscription_active=True)
    db = pg_session
    db.add(hotel)
    db.flush()

    category = RoomCategory(
        hotel_id=hotel.id,
        name="Performance test category",
        code="PERF",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()

    rooms = [
        Room(
            hotel_id=hotel.id,
            room_number=f"{index:03d}",
            floor=index,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
            is_accessible=True,
            score=index,
        )
        for index in range(1, 8)
    ]
    guests = [
        Guest(
            hotel_id=hotel.id,
            first_name=f"Guest{index}",
            last_name="Synthetic",
            document_type=DocumentTypeEnum.DNI,
            document_number=f"91001{index:04d}",
            terms_accepted=True,
        )
        for index in range(1, 7)
    ]
    db.add_all([*rooms, *guests])
    db.flush()

    reservations = [
        Reservation(
            hotel_id=hotel.id,
            confirmation_code=f"PG-BATCH-{index}",
            guest_id=guests[index - 1].id,
            room_id=rooms[0].id,
            category_id=category.id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 4),
            total_amount=100,
            amount_paid=0,
            deposit_amount=0,
        )
        for index in range(1, 7)
    ]
    db.add_all(reservations)
    db.flush()
    set_tenant_hotel_context(db, hotel.id)

    reservation_selects: list[str] = []

    def count_reservation_selects(_conn, _cursor, statement, _parameters, _context, _many):
        lowered = statement.lower()
        if lowered.lstrip().startswith("select") and "reservations" in lowered:
            reservation_selects.append(statement)

    engine = db.get_bind()
    sqlalchemy_event.listen(engine, "before_cursor_execute", count_reservation_selects)
    try:
        result = run_persisted_allocation(
            db,
            hotel_id=hotel.id,
            trigger_type="postgres_query_count_regression",
            horizon_start=date(2026, 7, 1),
            horizon_end=date(2026, 7, 5),
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", count_reservation_selects)

    assert result.solver_result.success is True
    assert len(reservation_selects) == 5
    assert db.query(AllocationRun).filter(AllocationRun.hotel_id == hotel.id).count() == 1

    events = (
        db.query(DomainEventOutbox)
        .filter(
            DomainEventOutbox.hotel_id == hotel.id,
            DomainEventOutbox.event_type == "allocation.read_model.changed",
        )
        .all()
    )
    assert len(events) == 3
    assert {item.domain for item in events} == {"reservations", "rooms", "analytics"}
