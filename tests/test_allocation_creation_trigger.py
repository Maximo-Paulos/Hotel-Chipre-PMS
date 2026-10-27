from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationRun,
    AllocationRunStatusEnum,
    ReservationAllocationLock,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.room import Room, RoomCategory
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.reservation import ReservationCreate
from app.services.allocation_runtime_service import (
    AllocationRuntimeError,
    accept_allocation_run,
    auto_apply_safe_allocation_run,
    run_persisted_allocation,
    set_reservation_reassignment_lock,
)
from app.services.allocation_trigger_service import (
    _request_allocation_proposal,
    trigger_reoptimization_bg,
)
from app.services.distributed_lock import DistributedLockBusy
from app.services.reservation_service import create_reservation
from app.services.tenant_context import set_tenant_hotel_context
from app.services.timezones import hotel_today
from app.tasks.allocation_tasks import (
    _process_hotel_request,
    process_recalculation_requests,
)


def _reservation_payload(*, guest_id, category_id, source=ReservationSourceEnum.DIRECT, waitlisted=False):
    today = date.today()
    return ReservationCreate(
        guest_id=guest_id,
        category_id=category_id,
        check_in_date=today + timedelta(days=3),
        check_out_date=today + timedelta(days=5),
        source=source,
        is_wait_listed=waitlisted,
    )


def _pending_requests(db, hotel_id=1):
    return (
        db.query(AllocationRun)
        .filter(
            AllocationRun.hotel_id == hotel_id,
            AllocationRun.trigger_type == "reservation_created_auto_proposal",
            AllocationRun.status == AllocationRunStatusEnum.PENDING,
        )
        .all()
    )


def test_direct_and_inbound_ota_bookings_request_one_coalesced_proposal(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    direct = create_reservation(
        db,
        _reservation_payload(guest_id=sample_guest.id, category_id=sample_categories[0].id),
        hotel_id=1,
    )
    ota = create_reservation(
        db,
        _reservation_payload(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            source=ReservationSourceEnum.BOOKING,
        ),
        hotel_id=1,
    )

    assert direct.room_id is not None
    assert ota.room_id is not None
    assert direct.room_id != ota.room_id
    assert len(_pending_requests(db)) == 1


def test_waitlisted_or_out_of_horizon_reservation_does_not_request_current_run(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    today = hotel_today(db, 1)
    waitlisted_payload = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=today + timedelta(days=3),
        check_out_date=today + timedelta(days=5),
        is_wait_listed=True,
    )
    waitlisted = create_reservation(db, waitlisted_payload, hotel_id=1)

    far_future = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        check_in_date=today + timedelta(days=95),
        check_out_date=today + timedelta(days=97),
    )
    beyond_horizon = create_reservation(db, far_future, hotel_id=1)

    assert waitlisted.room_id is None
    assert beyond_horizon.room_id is not None
    assert _pending_requests(db) == []


