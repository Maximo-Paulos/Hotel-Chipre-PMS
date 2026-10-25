import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy.dialects import postgresql

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationExplanation,
    AllocationPolicyVersion,
    ReservationAllocationLock,
    SolverMetric,
)
from app.models.commercial import FxPolicy
from app.models.company import Company
from app.models.domain_event_outbox import DomainEventOutbox
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import RoomMoveEvent, RoomMovementGroup
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.allocation_engine import (
    AllocationResult,
    ReservationSlot,
    RoomSlot,
    build_slots_from_db,
    run_allocation,
)
from app.services.allocation_runtime_service import (
    AllocationRuntimeError,
    accept_allocation_run,
    run_persisted_allocation,
)


def _slot(reservation_id: int, *, mobility: bool = False, room_id: int | None = None, locked: bool = False):
    return ReservationSlot(
        reservation_id=reservation_id,
        category_id=1,
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 4),
        current_room_id=room_id,
        is_locked=locked,
        mobility_restriction=mobility,
    )


def test_mobility_restriction_prefers_lowest_compatible_floor():
    rooms = [
        RoomSlot(room_id=1, room_number="001", category_id=1, floor=0, score=1, is_accessible=True),
        RoomSlot(room_id=2, room_number="201", category_id=1, floor=2, score=10, is_accessible=True),
        RoomSlot(room_id=3, room_number="101", category_id=1, floor=1, score=10, is_accessible=False),
    ]

    result = run_allocation([_slot(1, mobility=True)], rooms)

    assert result.success is True
    assert result.assignments[1] == 1


def test_score_only_breaks_equivalent_room_tie():
    rooms = [
        RoomSlot(room_id=1, room_number="101", category_id=1, floor=1, score=1, is_accessible=True),
        RoomSlot(room_id=2, room_number="102", category_id=1, floor=1, score=10, is_accessible=True),
    ]

    result = run_allocation([_slot(1)], rooms)

    assert result.success is True
    assert result.assignments[1] == 2


def test_net_revenue_objective_prioritizes_after_discount_commission_value():
    reservations = [
        ReservationSlot(
            reservation_id=11,
            category_id=1,
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 5),
            current_room_id=None,
            is_locked=False,
            net_revenue_minor_units=10_000,
            currency_code="ARS",
        ),
        ReservationSlot(
            reservation_id=12,
            category_id=1,
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 5),
            current_room_id=None,
            is_locked=False,
            net_revenue_minor_units=30_000,
            currency_code="ARS",
        ),
    ]
    room = RoomSlot(room_id=101, room_number="101", category_id=1)

    result = run_allocation(
        reservations,
        [room],
        policy_constraints={"optimization_objective": "net_revenue"},
    )

    assert result.assignments == {12: 101}
    assert result.unassigned_reservations == [11]


def test_net_revenue_objective_fails_closed_before_int64_overflow():
    oversized = replace(_slot(19), net_revenue_minor_units=2**63)

    result = run_allocation(
        [oversized],
        [RoomSlot(room_id=101, room_number="101", category_id=1)],
        policy_constraints={"optimization_objective": "net_revenue"},
    )

    assert result.success is False
    assert "safe integer range" in result.error


def test_combined_objective_uses_configured_weight_and_net_revenue_rejects_mixed_currencies():
    reservations = [
        ReservationSlot(
            reservation_id=21,
            category_id=1,
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 5),
            current_room_id=None,
            is_locked=False,
            net_revenue_minor_units=10_000,
            currency_code="ARS",
        ),
        ReservationSlot(
            reservation_id=22,
            category_id=1,
            check_in=date(2026, 7, 1),
            check_out=date(2026, 7, 3),
            current_room_id=None,
            is_locked=False,
            net_revenue_minor_units=30_000,
            currency_code="ARS",
        ),
    ]
    room = RoomSlot(room_id=101, room_number="101", category_id=1)

    occupancy_weighted = run_allocation(
        reservations,
        [room],
        policy_constraints={"optimization_objective": "combined"},
        policy_weights={"combined_revenue_weight": 0.2},
    )
    revenue_weighted = run_allocation(
        reservations,
        [room],
        policy_constraints={"optimization_objective": "combined"},
        policy_weights={"combined_revenue_weight": 0.8},
    )
    mixed_currency = run_allocation(
        [reservations[0], replace(reservations[1], reservation_id=23, currency_code="USD")],
        [room],
        policy_constraints={"optimization_objective": "net_revenue"},
    )

    assert occupancy_weighted.assignments == {21: 101}
    assert revenue_weighted.assignments == {22: 101}
    assert occupancy_weighted.primary_status == "OPTIMAL"
    assert revenue_weighted.primary_status == "OPTIMAL"
    assert mixed_currency.success is False
    assert "Mixed-currency" in mixed_currency.error


