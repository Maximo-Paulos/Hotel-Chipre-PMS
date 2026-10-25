"""PostgreSQL regressions for allocation freshness and room-lock serialization.

These tests require the repository's fail-closed ``pg_engine`` fixture. Run
them only against a disposable, synthetic-only PostgreSQL database.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import app.services.allocation_runtime_service as allocation_runtime_service
from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationPolicyVersion,
    AllocationRunStatusEnum,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.reservation import ReservationCreate
from app.services.allocation_runtime_service import (
    AllocationRuntimeError,
    accept_allocation_run,
    run_persisted_allocation,
)
from app.services.reservation_service import ReservationError, create_reservation
from app.services.tenant_context import set_tenant_hotel_context


def _seed_allocation_case(
    session_factory,
    *,
    room_count: int,
    assign_reservation: bool,
) -> dict[str, object]:
    suffix = uuid4().hex[:10].upper()
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    check_in = date.today() + timedelta(days=40)
    check_out = check_in + timedelta(days=2)
    db = session_factory()
    try:
        set_tenant_hotel_context(db, hotel_id)
        hotel = HotelConfiguration(
            id=hotel_id,
            hotel_name=f"Synthetic allocation PG {suffix}",
            subscription_active=True,
            default_currency="ARS",
            allow_overbooking=False,
        )
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic allocation PG {suffix}",
            code=f"APG{suffix[:7]}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        db.add_all([hotel, category])
        db.flush()

        rooms = [
            Room(
                hotel_id=hotel_id,
                room_number=f"{suffix[:6]}-{index}",
                floor=index,
                category_id=category.id,
                status=RoomStatusEnum.AVAILABLE,
                is_active=True,
                is_accessible=True,
                score=index,
            )
            for index in range(1, room_count + 1)
        ]
        guests = [
            Guest(
                hotel_id=hotel_id,
                first_name=f"Synthetic{index}",
                last_name="Allocation",
                terms_accepted=True,
            )
            for index in range(1, 4)
        ]
        db.add_all([*rooms, *guests])
        db.flush()

        reservation = Reservation(
            hotel_id=hotel_id,
            confirmation_code=f"APG-{suffix}",
            guest_id=guests[0].id,
            room_id=rooms[0].id if assign_reservation else None,
            category_id=category.id,
            check_in_date=check_in,
            check_out_date=check_out,
            total_amount=Decimal("200.00"),
            amount_paid=Decimal("0.00"),
            deposit_amount=Decimal("0.00"),
            status=ReservationStatusEnum.PENDING,
            allocation_status="assigned" if assign_reservation else "unassigned",
            num_adults=1,
            num_children=0,
        )
        db.add(reservation)
        db.commit()
        return {
            "hotel_id": hotel_id,
            "category_id": category.id,
            "room_ids": [room.id for room in rooms],
            "guest_ids": [guest.id for guest in guests],
            "reservation_id": reservation.id,
            "check_in": check_in,
            "check_out": check_out,
        }
    finally:
        db.close()


def _reservation_payload(
    *,
    guest_id: int,
    category_id: int,
    check_in: date,
    check_out: date,
    room_id: int | None,
) -> ReservationCreate:
    return ReservationCreate(
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=check_in,
        check_out_date=check_out,
        total_amount=Decimal("200.00"),
        target_currency="ARS",
    )


def _run_allocation(
    db,
    *,
    hotel_id: int,
    check_in: date,
    check_out: date,
    **kwargs,
):
    return run_persisted_allocation(
        db,
        hotel_id=hotel_id,
        trigger_type="postgres_allocation_runtime_regression",
        apply=True,
        horizon_start=check_in - timedelta(days=1),
        horizon_end=check_out + timedelta(days=1),
        **kwargs,
    )


def _wait_for_postgres_lock_wait(pg_engine, application_name: str, *, timeout: float = 8.0) -> bool:
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        with pg_engine.connect() as monitor:
            waiting = monitor.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT 1 FROM pg_stat_activity AS activity "
                    "WHERE activity.application_name = :application_name "
                    "AND activity.wait_event_type = 'Lock' "
                    "AND cardinality(pg_blocking_pids(activity.pid)) > 0"
                    ")"
                ),
                {"application_name": application_name},
            ).scalar_one()
        if waiting:
            return True
        sleep(0.05)
    return False


def test_postgres_autoapply_rejects_room_taken_after_solver_snapshot(pg_engine, monkeypatch):
    """A competing committed booking between solve and apply must fail closed."""
    assert pg_engine.dialect.name == "postgresql"
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    case = _seed_allocation_case(session_factory, room_count=1, assign_reservation=False)
    hotel_id = int(case["hotel_id"])
    category_id = int(case["category_id"])
    room_id = case["room_ids"][0]
    guest_ids = case["guest_ids"]
    reservation_id = int(case["reservation_id"])
    check_in = case["check_in"]
    check_out = case["check_out"]

    original_validate = allocation_runtime_service._lock_and_validate_initial_assignments

    def commit_competing_booking_before_revalidation(db, **kwargs):
        competitor = session_factory()
        try:
            set_tenant_hotel_context(competitor, hotel_id)
            create_reservation(
                competitor,
                _reservation_payload(
                    guest_id=guest_ids[1],
                    category_id=category_id,
                    check_in=check_in,
                    check_out=check_out,
                    room_id=room_id,
                ),
                hotel_id=hotel_id,
            )
            competitor.commit()
        finally:
            competitor.close()
        return original_validate(db, **kwargs)

    monkeypatch.setattr(
        allocation_runtime_service,
        "_lock_and_validate_initial_assignments",
        commit_competing_booking_before_revalidation,
    )

    allocation = session_factory()
    try:
        set_tenant_hotel_context(allocation, hotel_id)
        result = _run_allocation(
            allocation,
            hotel_id=hotel_id,
            check_in=check_in,
            check_out=check_out,
        )
        allocation.commit()
        assignment = (
            allocation.query(AllocationAssignment)
            .filter(
                AllocationAssignment.hotel_id == hotel_id,
                AllocationAssignment.allocation_run_id == result.run.id,
                AllocationAssignment.reservation_id == reservation_id,
            )
            .one()
        )
        reservation = allocation.query(Reservation).filter_by(id=reservation_id, hotel_id=hotel_id).one()
        assert result.solver_result.success is False
        assert result.run.status == AllocationRunStatusEnum.FAILED
        assert assignment.status == AllocationAssignmentStatusEnum.MANUAL_REVIEW
        assert reservation.room_id is None
        assert reservation.allocation_status == "manual_review"
        assert reservation.requires_manual_review is True
    finally:
        allocation.close()


@pytest.mark.parametrize("stale_change", ["policy", "fx"])
def test_postgres_acceptance_rejects_stale_policy_or_fx_configuration(pg_engine, stale_change):
    assert pg_engine.dialect.name == "postgresql"
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    case = _seed_allocation_case(session_factory, room_count=2, assign_reservation=True)
    hotel_id = int(case["hotel_id"])
    reservation_id = int(case["reservation_id"])
    room_ids = case["room_ids"]
    check_in = case["check_in"]
    check_out = case["check_out"]

    allocation = session_factory()
    try:
        set_tenant_hotel_context(allocation, hotel_id)
        result = _run_allocation(
            allocation,
            hotel_id=hotel_id,
            check_in=check_in,
            check_out=check_out,
            forbidden_room_ids_by_reservation={reservation_id: {room_ids[0]}},
        )
        allocation.commit()
        assert result.solver_result.success is True
    finally:
        allocation.close()

    change = session_factory()
    try:
        set_tenant_hotel_context(change, hotel_id)
        reservation = change.query(Reservation).filter_by(id=reservation_id, hotel_id=hotel_id).one()
        original_room_id = reservation.room_id
        if stale_change == "policy":
            current = (
                change.query(AllocationPolicyVersion)
                .filter(AllocationPolicyVersion.id == result.run.policy_version_id)
                .one()
            )
            current.is_published = False
            change.add(
                AllocationPolicyVersion(
                    hotel_id=hotel_id,
                    profile_id=current.profile_id,
                    version_number=current.version_number + 1,
                    source="manual",
                    constraints_json=current.constraints_json,
                    weights_json=current.weights_json,
                    prompt_summary="Synthetic PostgreSQL stale-policy regression",
                    is_published=True,
                )
            )
            expected_error = "active allocation policy changed"
        else:
            hotel = change.query(HotelConfiguration).filter_by(id=hotel_id).one()
            hotel.default_currency = "USD"
            expected_error = "FX configuration changed"
        change.commit()
    finally:
        change.close()

    acceptance = session_factory()
    try:
        set_tenant_hotel_context(acceptance, hotel_id)
        with pytest.raises(AllocationRuntimeError, match=expected_error):
            accept_allocation_run(
                acceptance,
                hotel_id=hotel_id,
                run_id=result.run.id,
                user_id=None,
            )
        acceptance.rollback()
    finally:
        acceptance.close()

    verification = session_factory()
    try:
        set_tenant_hotel_context(verification, hotel_id)
        reservation = verification.query(Reservation).filter_by(id=reservation_id, hotel_id=hotel_id).one()
        assignment = (
            verification.query(AllocationAssignment)
            .filter_by(
                hotel_id=hotel_id,
                allocation_run_id=result.run.id,
                reservation_id=reservation_id,
            )
            .one()
        )
        assert reservation.room_id == original_room_id == room_ids[0]
        assert assignment.status == AllocationAssignmentStatusEnum.PROPOSED
    finally:
        verification.close()


def test_postgres_autoapply_serializes_with_concurrent_reservation_creation(pg_engine, monkeypatch):
    """Creation waits for allocation's room lock and then observes its booking."""
    assert pg_engine.dialect.name == "postgresql"
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    case = _seed_allocation_case(session_factory, room_count=1, assign_reservation=False)
    hotel_id = int(case["hotel_id"])
    category_id = int(case["category_id"])
    room_id = case["room_ids"][0]
    reservation_id = int(case["reservation_id"])
    guest_ids = case["guest_ids"]
    check_in = case["check_in"]
    check_out = case["check_out"]
    suffix = uuid4().hex[:8]
    creator_application_name = f"alloc-create-{suffix}"

    allocation_has_room_lock = Event()
    allow_allocation_to_finish = Event()
    original_validate = allocation_runtime_service._lock_and_validate_initial_assignments

    def pause_after_room_lock(db, **kwargs):
        reservations_by_id = original_validate(db, **kwargs)
        if db.info.get("allocation_postgres_race_owner"):
            allocation_has_room_lock.set()
            if not allow_allocation_to_finish.wait(timeout=15):
                raise TimeoutError("allocation lock test timed out waiting for release")
        return reservations_by_id

    monkeypatch.setattr(allocation_runtime_service, "_lock_and_validate_initial_assignments", pause_after_room_lock)

    def autoassign():
        db = session_factory()
        try:
            set_tenant_hotel_context(db, hotel_id)
            db.execute(text("SET LOCAL statement_timeout = '12000ms'"))
            db.info["allocation_postgres_race_owner"] = True
            result = _run_allocation(
                db,
                hotel_id=hotel_id,
                check_in=check_in,
                check_out=check_out,
            )
            db.commit()
            return result.run.id
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def create_competing_reservation():
        db = session_factory()
        try:
            set_tenant_hotel_context(db, hotel_id)
            db.execute(text("SET LOCAL statement_timeout = '12000ms'"))
            db.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": creator_application_name},
            )
            try:
                reservation = create_reservation(
                    db,
                    _reservation_payload(
                        guest_id=guest_ids[1],
                        category_id=category_id,
                        check_in=check_in,
                        check_out=check_out,
                        room_id=None,
                    ),
                    hotel_id=hotel_id,
                )
                db.commit()
                return ("created", reservation.id)
            except ReservationError as exc:
                db.rollback()
                return ("rejected", str(exc))
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    blocked_while_allocation_holds_room = False
    with ThreadPoolExecutor(max_workers=2) as executor:
        allocation_future = executor.submit(autoassign)
        creator_future = None
        try:
            assert allocation_has_room_lock.wait(timeout=10), "allocation did not acquire its room lock"
            creator_future = executor.submit(create_competing_reservation)
            blocked_while_allocation_holds_room = _wait_for_postgres_lock_wait(
                pg_engine,
                creator_application_name,
            )
        finally:
            allow_allocation_to_finish.set()
        run_id = allocation_future.result(timeout=20)
        assert creator_future is not None
        creator_result = creator_future.result(timeout=20)

    assert blocked_while_allocation_holds_room is True
    assert creator_result[0] == "rejected"
    assert "No hay habitaciones disponibles" in creator_result[1]

    verification = session_factory()
    try:
        set_tenant_hotel_context(verification, hotel_id)
        allocation_reservation = verification.query(Reservation).filter_by(
            id=reservation_id,
            hotel_id=hotel_id,
        ).one()
        assignments = (
            verification.query(AllocationAssignment)
            .filter_by(
                hotel_id=hotel_id,
                allocation_run_id=run_id,
                reservation_id=reservation_id,
            )
            .all()
        )
        overlapping_reservations = verification.query(Reservation).filter(
            Reservation.hotel_id == hotel_id,
            Reservation.room_id == room_id,
            Reservation.status.notin_([ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT]),
            Reservation.check_in_date < check_out,
            Reservation.check_out_date > check_in,
        ).all()
        assert allocation_reservation.room_id == room_id
        assert len(overlapping_reservations) == 1
        assert len(assignments) == 1
        assert assignments[0].status == AllocationAssignmentStatusEnum.APPLIED
    finally:
        verification.close()
