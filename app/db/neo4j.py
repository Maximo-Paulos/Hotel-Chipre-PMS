from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings


logger = logging.getLogger(__name__)
_neo4j_driver: Any | None = None


def get_neo4j_driver() -> Any | None:
    global _neo4j_driver
    settings = get_settings()
    if not settings.NEO4J_ENABLED:
        return None
    if _neo4j_driver is not None:
        return _neo4j_driver

    try:
        from neo4j import GraphDatabase

        _neo4j_driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            connection_timeout=2,
        )
        _neo4j_driver.verify_connectivity()
        return _neo4j_driver
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("neo4j.unavailable", extra={"error_type": type(exc).__name__})
        _neo4j_driver = None
        return None


def neo4j_healthcheck() -> dict[str, Any]:
    settings = get_settings()
    if not settings.NEO4J_ENABLED:
        return {"status": "disabled", "enabled": False, "connected": False, "error": None}

    try:
        driver = get_neo4j_driver()
        if driver is None:
            return {"status": "error", "enabled": True, "connected": False, "error": "Neo4j unavailable"}
        driver.verify_connectivity()
        return {"status": "ok", "enabled": True, "connected": True, "error": None}
    except Exception as exc:  # pragma: no cover - defensive runtime fallback
        logger.warning("neo4j.healthcheck_failed", extra={"error_type": type(exc).__name__})
        return {"status": "error", "enabled": True, "connected": False, "error": "Neo4j healthcheck failed"}
