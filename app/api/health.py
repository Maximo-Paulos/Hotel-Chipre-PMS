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
    if not cache_enabled and not locks_enabled:
        return {
            "status": "disabled",
            "enabled": False,
            "connected": False,
            "cache_enabled": False,
            "distributed_locks_enabled": False,
            "distributed_locks_required": bool(settings.DISTRIBUTED_LOCK_REQUIRED),
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
            "error": str(exc),
        }


@router.get("/datastores")
def datastores_healthcheck() -> dict[str, Any]:
    return {
        "postgres": _postgres_healthcheck(),
        "redis": _redis_healthcheck(),
        "mongo": mongo_healthcheck(),
        "cassandra": cassandra_healthcheck(),
        "neo4j": neo4j_healthcheck(),
    }
