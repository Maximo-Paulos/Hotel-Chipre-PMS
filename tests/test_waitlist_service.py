from datetime import date

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.room import RoomCategory
from app.models.waitlist import WaitlistStatusEnum
from app.schemas.waitlist import WaitlistEntryCreate
from app.services.waitlist_service import (
    WaitlistError,
    add_to_waitlist,
    get_waitlist_entry,
    request_payment_link_for_waitlist,
)


def _seed_waitlist_base(db, hotel_id: int):
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name=f"Guest {hotel_id}", last_name="Wait", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"WAIT{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    return guest, category


def test_waitlist_entry_has_no_room_and_cannot_request_payment_link(db):
    guest, category = _seed_waitlist_base(db, 1)

    entry = add_to_waitlist(
        db,
        1,
        WaitlistEntryCreate(
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),
            contact_phone="+549111111111",
        ),
    )

    assert entry.status == WaitlistStatusEnum.WAITING
    assert entry.promoted_reservation_id is None
    assert not hasattr(entry, "room_id")
    with pytest.raises(WaitlistError, match="cannot request payment links"):
        request_payment_link_for_waitlist(db, 1, entry.id)


def test_waitlist_cross_hotel_isolation(db):
    guest, category = _seed_waitlist_base(db, 1)
    _seed_waitlist_base(db, 2)
    entry = add_to_waitlist(
        db,
        1,
        WaitlistEntryCreate(
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),
        ),
    )

    assert get_waitlist_entry(db, 1, entry.id).id == entry.id
    with pytest.raises(WaitlistError):
        get_waitlist_entry(db, 2, entry.id)