def test_configured_primary_objective_cannot_be_overridden_by_room_preferences():
    short_exact = ReservationSlot(
        reservation_id=31,
        category_id=2,
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 3),
        current_room_id=None,
        is_locked=False,
        net_revenue_minor_units=10_000_000,
        currency_code="ARS",
        allowed_category_ids=[2],
    )
    longer_fallback = ReservationSlot(
        reservation_id=32,
        category_id=1,
        check_in=date(2026, 7, 1),
        check_out=date(2026, 7, 4),
        current_room_id=None,
        is_locked=False,
        net_revenue_minor_units=10_000_001,
        currency_code="ARS",
        allowed_category_ids=[2],
        category_priority_by_id={2: 10},
    )
    room = RoomSlot(room_id=101, room_number="101", category_id=2)

    result = run_allocation(
        [short_exact, longer_fallback],
        [room],
        policy_constraints={"optimization_objective": "net_revenue"},
    )

    assert result.assignments == {32: 101}
    assert result.objective_value == 10_000_001
    assert result.primary_status == "OPTIMAL"


def test_solver_only_locks_checked_in_or_explicitly_pinned_reservations(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=5)
    company = Company(
        hotel_id=hotel.id,
        legal_name="Protected SA",
        display_name="Protected",
        requires_signature=True,
    )
    db.add(company)
    db.flush()
    reservations = [
        _reservation(db, hotel.id, guests[0].id, category.id, rooms[0].id, "CORP", company_id=company.id),
        _reservation(db, hotel.id, guests[1].id, category.id, rooms[1].id, "MANUAL", allocation_locked=True),
        _reservation(db, hotel.id, guests[2].id, category.id, rooms[2].id, "PRE", status=ReservationStatusEnum.PRE_CHECK_IN),
        _reservation(db, hotel.id, guests[3].id, category.id, rooms[3].id, "CHECKED", status=ReservationStatusEnum.CHECKED_IN),
    ]
    db.add(
        ReservationAllocationLock(
            hotel_id=hotel.id,
            reservation_id=reservations[1].id,
            locked_room_id=rooms[1].id,
            lock_reason_code="manual_pin",
            is_active=True,
        )
    )
    db.flush()

    slots, room_slots = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
    )
    locked_by_id = {slot.reservation_id: slot.is_locked for slot in slots}
    result = run_allocation(slots, room_slots, optimization_horizon=(date(2026, 7, 1), date(2026, 7, 5)))

    assert locked_by_id == {
        reservations[0].id: False,  # company features do not create an implicit pin
        reservations[1].id: True,  # explicit No permitir reasignar flag and lock row
        reservations[2].id: False,  # PRE_CHECK_IN alone is not an assignment lock
        reservations[3].id: True,  # a guest already checked in cannot move
    }
    assert result.success is True
    assert result.assignments[reservations[0].id] == rooms[0].id
    assert result.assignments[reservations[1].id] == rooms[1].id
    assert result.assignments[reservations[2].id] == rooms[2].id
    assert reservations[1].id not in result.moved_reservations
    assert reservations[3].id not in result.moved_reservations