def test_background_worker_runs_auto_apply_for_eligible_room_moves(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    reservation = create_reservation(
        db,
        _reservation_payload(guest_id=sample_guest.id, category_id=sample_categories[0].id),
        hotel_id=1,
    )
    original_room_id = reservation.room_id
    queued = _pending_requests(db)[0]
    db.commit()

    def fake_runner(
        session, *, hotel_id, trigger_type, apply, queued_run_id, origin_key=None
    ):
        assert hotel_id == 1
        assert trigger_type == "reservation_created_auto_proposal"
        assert apply is True
        assert queued_run_id == queued.id
        run = session.query(AllocationRun).filter(AllocationRun.id == queued_run_id).one()
        run.status = AllocationRunStatusEnum.SUCCEEDED
        return SimpleNamespace(run=run)

    counts = _process_hotel_request(db, hotel_id=1, allocation_runner=fake_runner)
    db.refresh(reservation)

    assert counts == {"selected": 1, "succeeded": 1, "failed": 0, "deferred": 0}
    assert reservation.room_id == original_room_id
    assert db.query(AllocationRun).filter(AllocationRun.id == queued.id).one().status == AllocationRunStatusEnum.SUCCEEDED


def test_real_background_solver_auto_applies_eligible_moves_and_keeps_locks(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    today = hotel_today(db, 1)
    first_room, second_room = sample_rooms[:2]
    checked_in_reservation = Reservation(
        hotel_id=1,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=first_room.id,
        confirmation_code="ALLOC-LOCK-A",
        check_in_date=today + timedelta(days=1),
        check_out_date=today + timedelta(days=3),
        total_amount=100,
        status=ReservationStatusEnum.PARTIAL_CHECK_IN,
        actual_check_in=datetime.now(timezone.utc),
    )
    locked_reservation = Reservation(
        hotel_id=1,
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=first_room.id,
        confirmation_code="ALLOC-LOCK-B",
        check_in_date=today + timedelta(days=4),
        check_out_date=today + timedelta(days=6),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
        allocation_locked=True,
    )
    db.add_all([checked_in_reservation, locked_reservation])
    db.flush()
    new_reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=second_room.id,
            check_in_date=today + timedelta(days=3),
            check_out_date=today + timedelta(days=4),
        ),
        hotel_id=1,
    )
    queued = _pending_requests(db)[0]
    original_room_id = new_reservation.room_id
    db.commit()

    counts = _process_hotel_request(db, hotel_id=1)
    db.refresh(new_reservation)
    assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == 1,
            AllocationAssignment.allocation_run_id == queued.id,
            AllocationAssignment.reservation_id == new_reservation.id,
        )
        .one()
    )

    assert counts == {"selected": 1, "succeeded": 1, "failed": 0, "deferred": 0}
    assert assignment.status == AllocationAssignmentStatusEnum.APPLIED
    assert assignment.room_id == first_room.id
    assert new_reservation.room_id == first_room.id
    assert new_reservation.room_id != original_room_id
    assert db.query(RoomMoveEvent).filter(
        RoomMoveEvent.reservation_id == new_reservation.id,
        RoomMoveEvent.trigger_event == "allocation_auto_applied",
    ).count() == 1
    assert db.query(SecurityAuditLog).filter(
        SecurityAuditLog.hotel_id == 1,
        SecurityAuditLog.action == "allocation.proposal.auto_applied",
    ).count() == 1
    assert checked_in_reservation.room_id == first_room.id
    assert checked_in_reservation.actual_check_in is not None
    assert locked_reservation.room_id == first_room.id
    assert locked_reservation.allocation_locked is True
    assert db.query(RoomMoveEvent).filter(
        RoomMoveEvent.reservation_id == checked_in_reservation.id,
    ).count() == 0


def test_pending_proposal_coalesces_different_automatic_triggers(
    db, hotel_config
):
    first = _request_allocation_proposal(
        db,
        hotel_id=1,
        trigger_type="reservation_date_change",
    )
    second = _request_allocation_proposal(
        db,
        hotel_id=1,
        trigger_type="reservation_update",
    )

    assert first.id == second.id
    assert first.trigger_type == "reservation_date_change"
    assert len(_pending_requests(db)) == 0
    assert (
        db.query(AllocationRun)
        .filter(
            AllocationRun.hotel_id == 1,
            AllocationRun.trigger_type == "reservation_date_change",
            AllocationRun.status == AllocationRunStatusEnum.PENDING,
        )
        .count()
        == 1
    )


def test_automatic_proposal_requests_remain_scoped_to_their_hotel(
    db, hotel_config, sample_categories_hotel2
):
    hotel_one = _request_allocation_proposal(
        db,
        hotel_id=1,
        trigger_type="reservation_date_change",
    )
    hotel_two = _request_allocation_proposal(
        db,
        hotel_id=2,
        trigger_type="reservation_date_change",
    )

    assert hotel_one.id != hotel_two.id
    assert hotel_one.hotel_id == 1
    assert hotel_two.hotel_id == 2


