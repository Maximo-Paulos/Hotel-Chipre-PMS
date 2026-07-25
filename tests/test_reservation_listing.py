"""Tests for A2: paginated + orderable reservation listing.

app/services/reservation_service.py::list_reservations used to do an
unbounded `.all()` ordered only by check_in_date. This covers the new
skip/limit/order contract and the selectin fan-out (additional_guests,
guest.companions, guest.tags) that a `limit` is supposed to bound.
"""
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import event

from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation, list_reservations


def _make_reservations(db, guest, rooms, hotel_id, count, start_date=date(2027, 1, 1)):
    created = []
    for i in range(count):
        room = rooms[i % len(rooms)]
        check_in = start_date + timedelta(days=i * 3)
        check_out = check_in + timedelta(days=2)
        reservation = create_reservation(
            db,
            ReservationCreate(
                guest_id=guest.id,
                category_id=room.category_id,
                room_id=room.id,
                check_in_date=check_in,
                check_out_date=check_out,
            ),
            hotel_id=hotel_id,
        )
        db.flush()
        created.append(reservation)
    return created


def test_default_limit_caps_result_at_50(db, sample_guest, sample_rooms, hotel_config):
    _make_reservations(db, sample_guest, sample_rooms, hotel_id=1, count=60)

    results = list_reservations(db, hotel_id=1)

    assert len(results) == 50


def test_skip_and_limit_page_through_results(db, sample_guest, sample_rooms, hotel_config):
    reservations = _make_reservations(db, sample_guest, sample_rooms, hotel_id=1, count=10)
    # order="recent" -> created_at DESC, id DESC, so index 0 in `reservations`
    # (created first) is last in the recent-ordered list.
    expected_recent_order = list(reversed([r.id for r in reservations]))

    page1 = list_reservations(db, hotel_id=1, skip=0, limit=4)
    page2 = list_reservations(db, hotel_id=1, skip=4, limit=4)

    assert [r.id for r in page1] == expected_recent_order[0:4]
    assert [r.id for r in page2] == expected_recent_order[4:8]


def test_order_recent_is_created_at_desc_id_desc(db, sample_guest, sample_rooms, hotel_config):
    reservations = _make_reservations(db, sample_guest, sample_rooms, hotel_id=1, count=3)
    # Force distinct, explicit created_at values -- creation happens fast
    # enough in a test run that relying on wall-clock timing to differ would
    # be flaky.
    base = datetime(2027, 1, 1, tzinfo=timezone.utc)
    for offset, reservation in enumerate(reservations):
        reservation.created_at = base + timedelta(minutes=offset)
    db.flush()

    results = list_reservations(db, hotel_id=1, order="recent")

    assert [r.id for r in results] == [reservations[2].id, reservations[1].id, reservations[0].id]


def test_order_check_in_preserves_pre_a2_default(db, sample_guest, sample_rooms, hotel_config):
    # Create out of check_in_date order so a naive re-use of insertion/created_at
    # order would fail this assertion.
    room = sample_rooms[0]
    later = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=room.category_id,
            room_id=room.id,
            check_in_date=date(2027, 6, 1),
            check_out_date=date(2027, 6, 3),
        ),
        hotel_id=1,
    )
    db.flush()
    earlier = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=room.category_id,
            room_id=room.id,
            check_in_date=date(2027, 1, 1),
            check_out_date=date(2027, 1, 3),
        ),
        hotel_id=1,
    )
    db.flush()

    results = list_reservations(db, hotel_id=1, order="check_in")

    assert [r.id for r in results] == [earlier.id, later.id]


def test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(db, sample_guest, sample_rooms, hotel_config):
    """A2 hidden cost: additional_guests/guest.companions/guest.tags are
    lazy="selectin" on Reservation/Guest. Before A2 this listing fetched the
    whole hotel history, so the fan-out scaled with the hotel's lifetime
    reservation count. With `limit` applied it must scale with `limit`
    instead -- verified here by asserting the query count stays a small,
    fixed bound even with 120 reservations already in the hotel.
    """
    _make_reservations(db, sample_guest, sample_rooms, hotel_id=1, count=120)

    engine = db.get_bind()
    query_counts = [0]

    def _count_query(*_args, **_kwargs):
        query_counts[0] += 1

    event.listen(engine, "before_cursor_execute", _count_query)
    try:
        results = list_reservations(db, hotel_id=1, limit=50)
    finally:
        event.remove(engine, "before_cursor_execute", _count_query)

    assert len(results) == 50
    # Bounded fan-out: 1 main query + a handful of selectin batches
    # (additional_guests, guest.companions, guest.tags, ...), not one query
    # per reservation and not scaling with the 120 reservations that exist.
    assert query_counts[0] <= 10, (
        f"expected a small, limit-bounded query count, got {query_counts[0]} "
        "queries for a limit=50 page out of 120 reservations"
    )
