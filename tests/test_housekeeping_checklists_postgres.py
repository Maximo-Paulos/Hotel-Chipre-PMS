"""PostgreSQL tenant and concurrent item completion regressions."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.housekeeping_checklist import (
    HousekeepingChecklist,
    HousekeepingChecklistItem,
    HousekeepingChecklistItemCodeEnum,
)
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.services.checkin_service import perform_checkout
from app.services.housekeeping_checklist_service import (
    complete_checklist_item,
    create_checkout_checklist,
    list_open_checklists,
)
from app.services.tenant_context import set_tenant_hotel_context


def test_postgres_serializes_concurrent_checklist_item_completion_and_scopes_tenant(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    room_id: int | None = None
    reservation_id: int | None = None
    checklist_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic housekeeping {suffix}"))
        seed.flush()
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic housekeeping {suffix}",
            code=f"HK{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()
        room = Room(
            hotel_id=hotel_id,
            room_number=f"H{suffix[:8]}",
            category_id=category.id,
            status=RoomStatusEnum.CLEANING,
            housekeeping_status=RoomHousekeepingStatusEnum.DIRTY,
        )
        seed.add(room)
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"HK-PG-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today(),
            total_amount=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            num_adults=1,
            status=ReservationStatusEnum.CHECKED_OUT,
        )
        seed.add(reservation)
        seed.flush()
        checklist = create_checkout_checklist(
            seed,
            hotel_id=hotel_id,
            room_id=room.id,
            reservation_id=reservation.id,
            actor_user_id=None,
        )
        seed.commit()
        room_id, reservation_id, checklist_id = room.id, reservation.id, checklist.id
    finally:
        seed.close()

    barrier = Barrier(2)

    def complete_same_item():
        session = session_factory()
        try:
            set_tenant_hotel_context(session, hotel_id)
            barrier.wait(timeout=10)
            result = complete_checklist_item(
                session,
                hotel_id=hotel_id,
                checklist_id=checklist_id,
                item_code=HousekeepingChecklistItemCodeEnum.CHANGE_SHEETS,
                actor_user_id=None,
            )
            session.commit()
            return result.checklist.version, result.changed
        finally:
            session.close()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: complete_same_item(), range(2)))

        check = session_factory()
        try:
            set_tenant_hotel_context(check, hotel_id)
            current = (
                check.query(HousekeepingChecklist)
                .filter(HousekeepingChecklist.id == checklist_id, HousekeepingChecklist.hotel_id == hotel_id)
                .one()
            )
            assert sorted(version for version, _changed in results) == [2, 2]
            assert sum(changed for _version, changed in results) == 1
            assert current.version == 2
            assert check.query(HousekeepingChecklistItem).filter(
                HousekeepingChecklistItem.checklist_id == checklist_id,
                HousekeepingChecklistItem.completed.is_(True),
            ).count() == 1
            assert check.query(AuditLog).filter(
                AuditLog.hotel_id == hotel_id,
                AuditLog.table_name == "housekeeping_checklist_items",
            ).count() == 1
            assert list_open_checklists(check, hotel_id=hotel_id + 1).checklists == []
        finally:
            check.close()
    finally:
        cleanup = session_factory()
        try:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(AuditLog).filter(AuditLog.hotel_id == hotel_id).delete(synchronize_session=False)
            if checklist_id is not None:
                cleanup.query(HousekeepingChecklistItem).filter(
                    HousekeepingChecklistItem.hotel_id == hotel_id,
                    HousekeepingChecklistItem.checklist_id == checklist_id,
                ).delete(synchronize_session=False)
                cleanup.query(HousekeepingChecklist).filter(
                    HousekeepingChecklist.hotel_id == hotel_id,
                    HousekeepingChecklist.id == checklist_id,
                ).delete(synchronize_session=False)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.hotel_id == hotel_id,
                    Reservation.id == reservation_id,
                ).delete(synchronize_session=False)
            if room_id is not None:
                cleanup.query(Room).filter(Room.hotel_id == hotel_id, Room.id == room_id).delete(
                    synchronize_session=False
                )
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.commit()
        finally:
            cleanup.close()


def test_postgres_checkout_checklist_and_room_audit_roll_back_atomically(pg_engine, monkeypatch):
    """Checkout, checklist creation, and room audit share the caller transaction."""
    from app.services import checkin_service

    monkeypatch.setattr(checkin_service, "_notify_reservation_event", lambda *args, **kwargs: None)
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    room_id: int | None = None
    reservation_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic checkout {suffix}"))
        seed.flush()
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic checkout {suffix}",
            code=f"CO{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()
        room = Room(
            hotel_id=hotel_id,
            room_number=f"C{suffix[:8]}",
            category_id=category.id,
            status=RoomStatusEnum.OCCUPIED,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add(room)
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"HK-CO-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today(),
            actual_check_in=datetime.now(UTC),
            total_amount=Decimal("0.00"),
            amount_paid=Decimal("0.00"),
            num_adults=1,
            status=ReservationStatusEnum.CHECKED_IN,
        )
        seed.add(reservation)
        seed.commit()
        room_id, reservation_id = room.id, reservation.id
    finally:
        seed.close()

    checkout_session = session_factory()
    try:
        set_tenant_hotel_context(checkout_session, hotel_id)
        checked_out = perform_checkout(
            checkout_session,
            reservation_id,
            hotel_id=hotel_id,
            force=True,
            actor_user_id=None,
        )
        room = (
            checkout_session.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .one()
        )
        checklist = (
            checkout_session.query(HousekeepingChecklist)
            .filter(
                HousekeepingChecklist.hotel_id == hotel_id,
                HousekeepingChecklist.reservation_id == reservation_id,
            )
            .one()
        )
        assert checked_out.status == ReservationStatusEnum.CHECKED_OUT
        assert room.status == RoomStatusEnum.CLEANING
        assert room.housekeeping_status == RoomHousekeepingStatusEnum.DIRTY
        assert checklist.status == "open"
        assert checkout_session.query(AuditLog).filter(
            AuditLog.hotel_id == hotel_id,
            AuditLog.table_name == "rooms",
            AuditLog.record_id == room_id,
        ).count() == 1
        checkout_session.rollback()
    finally:
        checkout_session.close()

    verify = session_factory()
    try:
        set_tenant_hotel_context(verify, hotel_id)
        persisted_reservation = (
            verify.query(Reservation)
            .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            .one()
        )
        persisted_room = (
            verify.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .one()
        )
        assert persisted_reservation.status == ReservationStatusEnum.CHECKED_IN
        assert persisted_room.status == RoomStatusEnum.OCCUPIED
        assert persisted_room.housekeeping_status == RoomHousekeepingStatusEnum.CLEAN
        assert verify.query(HousekeepingChecklist).filter(
            HousekeepingChecklist.hotel_id == hotel_id,
            HousekeepingChecklist.reservation_id == reservation_id,
        ).count() == 0
        assert verify.query(AuditLog).filter(
            AuditLog.hotel_id == hotel_id,
            AuditLog.table_name == "rooms",
            AuditLog.record_id == room_id,
        ).count() == 0
    finally:
        verify.close()

        cleanup = session_factory()
        try:
            set_tenant_hotel_context(cleanup, hotel_id)
            cleanup.query(AuditLog).filter(AuditLog.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(HousekeepingChecklistItem).filter(
                HousekeepingChecklistItem.hotel_id == hotel_id
            ).delete(synchronize_session=False)
            cleanup.query(HousekeepingChecklist).filter(
                HousekeepingChecklist.hotel_id == hotel_id
            ).delete(synchronize_session=False)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.hotel_id == hotel_id,
                    Reservation.id == reservation_id,
                ).delete(synchronize_session=False)
            if room_id is not None:
                cleanup.query(Room).filter(Room.hotel_id == hotel_id, Room.id == room_id).delete(
                    synchronize_session=False
                )
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.commit()
        finally:
            cleanup.close()
