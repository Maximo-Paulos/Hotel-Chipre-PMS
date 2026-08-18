"""Integration coverage: the real domain-event call sites (reservation
lifecycle, check-in/out, guest restriction, low stock) actually enqueue
NotificationOutbox rows -- not just the isolated enqueue_notifications_for_event
unit tests in test_notification_service.py."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.notification import NotificationOutbox
from app.models.user import User
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.checkin_service import perform_checkin, perform_checkout
from app.services.guest_restriction_service import create_guest_restriction, resolve_guest_restriction
from app.services.reservation_service import (
    create_reservation,
    mark_reservation_no_show,
    transition_reservation_status,
    update_reservation_fields,
)
from app.models.reservation import ReservationStatusEnum
from app.services.stock_service import create_stock_item, register_movement


def _owner(db: Session, hotel_id: int = 1, user_id: int = 900) -> User:
    user = User(id=user_id, email=f"owner{user_id}@example.test", password_hash="x", is_verified=True)
    db.add(user)
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user_id, role="owner", status="active"))
    db.flush()
    return user


def _outbox_event_types(db: Session, hotel_id: int = 1) -> set[str]:
    return {row.event_type for row in db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == hotel_id).all()}


def test_reservation_lifecycle_enqueues_notifications(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    _owner(db)

    data = ReservationCreate(
        guest_id=sample_guest.id, category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1), check_out_date=date(2026, 4, 5),
    )
    reservation = create_reservation(db, data)
    db.flush()
    assert "reservation.created" in _outbox_event_types(db)

    update_reservation_fields(db, reservation, ReservationUpdate(notes="updated"), client_version=reservation.version)
    db.flush()
    assert "reservation.updated" in _outbox_event_types(db)

    transition_reservation_status(db, reservation, ReservationStatusEnum.CANCELLED)
    db.flush()
    assert "reservation.cancelled" in _outbox_event_types(db)


def test_no_show_enqueues_notification(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    _owner(db)
    data = ReservationCreate(
        guest_id=sample_guest.id, category_id=sample_categories[0].id,
        check_in_date=date(2026, 4, 1), check_out_date=date(2026, 4, 5),
    )
    reservation = create_reservation(db, data)
    db.flush()

    mark_reservation_no_show(db, reservation, hotel_id=1, client_version=reservation.version)
    db.flush()
    assert "reservation.no_show" in _outbox_event_types(db)


def test_checkin_checkout_enqueue_notifications(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    _owner(db)
    data = ReservationCreate(
        guest_id=sample_guest.id, category_id=sample_categories[0].id,
        check_in_date=date.today(), check_out_date=date.today(),
    )
    data.check_out_date = date(2026, 4, 2)
    data.check_in_date = date(2026, 4, 1)
    reservation = create_reservation(db, data)
    reservation.status = ReservationStatusEnum.FULLY_PAID
    reservation.amount_paid = reservation.total_amount
    db.flush()

    perform_checkin(db, reservation.id, hotel_id=1)
    db.flush()
    assert "reservation.checked_in" in _outbox_event_types(db)

    perform_checkout(db, reservation.id, hotel_id=1)
    db.flush()
    assert "reservation.checked_out" in _outbox_event_types(db)


def test_guest_restriction_lifecycle_enqueues_notifications(db, sample_guest, hotel_config):
    _owner(db)
    restriction = create_guest_restriction(db, hotel_id=1, guest_id=sample_guest.id, reason="test reason")
    db.flush()
    assert "guest.restriction.created" in _outbox_event_types(db)

    resolve_guest_restriction(db, hotel_id=1, guest_id=sample_guest.id, restriction_id=restriction.id)
    db.flush()
    assert "guest.restriction.resolved" in _outbox_event_types(db)

    # Non-disclosure: neither event's stored payload/title carries reason/detail text.
    rows = db.query(NotificationOutbox).filter(NotificationOutbox.hotel_id == 1).all()
    for row in rows:
        assert "test reason" not in (row.title or "")
        assert "test reason" not in (row.body or "")
        assert "test reason" not in (row.payload or "")


def test_low_stock_movement_enqueues_notification(db, hotel_config):
    _owner(db)
    item = create_stock_item(db, hotel_id=1, name="Toallas", unit="unidad", min_quantity=Decimal("5"))
    db.flush()
    register_movement(db, hotel_id=1, item_id=item.id, location_id=None, movement_type="in", quantity=Decimal("10"))
    db.flush()
    assert _outbox_event_types(db) == set()  # still above threshold, no notification yet

    register_movement(db, hotel_id=1, item_id=item.id, location_id=None, movement_type="out", quantity=Decimal("8"))
    db.flush()
    assert "stock.low" in _outbox_event_types(db)
