"""PostgreSQL regressions for fail-fast room movement locks."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory
from app.services.room_movement_group_service import (
    ROOM_MOVE_LOCK_CONFLICT_DETAIL,
    RoomMovementGroupError,
    lock_room_for_movement,
)
from app.services.tenant_context import set_tenant_hotel_context


def test_opposite_room_movement_locks_fail_fast_in_two_postgres_transactions(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, expire_on_commit=False)
    suffix = uuid4().hex[:10].upper()
    hotel_id = 80_000_000 + uuid4().int % 10_000_000
    room_ids: tuple[int, int] | None = None

    seed = session_factory()
    try:
        set_tenant_hotel_context(seed, hotel_id)
        seed.add(HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic room move locks {suffix}"))
        seed.flush()
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Synthetic room move locks {suffix}",
            code=f"RM{suffix}",
            base_price_per_night=100,
            max_occupancy=2,
        )
        seed.add(category)
        seed.flush()
        rooms = [
            Room(hotel_id=hotel_id, room_number=f"L{suffix[:8]}{index}", category_id=category.id)
            for index in (1, 2)
        ]
        seed.add_all(rooms)
        seed.commit()
        room_ids = (rooms[0].id, rooms[1].id)
    finally:
        seed.close()

    first = session_factory()
    second = session_factory()
    try:
        set_tenant_hotel_context(first, hotel_id)
        set_tenant_hotel_context(second, hotel_id)
        first.execute(text("SET LOCAL statement_timeout = '2s'"))
        second.execute(text("SET LOCAL statement_timeout = '2s'"))

        # Each transaction holds the destination lock of an opposite move.
        assert lock_room_for_movement(first, hotel_id=hotel_id, room_id=room_ids[0]) is not None
        assert lock_room_for_movement(second, hotel_id=hotel_id, room_id=room_ids[1]) is not None

        # The next lock in each direction would form a wait cycle with blocking
        # FOR UPDATE. NOWAIT must turn both attempts into safe domain conflicts.
        first_attempt = first.begin_nested()
        try:
            with pytest.raises(RoomMovementGroupError, match=ROOM_MOVE_LOCK_CONFLICT_DETAIL):
                lock_room_for_movement(first, hotel_id=hotel_id, room_id=room_ids[1])
        finally:
            first_attempt.rollback()

        second_attempt = second.begin_nested()
        try:
            with pytest.raises(RoomMovementGroupError, match=ROOM_MOVE_LOCK_CONFLICT_DETAIL):
                lock_room_for_movement(second, hotel_id=hotel_id, room_id=room_ids[0])
        finally:
            second_attempt.rollback()
    finally:
        first.rollback()
        second.rollback()
        first.close()
        second.close()

        cleanup = session_factory()
        try:
            set_tenant_hotel_context(cleanup, hotel_id)
            if room_ids is not None:
                cleanup.query(Room).filter(Room.hotel_id == hotel_id, Room.id.in_(room_ids)).delete(
                    synchronize_session=False
                )
            cleanup.query(RoomCategory).filter(RoomCategory.hotel_id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).delete(
                synchronize_session=False
            )
            cleanup.commit()
        finally:
            cleanup.close()