def test_paid_reservation_with_room_is_still_eligible_for_reassignment(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    confirmed = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        rooms[0].id,
        "ROOM-AND-PAID",
        amount_paid=25,
    )
    competing = _reservation(
        db,
        hotel.id,
        guests[1].id,
        category.id,
        rooms[0].id,
        "UNPAID-COMPETITOR",
    )
    db.flush()

    slots, room_slots = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
    )
    slot_by_id = {slot.reservation_id: slot for slot in slots}
    result = run_allocation(
        slots,
        room_slots,
        optimization_horizon=(date(2026, 7, 1), date(2026, 7, 5)),
    )

    assert slot_by_id[confirmed.id].is_locked is False
    assert result.success is True
    # Both bookings remain eligible for the solver. Since both had the same
    # original room, either may be the one retained when their objectives tie.
    assert set(result.assignments) == {confirmed.id, competing.id}
    assert set(result.assignments.values()) == {rooms[0].id, rooms[1].id}


def test_solver_loads_net_revenue_before_tax_after_commission(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=1)
    reservation = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        rooms[0].id,
        "NET-SNAPSHOT",
    )
    reservation.total_amount = 110
    reservation.subtotal_amount = 100
    reservation.tax_amount = 10
    reservation.commission_amount = 7.25
    db.flush()

    slots, _rooms = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
    )

    assert slots[0].net_revenue_minor_units == 9_275
    assert slots[0].currency_code == "ARS"


def test_mixed_currency_revenue_uses_fresh_hotel_fx_snapshot_only(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=1)
    ars_reservation = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        rooms[0].id,
        "ARS-REVENUE",
    )
    usd_reservation = _reservation(
        db,
        hotel.id,
        guests[1].id,
        category.id,
        rooms[0].id,
        "USD-REVENUE",
    )
    ars_reservation.total_amount = 10_000
    ars_reservation.subtotal_amount = 10_000
    usd_reservation.total_amount = 100
    usd_reservation.subtotal_amount = 100
    usd_reservation.currency_code = "USD"
    db.flush()

    slots, _rooms = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        policy_constraints={"optimization_objective": "net_revenue"},
    )
    assert {slot.currency_code for slot in slots} == {"ARS", "USD"}
    missing_quote = run_allocation(
        slots,
        [RoomSlot(room_id=101, room_number="101", category_id=category.id)],
        policy_constraints={"optimization_objective": "net_revenue"},
    )
    assert missing_quote.success is False
    assert "fresh hotel-scoped FX snapshot" in missing_quote.error

    now = datetime.now(timezone.utc)
    snapshot = FxRateSnapshot(
        hotel_id=hotel.id,
        rate_type="oficial",
        provider_market="oficial",
        moneda="USD",
        compra=1_000,
        venta=1_100,
        fetched_at=now,
        provider_updated_at=now,
        selected_side="venta",
        base_currency="ARS",
        quote_currency="USD",
        applied_rate=1_100,
        source="synthetic-test",
    )
    db.add(snapshot)
    db.flush()

    normalized_slots, _rooms = build_slots_from_db(
        db,
        hotel_id=hotel.id,
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 5),
        policy_constraints={"optimization_objective": "net_revenue"},
    )
    by_source_currency = {slot.source_currency_code: slot for slot in normalized_slots}
    assert {slot.currency_code for slot in normalized_slots} == {"ARS"}
    assert by_source_currency["ARS"].net_revenue_minor_units == 1_000_000
    assert by_source_currency["USD"].net_revenue_minor_units == 11_000_000
    assert by_source_currency["USD"].fx_conversion_details["snapshot_ids"] == [snapshot.id]


