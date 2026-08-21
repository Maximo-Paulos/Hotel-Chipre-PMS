from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)
_cassandra_session: Any | None = None


def _contact_points(raw_hosts: str) -> list[str]:
    return [host.strip() for host in raw_hosts.split(",") if host.strip()]


def get_cassandra_session() -> Any | None:
    global _cassandra_session
    settings = get_settings()
    if not settings.CASSANDRA_ENABLED:
        return None
    if _cassandra_session is not None:
        return _cassandra_session

    try:
        from cassandra.cluster import Cluster

        hosts = _contact_points(settings.CASSANDRA_HOSTS) or ["localhost"]
        cluster = Cluster(contact_points=hosts, connect_timeout=2, control_connection_timeout=2)
        _cassandra_session = cluster.connect(settings.CASSANDRA_KEYSPACE)
        return _cassandra_session
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("cassandra.unavailable", extra={"error_type": type(exc).__name__})
        _cassandra_session = None
        return None


def cassandra_healthcheck() -> dict[str, Any]:
    settings = get_settings()
    if not settings.CASSANDRA_ENABLED:
        return {"status": "disabled", "enabled": False, "connected": False, "error": None}

    try:
        session = get_cassandra_session()
        if session is None:
            return {"status": "error", "enabled": True, "connected": False, "error": "Cassandra unavailable"}
        session.execute("SELECT now() FROM system.local")
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("cassandra.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {"status": "error", "enabled": True, "connected": False, "error": "Cassandra healthcheck failed"}
