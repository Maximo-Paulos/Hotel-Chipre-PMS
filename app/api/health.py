from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

import app.database as db_module
from app.config import get_settings
from app.db.cassandra import cassandra_healthcheck
from app.db.mongo import mongo_healthcheck
from app.db.neo4j import neo4j_healthcheck
from app.services.analytics_warehouse import AnalyticsWarehouseUnavailable, get_clickhouse_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


def _postgres_healthcheck() -> dict[str, Any]:
    try:
        factory = db_module.get_session_factory()
        with factory() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("postgres.healthcheck_failed", extra={"error": str(exc)})
        return {"status": "error", "enabled": True, "connected": False, "error": str(exc)}


def _redis_healthcheck() -> dict[str, Any]:
    settings = get_settings()
    cache_enabled = bool(settings.READ_MODEL_CACHE_ENABLED)
    locks_enabled = bool(settings.DISTRIBUTED_LOCK_ENABLED)
    realtime_enabled = bool(settings.REALTIME_EVENTS_ENABLED)
    if not cache_enabled and not locks_enabled and not realtime_enabled:
        return {
            "status": "disabled",
            "enabled": False,
            "connected": False,
            "cache_enabled": False,
            "distributed_locks_enabled": False,
            "distributed_locks_required": bool(settings.DISTRIBUTED_LOCK_REQUIRED),
            "realtime_events_enabled": False,
            "error": None,
        }

    try:
        import redis

        client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1, socket_timeout=1)
        client.ping()
        return {
            "status": "ok",
            "enabled": True,
            "connected": True,
            "cache_enabled": cache_enabled,
            "distributed_locks_enabled": locks_enabled,
            "distributed_locks_required": bool(settings.DISTRIBUTED_LOCK_REQUIRED),
            "realtime_events_enabled": realtime_enabled,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("redis.healthcheck_failed", extra={"error": str(exc)})
        return {
            "status": "error",
            "enabled": True,
            "connected": False,
            "cache_enabled": cache_enabled,
            "distributed_locks_enabled": locks_enabled,
            "distributed_locks_required": bool(settings.DISTRIBUTED_LOCK_REQUIRED),
            "realtime_events_enabled": realtime_enabled,
            "error": str(exc),
        }


def _clickhouse_healthcheck() -> dict[str, Any]:
    settings = get_settings()
    if not settings.CLICKHOUSE_ENABLED:
        return {"status": "disabled", "enabled": False, "connected": False, "error": None}
    try:
        client = get_clickhouse_client()
        if client is None:
            return {
                "status": "error" if settings.CLICKHOUSE_REQUIRED else "disabled",
                "enabled": True,
                "connected": False,
                "error": "ClickHouse warehouse is not configured",
            }
        client.execute("SELECT 1 FORMAT JSONCompact")
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except AnalyticsWarehouseUnavailable as exc:
        return {"status": "error", "enabled": True, "connected": False, "error": str(exc)}
    except Exception as exc:  # pragma: no cover - provider-specific runtime failure
        logger.warning("clickhouse.healthcheck_failed", extra={"error": str(exc)})
        return {"status": "error", "enabled": True, "connected": False, "error": str(exc)}


@router.get("/datastores")
def datastores_healthcheck() -> dict[str, Any]:
    return {
        "postgres": _postgres_healthcheck(),
        "redis": _redis_healthcheck(),
        "clickhouse": _clickhouse_healthcheck(),
        "mongo": mongo_healthcheck(),
        "cassandra": cassandra_healthcheck(),
        "neo4j": neo4j_healthcheck(),
    }
