from datetime import date, timedelta
from types import SimpleNamespace

from sqlalchemy.orm import sessionmaker

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationRun,
    AllocationRunStatusEnum,
)
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.schemas.reservation import ReservationCreate
from app.services.allocation_trigger_service import (
    _request_allocation_proposal,
    trigger_reoptimization_bg,
)
from app.services.distributed_lock import DistributedLockBusy
from app.services.reservation_service import create_reservation
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


def test_background_worker_generates_only_a_reviewable_run_and_preserves_first_fit(
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
        assert apply is False
        assert queued_run_id == queued.id
        run = session.query(AllocationRun).filter(AllocationRun.id == queued_run_id).one()
        run.status = AllocationRunStatusEnum.SUCCEEDED
        return SimpleNamespace(run=run)

    counts = _process_hotel_request(db, hotel_id=1, allocation_runner=fake_runner)
    db.refresh(reservation)

    assert counts == {"selected": 1, "succeeded": 1, "failed": 0, "deferred": 0}
    assert reservation.room_id == original_room_id
    assert db.query(AllocationRun).filter(AllocationRun.id == queued.id).one().status == AllocationRunStatusEnum.SUCCEEDED


def test_real_background_solver_stores_room_moves_as_proposals(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    today = hotel_today(db, 1)
    first_room, second_room = sample_rooms[:2]
    db.add_all(
        [
            Reservation(
                hotel_id=1,
                guest_id=sample_guest.id,
                category_id=sample_categories[0].id,
                room_id=first_room.id,
                confirmation_code="ALLOC-LOCK-A",
                check_in_date=today + timedelta(days=1),
                check_out_date=today + timedelta(days=3),
                total_amount=100,
                status=ReservationStatusEnum.PENDING,
                allocation_locked=True,
            ),
            Reservation(
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
            ),
        ]
    )
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
    assert assignment.status == AllocationAssignmentStatusEnum.PROPOSED
    assert assignment.room_id == first_room.id
    assert new_reservation.room_id == original_room_id


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
