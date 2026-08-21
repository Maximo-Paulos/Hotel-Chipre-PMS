from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)
_mongo_db: Any | None = None


def get_mongo_db() -> Any | None:
    global _mongo_db
    settings = get_settings()
    if not settings.MONGO_ENABLED:
        return None
    if _mongo_db is not None:
        return _mongo_db

    try:
        import pymongo

        client = pymongo.MongoClient(
            settings.MONGO_URL,
            serverSelectionTimeoutMS=1500,
            connectTimeoutMS=1500,
            socketTimeoutMS=1500,
        )
        client.admin.command("ping")
        _mongo_db = client[settings.MONGO_DB]
        return _mongo_db
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("mongo.unavailable", extra={"error_type": type(exc).__name__})
        _mongo_db = None
        return None


def mongo_healthcheck() -> dict[str, Any]:
    settings = get_settings()
    if not settings.MONGO_ENABLED:
        return {"status": "disabled", "enabled": False, "connected": False, "error": None}

    try:
        db = get_mongo_db()
        if db is None:
            return {"status": "error", "enabled": True, "connected": False, "error": "MongoDB unavailable"}
        db.command("ping")
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("mongo.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {"status": "error", "enabled": True, "connected": False, "error": "MongoDB healthcheck failed"}
