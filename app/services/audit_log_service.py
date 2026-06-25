from __future__ import annotations

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum, AuditLog

logger = logging.getLogger(__name__)


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def model_snapshot(entity: Any) -> dict[str, Any] | None:
    if entity is None or not hasattr(entity, "__table__"):
        return None
    return {
        column.name: getattr(entity, column.name, None)
        for column in entity.__table__.columns
        if not column.name.startswith("_")
    }


def payload_json(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    return json.dumps(payload, sort_keys=True, default=_json_default)


def create_audit_log(
    db: Session,
    *,
    hotel_id: int,
    table_name: str,
    record_id: int,
    action: AuditActionEnum | str,
    actor_user_id: int | None = None,
    payload_before: dict[str, Any] | str | None = None,
    payload_after: dict[str, Any] | str | None = None,
) -> AuditLog:
    audit_action = action if isinstance(action, AuditActionEnum) else AuditActionEnum(action)
    audit_log = AuditLog(
        hotel_id=hotel_id,
        table_name=table_name,
        record_id=record_id,
        action=audit_action,
        actor_user_id=actor_user_id,
        payload_before=payload_before if isinstance(payload_before, str) else payload_json(payload_before),
        payload_after=payload_after if isinstance(payload_after, str) else payload_json(payload_after),
    )
    db.add(audit_log)
    db.commit()
    return audit_log


def safe_create_audit_log(
    db: Session,
    *,
    hotel_id: int,
    table_name: str,
    record_id: int,
    action: AuditActionEnum | str,
    actor_user_id: int | None = None,
    payload_before: dict[str, Any] | str | None = None,
    payload_after: dict[str, Any] | str | None = None,
) -> AuditLog | None:
    try:
        return create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name=table_name,
            record_id=record_id,
            action=action,
            actor_user_id=actor_user_id,
            payload_before=payload_before,
            payload_after=payload_after,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Audit logging failed table=%s record_id=%s action=%s hotel_id=%s",
            table_name,
            record_id,
            action.value if isinstance(action, AuditActionEnum) else action,
            hotel_id,
        )
        return None
