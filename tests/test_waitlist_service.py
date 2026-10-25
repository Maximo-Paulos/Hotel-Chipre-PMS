import json
from datetime import date

import pytest
from pydantic import ValidationError

from app.models.allocation import (
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    AllocationRun,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.waitlist import WaitlistStatusEnum
from app.schemas.waitlist import WaitlistEntryCreate, WaitlistPromoteRequest
from app.services.waitlist_service import (
    WaitlistError,
    add_to_waitlist,
    get_waitlist_entry,
    promote_from_waitlist,
    request_payment_link_for_waitlist,
    suggest_waitlist_promotion,
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


def test_waitlist_suggestion_is_feasibility_only_and_does_not_promote(db):
    guest, category = _seed_waitlist_base(db, 1)
    room = Room(
        hotel_id=1,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    profile = AllocationPolicyProfile(
        hotel_id=1,
        code="revenue",
        name="Revenue objective",
        is_active=True,
    )
    db.add_all([room, profile])
    db.flush()
    db.add(
        AllocationPolicyVersion(
            hotel_id=1,
            profile_id=profile.id,
            version_number=1,
            source="manual",
            constraints_json=json.dumps({"optimization_objective": "net_revenue"}),
            weights_json="{}",
            is_published=True,
        )
    )
    entry = add_to_waitlist(
        db,
        1,
        WaitlistEntryCreate(
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 11, 1),
            check_out_date=date(2026, 11, 3),
        ),
    )
    db.flush()

    suggestion = suggest_waitlist_promotion(db, hotel_id=1, entry_id=entry.id)

    assert suggestion is not None
    assert suggestion["suggested_room_id"] == room.id
    assert len(suggestion["expected_entry_fingerprint"]) == 64
    assert suggestion["allocation_basis"] == "feasibility_only_no_price_snapshot"
    assert entry.status == WaitlistStatusEnum.WAITING
    assert entry.promoted_reservation_id is None
    assert db.query(Reservation).filter(Reservation.hotel_id == 1).count() == 0
    assert db.query(AllocationRun).filter(AllocationRun.hotel_id == 1).count() == 0


def test_waitlist_promotion_requires_a_reviewed_room_and_fingerprint():
    with pytest.raises(ValidationError):
        WaitlistPromoteRequest(room_id=1)
    with pytest.raises(ValidationError):
        WaitlistPromoteRequest(room_id=1, expected_entry_fingerprint="not-a-sha256")


def test_waitlist_promotion_rejects_entry_changed_after_suggestion(db):
    guest, category = _seed_waitlist_base(db, 1)
    room = Room(
        hotel_id=1,
        category_id=category.id,
        room_number="101",
        floor=1,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()
    entry = add_to_waitlist(
        db,
        1,
        WaitlistEntryCreate(
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 11, 1),
            check_out_date=date(2026, 11, 3),
        ),
    )
    suggestion = suggest_waitlist_promotion(db, hotel_id=1, entry_id=entry.id)
    assert suggestion is not None

    entry.priority += 1
    db.flush()

    with pytest.raises(WaitlistError, match="changed; request a new suggestion"):
        promote_from_waitlist(
            db,
            1,
            entry.id,
            room_id=suggestion["suggested_room_id"],
            expected_entry_fingerprint=suggestion["expected_entry_fingerprint"],
        )

    assert entry.status == WaitlistStatusEnum.WAITING
    assert db.query(Reservation).filter(Reservation.hotel_id == 1).count() == 0