def test_postgres_worker_auto_applies_only_unchecked_in_unlocked_moves(pg_session):
    """Exercise the real auto-apply path on the isolated PostgreSQL fixture."""
    db = pg_session
    hotel_id = 1
    db.add(
        HotelConfiguration(
            id=hotel_id,
            deposit_percentage=30,
            deposit_policy_configured=True,
            subscription_active=True,
        )
    )
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Auto allocation test",
        code="AUTO_TEST",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Test", last_name="Guest")
    db.add_all([category, guest])
    db.flush()
    today = hotel_today(db, hotel_id)
    first_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="101")
    second_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="102")
    db.add_all([first_room, second_room])
    db.flush()

    checked_in = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=first_room.id,
        confirmation_code="AUTO-PG-CHECKED-IN",
        check_in_date=today + timedelta(days=1),
        check_out_date=today + timedelta(days=3),
        total_amount=100,
        status=ReservationStatusEnum.PARTIAL_CHECK_IN,
        actual_check_in=datetime.now(timezone.utc),
    )
    locked = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=first_room.id,
        confirmation_code="AUTO-PG-LOCKED",
        check_in_date=today + timedelta(days=4),
        check_out_date=today + timedelta(days=6),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
        allocation_locked=True,
    )
    eligible = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=second_room.id,
        confirmation_code="AUTO-PG-ELIGIBLE",
        check_in_date=today + timedelta(days=3),
        check_out_date=today + timedelta(days=4),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    db.add_all([checked_in, locked, eligible])
    db.flush()
    original_room_id = eligible.room_id
    queued = _request_allocation_proposal(
        db,
        hotel_id=hotel_id,
        trigger_type="reservation_created_auto_proposal",
    )
    db.commit()

    counts = _process_hotel_request(db, hotel_id=hotel_id)
    db.refresh(eligible)
    db.refresh(checked_in)
    db.refresh(locked)
    assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel_id,
            AllocationAssignment.allocation_run_id == queued.id,
            AllocationAssignment.reservation_id == eligible.id,
        )
        .one()
    )

    assert counts == {"selected": 1, "succeeded": 1, "failed": 0, "deferred": 0}
    assert eligible.room_id == first_room.id
    assert eligible.room_id != original_room_id
    assert assignment.status == AllocationAssignmentStatusEnum.APPLIED
    assert checked_in.room_id == first_room.id
    assert locked.room_id == first_room.id
    assert locked.allocation_locked is True
    assert db.query(RoomMoveEvent).filter(
        RoomMoveEvent.reservation_id == checked_in.id,
    ).count() == 0
    assert db.query(SecurityAuditLog).filter(
        SecurityAuditLog.hotel_id == hotel_id,
        SecurityAuditLog.action == "allocation.proposal.auto_applied",
    ).count() == 1


def test_postgres_locked_move_requires_one_time_approval_and_keeps_pin(pg_session):
    db = pg_session
    hotel_id = 1
    db.add_all([
        HotelConfiguration(
            id=hotel_id,
            deposit_percentage=30,
            deposit_policy_configured=True,
            subscription_active=True,
        ),
        User(id=9901, email="allocation-approver@example.test", password_hash="synthetic-only"),
    ])
    db.flush()
    set_tenant_hotel_context(db, hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name="One-time approval test",
        code="ONE_TIME_APPROVAL",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Test", last_name="Guest")
    db.add_all([category, guest])
    db.flush()
    today = hotel_today(db, hotel_id)
    first_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="201")
    second_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="202")
    db.add_all([first_room, second_room])
    db.flush()

    first = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=first_room.id,
        confirmation_code="ONE-TIME-FIRST",
        check_in_date=today + timedelta(days=10),
        check_out_date=today + timedelta(days=12),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    mover = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=second_room.id,
        confirmation_code="ONE-TIME-MOVER",
        check_in_date=today + timedelta(days=12),
        check_out_date=today + timedelta(days=13),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    second = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=first_room.id,
        confirmation_code="ONE-TIME-SECOND",
        check_in_date=today + timedelta(days=13),
        check_out_date=today + timedelta(days=15),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    db.add_all([first, mover, second])
    db.flush()
    set_reservation_reassignment_lock(
        db,
        hotel_id=hotel_id,
        reservation_id=mover.id,
        locked=True,
        reason="Guest requested no room changes",
        user_id=9901,
    )
    db.flush()

    result = run_persisted_allocation(
        db,
        hotel_id=hotel_id,
        trigger_type="manual_api_recalculate",
        apply=False,
        horizon_start=today + timedelta(days=9),
        horizon_end=today + timedelta(days=16),
    )
    proposed_move = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel_id,
            AllocationAssignment.allocation_run_id == result.run.id,
            AllocationAssignment.reservation_id == mover.id,
        )
        .one()
    )
    assert proposed_move.room_id == first_room.id
    assert proposed_move.status == AllocationAssignmentStatusEnum.PROPOSED

    with pytest.raises(AllocationRuntimeError, match="authenticated user"):
        accept_allocation_run(
            db,
            hotel_id=hotel_id,
            run_id=result.run.id,
            user_id=None,
            explicitly_approved_locked_reservation_ids={mover.id},
        )

    details = accept_allocation_run(
        db,
        hotel_id=hotel_id,
        run_id=result.run.id,
        user_id=9901,
        explicitly_approved_locked_reservation_ids={mover.id},
    )
    db.refresh(mover)
    lock = (
        db.query(ReservationAllocationLock)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.reservation_id == mover.id,
            ReservationAllocationLock.is_active.is_(True),
        )
        .one()
    )
    assert mover.room_id == first_room.id
    assert mover.allocation_locked is True
    assert lock.locked_room_id == first_room.id
    assert any(
        item.reservation_id == mover.id
        and item.status == AllocationAssignmentStatusEnum.APPLIED
        for item in details.assignments
    )

    future_run = run_persisted_allocation(
        db,
        hotel_id=hotel_id,
        trigger_type="reservation_update",
        apply=True,
        horizon_start=today + timedelta(days=9),
        horizon_end=today + timedelta(days=16),
    )
    assert future_run.solver_result.assignments[mover.id] == first_room.id


