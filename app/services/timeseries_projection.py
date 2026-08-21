from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, time, timezone
from typing import Any

from app.config import get_settings
from app.db.cassandra import get_cassandra_session


logger = logging.getLogger(__name__)

_schema_initialized = False
_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _cql_identifier(value: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise ValueError("Invalid Cassandra identifier")
    return value


def _to_datetime(value: datetime | date) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _json_payload(payload: Any) -> str:
    return json.dumps(payload or {}, ensure_ascii=True, sort_keys=True, default=str)


def _room_state_event_row(
    hotel_id: int,
    room_id: int,
    event_type: str,
    occurred_at: datetime | date,
    payload: Any,
) -> dict[str, Any]:
    occurred = _to_datetime(occurred_at)
    return {
        "hotel_id": int(hotel_id),
        "event_date": occurred.date(),
        "occurred_at": occurred,
        "room_id": int(room_id),
        "event_type": str(_enum_value(event_type)),
        "payload": _json_payload(payload),
    }


def _daily_rate_change_row(
    hotel_id: int,
    category_id: int,
    rate_date: date,
    price: float,
    changed_at: datetime | date,
) -> dict[str, Any]:
    return {
        "hotel_id": int(hotel_id),
        "rate_date": rate_date,
        "changed_at": _to_datetime(changed_at),
        "category_id": int(category_id),
        "price": float(price),
    }


def _schema_statements(keyspace: str) -> list[str]:
    keyspace = _cql_identifier(keyspace)
    return [
        (
            f"CREATE KEYSPACE IF NOT EXISTS {keyspace} "
            "WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 1}"
        ),
        (
            f"CREATE TABLE IF NOT EXISTS {keyspace}.room_state_events ("
            "hotel_id int, "
            "event_date date, "
            "occurred_at timestamp, "
            "room_id int, "
            "event_type text, "
            "payload text, "
            "PRIMARY KEY ((hotel_id, event_date), occurred_at, room_id)"
            ") WITH CLUSTERING ORDER BY (occurred_at DESC, room_id ASC)"
        ),
        (
            f"CREATE TABLE IF NOT EXISTS {keyspace}.daily_rate_history ("
            "hotel_id int, "
            "rate_date date, "
            "changed_at timestamp, "
            "category_id int, "
            "price double, "
            "PRIMARY KEY ((hotel_id, rate_date), changed_at, category_id)"
            ") WITH CLUSTERING ORDER BY (changed_at DESC, category_id ASC)"
        ),
    ]


def ensure_cassandra_schema(session: Any | None) -> None:
    global _schema_initialized
    if session is None or _schema_initialized:
        return
    for statement in _schema_statements(get_settings().CASSANDRA_KEYSPACE):
        session.execute(statement)
    _schema_initialized = True


def project_room_state_event(
    hotel_id: int,
    room_id: int,
    event_type: str,
    occurred_at: datetime | date,
    payload: Any,
) -> None:
    try:
        session = get_cassandra_session()
        if session is None:
            return
        ensure_cassandra_schema(session)
        row = _room_state_event_row(hotel_id, room_id, event_type, occurred_at, payload)
        session.execute(
            (
                "INSERT INTO room_state_events "
                "(hotel_id, event_date, occurred_at, room_id, event_type, payload) "
                "VALUES (%(hotel_id)s, %(event_date)s, %(occurred_at)s, %(room_id)s, %(event_type)s, %(payload)s)"
            ),
            row,
        )
    except Exception as exc:  # pragma: no cover - defensive datastore isolation
        logger.warning("cassandra.room_state_projection_failed", extra={"error_type": type(exc).__name__})


def project_daily_rate_change(
    hotel_id: int,
    category_id: int,
    rate_date: date,
    price: float,
    changed_at: datetime | date,
) -> None:
    try:
        session = get_cassandra_session()
        if session is None:
            return
        ensure_cassandra_schema(session)
        row = _daily_rate_change_row(hotel_id, category_id, rate_date, price, changed_at)
        session.execute(
            (
                "INSERT INTO daily_rate_history "
                "(hotel_id, rate_date, changed_at, category_id, price) "
                "VALUES (%(hotel_id)s, %(rate_date)s, %(changed_at)s, %(category_id)s, %(price)s)"
            ),
            row,
        )
    except Exception as exc:  # pragma: no cover - defensive datastore isolation
        logger.warning("cassandra.daily_rate_projection_failed", extra={"error_type": type(exc).__name__})
