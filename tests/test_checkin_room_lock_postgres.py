"""PostgreSQL regressions for the check-in room row lock and ORM identity map."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.company import Company
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.transaction import Transaction
from app.services.checkin_service import (
    CheckInConflictError,
    CheckInError,
    CheckOutConflictError,
    _load_ready_room_for_checkin,
    _load_reservation,
    perform_checkout,
)
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.services.tenant_context import set_tenant_hotel_context


def test_checkin_room_lock_refreshes_room_loaded_before_competing_status_change(pg_engine):
    """A stale eagerly loaded Room must not pass check-in after another commit."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    room_id: int | None = None
    reservation_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic check-in race {suffix}"))
        seed.flush()

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic check-in race {suffix}",
            code=f"CR{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()

        room = Room(
            hotel_id=hotel_id,
            room_number=f"R{suffix[:7]}",
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add(room)
        seed.flush()

        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"CI-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=30),
            check_out_date=date.today() + timedelta(days=32),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
        )
        seed.add(reservation)
        seed.commit()
        room_id = room.id
        reservation_id = reservation.id
    finally:
        seed.close()

    checkin_session = session_factory()
    competing_session = session_factory()
    try:
        set_tenant_hotel_context(checkin_session, hotel_id)
        reservation = (
            checkin_session.query(Reservation)
            .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            .one()
        )
        # Reservation.room is joined eagerly, so this Session now holds the
        # pre-race Room state in its identity map before acquiring the row lock.
        assert reservation.room.status == RoomStatusEnum.AVAILABLE

        set_tenant_hotel_context(competing_session, hotel_id)
        competing_room = (
            competing_session.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .one()
        )
        competing_room.status = RoomStatusEnum.OCCUPIED
        competing_session.commit()

        with pytest.raises(CheckInError, match="debe estar disponible"):
            _load_ready_room_for_checkin(checkin_session, reservation, hotel_id)
    finally:
        checkin_session.rollback()
        competing_session.rollback()
        checkin_session.close()
        competing_session.close()

        # pg_engine is a verified disposable fixture; remove only this test's
        # tenant rows so the regression is safe alongside other PG tests.
        with session_factory.begin() as cleanup:
            set_tenant_hotel_context(cleanup, hotel_id)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            if room_id is not None:
                cleanup.query(Room).filter(
                    Room.id == room_id,
                    Room.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )


