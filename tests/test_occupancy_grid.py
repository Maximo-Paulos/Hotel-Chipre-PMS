"""Tests for B2: GET /api/reservations/occupancy-grid (planilla de ocupación).

Cross-hotel isolation for this endpoint is covered separately in
tests/test_cross_hotel_id_collision_api.py::test_occupancy_grid_never_leaks_hotel_b_data
(same suite the API relies on for id-collision regression).
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.room_block import RoomBlockReasonEnum
from app.schemas.reservation import ReservationCreate
from app.services.reservation_operations_service import add_reservation_charge
from app.services.reservation_service import create_reservation, get_occupancy_grid
from app.services.room_block_service import create_block


def _reserve(db, guest, room, check_in, check_out, hotel_id=1, **extra):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=room.category_id,
            room_id=room.id,
            check_in_date=check_in,
            check_out_date=check_out,
            **extra,
        ),
        hotel_id=hotel_id,
    )
    db.flush()
    return reservation


def test_rooms_are_grouped_by_category_and_scoped_to_hotel(db, sample_rooms, sample_categories, hotel_config):
    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))
    assert len(grid["rooms"]) == 38
    category_names = {r["category_name"] for r in grid["rooms"]}
    assert category_names == {c.name for c in sample_categories}


def test_reservation_spanning_the_window_is_returned_unclipped(db, sample_guest, sample_rooms, hotel_config):
    room = sample_rooms[0]
    res = _reserve(db, sample_guest, room, date(2027, 1, 1), date(2027, 1, 20))

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 5), date_to=date(2027, 1, 10))

    matches = [r for r in grid["reservations"] if r["id"] == res.id]
    assert len(matches) == 1
    # Full original dates come back -- clipping to the visible window is a
    # frontend display concern, not something the backend should truncate.
    assert matches[0]["check_in_date"] == date(2027, 1, 1)
    assert matches[0]["check_out_date"] == date(2027, 1, 20)


def test_reservation_entirely_before_or_after_window_is_excluded(db, sample_guest, sample_rooms, hotel_config):
    room = sample_rooms[0]
    _reserve(db, sample_guest, room, date(2027, 1, 1), date(2027, 1, 5))  # ends exactly at date_from
    _reserve(db, sample_guest, sample_rooms[1], date(2027, 1, 10), date(2027, 1, 12))  # starts at/after date_to

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 5), date_to=date(2027, 1, 10))

    assert grid["reservations"] == []


def test_cancelled_reservation_is_excluded(db, sample_guest, sample_rooms, hotel_config):
    from app.services.reservation_service import transition_reservation_status
    from app.models.reservation import ReservationStatusEnum

    room = sample_rooms[0]
    res = _reserve(db, sample_guest, room, date(2027, 1, 1), date(2027, 1, 5))
    transition_reservation_status(db, res, ReservationStatusEnum.CANCELLED, hotel_id=1)

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))

    assert grid["reservations"] == []


def test_unassigned_reservation_has_no_room_and_lands_in_unassigned(db, sample_guest, sample_categories, hotel_config):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=None,
            check_in_date=date(2027, 1, 1),
            check_out_date=date(2027, 1, 3),
            # No physical room available/assigned yet -- this is exactly the
            # "Sin asignar" row the plan says a receptionist assigns from.
            is_wait_listed=True,
        ),
        hotel_id=1,
    )
    db.flush()

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))

    assert grid["reservations"] == []
    assert len(grid["unassigned"]) == 1
    assert grid["unassigned"][0]["id"] == reservation.id
    assert grid["unassigned"][0]["room_id"] is None


def test_operational_balance_due_includes_consumption_charges(db, sample_guest, sample_rooms, hotel_config):
    """Regression guard for the plan's explicit note: the naive `balance_due`
    ignores consumption charges. The grid must use the same
    operational_balance_due semantics the drawer (B1) uses."""
    room = sample_rooms[0]
    res = _reserve(db, sample_guest, room, date(2027, 1, 1), date(2027, 1, 5), total_amount=100)
    res.total_amount = Decimal("100.00")
    res.amount_paid = Decimal("100.00")
    db.flush()

    add_reservation_charge(
        db,
        reservation=res,
        hotel_id=1,
        amount=Decimal("30.00"),
        currency_code="ARS",
        description="Minibar",
    )
    db.flush()

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))

    match = next(r for r in grid["reservations"] if r["id"] == res.id)
    # Fully paid on total_amount but the extra 30 consumption charge is still
    # collectible -- a naive total_amount - amount_paid would show 0 here.
    assert match["operational_balance_due"] == 30.0


def test_room_blocks_are_included_with_indefinite_ends_at_raw(db, sample_rooms, hotel_config):
    room = sample_rooms[0]
    block = create_block(
        db,
        hotel_id=1,
        room_id=room.id,
        starts_at=date(2027, 1, 3),
        is_indefinite=True,
        reason_code=RoomBlockReasonEnum.MAINTENANCE,
    )
    db.flush()

    grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))

    matches = [b for b in grid["blocks"] if b["room_id"] == room.id]
    assert len(matches) == 1
    assert matches[0]["ends_at"] is None
    assert matches[0]["reason_code"] == "maintenance"
    assert block.is_active


def test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(db, sample_guest, sample_rooms, hotel_config):
    for i, room in enumerate(sample_rooms):
        _reserve(db, sample_guest, room, date(2027, 1, 1), date(2027, 1, 1 + (i % 5) + 2))

    engine = db.get_bind()
    query_counts = [0]

    def _count_query(*_args, **_kwargs):
        query_counts[0] += 1

    event.listen(engine, "before_cursor_execute", _count_query)
    try:
        grid = get_occupancy_grid(db, hotel_id=1, date_from=date(2027, 1, 1), date_to=date(2027, 1, 8))
    finally:
        event.remove(engine, "before_cursor_execute", _count_query)

    assert len(grid["rooms"]) == 38
    assert len(grid["reservations"]) == 38
    # rooms + reservations + paid-amounts + adjustments + blocks -- a fixed,
    # small handful of queries regardless of how many rooms/reservations exist.
    assert query_counts[0] <= 8, f"expected O(1) queries, got {query_counts[0]}"


def test_api_rejects_range_over_92_days_and_inverted_range():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=1, user_id=1, user_email="owner@test.com",
            user_role="owner", is_verified=True, permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        too_wide = client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": "2027-01-01", "date_to": "2027-06-01"},
        )
        assert too_wide.status_code == 422, too_wide.text

        inverted = client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": "2027-01-10", "date_to": "2027-01-01"},
        )
        assert inverted.status_code == 422, inverted.text

        ok = client.get(
            "/api/reservations/occupancy-grid",
            params={"date_from": "2027-01-01", "date_to": "2027-01-31"},
        )
        assert ok.status_code == 200, ok.text
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
