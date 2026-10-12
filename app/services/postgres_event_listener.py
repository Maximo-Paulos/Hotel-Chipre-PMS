"""Low-volume PostgreSQL LISTEN/NOTIFY transport for durable domain events.

Notifications contain only invalidation metadata. The outbox remains the
durable source of truth, and callers fall back to bounded outbox polling when
the configured connection uses transaction pooling or LISTEN is unavailable.
"""

from __future__ import annotations

import json
import logging
import select
import threading
from typing import Any, Callable
from uuid import UUID

import psycopg2
from sqlalchemy.engine import make_url


logger = logging.getLogger(__name__)
POSTGRES_EVENT_NOTIFY_CHANNEL = "hotel_pms_domain_events"
MAX_NOTIFICATION_BYTES = 4 * 1024


def listener_connection_string(database_url: str, *, enabled: bool = True) -> str | None:
    """Return a psycopg2 URL only when session-level LISTEN can work.

    Supabase's shared transaction pooler uses port 6543 and does not preserve
    LISTEN state. Session mode (port 5432) and direct PostgreSQL connections
    support it. The URL is returned for use in memory and must never be logged.
    """

    if not enabled or not database_url:
        return None
    try:
        url = make_url(database_url)
    except (TypeError, ValueError):
        return None
    if not url.drivername.startswith("postgresql") or url.port == 6543:
        return None
    try:
        return url.set(drivername="postgresql").render_as_string(hide_password=False)
    except (TypeError, ValueError):  # pragma: no cover - defensive malformed URL
        return None


def parse_domain_event_notification(raw_payload: str) -> dict[str, Any] | None:
    """Validate and project a bounded, privacy-safe PostgreSQL notification."""

    if not isinstance(raw_payload, str) or not raw_payload:
        return None
    if len(raw_payload.encode("utf-8")) > MAX_NOTIFICATION_BYTES:
        return None
    try:
        raw = json.loads(raw_payload)
        row_id = int(raw["id"])
        hotel_id = int(raw["hotel_id"])
        # The PostgreSQL trigger names this field ``stream_cursor`` to match
        # the outbox column. Accept ``cursor`` as a compatibility alias for
        # notifications emitted by older deployments.
        cursor = int(raw.get("stream_cursor", raw.get("cursor")))
        revision = int(raw.get("revision") or 0)
        schema_version = int(raw.get("schema_version") or 1)
        event_id = str(raw["event_id"])
        domain = str(raw["domain"]).strip().lower()
        event_type = str(raw["event_type"]).strip()
        occurred_at = raw.get("occurred_at")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None

    raw_origin_key = raw.get("origin_key")
    try:
        origin_key = str(UUID(str(raw_origin_key))) if raw_origin_key is not None else None
    except (AttributeError, TypeError, ValueError):
        origin_key = None

    if (
        row_id <= 0
        or hotel_id <= 0
        or cursor <= 0
        or revision < 0
        or schema_version <= 0
        or not event_id
        or len(event_id) > 64
        or not domain
        or len(domain) > 50
        or not event_type
        or len(event_type) > 100
        or (occurred_at is not None and not isinstance(occurred_at, str))
    ):
        return None

    # Deliberately discard unknown fields so a future trigger cannot start
    # forwarding an outbox payload, guest data, or other business content.
    payload = {
        "id": row_id,
        "event_id": event_id,
        "hotel_id": hotel_id,
        "domain": domain,
        "event_type": event_type,
        "schema_version": schema_version,
        "stream_cursor": cursor,
        "revision": revision,
        "occurred_at": occurred_at,
    }
    if origin_key:
        payload["origin_key"] = origin_key
    return payload


class PostgresEventNotificationListener:
    """One reconnecting LISTEN connection shared by all SSE streams in a process."""

    def __init__(
        self,
        database_url: str,
        *,
        enabled: bool,
        on_notification: Callable[[dict[str, Any]], None],
        on_state_change: Callable[[bool], None],
        connect_timeout_seconds: int = 3,
    ) -> None:
        self._connection_string = listener_connection_string(database_url, enabled=enabled)
        self._on_notification = on_notification
        self._on_state_change = on_state_change
        self._connect_timeout_seconds = max(1, int(connect_timeout_seconds))
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._available = False

    @property
    def enabled(self) -> bool:
        return self._connection_string is not None

    @property
    def available(self) -> bool:
        with self._lock:
            return self._available

    def start(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="postgres-domain-event-listener",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        """Stop the listener and wait briefly for its socket loop to exit."""

        self._stop.set()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            # select() wakes at most once per second; connect() is also bounded.
            thread.join(timeout=self._connect_timeout_seconds + 1)
        with self._lock:
            if self._thread is thread and (thread is None or not thread.is_alive()):
                self._thread = None

    def _set_available(self, available: bool) -> None:
        changed = False
        with self._lock:
            if self._available != available:
                self._available = available
                changed = True
        if changed:
            try:
                self._on_state_change(available)
            except Exception as exc:  # pragma: no cover - defensive callback boundary
                logger.warning(
                    "realtime_events.postgres_listener_state_callback_failed",
                    extra={"error_type": type(exc).__name__},
                )

    def _run(self) -> None:
        backoff_seconds = 1
        while not self._stop.is_set():
            connection = None
            try:
                connection = psycopg2.connect(
                    self._connection_string,
                    connect_timeout=self._connect_timeout_seconds,
                )
                connection.autocommit = True
                with connection.cursor() as cursor:
                    # Channel is a fixed constant, never input from a request.
                    cursor.execute(f"LISTEN {POSTGRES_EVENT_NOTIFY_CHANNEL}")
                self._set_available(True)
                backoff_seconds = 1

                while not self._stop.is_set():
                    readable, _, _ = select.select([connection], [], [], 1.0)
                    if not readable:
                        continue
                    connection.poll()
                    while connection.notifies:
                        notification = connection.notifies.pop(0)
                        payload = parse_domain_event_notification(notification.payload)
                        if payload is None:
                            continue
                        try:
                            self._on_notification(payload)
                        except Exception as exc:  # pragma: no cover - defensive callback boundary
                            logger.warning(
                                "realtime_events.postgres_listener_notification_callback_failed",
                                extra={"error_type": type(exc).__name__},
                            )
            except Exception as exc:  # provider outages use the PostgreSQL polling fallback
                self._set_available(False)
                logger.warning(
                    "realtime_events.postgres_listener_unavailable",
                    extra={
                        "error_type": type(exc).__name__,
                        "retry_seconds": backoff_seconds,
                    },
                )
                self._stop.wait(backoff_seconds)
                backoff_seconds = min(backoff_seconds * 2, 30)
            finally:
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:  # pragma: no cover - cleanup should not mask disconnect
                        pass
                self._set_available(False)