def test_checkin_refreshes_concurrent_room_move_and_fails_fast_on_room_lock(pg_engine):
    """A moved reservation is refreshed before check-in; a busy room returns a conflict."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 90_000_000 + uuid4().int % 10_000_000
    room_ids: tuple[int, int] | None = None
    reservation_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic check-in move race {suffix}"))
        seed.flush()
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic check-in move race {suffix}",
            code=f"CM{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()
        rooms = [
            Room(
                hotel_id=hotel_id,
                room_number=f"M{suffix[:7]}{index}",
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE,
                housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
            )
            for index in (1, 2)
        ]
        seed.add_all(rooms)
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"CM-{suffix}",
            guest_id=guest.id,
            room_id=rooms[0].id,
            category_id=category.id,
            check_in_date=date.today() + timedelta(days=30),
            check_out_date=date.today() + timedelta(days=32),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
        )
        seed.add(reservation)
        seed.commit()
        room_ids = (rooms[0].id, rooms[1].id)
        reservation_id = reservation.id
    finally:
        seed.close()

    checkin_session = session_factory()
    move_session = session_factory()
    competing_session = session_factory()
    try:
        for session in (checkin_session, move_session, competing_session):
            set_tenant_hotel_context(session, hotel_id)

        stale_reservation = (
            checkin_session.query(Reservation)
            .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
            .one()
        )
        assert stale_reservation.room_id == room_ids[0]
        assert stale_reservation.room.id == room_ids[0]

        moved_reservation = move_session.query(Reservation).filter(
            Reservation.id == reservation_id,
            Reservation.hotel_id == hotel_id,
        ).one()
        moved_reservation.room_id = room_ids[1]
        move_session.commit()

        refreshed_reservation, resolved_hotel_id = _load_reservation(
            checkin_session,
            reservation_id=reservation_id,
            hotel_id=hotel_id,
        )
        assert resolved_hotel_id == hotel_id
        assert refreshed_reservation.room_id == room_ids[1]

        competing_room = (
            competing_session.query(Room)
            .filter(Room.id == room_ids[1], Room.hotel_id == hotel_id)
            .with_for_update(of=Room)
            .one()
        )
        assert competing_room.id == room_ids[1]
        with pytest.raises(CheckInConflictError, match="reintentá el check-in"):
            _load_ready_room_for_checkin(checkin_session, refreshed_reservation, hotel_id)
    finally:
        checkin_session.rollback()
        move_session.rollback()
        competing_session.rollback()
        checkin_session.close()
        move_session.close()
        competing_session.close()

        with session_factory.begin() as cleanup:
            set_tenant_hotel_context(cleanup, hotel_id)
            if reservation_id is not None:
                cleanup.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            if room_ids is not None:
                cleanup.query(Room).filter(
                    Room.hotel_id == hotel_id,
                    Room.id.in_(room_ids),
                ).delete(synchronize_session=False)
            cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(synchronize_session=False)
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )


def test_checkout_returns_retryable_conflict_when_another_transaction_holds_room(pg_engine):
    """Checkout uses PostgreSQL NOWAIT while holding the reservation lock."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 100_000_000 + uuid4().int % 10_000_000
    room_id: int | None = None
    reservation_id: int | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic checkout lock {suffix}"))
        seed.flush()
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic checkout lock {suffix}",
            code=f"CO{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()
        room = Room(
            hotel_id=hotel_id,
            room_number=f"O{suffix[:7]}",
            category_id=category.id,
            status=RoomStatusEnum.OCCUPIED,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add(room)
        seed.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"CO-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today(),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            amount_paid=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.CHECKED_IN,
        )
        seed.add(reservation)
        seed.commit()
        room_id = room.id
        reservation_id = reservation.id
    finally:
        seed.close()

    checkout_session = session_factory()
    room_owner_session = session_factory()
    try:
        set_tenant_hotel_context(checkout_session, hotel_id)
        set_tenant_hotel_context(room_owner_session, hotel_id)
        locked_room = (
            room_owner_session.query(Room)
            .filter(Room.id == room_id, Room.hotel_id == hotel_id)
            .with_for_update(of=Room)
            .one()
        )
        assert locked_room.id == room_id

        with pytest.raises(CheckOutConflictError, match="reintentá el check-out"):
            perform_checkout(
                checkout_session,
                reservation_id,
                hotel_id=hotel_id,
                force=True,
            )

        checkout_session.rollback()
        room_owner_session.rollback()
    finally:
        checkout_session.close()
        room_owner_session.close()

        with session_factory.begin() as verify:
            set_tenant_hotel_context(verify, hotel_id)
            unchanged = verify.query(Reservation).filter(
                Reservation.id == reservation_id,
                Reservation.hotel_id == hotel_id,
            ).one()
            assert unchanged.status == ReservationStatusEnum.CHECKED_IN
            if reservation_id is not None:
                verify.query(Reservation).filter(
                    Reservation.id == reservation_id,
                    Reservation.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            if room_id is not None:
                verify.query(Room).filter(
                    Room.id == room_id,
                    Room.hotel_id == hotel_id,
                ).delete(synchronize_session=False)
            verify.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
            verify.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            verify.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )


def test_checkout_allows_deferred_company_balance_without_financial_mutation_postgres(pg_engine):
    """Deferred billing permits checkout without turning the balance into a payment."""
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 110_000_000 + uuid4().int % 10_000_000
    db = session_factory()
    try:
        set_tenant_hotel_context(db, hotel_id)
        db.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic deferred checkout {suffix}"))
        db.flush()

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic deferred checkout {suffix}",
            code=f"DC{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        company = Company(
            hotel_id=hotel_id,
            legal_name=f"Synthetic deferred company {suffix}",
            display_name=f"Synthetic deferred company {suffix}",
            payment_deferred=True,
        )
        db.add_all([category, guest, company])
        db.flush()

        room = Room(
            hotel_id=hotel_id,
            room_number=f"D{suffix[:7]}",
            category_id=category.id,
            status=RoomStatusEnum.OCCUPIED,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        db.add(room)
        db.flush()
        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"DC-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            company_id=company.id,
            check_in_date=date.today() - timedelta(days=1),
            check_out_date=date.today(),
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            amount_paid=Decimal("0.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.CHECKED_IN,
        )
        db.add(reservation)
        db.flush()

        adjustment = BillingAdjustment(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=Decimal("25.00"),
            currency_code="ARS",
            total_amount=Decimal("25.00"),
            notes="Synthetic deferred checkout balance",
        )
        db.add(adjustment)
        db.flush()
        payment_count_before = db.query(Transaction).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation.id,
        ).count()
        paid_before = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
        total_before = Decimal(str(reservation.total_amount))

        result = perform_checkout(db, reservation.id, hotel_id=hotel_id)
        db.flush()

        paid_after = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
        payment_count_after = db.query(Transaction).filter(
            Transaction.hotel_id == hotel_id,
            Transaction.reservation_id == reservation.id,
        ).count()
        balance_after = total_before + Decimal(str(adjustment.total_amount)) - paid_after

        assert result.status == ReservationStatusEnum.CHECKED_OUT
        assert Decimal(str(reservation.total_amount)) == total_before
        assert paid_after == paid_before == Decimal("0.00")
        assert Decimal(str(adjustment.total_amount)) == Decimal("25.00")
        assert payment_count_after == payment_count_before == 0
        assert balance_after == Decimal("225.00")
    finally:
        db.rollback()
        db.close()
