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

_GUEST_AUDIT_FIELDS = frozenset(
    {
        "id",
        "hotel_id",
        "rating",
        "terms_accepted",
        "created_at",
        "updated_at",
        "retention_until",
    }
)
_GUEST_COMPANION_AUDIT_FIELDS = frozenset({"id", "guest_id"})
_AUDIT_FIELDS_BY_TABLE = {
    "guests": _GUEST_AUDIT_FIELDS,
    "guest_companions": _GUEST_COMPANION_AUDIT_FIELDS,
}


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
    snapshot = {
        column.name: getattr(entity, column.name, None)
        for column in entity.__table__.columns
        if not column.name.startswith("_")
    }
    return sanitize_audit_payload(entity.__tablename__, snapshot)


def sanitize_audit_payload(table_name: str, payload: dict[str, Any] | str | None) -> dict[str, Any] | str | None:
    """Allow-list guest audit context before persistence or external projection."""

    allowed_fields = _AUDIT_FIELDS_BY_TABLE.get(table_name)
    if allowed_fields is None or payload is None:
        return payload

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (TypeError, ValueError):
            return None

    if not isinstance(payload, dict):
        return None

    return {field: payload[field] for field in allowed_fields if field in payload}


def payload_json(payload: dict[str, Any] | str | None, *, table_name: str | None = None) -> str | None:
    if table_name is not None:
        payload = sanitize_audit_payload(table_name, payload)
    if not payload:
        return None
    if isinstance(payload, str):
        return payload
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
        payload_before=payload_json(payload_before, table_name=table_name),
        payload_after=payload_json(payload_after, table_name=table_name),
    )
    db.add(audit_log)
    db.commit()
    return audit_log


def queue_audit_log(
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
        payload_before=payload_json(payload_before, table_name=table_name),
        payload_after=payload_json(payload_after, table_name=table_name),
    )
    db.add(audit_log)
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
    """Best-effort audit log: a failure here must never discard the caller's
    real, already-flushed change (production incident 2026-07-28 -- a stray
    NOT NULL column left over on audit_logs from an old schema made every
    insert here fail, and the plain db.rollback() that used to run on that
    failure wiped out the caller's pending stock-item soft-delete in the same
    session, so DELETE /api/stock/items/{id} returned 204 while the item was
    never actually deleted). Runs inside a SAVEPOINT so any failure here rolls
    back only this audit row, never the caller's outer transaction.
    """
    audit_action = action if isinstance(action, AuditActionEnum) else AuditActionEnum(action)
    try:
        with db.begin_nested():
            audit_log = queue_audit_log(
                db,
                hotel_id=hotel_id,
                table_name=table_name,
                record_id=record_id,
                action=audit_action,
                actor_user_id=actor_user_id,
                payload_before=payload_before,
                payload_after=payload_after,
            )
            db.flush()
        return audit_log
    except Exception:
        logger.exception(
            "Audit logging failed table=%s record_id=%s action=%s hotel_id=%s",
            table_name,
            record_id,
            audit_action.value,
            hotel_id,
        )
        return None
