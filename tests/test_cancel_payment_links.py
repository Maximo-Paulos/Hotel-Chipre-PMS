"""Cancelling a reservation must cancel its still-payable seña links (BR §M)."""
from datetime import date
from decimal import Decimal

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.services.payment_link_service import cancel_active_links_for_reservation


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    if db.get(HotelConfiguration, hotel_id) is None:
        db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
        db.flush()
    guest = Guest(first_name="Ada", last_name="Guest", email=f"g-{code}@test.com", hotel_id=hotel_id)
    category = RoomCategory(hotel_id=hotel_id, name=f"Std {code}", code=f"C{code}", base_price_per_night=100, max_occupancy=2)
    db.add_all([guest, category])
    db.flush()
    res = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 7, 1),
        check_out_date=date(2026, 7, 3),
        total_amount=Decimal("200.00"),
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(res)
    db.flush()
    return res


def _link(db, hotel_id: int, reservation_id: int, code: str, status: str) -> PaymentLink:
    link = PaymentLink(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        link_code=code,
        requested_amount=Decimal("100.00"),
        recipient_email="guest@test.com",
        status=status,
    )
    db.add(link)
    db.flush()
    return link


def test_cancel_active_links_cancels_payable_and_leaves_terminal(db):
    res = _reservation(db, 1, "RA")
    other = _reservation(db, 1, "RB")
    pending = _link(db, 1, res.id, "LNK-PENDING", "pending")
    partial = _link(db, 1, res.id, "LNK-PARTIAL", "partially_paid")
    completed = _link(db, 1, res.id, "LNK-DONE", "completed")
    other_link = _link(db, 1, other.id, "LNK-OTHER", "pending")

    count = cancel_active_links_for_reservation(db, 1, res.id, reason="reservation cancelled")

    assert count == 2
    assert pending.status == "cancelled"
    assert pending.cancelled_at is not None
    assert partial.status == "cancelled"
    assert completed.status == "completed"  # terminal: untouched
    assert other_link.status == "pending"  # different reservation: untouched


def test_cancel_active_links_noop_when_none_payable(db):
    res = _reservation(db, 1, "RC")
    _link(db, 1, res.id, "LNK-DONE-2", "completed")
    assert cancel_active_links_for_reservation(db, 1, res.id) == 0
