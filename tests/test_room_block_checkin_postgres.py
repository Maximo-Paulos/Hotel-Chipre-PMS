"""PostgreSQL regression for a room block encountered during check-in."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.orm import sessionmaker

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.room_block import RoomBlock
from app.services.checkin_service import (
    CheckInConflictError,
    CheckInError,
    _load_ready_room_for_checkin,
    _load_reservation,
)
from app.services.room_block_service import (
    RoomBlockError,
    RoomBlockExtensionConflictError,
    RoomBlockReservationConflictError,
    RoomBlockReleaseConflictError,
    create_block,
    extend_block,
    resolve_block,
)
from app.services.tenant_context import set_tenant_hotel_context


def test_postgres_checkin_rejects_overlapping_room_block_after_room_lock(pg_session):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 150_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic room block check-in {suffix}")
    pg_session.add(hotel)
    pg_session.flush()

    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic room block category {suffix}",
        code=f"RB{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
    pg_session.add_all([category, guest])
    pg_session.flush()

    room = Room(
        hotel_id=hotel_id,
        room_number=f"B{suffix[:8]}",
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
    )
    pg_session.add(room)
    pg_session.flush()

    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"RB-{suffix}",
        guest_id=guest.id,
        room_id=room.id,
        category_id=category.id,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=Decimal("200.00"),
        subtotal_amount=Decimal("200.00"),
        net_amount=Decimal("200.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.FULLY_PAID,
    )
    block = RoomBlock(
        hotel_id=hotel_id,
        room_id=room.id,
        starts_at=check_in + timedelta(days=1),
        ends_at=check_out + timedelta(days=1),
    )
    pg_session.add_all([reservation, block])
    pg_session.flush()

    statements: list[str] = []

    def capture_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.casefold().replace('"', ""))

    connection = pg_session.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        with pytest.raises(CheckInError, match="bloqueo activo para las fechas de la estadía"):
            _load_ready_room_for_checkin(pg_session, reservation, hotel_id)
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    room_lock_index = next(
        index for index, statement in enumerate(statements)
        if "for update of rooms nowait" in statement
    )
    block_lookup_index = next(
        index for index, statement in enumerate(statements)
        if "from room_blocks" in statement
    )
    assert room_lock_index < block_lookup_index


def _seed_room_block_checkin_case(engine, *, existing_block: bool = False):
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 190_000_000 + uuid4().int % 20_000_000
    check_in = date.today() + timedelta(days=30)
    check_out = check_in + timedelta(days=2)

    with session_factory.begin() as seed:
        set_tenant_hotel_context(seed, hotel_id)
        hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic block race {suffix}")
        seed.add(hotel)
        seed.flush()

        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic block race category {suffix}",
            code=f"BR{suffix}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Guest")
        seed.add_all([category, guest])
        seed.flush()

        room = Room(
            hotel_id=hotel_id,
            room_number=f"R{suffix[:8]}",
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        alternate_room = Room(
            hotel_id=hotel_id,
            room_number=f"A{suffix[:8]}",
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
        )
        seed.add_all([room, alternate_room])
        seed.flush()

        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"BR-{suffix}",
            guest_id=guest.id,
            room_id=room.id,
            category_id=category.id,
            check_in_date=check_in,
            check_out_date=check_out,
            total_amount=Decimal("200.00"),
            subtotal_amount=Decimal("200.00"),
            net_amount=Decimal("200.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.FULLY_PAID,
        )
        seed.add(reservation)
        seed.flush()

        block_id = None
        if existing_block:
            block = create_block(
                seed,
                hotel_id=hotel_id,
                room_id=room.id,
                starts_at=check_in - timedelta(days=3),
                ends_at=check_in,
            )
            block_id = block.id

        case = {
            "hotel_id": hotel_id,
            "room_id": room.id,
            "alternate_room_id": alternate_room.id,
            "reservation_id": reservation.id,
            "block_id": block_id,
            "check_in": check_in,
            "check_out": check_out,
        }
    return session_factory, case


def _hold_room_for_checkin(session, *, hotel_id: int, reservation_id: int) -> int:
    set_tenant_hotel_context(session, hotel_id)
    backend_pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
    reservation, resolved_hotel_id = _load_reservation(session, reservation_id, hotel_id)
    room = _load_ready_room_for_checkin(session, reservation, resolved_hotel_id)
    reservation.status = ReservationStatusEnum.CHECKED_IN
    room.status = RoomStatusEnum.OCCUPIED
    session.flush()
    # Do not commit here: the Room FOR UPDATE remains held until the caller
    # explicitly releases this transaction after observing the competing wait.
    assert session.in_transaction()
    return int(backend_pid)


def _wait_for_worker_blocked_by(
    engine,
    *,
    worker_backend_pid: int,
    expected_blocker_pid: int,
    timeout_seconds: float = 8.0,
) -> bool:
    """Observe the exact PostgreSQL lock dependency, without SQL-text filters."""
    deadline = monotonic() + timeout_seconds
    with engine.connect() as observer:
        while monotonic() < deadline:
            blocker_pids = observer.execute(
                text("SELECT pg_blocking_pids(:worker_backend_pid)"),
                {"worker_backend_pid": worker_backend_pid},
            ).scalar_one()
            if expected_blocker_pid in blocker_pids:
                return True
            sleep(0.02)
    return False


def _start_block_mutation(
    engine, *, hotel_id: int, operation, label: str
) -> tuple[ThreadPoolExecutor, Future, tuple[Event, list[int]]]:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix=f"room-block-{label}")
    backend_pid_ready = Event()
    worker_backend_pid: list[int] = []

    def run_mutation():
        with session_factory() as session:
            set_tenant_hotel_context(session, hotel_id)
            backend_pid = session.execute(text("SELECT pg_backend_pid()")).scalar_one()
            worker_backend_pid.append(int(backend_pid))
            backend_pid_ready.set()
            session.execute(text("SET LOCAL lock_timeout = '20s'"))
            operation(session)
            session.commit()

    future: Future = executor.submit(run_mutation)
    return executor, future, (backend_pid_ready, worker_backend_pid)


def _cleanup_room_block_case(engine, *, hotel_id: int) -> None:
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    with session_factory.begin() as cleanup:
        set_tenant_hotel_context(cleanup, hotel_id)
        cleanup.query(RoomBlock).filter(RoomBlock.hotel_id == hotel_id).delete(synchronize_session=False)
        cleanup.query(Reservation).filter(Reservation.hotel_id == hotel_id).delete(synchronize_session=False)
        cleanup.query(Room).filter(Room.hotel_id == hotel_id).delete(synchronize_session=False)
        cleanup.query(Guest).filter(Guest.hotel_id == hotel_id).delete(synchronize_session=False)
        cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(synchronize_session=False)
        cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(synchronize_session=False)


def test_postgres_create_block_rejects_existing_reservation_during_checkin(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine)
    hotel_id = case["hotel_id"]
    checkin_session = session_factory()
    executor = None
    future = None
    try:
        _hold_room_for_checkin(
            checkin_session,
            hotel_id=hotel_id,
            reservation_id=case["reservation_id"],
        )
        executor, future, worker_identity = _start_block_mutation(
            pg_engine,
            hotel_id=hotel_id,
            label="create",
            operation=lambda session: create_block(
                session,
                hotel_id=hotel_id,
                room_id=case["room_id"],
                starts_at=case["check_in"],
                ends_at=case["check_out"],
            ),
        )
        backend_pid_ready, worker_backend_pid = worker_identity
        assert backend_pid_ready.wait(timeout=5), "create worker did not start a PostgreSQL session"
        assert worker_backend_pid
        with pytest.raises(RoomBlockReservationConflictError) as conflict:
            future.result(timeout=5)
        checkin_session.commit()

        assert conflict.value.reservation_ids == [case["reservation_id"]]
        with session_factory() as verify:
            set_tenant_hotel_context(verify, hotel_id)
            assert verify.query(RoomBlock).filter(RoomBlock.hotel_id == hotel_id).count() == 0
    finally:
        if future is not None and checkin_session.in_transaction():
            checkin_session.commit()
        else:
            checkin_session.rollback()
        checkin_session.close()
        if executor is not None:
            executor.shutdown(wait=True)
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_extend_block_waits_for_checkin_then_rechecks_protected_reservation(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine, existing_block=True)
    hotel_id = case["hotel_id"]
    checkin_session = session_factory()
    executor = None
    future = None
    try:
        checkin_backend_pid = _hold_room_for_checkin(
            checkin_session,
            hotel_id=hotel_id,
            reservation_id=case["reservation_id"],
        )
        executor, future, worker_identity = _start_block_mutation(
            pg_engine,
            hotel_id=hotel_id,
            label="extend",
            operation=lambda session: extend_block(
                session,
                hotel_id=hotel_id,
                block_id=case["block_id"],
                ends_at=case["check_in"] + timedelta(days=1),
            ),
        )
        backend_pid_ready, worker_backend_pid = worker_identity
        assert backend_pid_ready.wait(timeout=5), "extend worker did not start a PostgreSQL session"
        waiting_for_room = _wait_for_worker_blocked_by(
            pg_engine,
            worker_backend_pid=worker_backend_pid[0],
            expected_blocker_pid=checkin_backend_pid,
        )
        worker_done_before_release = future.done()
        worker_exception = future.exception() if worker_done_before_release else None
        worker_exception_type = type(worker_exception).__name__ if worker_exception else None
        checkin_session.commit()

        assert waiting_for_room, (
            "extend_block should wait on the check-in transaction's Room lock; "
            f"worker_done_before_release={worker_done_before_release}, "
            f"worker_exception_type={worker_exception_type}"
        )
        with pytest.raises(RoomBlockExtensionConflictError) as conflict:
            future.result(timeout=10)
        assert conflict.value.protected_reservation_count == 1
    finally:
        if future is not None and checkin_session.in_transaction():
            checkin_session.commit()
        else:
            checkin_session.rollback()
        checkin_session.close()
        if executor is not None:
            executor.shutdown(wait=True)
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_create_block_requires_allocation_proposal_to_clear_reservation(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine)
    hotel_id = case["hotel_id"]
    block_session = session_factory()
    checkin_session = session_factory()
    try:
        set_tenant_hotel_context(block_session, hotel_id)
        with pytest.raises(RoomBlockReservationConflictError):
            create_block(
                block_session,
                hotel_id=hotel_id,
                room_id=case["room_id"],
                starts_at=case["check_in"],
                ends_at=case["check_out"],
            )
        assert block_session.query(RoomBlock).filter(RoomBlock.hotel_id == hotel_id).count() == 0

        set_tenant_hotel_context(checkin_session, hotel_id)
        reservation, resolved_hotel_id = _load_reservation(
            checkin_session, case["reservation_id"], hotel_id
        )
        ready_room = _load_ready_room_for_checkin(checkin_session, reservation, resolved_hotel_id)
        assert ready_room.id == case["room_id"]
    finally:
        checkin_session.rollback()
        block_session.rollback()
        checkin_session.close()
        block_session.close()
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_extend_block_requires_allocation_proposal_to_clear_reservation(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine, existing_block=True)
    hotel_id = case["hotel_id"]
    block_session = session_factory()
    checkin_session = session_factory()
    try:
        set_tenant_hotel_context(block_session, hotel_id)
        with pytest.raises(RoomBlockExtensionConflictError, match="propuesta válida"):
            extend_block(
                block_session,
                hotel_id=hotel_id,
                block_id=case["block_id"],
                ends_at=case["check_in"] + timedelta(days=1),
            )
        assert block_session.query(RoomBlock).filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.id == case["block_id"],
        ).one().ends_at == case["check_in"]

        set_tenant_hotel_context(checkin_session, hotel_id)
        reservation, resolved_hotel_id = _load_reservation(
            checkin_session, case["reservation_id"], hotel_id
        )
        ready_room = _load_ready_room_for_checkin(checkin_session, reservation, resolved_hotel_id)
        assert ready_room.id == case["room_id"]
    finally:
        checkin_session.rollback()
        block_session.rollback()
        checkin_session.close()
        block_session.close()
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_resolve_block_first_makes_checkin_retry_then_accept(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine, existing_block=True)
    hotel_id = case["hotel_id"]
    block_session = session_factory()
    checkin_session = session_factory()
    retry_session = session_factory()
    try:
        set_tenant_hotel_context(block_session, hotel_id)
        statements: list[str] = []

        def capture_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement.casefold().replace('"', ""))

        connection = block_session.connection()
        event.listen(connection, "before_cursor_execute", capture_statement)
        try:
            resolved_block = resolve_block(
                block_session,
                hotel_id=hotel_id,
                block_id=case["block_id"],
            )
        finally:
            event.remove(connection, "before_cursor_execute", capture_statement)
        assert resolved_block.resolved_at is not None

        room_lock_index = next(
            index for index, statement in enumerate(statements)
            if "for update of rooms" in statement
        )
        block_lock_index = next(
            index for index, statement in enumerate(statements)
            if "for update of room_blocks" in statement
        )
        assert room_lock_index < block_lock_index

        set_tenant_hotel_context(checkin_session, hotel_id)
        reservation, resolved_hotel_id = _load_reservation(
            checkin_session, case["reservation_id"], hotel_id
        )
        with pytest.raises(CheckInConflictError, match="Otra operación está modificando la habitación"):
            _load_ready_room_for_checkin(checkin_session, reservation, resolved_hotel_id)
        checkin_session.rollback()
        block_session.commit()

        set_tenant_hotel_context(retry_session, hotel_id)
        retry_reservation, resolved_hotel_id = _load_reservation(
            retry_session, case["reservation_id"], hotel_id
        )
        ready_room = _load_ready_room_for_checkin(
            retry_session, retry_reservation, resolved_hotel_id
        )
        assert ready_room.id == case["room_id"]
        assert retry_session.query(RoomBlock).filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.id == case["block_id"],
            RoomBlock.resolved_at.is_(None),
        ).count() == 0
    finally:
        checkin_session.rollback()
        retry_session.rollback()
        block_session.rollback()
        checkin_session.close()
        retry_session.close()
        block_session.close()
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_resolve_block_waits_for_checkin_then_rechecks_room_state(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine, existing_block=True)
    hotel_id = case["hotel_id"]
    checkin_session = session_factory()
    executor = None
    future = None
    try:
        checkin_backend_pid = _hold_room_for_checkin(
            checkin_session,
            hotel_id=hotel_id,
            reservation_id=case["reservation_id"],
        )
        executor, future, worker_identity = _start_block_mutation(
            pg_engine,
            hotel_id=hotel_id,
            label="resolve",
            operation=lambda session: resolve_block(
                session,
                hotel_id=hotel_id,
                block_id=case["block_id"],
            ),
        )
        backend_pid_ready, worker_backend_pid = worker_identity
        assert backend_pid_ready.wait(timeout=5), "resolve worker did not start a PostgreSQL session"
        waiting_for_room = _wait_for_worker_blocked_by(
            pg_engine,
            worker_backend_pid=worker_backend_pid[0],
            expected_blocker_pid=checkin_backend_pid,
        )
        worker_done_before_release = future.done()
        worker_exception = future.exception() if worker_done_before_release else None
        worker_exception_type = type(worker_exception).__name__ if worker_exception else None
        checkin_session.commit()

        assert waiting_for_room, (
            "resolve_block should wait on the check-in transaction's Room lock; "
            f"worker_done_before_release={worker_done_before_release}, "
            f"worker_exception_type={worker_exception_type}"
        )
        with pytest.raises(RoomBlockReleaseConflictError, match="La habitación debe estar disponible"):
            future.result(timeout=10)

        with session_factory() as verify:
            set_tenant_hotel_context(verify, hotel_id)
            block = verify.query(RoomBlock).filter(
                RoomBlock.hotel_id == hotel_id,
                RoomBlock.id == case["block_id"],
            ).one()
            assert block.resolved_at is None
    finally:
        if future is not None and checkin_session.in_transaction():
            checkin_session.commit()
        else:
            checkin_session.rollback()
        checkin_session.close()
        if executor is not None:
            executor.shutdown(wait=True)
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)


def test_postgres_extend_rechecks_fresh_block_after_waiting_for_room(pg_engine):
    session_factory, case = _seed_room_block_checkin_case(pg_engine, existing_block=True)
    hotel_id = case["hotel_id"]
    with session_factory.begin() as setup:
        set_tenant_hotel_context(setup, hotel_id)
        setup.query(Reservation).filter(
            Reservation.hotel_id == hotel_id,
            Reservation.id == case["reservation_id"],
        ).update({Reservation.room_id: case["alternate_room_id"]}, synchronize_session=False)
    paused_at_room_lock = Event()
    resume_room_lock = Event()
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="room-block-preview-refresh")
    delayed_session = None
    delayed_connection = None
    pause_listener_attached = False
    delayed_future = None
    winner_session = session_factory()
    try:
        delayed_session = session_factory()
        set_tenant_hotel_context(delayed_session, hotel_id)
        delayed_connection = delayed_session.connection()

        def pause_before_room_lock(_connection, _cursor, statement, _parameters, _context, _executemany):
            normalized_statement = statement.casefold().replace('"', "")
            if "for update of rooms" in normalized_statement:
                paused_at_room_lock.set()
                if not resume_room_lock.wait(timeout=10):
                    raise TimeoutError("test did not resume the extension lock attempt")

        event.listen(delayed_connection, "before_cursor_execute", pause_before_room_lock)
        pause_listener_attached = True

        def delayed_extension():
            return extend_block(
                delayed_session,
                hotel_id=hotel_id,
                block_id=case["block_id"],
                ends_at=case["check_in"] + timedelta(days=1),
            )

        delayed_future = executor.submit(delayed_extension)
        assert paused_at_room_lock.wait(timeout=10), "extension did not reach its Room lock"

        set_tenant_hotel_context(winner_session, hotel_id)
        winner_block = extend_block(
            winner_session,
            hotel_id=hotel_id,
            block_id=case["block_id"],
            ends_at=case["check_in"] + timedelta(days=2),
        )
        assert winner_block.ends_at == case["check_in"] + timedelta(days=2)
        winner_session.commit()

        resume_room_lock.set()
        with pytest.raises(RoomBlockError, match="La nueva fecha debe ser posterior"):
            delayed_future.result(timeout=10)

        fresh_block = delayed_session.query(RoomBlock).filter(
            RoomBlock.hotel_id == hotel_id,
            RoomBlock.id == case["block_id"],
        ).one()
        assert fresh_block.ends_at == case["check_in"] + timedelta(days=2)
    finally:
        resume_room_lock.set()
        executor.shutdown(wait=True)
        if pause_listener_attached and delayed_connection is not None:
            event.remove(delayed_connection, "before_cursor_execute", pause_before_room_lock)
        if delayed_session is not None:
            delayed_session.rollback()
            delayed_session.close()
        winner_session.rollback()
        winner_session.close()
        _cleanup_room_block_case(pg_engine, hotel_id=hotel_id)
