from datetime import date
from decimal import Decimal
from uuid import uuid4

from app.dependencies.auth import AuthContext
from app.models.analytics import (
    FactRoomOccupancyDaily,
    FactRoomOccupancyStatusAtNightEnum,
)
from app.models.hotel_config import HotelConfiguration
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.user import User
from app.schemas.analytics_api import RoomStateEventCreate
from app.services.tenant_context import set_tenant_hotel_context


def test_postgres_room_state_event_create_with_server_time_and_materialized_facts(
    pg_session, monkeypatch
):
    """Exercise the route's write/commit path against a materialized PostgreSQL fact."""
    from app.api import room_state_events

    suffix = uuid4().hex[:10].upper()
    hotel_id = 300_000_000 + uuid4().int % 100_000_000
    set_tenant_hotel_context(pg_session, hotel_id)

    hotel = HotelConfiguration(id=hotel_id, hotel_name=f"Synthetic room event {suffix}")
    pg_session.add(hotel)
    pg_session.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Synthetic event category {suffix}",
        code=f"RE{suffix}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    actor = User(
        email=f"room-event-{suffix.lower()}@example.test",
        password_hash="test-only-hash",
        role="owner",
        is_active=True,
        is_verified=True,
    )
    pg_session.add_all([category, actor])
    pg_session.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"E{suffix[:8]}",
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
    )
    pg_session.add(room)
    pg_session.flush()
    pg_session.add(
        FactRoomOccupancyDaily(
            hotel_id=hotel_id,
            room_id=room.id,
            stay_date=date.today(),
            category_id=category.id,
            status_at_night=FactRoomOccupancyStatusAtNightEnum.AVAILABLE,
            is_sellable_night=True,
            is_occupied=False,
            reservation_id=None,
            revenue_net_ars=Decimal(0),
            revenue_net_usd=Decimal(0),
            margin_operating_ars=Decimal(0),
            margin_operating_usd=Decimal(0),
        )
    )
    pg_session.flush()

    monkeypatch.setattr(room_state_events, "require_analytics_plan", lambda *_args: None)
    monkeypatch.setattr(room_state_events, "project_room_state_event", lambda *_args, **_kwargs: None)

    event = room_state_events.create_room_state_event_route(
        RoomStateEventCreate(
            room_id=room.id,
            event_type="maintenance",
            reason_code="inspection",
            reason_note=None,
            started_at=None,
        ),
        db=pg_session,
        context=AuthContext(
            hotel_id=hotel_id,
            user_id=actor.id,
            user_role="owner",
            is_verified=True,
        ),
    )

    assert event.id is not None
    assert event.started_at is not None
    assert pg_session.query(FactRoomOccupancyDaily).filter_by(
        hotel_id=hotel_id, room_id=room.id, stay_date=date.today()
    ).one().status_at_night == FactRoomOccupancyStatusAtNightEnum.MAINTENANCE
