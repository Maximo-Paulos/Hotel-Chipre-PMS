"""Regression coverage for room soft-delete visibility across count surfaces."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.api.subscription import _serialize_status_payload
from app.models.analytics import FactRoomOccupancyDaily
from app.models.room import Room, RoomStatusEnum
from app.services import subscription_service
from app.services.analytics_facts import calculate_physical_room_nights_for_window, refresh_fact_room_occupancy_daily
from app.services.analytics_service import build_rooms_overview_payload, build_starter_summary_payload
from app.services.subscription_service import ensure_room_within_limit, set_subscription_plan


def _create_rooms_with_soft_deleted_tail(db, *, category_id: int) -> tuple[list[Room], set[int]]:
    """Create the reported 42-room case, leaving three soft-deleted rows active."""
    rooms = [
        Room(
            hotel_id=1,
            room_number=f"SD{number:03d}",
            floor=1,
            category_id=category_id,
            status=RoomStatusEnum.AVAILABLE,
            is_active=True,
        )
        for number in range(1, 43)
    ]
    db.add_all(rooms)
    db.flush()

    soft_deleted_ids = {room.id for room in rooms[-3:]}
    for room in rooms[-3:]:
        room.deleted_at = datetime.now(timezone.utc)
    db.flush()
    return rooms, soft_deleted_ids


@pytest.mark.parametrize(
    "surface",
    [
        "subscription_status",
        "room_creation_guard",
        "plan_change_validation",
        "physical_room_nights",
        "starter_occupancy",
        "rooms_overview",
    ],
)
def test_soft_deleted_rooms_are_excluded_from_every_room_count_surface(
    db,
    hotel_config,
    sample_categories,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
):
    """Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.

    This fails if a surface treats ``is_active`` as the only definition of an
    existing room, which is the state left by the room soft-delete endpoint.
    """
    rooms, soft_deleted_ids = _create_rooms_with_soft_deleted_tail(
        db,
        category_id=sample_categories[0].id,
    )
    assert len(rooms) == 42
    assert all(room.is_active for room in rooms if room.id in soft_deleted_ids)

    if surface == "subscription_status":
        assert _serialize_status_payload(db, hotel_config.id)["rooms_in_use"] == 39
        return

    if surface == "room_creation_guard":
        monkeypatch.setattr(subscription_service, "is_enforcement_enabled", lambda: False)
        set_subscription_plan(db, hotel_config.id, "pro")
        monkeypatch.setattr(subscription_service, "is_enforcement_enabled", lambda: True)

        ensure_room_within_limit(db, hotel_config.id)
        return

    if surface == "plan_change_validation":
        monkeypatch.setattr(subscription_service, "is_enforcement_enabled", lambda: True)

        result = set_subscription_plan(db, hotel_config.id, "pro")
        assert result["rooms_in_use"] == 39
        return

    if surface == "physical_room_nights":
        assert calculate_physical_room_nights_for_window(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 8, 31),
            date_to=date(2026, 8, 31),
        ) == 39
        return

    refresh = refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 8, 31),
        date_to=date(2026, 8, 31),
    )
    assert refresh.inserted == 39

    active_room_ids = {room.id for room in rooms} - soft_deleted_ids
    fact_timestamp = datetime(2026, 8, 31, tzinfo=timezone.utc)
    for fact in db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id):
        fact.is_occupied = fact.room_id in active_room_ids
        fact.updated_at = fact_timestamp
    db.flush()
    db.expire_all()

    summary = build_starter_summary_payload(
        db,
        hotel_id=hotel_config.id,
        date_from=date(2026, 8, 31),
        date_to=date(2026, 8, 31),
    )
    cards = {card["card_code"]: card for card in summary["data"]["cards"]}
    assert cards["starter_occupancy_today"]["value_pct"] == 100.0

    if surface == "rooms_overview":
        overview = build_rooms_overview_payload(
            db,
            hotel_id=hotel_config.id,
            date_from=date(2026, 8, 31),
            date_to=date(2026, 8, 31),
            compare_previous=False,
            compare_yoy=False,
            currency_display="ARS",
        )
        overview_cards = {card["card_code"]: card for card in overview["data"]["cards"]}
        assert len(overview["data"]["rooms"]) == 39
        assert overview_cards["rooms_total"]["value_count"] == 39
