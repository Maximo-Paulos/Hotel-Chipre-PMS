"""PostgreSQL regression for waitlist suggestion freshness under row locks."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.schemas.waitlist import WaitlistEntryCreate
from app.services.tenant_context import set_tenant_hotel_context
from app.services.waitlist_service import (
    WaitlistError,
    add_to_waitlist,
    promote_from_waitlist,
    suggest_waitlist_promotion,
)


def test_postgres_waitlist_promotion_rejects_stale_suggestion(pg_session):
    suffix = uuid4().hex[:10].upper()
    hotel_id = 260_000_000 + uuid4().int % 20_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    pg_session.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic waitlist {suffix}"))
    pg_session.flush()

    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic waitlist category {suffix}",
        code=f"WL{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(hotel_id=hotel_id, first_name="Synthetic", last_name="Waitlist")
    pg_session.add_all([category, guest])
    pg_session.flush()

    room = Room(
        hotel_id=hotel_id,
        room_number=f"W{suffix[:8]}",
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
    )
    pg_session.add(room)
    pg_session.flush()

    check_in = date.today() + timedelta(days=30)
    entry = add_to_waitlist(
        pg_session,
        hotel_id,
        WaitlistEntryCreate(
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=check_in,
            check_out_date=check_in + timedelta(days=2),
        ),
    )
    suggestion = suggest_waitlist_promotion(pg_session, hotel_id=hotel_id, entry_id=entry.id)
    assert suggestion is not None

    entry.priority += 1
    pg_session.flush()

    with pytest.raises(WaitlistError, match="changed; request a new suggestion"):
        promote_from_waitlist(
            pg_session,
            hotel_id,
            entry.id,
            room_id=suggestion["suggested_room_id"],
            expected_entry_fingerprint=suggestion["expected_entry_fingerprint"],
        )

    assert pg_session.query(Reservation).filter(Reservation.hotel_id == hotel_id).count() == 0