def test_allocation_run_creates_movement_group_and_events(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    _reservation(db, hotel.id, guests[0].id, category.id, rooms[0].id, "LOCK1", date(2026, 7, 1), date(2026, 7, 3), allocation_locked=True)
    _reservation(db, hotel.id, guests[1].id, category.id, rooms[0].id, "LOCK2", date(2026, 7, 4), date(2026, 7, 6), allocation_locked=True)
    mover = _reservation(db, hotel.id, guests[2].id, category.id, rooms[1].id, "MOVE", date(2026, 7, 3), date(2026, 7, 4))
    db.flush()

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="test_gap_fill",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )

    allocation_assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel.id,
            AllocationAssignment.allocation_run_id == result.run.id,
            AllocationAssignment.reservation_id == mover.id,
        )
        .one()
    )
    assert allocation_assignment.status == AllocationAssignmentStatusEnum.PROPOSED
    db.refresh(mover)
    assert result.solver_result.success is True
    assert mover.room_id == rooms[1].id
    assert db.query(RoomMovementGroup).filter(RoomMovementGroup.hotel_id == hotel.id).count() == 0

    accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)
    group = db.query(RoomMovementGroup).filter(RoomMovementGroup.hotel_id == hotel.id).one()
    event = db.query(RoomMoveEvent).filter(RoomMoveEvent.movement_group_id == group.id).one()
    db.refresh(mover)
    assert mover.room_id == rooms[0].id
    assert group.trigger_reason == "test_gap_fill"
    assert event.reservation_id == mover.id
    assert event.from_room_id == rooms[1].id
    assert event.to_room_id == rooms[0].id

    accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)
    assert db.query(RoomMovementGroup).filter(RoomMovementGroup.hotel_id == hotel.id).count() == 1
    assert db.query(RoomMoveEvent).filter(RoomMoveEvent.movement_group_id == group.id).count() == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("check_out_date", date(2026, 7, 5)),
        ("commission_amount", 1),
    ],
)
def test_stale_allocation_proposal_cannot_move_reservation_after_source_change(db, field, value):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        rooms[0].id,
        "STALE-LOCK1",
        date(2026, 7, 1),
        date(2026, 7, 3),
        allocation_locked=True,
    )
    _reservation(
        db,
        hotel.id,
        guests[1].id,
        category.id,
        rooms[0].id,
        "STALE-LOCK2",
        date(2026, 7, 4),
        date(2026, 7, 6),
        allocation_locked=True,
    )
    mover = _reservation(
        db,
        hotel.id,
        guests[2].id,
        category.id,
        rooms[1].id,
        "STALE-MOVE",
        date(2026, 7, 3),
        date(2026, 7, 4),
    )
    db.flush()

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="stale_proposal_test",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )
    original_room_id = mover.room_id
    # The fingerprint covers assignment fields and financial inputs because
    # the solver can rank reservations using net revenue.
    setattr(mover, field, value)
    db.flush()

    with pytest.raises(AllocationRuntimeError, match="changed after this proposal"):
        accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)

    db.refresh(mover)
    assert mover.room_id == original_room_id


def test_initial_autoassignment_rechecks_locked_room_and_routes_stale_conflict_to_review(db, monkeypatch):
    import app.services.allocation_runtime_service as runtime_service
    import app.services.reservation_service as reservation_service

    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    reservation = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        None,
        "AUTOASSIGN-STALE",
        date(2026, 7, 3),
        date(2026, 7, 4),
    )
    room_lock_sql: list[str] = []
    real_lock_query = runtime_service.lock_query

    def record_room_lock_query(query, model):
        if model is Room:
            locked_query = real_lock_query(query, model)
            room_lock_sql.append(str(locked_query.statement.compile(dialect=postgresql.dialect())))
            return locked_query
        return real_lock_query(query, model)

    monkeypatch.setattr(runtime_service, "lock_query", record_room_lock_query)
    monkeypatch.setattr(reservation_service, "check_room_availability", lambda *args, **kwargs: False)

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="autoassign_stale_conflict_test",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )

    assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel.id,
            AllocationAssignment.allocation_run_id == result.run.id,
            AllocationAssignment.reservation_id == reservation.id,
        )
        .one()
    )
    db.refresh(reservation)
    assert result.solver_result.success is False
    assert result.run.status.value == "failed"
    assert reservation.room_id is None
    assert reservation.allocation_status == "manual_review"
    assert reservation.requires_manual_review is True
    assert assignment.status == AllocationAssignmentStatusEnum.MANUAL_REVIEW
    assert "no longer available" in result.run.error_message
    assert room_lock_sql
    assert "ORDER BY rooms.id ASC" in room_lock_sql[0]
    assert "FOR UPDATE OF rooms" in room_lock_sql[0]
    assert (
        db.query(runtime_service.AllocationExplanation)
        .filter(
            runtime_service.AllocationExplanation.hotel_id == hotel.id,
            runtime_service.AllocationExplanation.allocation_run_id == result.run.id,
            runtime_service.AllocationExplanation.explanation_type == "initial_assignment_failed",
        )
        .count()
        == 1
    )