def test_postgres_auto_apply_keeps_locked_move_pending_for_one_time_approval(pg_session):
    db = pg_session
    hotel_id = 1
    approver_id = 9902
    db.add_all(
        [
            HotelConfiguration(
                id=hotel_id,
                deposit_percentage=30,
                deposit_policy_configured=True,
                subscription_active=True,
            ),
            User(
                id=approver_id,
                email="allocation-auto-approver@example.test",
                password_hash="synthetic-only",
            ),
        ]
    )
    db.flush()
    set_tenant_hotel_context(db, hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Automatic exception test",
        code="AUTO_EXCEPTION",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Test", last_name="Guest")
    db.add_all([category, guest])
    db.flush()
    today = hotel_today(db, hotel_id)
    first_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="301")
    second_room = Room(hotel_id=hotel_id, category_id=category.id, room_number="302")
    db.add_all([first_room, second_room])
    db.flush()

    checked_in = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=first_room.id,
        confirmation_code="AUTO-EXCEPTION-CHECKED-IN",
        check_in_date=today - timedelta(days=1),
        check_out_date=today + timedelta(days=2),
        total_amount=100,
        status=ReservationStatusEnum.PARTIAL_CHECK_IN,
        actual_check_in=datetime.now(timezone.utc),
    )
    locked = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=second_room.id,
        confirmation_code="AUTO-EXCEPTION-LOCKED",
        check_in_date=today + timedelta(days=2),
        check_out_date=today + timedelta(days=3),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    eligible = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        category_id=category.id,
        room_id=second_room.id,
        confirmation_code="AUTO-EXCEPTION-ELIGIBLE",
        check_in_date=today + timedelta(days=3),
        check_out_date=today + timedelta(days=4),
        total_amount=100,
        status=ReservationStatusEnum.PENDING,
    )
    db.add_all([checked_in, locked, eligible])
    db.flush()
    set_reservation_reassignment_lock(
        db,
        hotel_id=hotel_id,
        reservation_id=locked.id,
        locked=True,
        reason="Guest requested no room changes",
        user_id=approver_id,
    )
    db.flush()

    result = run_persisted_allocation(
        db,
        hotel_id=hotel_id,
        trigger_type="manual_api_recalculate",
        apply=True,
        horizon_start=today,
        horizon_end=today + timedelta(days=6),
    )
    details = auto_apply_safe_allocation_run(
        db, hotel_id=hotel_id, run_id=result.run.id
    )
    assert details is not None
    db.refresh(checked_in)
    db.refresh(locked)
    db.refresh(eligible)
    assignments = {item.reservation_id: item for item in details.assignments}
    assert checked_in.room_id == first_room.id
    assert assignments[checked_in.id].status != AllocationAssignmentStatusEnum.PROPOSED
    assert locked.room_id == second_room.id
    assert assignments[locked.id].status == AllocationAssignmentStatusEnum.PROPOSED
    assert assignments[locked.id].room_id == first_room.id
    assert eligible.room_id == first_room.id
    assert assignments[eligible.id].status == AllocationAssignmentStatusEnum.APPLIED

    approve_lock = (
        db.query(ReservationAllocationLock)
        .filter(
            ReservationAllocationLock.hotel_id == hotel_id,
            ReservationAllocationLock.reservation_id == locked.id,
            ReservationAllocationLock.is_active.is_(True),
        )
        .one()
    )
    assert approve_lock.locked_room_id == second_room.id

    reviewed = accept_allocation_run(
        db,
        hotel_id=hotel_id,
        run_id=result.run.id,
        user_id=approver_id,
        explicitly_approved_locked_reservation_ids={locked.id},
    )
    db.refresh(locked)
    db.refresh(approve_lock)
    assert locked.room_id == first_room.id
    assert locked.allocation_locked is True
    assert approve_lock.locked_room_id == first_room.id
    assert any(
        item.reservation_id == locked.id
        and item.status == AllocationAssignmentStatusEnum.APPLIED
        for item in reviewed.assignments
    )

    future_run = run_persisted_allocation(
        db,
        hotel_id=hotel_id,
        trigger_type="reservation_update",
        apply=True,
        horizon_start=today,
        horizon_end=today + timedelta(days=6),
    )
    auto_apply_safe_allocation_run(
        db, hotel_id=hotel_id, run_id=future_run.run.id
    )
    db.refresh(locked)
    assert locked.room_id == first_room.id
    assert locked.allocation_locked is True


