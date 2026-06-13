from datetime import date
from decimal import Decimal

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import Transaction
from app.schemas.payment_link import PaymentLinkCreate
from app.services.payment_link_service import PaymentLinkError, cancel_link, create_link, list_links_for_reservation


def _reservation(db, hotel_id: int, code: str = "RL-1") -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name="Ada", last_name="Guest", email=f"guest-{hotel_id}@test.com", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
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
    db.add(reservation)
    db.flush()
    return reservation


def test_create_payment_link_persists_link_without_transaction(db):
    reservation = _reservation(db, 1)

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("75.50"),
            recipient_email="guest@example.com",
            description="Deposit",
        ),
    )

    assert link.id is not None
    assert link.provider == "mercado_pago"
    assert link.link_code
    assert link.requested_amount == Decimal("75.50")
    assert link.collected_amount == Decimal("0.00")
    assert db.query(Transaction).count() == 0


def test_cross_hotel_isolation_for_payment_link_service(db):
    reservation_a = _reservation(db, 1, "RL-A")
    reservation_b = _reservation(db, 2, "RL-B")
    link_b = create_link(
        db,
        2,
        PaymentLinkCreate(
            reservation_id=reservation_b.id,
            requested_amount=Decimal("20.00"),
            recipient_email="guest-b@example.com",
        ),
    )

    assert list_links_for_reservation(db, 1, reservation_a.id) == []
    assert list_links_for_reservation(db, 1, reservation_b.id) == []
    with pytest.raises(PaymentLinkError):
        cancel_link(db, 1, link_b.id)