def test_partial_solver_result_keeps_unapplied_initial_assignment_in_manual_review(db, monkeypatch):
    import app.services.allocation_runtime_service as runtime_service

    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=1)
    assigned_candidate = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        None,
        "PARTIAL-CANDIDATE",
    )
    unassigned = _reservation(
        db,
        hotel.id,
        guests[1].id,
        category.id,
        None,
        "PARTIAL-UNASSIGNED",
    )
    monkeypatch.setattr(
        runtime_service,
        "run_allocation",
        lambda *_args, **_kwargs: AllocationResult(
            success=False,
            assignments={assigned_candidate.id: rooms[0].id},
            unassigned_reservations=[unassigned.id],
            error="partial plan requires review",
        ),
    )

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="partial_solver_result_test",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )

    assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel.id,
            AllocationAssignment.allocation_run_id == result.run.id,
            AllocationAssignment.reservation_id == assigned_candidate.id,
        )
        .one()
    )
    db.refresh(assigned_candidate)
    assert result.run.status.value == "failed"
    assert assigned_candidate.room_id is None
    assert assigned_candidate.allocation_status == "manual_review"
    assert assigned_candidate.requires_manual_review is True
    assert assignment.status == AllocationAssignmentStatusEnum.MANUAL_REVIEW
    assert assignment.applied_at is None


@pytest.mark.parametrize(
    ("status", "expected_label", "metric_key"),
    [
        ("OPTIMAL", "OPTIMAL (optimality proven)", "primary_objective_status_optimal"),
        ("FEASIBLE", "FEASIBLE (optimality not proven)", "primary_objective_status_feasible"),
        ("HEURISTIC", "HEURISTIC (optimality not proven)", "primary_objective_status_heuristic"),
    ],
)
def test_allocation_run_exposes_solver_proof_status_without_overclaiming(
    db,
    monkeypatch,
    status,
    expected_label,
    metric_key,
):
    import app.services.allocation_runtime_service as runtime_service

    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=1)
    reservation = _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        None,
        f"STATUS-{status}",
    )
    monkeypatch.setattr(
        runtime_service,
        "run_allocation",
        lambda *_args, **_kwargs: AllocationResult(
            success=True,
            assignments={reservation.id: rooms[0].id},
            primary_status=status,
            tie_break_status="OPTIMAL" if status == "OPTIMAL" else "not_run_primary_not_proven",
        ),
    )

    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="solver_status_test",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )

    metrics = {
        metric.metric_key: metric.metric_value
        for metric in db.query(SolverMetric)
        .filter(
            SolverMetric.hotel_id == hotel.id,
            SolverMetric.allocation_run_id == result.run.id,
        )
        .all()
    }
    assert result.run.solver_summary.find(expected_label) >= 0
    assert metrics[metric_key] == 1.0
    assert sum(
        metrics[key]
        for key in (
            "primary_objective_status_optimal",
            "primary_objective_status_feasible",
            "primary_objective_status_heuristic",
        )
    ) == 1.0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("default_currency", "USD"),
        ("fx_conversion_rate_type", "blue"),
        ("fx_usd_to_ars_rate_type", "blue"),
        ("fx_ars_to_usd_rate_type", "blue"),
        ("fx_usd_to_ars_rate_side", "compra"),
        ("fx_ars_to_usd_rate_side", "compra"),
        ("spread_pct", 2.5),
    ],
)
def test_allocation_proposal_is_rejected_after_fx_configuration_changes(db, field, value):
    hotel, mover, result = _create_pending_reallocation_proposal(db)
    original_room_id = mover.room_id
    if field == "spread_pct":
        db.add(
            FxPolicy(
                hotel_id=hotel.id,
                code="allocation-spread",
                name="Allocation spread",
                spread_pct=value,
                is_active=True,
            )
        )
    else:
        setattr(hotel, field, value)
    db.flush()

    with pytest.raises(AllocationRuntimeError, match="FX configuration changed"):
        accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)

    db.refresh(mover)
    assert mover.room_id == original_room_id


