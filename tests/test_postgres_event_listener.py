from __future__ import annotations

import json

from sqlalchemy.engine import make_url

from app.services.postgres_event_listener import (
    MAX_NOTIFICATION_BYTES,
    listener_connection_string,
    parse_domain_event_notification,
)


def test_listener_uses_session_connections_but_skips_supabase_transaction_pooler():
    direct = listener_connection_string(
        "postgresql+psycopg2://pms:secret@db.example.test:5432/hotel?sslmode=require"
    )
    transaction_pooler = listener_connection_string(
        "postgresql://pms:secret@pooler.example.test:6543/hotel?sslmode=require"
    )

    assert direct is not None
    parsed_direct = make_url(direct)
    assert parsed_direct.drivername == "postgresql"
    assert parsed_direct.host == "db.example.test"
    assert parsed_direct.port == 5432
    assert parsed_direct.query["sslmode"] == "require"
    assert transaction_pooler is None
    assert listener_connection_string("sqlite:///local.db") is None
    assert listener_connection_string(direct, enabled=False) is None


def test_notification_parser_keeps_only_bounded_invalidation_metadata():
    origin_key = "123e4567-e89b-42d3-a456-426614174000"
    raw = json.dumps(
        {
            "id": 31,
            "event_id": "event-31",
            "hotel_id": 9,
            "domain": "reservations",
            "event_type": "reservation.updated",
            "schema_version": 1,
            "stream_cursor": 31,
            "revision": 0,
            "occurred_at": "2026-10-09T12:00:00+00:00",
            "origin_key": origin_key,
            "payload": {"guest_name": "must not escape"},
        }
    )

    parsed = parse_domain_event_notification(raw)

    assert parsed == {
        "id": 31,
        "event_id": "event-31",
        "hotel_id": 9,
        "domain": "reservations",
        "event_type": "reservation.updated",
        "schema_version": 1,
        "stream_cursor": 31,
        "revision": 0,
        "occurred_at": "2026-10-09T12:00:00+00:00",
        "origin_key": origin_key,
    }
    assert "payload" not in parsed
    invalid_origin = json.loads(raw)
    invalid_origin["origin_key"] = "not-a-uuid"
    sanitized = parse_domain_event_notification(json.dumps(invalid_origin))
    assert sanitized is not None
    assert "origin_key" not in sanitized
    assert parse_domain_event_notification("not-json") is None
    assert parse_domain_event_notification("x" * (MAX_NOTIFICATION_BYTES + 1)) is None
