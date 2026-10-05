"""Regression coverage for room soft-delete visibility across count surfaces."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect

from app.api.subscription import _serialize_status_payload
from app.models.analytics import FactRoomOccupancyDaily
from app.models.room import Room, RoomStatusEnum
from app.services import domain_events
from app.services import subscription_service
from app.services.analytics_facts import calculate_physical_room_nights_for_window, refresh_fact_room_occupancy_daily
from app.services.analytics_service import build_rooms_overview_payload, build_starter_summary_payload
from app.services.domain_events import PENDING_EVENTS_KEY
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
    fact_timestamp = datetime.now(timezone.utc)
    for fact in db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id):
        fact.is_occupied = fact.room_id in active_room_ids
        fact.updated_at = fact_timestamp
    db.flush()
    # ``queue_model_changes`` adds outbox rows during flush; flush a second
    # time so the queued ORM objects are persistent before expiring the session.
    db.flush()
    pending_events = db.info.get(PENDING_EVENTS_KEY, {})
    queued_outbox_changes = [change for change in pending_events.values() if change.outbox_event_id]
    assert queued_outbox_changes
    assert all(inspect(change.outbox).identity for change in queued_outbox_changes)
    # The analytics read below can repair stale facts and commit this session.
    # Keep queued outbox ORM objects expired to guard the after-commit path
    # against issuing lazy SQL through attributes on the committed session.
    db.expire_all()
    assert any("event_id" in inspect(change.outbox).expired_attributes for change in queued_outbox_changes)

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


def test_inline_fact_repair_commits_with_expired_outbox_objects(
    db,
    hotel_config,
    sample_categories,
    monkeypatch: pytest.MonkeyPatch,
):
    """Analytics repair can commit while queued outbox ORM objects are expired."""
    _create_rooms_with_soft_deleted_tail(db, category_id=sample_categories[0].id)
    repair_date = date(2026, 8, 31)
    refresh_fact_room_occupancy_daily(
        db,
        hotel_id=hotel_config.id,
        date_from=repair_date,
        date_to=repair_date,
    )

    stale_at = datetime.now(timezone.utc) - timedelta(hours=1)
    for fact in db.query(FactRoomOccupancyDaily).filter(FactRoomOccupancyDaily.hotel_id == hotel_config.id):
        fact.updated_at = stale_at
    db.flush()
    # Persist the outbox rows queued by after_flush before expiring their ORM
    # state, so the following read repair hits the exact post-commit case.
    db.flush()
    pending_events = db.info.get(PENDING_EVENTS_KEY, {})
    queued_outbox_changes = [change for change in pending_events.values() if change.outbox_event_id]
    assert queued_outbox_changes
    assert all(inspect(change.outbox).identity for change in queued_outbox_changes)
    change_under_test = queued_outbox_changes[0]
    expected_event_id = change_under_test.outbox_event_id
    expected_outbox_id = inspect(change_under_test.outbox).identity[0]
    assert expected_event_id
    # The first publish uses the persisted outbox primary key when no explicit
    # stream cursor has been assigned yet.
    assert change_under_test.outbox_cursor is None
    expected_cursor = expected_outbox_id
    expected_schema_version = change_under_test.outbox_schema_version or 1
    db.expire_all()
    assert any("event_id" in inspect(change.outbox).expired_attributes for change in queued_outbox_changes)

    original_publish = domain_events.publish_queued_domain_changes
    callback_sql_attempts = []
    published_calls = []

    def capture_publish_call(**kwargs):
        published_calls.append(dict(kwargs))
        return domain_events.DomainEvent(
            hotel_id=kwargs["hotel_id"],
            domain=kwargs["domain"],
            event_type=kwargs["event_type"],
            revision=17,
            occurred_at="2026-10-05T00:00:00+00:00",
            payload=kwargs["payload"],
            event_id=kwargs.get("event_id"),
            schema_version=kwargs.get("schema_version", 1),
            cursor=kwargs.get("cursor"),
        )

    monkeypatch.setattr(domain_events, "publish_domain_event", capture_publish_call)

    def guarded_publish(session):
        if session is not db:
            return original_publish(session)

        def reject_request_session_sql(*args, **kwargs):
            callback_sql_attempts.append((args, kwargs))
            raise AssertionError("after_commit must not issue SQL through the committed request session")

        # SQLAlchemy does not allow the committed Session to start another
        # transaction from after_commit. Fail and record any attempt even if
        # the publisher's defensive error handling catches it.
        with monkeypatch.context() as callback_guard:
            callback_guard.setattr(session, "execute", reject_request_session_sql)
            return original_publish(session)

    monkeypatch.setattr(domain_events, "publish_queued_domain_changes", guarded_publish)

    summary = build_starter_summary_payload(
        db,
        hotel_id=hotel_config.id,
        date_from=repair_date,
        date_to=repair_date,
    )
    assert summary["data"]["cards"]
    assert callback_sql_attempts == []
    matching_publish_calls = [
        call for call in published_calls if call.get("event_id") == expected_event_id
    ]
    assert len(matching_publish_calls) == 1
    published_call = matching_publish_calls[0]
    assert {"event_id", "cursor", "schema_version"}.issubset(published_call)
    assert published_call["event_id"] == expected_event_id
    assert published_call["cursor"] == expected_cursor
    assert published_call["schema_version"] == expected_schema_version == 1
    # The read-repair request continues to use its session after the commit
    # callback has published and recorded outbox attempts.
    assert db.query(FactRoomOccupancyDaily).count() == 39