def test_allocation_proposal_is_rejected_when_policy_version_is_no_longer_active(db):
    hotel, mover, result = _create_pending_reallocation_proposal(db)
    original_room_id = mover.room_id
    current = (
        db.query(AllocationPolicyVersion)
        .filter(AllocationPolicyVersion.id == result.run.policy_version_id)
        .one()
    )
    current.is_published = False
    db.add(
        AllocationPolicyVersion(
            hotel_id=hotel.id,
            profile_id=current.profile_id,
            version_number=current.version_number + 1,
            source="manual",
            constraints_json=current.constraints_json,
            weights_json=current.weights_json,
            is_published=True,
        )
    )
    db.flush()

    with pytest.raises(AllocationRuntimeError, match="active allocation policy changed"):
        accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)

    db.refresh(mover)
    assert mover.room_id == original_room_id


@pytest.mark.parametrize("snapshot_state", ["stale", "missing", "other_hotel"])
def test_allocation_proposal_requires_fresh_hotel_scoped_fx_snapshot(db, snapshot_state):
    hotel, mover, result = _create_pending_reallocation_proposal(db)
    original_room_id = mover.room_id
    other_hotel_id = None
    if snapshot_state == "other_hotel":
        other_hotel_id = 999
        db.add(HotelConfiguration(id=other_hotel_id, subscription_active=True))
        db.flush()

    snapshot = None
    snapshot_id = 999999
    if snapshot_state != "missing":
        age = timedelta(hours=25) if snapshot_state == "stale" else timedelta(minutes=5)
        now = datetime.now(timezone.utc)
        snapshot = FxRateSnapshot(
            hotel_id=other_hotel_id or hotel.id,
            rate_type="oficial",
            provider_market="oficial",
            moneda="USD",
            compra=1000,
            venta=1100,
            fetched_at=now - age,
            provider_updated_at=now - age,
            selected_side="venta",
            base_currency="ARS",
            quote_currency="USD",
            applied_rate=1100,
            source="synthetic-test",
        )
        db.add(snapshot)
        db.flush()
        snapshot_id = snapshot.id

    assignment_explanation = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.hotel_id == hotel.id,
            AllocationExplanation.allocation_run_id == result.run.id,
            AllocationExplanation.reservation_id == mover.id,
            AllocationExplanation.explanation_type == "assignment",
        )
        .one()
    )
    explanation_details = json.loads(assignment_explanation.details_json)
    explanation_details["allocation_fx_conversion"] = {
        "source_currency": "USD",
        "allocation_currency": "ARS",
        "snapshot_ids": [snapshot_id],
    }
    assignment_explanation.details_json = json.dumps(explanation_details)
    db.flush()

    expected_reason = {
        "stale": "older than 24 hours",
        "missing": "missing or belongs to another hotel",
        "other_hotel": "missing or belongs to another hotel",
    }[snapshot_state]
    with pytest.raises(AllocationRuntimeError, match=expected_reason):
        accept_allocation_run(db, hotel_id=hotel.id, run_id=result.run.id, user_id=None)

    db.refresh(mover)
    assert mover.room_id == original_room_id


