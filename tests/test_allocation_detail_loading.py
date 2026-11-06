from __future__ import annotations

import json
from datetime import date

from sqlalchemy import event
from sqlalchemy.orm import selectinload

from app.models.allocation import (
    AllocationAssignment,
    AllocationAssignmentStatusEnum,
    AllocationExplanation,
    AllocationRun,
    AllocationRunStatusEnum,
    SolverMetric,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.services.allocation_runtime_service import (
    AllocationRunDetails,
    get_latest_allocation_run_details,
)


def _legacy_latest_run_details(db, *, hotel_id: int) -> AllocationRunDetails | None:
    """Keep the pre-optimization ORM path as a query-count regression baseline."""
    latest = (
        db.query(AllocationRun)
        .filter(AllocationRun.hotel_id == hotel_id)
        .order_by(AllocationRun.id.desc())
        .first()
    )
    if latest is None:
        return None
    run = (
        db.query(AllocationRun)
        .options(selectinload(AllocationRun.assignments))
        .filter(AllocationRun.id == latest.id, AllocationRun.hotel_id == hotel_id)
        .first()
    )
    explanations = (
        db.query(AllocationExplanation)
        .filter(
            AllocationExplanation.allocation_run_id == latest.id,
            AllocationExplanation.hotel_id == hotel_id,
        )
        .order_by(AllocationExplanation.id.asc())
        .all()
    )
    metrics = (
        db.query(SolverMetric)
        .filter(
            SolverMetric.allocation_run_id == latest.id,
            SolverMetric.hotel_id == hotel_id,
        )
        .order_by(SolverMetric.id.asc())
        .all()
    )
    return AllocationRunDetails(
        run=run,
        explanations=explanations,
        metrics=metrics,
        assignments=list(run.assignments),
    )


def test_latest_run_details_preserve_response_and_avoid_eager_relationship_joins(pg_session):
    hotel = HotelConfiguration(id=9001, owner_email="allocation-query-test@example.invalid")
    other_hotel = HotelConfiguration(id=9002, owner_email="allocation-query-other@example.invalid")
    pg_session.add_all([hotel, other_hotel])
    pg_session.flush()

    category = RoomCategory(
        hotel_id=hotel.id,
        name="Allocation Query Test",
        code="AQT",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel.id, first_name="Synthetic", last_name="Allocation")
    pg_session.add_all([category, guest])
    pg_session.flush()

    reservation = Reservation(
        confirmation_code="ALLOCATION-DETAIL-TEST",
        hotel_id=hotel.id,
        guest_id=guest.id,
        room_id=None,
        category_id=category.id,
        check_in_date=date(2027, 1, 10),
        check_out_date=date(2027, 1, 12),
        total_amount=200,
        status=ReservationStatusEnum.PENDING,
    )
    pg_session.add(reservation)
    pg_session.flush()

    old_run = AllocationRun(
        hotel_id=hotel.id,
        trigger_type="manual_api_recalculate",
        status=AllocationRunStatusEnum.SUCCEEDED,
    )
    latest_run = AllocationRun(
        hotel_id=hotel.id,
        trigger_type="manual_api_recalculate",
        status=AllocationRunStatusEnum.SUCCEEDED,
    )
    other_hotel_run = AllocationRun(
        hotel_id=other_hotel.id,
        trigger_type="manual_api_recalculate",
        status=AllocationRunStatusEnum.SUCCEEDED,
    )
    pg_session.add_all([old_run, latest_run, other_hotel_run])
    pg_session.flush()
    pg_session.add_all(
        [
            AllocationAssignment(
                hotel_id=hotel.id,
                allocation_run_id=latest_run.id,
                reservation_id=reservation.id,
                room_id=None,
                status=AllocationAssignmentStatusEnum.PROPOSED,
                explanation_summary="Synthetic suggestion",
            ),
            AllocationExplanation(
                hotel_id=hotel.id,
                allocation_run_id=latest_run.id,
                reservation_id=reservation.id,
                explanation_type="assignment",
                summary="Synthetic explanation",
                details_json=json.dumps({"source_room_id": 41}),
            ),
            SolverMetric(
                hotel_id=hotel.id,
                allocation_run_id=latest_run.id,
                metric_key="assigned_reservations",
                metric_value=1,
            ),
        ]
    )
    pg_session.flush()

    statements: list[str] = []

    def capture_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().casefold().startswith("select"):
            statements.append(statement)

    connection = pg_session.connection()
    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        details = get_latest_allocation_run_details(pg_session, hotel_id=hotel.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)

    assert details is not None
    assert details.run.id == latest_run.id
    assert details.run.status == AllocationRunStatusEnum.SUCCEEDED
    assert [item.reservation_id for item in details.assignments] == [reservation.id]
    assert details.assignments[0].status == AllocationAssignmentStatusEnum.PROPOSED
    assert details.assignments[0].explanation_summary == "Synthetic suggestion"
    assert [(item.explanation_type, item.summary) for item in details.explanations] == [
        ("assignment", "Synthetic explanation")
    ]
    assert [(item.metric_key, item.metric_value) for item in details.metrics] == [
        ("assigned_reservations", 1)
    ]

    # The latest-run query is reused for details; no second AllocationRun query
    # or mapper-level relationship joins are needed to return the same payload.
    assert len(statements) == 4
    run_queries = [sql.casefold() for sql in statements if "from allocation_runs" in sql.casefold()]
    assert len(run_queries) == 1
    assignment_queries = [
        sql.casefold()
        for sql in statements
        if "from allocation_assignments" in sql.casefold()
    ]
    assert len(assignment_queries) == 1
    assert " join reservations " not in assignment_queries[0]
    assert " join rooms " not in assignment_queries[0]

    pg_session.expunge_all()
    legacy_statements: list[str] = []

    def capture_legacy_statement(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().casefold().startswith("select"):
            legacy_statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture_legacy_statement)
    try:
        legacy_details = _legacy_latest_run_details(pg_session, hotel_id=hotel.id)
    finally:
        event.remove(connection, "before_cursor_execute", capture_legacy_statement)

    assert legacy_details is not None
    assert [item.reservation_id for item in legacy_details.assignments] == [
        item.reservation_id for item in details.assignments
    ]
    assert [(item.explanation_type, item.summary) for item in legacy_details.explanations] == [
        (item.explanation_type, item.summary) for item in details.explanations
    ]
    assert [(item.metric_key, item.metric_value) for item in legacy_details.metrics] == [
        (item.metric_key, item.metric_value) for item in details.metrics
    ]
    assert len(legacy_statements) >= len(statements) * 2

