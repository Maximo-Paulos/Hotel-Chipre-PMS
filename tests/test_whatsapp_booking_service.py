from datetime import date
from decimal import Decimal

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationChannelCodeEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.whatsapp_hooks import (
    WhatsAppPaymentLinkCreate,
    WhatsAppReservationCreate,
)
from app.services.whatsapp_booking_service import (
    WhatsAppBookingError,
    create_reservation,
    generate_payment_link,
)


def _seed_whatsapp_hotel(db, hotel_id: int):
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True, deposit_percentage=30.0)
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"WhatsApp Standard {hotel_id}",
        code=f"WSTD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name="WhatsApp",
        last_name=f"Guest {hotel_id}",
        email=f"whatsapp{hotel_id}@example.com",
        phone=f"+549110000{hotel_id}",
    )
    db.add_all([category, guest])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"W{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return category, room, guest


def test_whatsapp_create_reservation_sets_channel_code_whatsapp(db):
    category, room, guest = _seed_whatsapp_hotel(db, 1)

    reservation = create_reservation(
        db,
        hotel_id=1,
        payload=WhatsAppReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
            num_adults=1,
        ),
    )

    assert reservation.hotel_id == 1
    assert reservation.channel_code == ReservationChannelCodeEnum.WHATSAPP
    assert reservation.source_provider_code == "whatsapp"


def test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(db):
    category, room, guest = _seed_whatsapp_hotel(db, 1)
    reservation = create_reservation(
        db,
        hotel_id=1,
        payload=WhatsAppReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 2),
            num_adults=1,
        ),
    )

    link = generate_payment_link(
        db,
        hotel_id=1,
        payload=WhatsAppPaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="wa-pay@example.com",
            recipient_phone="+5491111111111",
        ),
    )

    assert link.hotel_id == 1
    assert link.reservation_id == reservation.id
    assert link.sent_via_whatsapp is True


def test_whatsapp_service_rejects_cross_hotel_reservation_payment_link(db):
    _category_a, _room_a, _guest_a = _seed_whatsapp_hotel(db, 1)
    category_b, room_b, guest_b = _seed_whatsapp_hotel(db, 2)
    reservation_b = Reservation(
        hotel_id=2,
        confirmation_code="WA-H2",
        guest_id=guest_b.id,
        room_id=room_b.id,
        category_id=category_b.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 2),
        total_amount=Decimal("100.00"),
        deposit_amount=Decimal("30.00"),
    )
    db.add(reservation_b)
    db.flush()

    with pytest.raises(WhatsAppBookingError):
        generate_payment_link(
            db,
            hotel_id=1,
            payload=WhatsAppPaymentLinkCreate(
                reservation_id=reservation_b.id,
                requested_amount=Decimal("100.00"),
                recipient_email="cross@example.com",
            ),
        )

    assert db.query(PaymentLink).count() == 0