def test_background_trigger_commits_before_best_effort_celery_dispatch(
    db, hotel_config, monkeypatch
):
    factory = sessionmaker(
        bind=db.connection(),
        join_transaction_mode="create_savepoint",
    )
    monkeypatch.setattr("app.database.get_session_factory", lambda: factory)
    dispatches = []

    def fail_dispatch(**kwargs):
        dispatches.append(kwargs)
        raise RuntimeError("broker unavailable")

    monkeypatch.setattr(process_recalculation_requests, "apply_async", fail_dispatch)

    trigger_reoptimization_bg(
        hotel_id=1,
        trigger_type="reservation_date_change",
        origin_key="d50e100a-609a-43de-8f23-94e2720bd81c",
    )

    pending = (
        db.query(AllocationRun)
        .filter(
            AllocationRun.hotel_id == 1,
            AllocationRun.trigger_type == "reservation_date_change",
            AllocationRun.status == AllocationRunStatusEnum.PENDING,
        )
        .one()
    )
    assert pending.id is not None
    assert dispatches == [
        {
            "kwargs": {
                "hotel_id": 1,
                "origin_key": "d50e100a-609a-43de-8f23-94e2720bd81c",
            },
            "retry": False,
        }
    ]


def test_worker_defers_when_allocation_lock_is_busy_and_keeps_request_retryable(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    create_reservation(
        db,
        _reservation_payload(guest_id=sample_guest.id, category_id=sample_categories[0].id),
        hotel_id=1,
    )
    queued = _pending_requests(db)[0]
    db.commit()

    def busy_runner(*args, **kwargs):
        raise DistributedLockBusy("shared allocation lock is busy")

    counts = _process_hotel_request(db, hotel_id=1, allocation_runner=busy_runner)

    assert counts == {"selected": 1, "succeeded": 0, "failed": 0, "deferred": 1}
    assert db.query(AllocationRun).filter(AllocationRun.id == queued.id).one().status == AllocationRunStatusEnum.PENDING


def test_worker_failure_is_audited_without_changing_reservation_assignment(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    reservation = create_reservation(
        db,
        _reservation_payload(guest_id=sample_guest.id, category_id=sample_categories[0].id),
        hotel_id=1,
    )
    original_room_id = reservation.room_id
    queued = _pending_requests(db)[0]
    db.commit()

    def failing_runner(*args, **kwargs):
        raise RuntimeError("solver backend failed")

    counts = _process_hotel_request(db, hotel_id=1, allocation_runner=failing_runner)
    db.refresh(reservation)
    failed_run = db.query(AllocationRun).filter(AllocationRun.id == queued.id).one()

    assert counts == {"selected": 1, "succeeded": 0, "failed": 1, "deferred": 0}
    assert reservation.room_id == original_room_id
    assert failed_run.status == AllocationRunStatusEnum.FAILED
    assert failed_run.error_message == "Automatic room optimization failed; manual recalculation is available."