def test_persisted_allocation_batches_reservation_entity_reads(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=7)
    for index in range(6):
        _reservation(
            db,
            hotel.id,
            guests[index].id,
            category.id,
            rooms[0].id,
            f"BATCH{index}",
        )
    db.flush()

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
            trigger_type="query_count_regression",
            horizon_start=date(2026, 7, 1),
            horizon_end=date(2026, 7, 5),
        )
    finally:
        sqlalchemy_event.remove(engine, "before_cursor_execute", count_reservation_selects)

    assert result.solver_result.success is True
    # The candidate and history projections plus one tenant-scoped ORM batch
    # and two select-in relationship batches serve all six assignments. The
    # per-assignment db.get()/Query.first() pattern is absent.
    assert len(reservation_selects) == 5
    allocation_events = (
        db.query(DomainEventOutbox)
        .filter(
            DomainEventOutbox.hotel_id == hotel.id,
            DomainEventOutbox.event_type == "allocation.read_model.changed",
        )
        .all()
    )
    assert len(allocation_events) == 3
    assert {event.domain for event in allocation_events} == {"reservations", "rooms", "analytics"}


def _seed_hotel_rooms_guests(db, *, hotel_id: int = 1, room_count: int = 3):
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True)
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    rooms = [
        Room(
            hotel_id=hotel_id,
            room_number=f"{hotel_id}{idx:02d}",
            floor=idx,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
            is_accessible=True,
            score=idx,
        )
        for idx in range(1, room_count + 1)
    ]
    guests = [
        Guest(
            hotel_id=hotel_id,
            first_name=f"Guest{idx}",
            last_name="Test",
            document_type=DocumentTypeEnum.DNI,
            document_number=f"{hotel_id}{idx:04d}",
            terms_accepted=True,
        )
        for idx in range(1, max(room_count + 2, 5))
    ]
    db.add_all([*rooms, *guests])
    db.flush()
    return hotel, category, rooms, guests


def _reservation(
    db,
    hotel_id: int,
    guest_id: int,
    category_id: int,
    room_id: int,
    code: str,
    check_in: date = date(2026, 7, 1),
    check_out: date = date(2026, 7, 4),
    *,
    status: ReservationStatusEnum = ReservationStatusEnum.PENDING,
    allocation_locked: bool = False,
    company_id: int | None = None,
    amount_paid: float = 0,
) -> Reservation:
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"{hotel_id}-{code}",
        guest_id=guest_id,
        room_id=room_id,
        category_id=category_id,
        company_id=company_id,
        check_in_date=check_in,
        check_out_date=check_out,
        status=status,
        total_amount=100,
        amount_paid=amount_paid,
        deposit_amount=0,
        allocation_locked=allocation_locked,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _create_pending_reallocation_proposal(db):
    hotel, category, rooms, guests = _seed_hotel_rooms_guests(db, room_count=2)
    _reservation(
        db,
        hotel.id,
        guests[0].id,
        category.id,
        rooms[0].id,
        "PROPOSAL-LOCK1",
        date(2026, 7, 1),
        date(2026, 7, 3),
        allocation_locked=True,
    )
    _reservation(
        db,
        hotel.id,
        guests[1].id,
        category.id,
        rooms[0].id,
        "PROPOSAL-LOCK2",
        date(2026, 7, 4),
        date(2026, 7, 6),
        allocation_locked=True,
    )
    mover = _reservation(
        db,
        hotel.id,
        guests[2].id,
        category.id,
        rooms[1].id,
        "PROPOSAL-MOVE",
        date(2026, 7, 3),
        date(2026, 7, 4),
    )
    db.flush()
    result = run_persisted_allocation(
        db,
        hotel_id=hotel.id,
        trigger_type="proposal_acceptance_test",
        apply=True,
        horizon_start=date(2026, 7, 1),
        horizon_end=date(2026, 7, 6),
    )
    assignment = (
        db.query(AllocationAssignment)
        .filter(
            AllocationAssignment.hotel_id == hotel.id,
            AllocationAssignment.allocation_run_id == result.run.id,
            AllocationAssignment.reservation_id == mover.id,
        )
        .one()
    )
    assert assignment.status == AllocationAssignmentStatusEnum.PROPOSED
    return hotel, mover, result
