from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

import app.database as db_module
from app.config import get_settings
from app.db.cassandra import cassandra_healthcheck
from app.db.mongo import mongo_healthcheck
from app.db.neo4j import neo4j_healthcheck
from app.services.analytics_warehouse import AnalyticsWarehouseUnavailable, get_clickhouse_client
from app.infrastructure.redis_backend import get_sync_redis_client


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


def _postgres_healthcheck() -> dict[str, Any]:
    try:
        factory = db_module.get_session_factory()
        with factory() as db:
            db.execute(text("SELECT 1"))
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("postgres.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {"status": "error", "enabled": True, "connected": False, "error": "PostgreSQL healthcheck failed"}


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
        client = get_sync_redis_client(capability="health")
        if client is None:
            raise RuntimeError("Redis client unavailable")
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
        logger.warning("redis.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {
            "status": "error",
            "enabled": True,
            "connected": False,
            "cache_enabled": cache_enabled,
            "distributed_locks_enabled": locks_enabled,
            "distributed_locks_required": bool(settings.DISTRIBUTED_LOCK_REQUIRED),
            "realtime_events_enabled": realtime_enabled,
            "error": "Redis healthcheck failed",
        }


def _critical_lock_readiness(redis_payload: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    if not settings.DISTRIBUTED_LOCK_ENABLED:
        return {
            "status": "error" if settings.DISTRIBUTED_LOCK_REQUIRED else "disabled",
            "safe": not settings.DISTRIBUTED_LOCK_REQUIRED,
            "mechanism": "none",
        }
    if redis_payload.get("connected"):
        return {"status": "ok", "safe": True, "mechanism": "redis"}
    # distributed_lock.py uses a transaction-scoped PostgreSQL advisory lock
    # when Redis is unavailable. PostgreSQL is checked by the same readiness
    # response, so this is safe but explicitly degraded.
    return {"status": "degraded", "safe": True, "mechanism": "postgres_advisory_xact_lock"}


@router.get("/live")
def live_healthcheck() -> dict[str, Any]:
    """Process liveness only; never depends on PostgreSQL or Redis."""
    return {"status": "ok"}


@router.get("/ready")
def ready_healthcheck() -> JSONResponse:
    """Report whether the API can safely accept critical writes."""
    settings = get_settings()
    postgres = _postgres_healthcheck()
    redis = _redis_healthcheck()
    critical_lock = _critical_lock_readiness(redis)
    ready = postgres.get("connected") is True and critical_lock["safe"]
    payload = {
        "status": "ok" if ready else "error",
        "ready": ready,
        "postgres": postgres,
        "redis": redis,
        "critical_lock": critical_lock,
        "optional_degraded": bool(redis.get("status") == "error" and not settings.DISTRIBUTED_LOCK_REQUIRED),
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)


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
    except AnalyticsWarehouseUnavailable:
        return {"status": "error", "enabled": True, "connected": False, "error": "ClickHouse healthcheck failed"}
    except Exception as exc:  # pragma: no cover - provider-specific runtime failure
        logger.warning("clickhouse.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {"status": "error", "enabled": True, "connected": False, "error": "ClickHouse healthcheck failed"}


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
