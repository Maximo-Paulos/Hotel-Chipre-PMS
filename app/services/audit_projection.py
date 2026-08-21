from __future__ import annotations

import logging
from typing import Any

from app.db.mongo import get_mongo_db


logger = logging.getLogger(__name__)


def project_audit_to_mongo(doc: dict[str, Any]) -> None:
    db = get_mongo_db()
    if db is None:
        return
    try:
        db.audit_logs.insert_one(doc)
    except Exception as exc:  # pragma: no cover - defensive projection isolation
        logger.debug("audit_projection.mongo_insert_failed", extra={"error_type": type(exc).__name__})
