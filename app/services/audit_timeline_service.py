"""Read-only, tenant-scoped projection of the three hotel audit streams."""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.analytics import HotelAuditEvent
from app.models.audit_log import AuditLog
from app.models.security_audit_log import SecurityAuditLog


_REDACTED = "[REDACTED]"
_SENSITIVE_KEY_RE = re.compile(
    r"(?:password|passwd|passphrase|secret|token|totp|otp|mfa|recovery|"
    r"credential|authorization|cookie|session|private.?key|api.?key|"
    r"access.?key|refresh.?key|id.?token|assertion|jwt|bearer|signature|code)",
    re.IGNORECASE,
)
_SENSITIVE_TEXT_RE = re.compile(
    r"(?i)(?:bearer\s+|(?:password|passwd|secret|token|totp|otp|recovery|"
    r"authorization|cookie|session|private[_ -]?key|api[_ -]?key|"
    r"access[_ -]?token|refresh[_ -]?token|id[_ -]?token|jwt|code)\s*[:=]\s*)"
    r"[^,;\s}\]]+"
)
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b")
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SAFE_SECURITY_RESOURCE_TYPES = frozenset(
    {
        "permission",
        "permission_override",
        "reservation",
        "company_document",
        "room_movement_group",
    }
)


def _redact_text(value: str) -> str:
    """Remove credential-like values from otherwise useful text fields."""

    value = _SENSITIVE_TEXT_RE.sub(lambda match: match.group(0).split(":")[0].split("=")[0] + _REDACTED, value)
    value = _JWT_RE.sub(_REDACTED, value)
    return _EMAIL_RE.sub(_REDACTED, value)


def _redact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _redact_value(item)
            for key, item in value.items()
            if not _SENSITIVE_KEY_RE.search(str(key))
        }
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return [_redact_value(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _parse_redacted_json(raw: str | None) -> Any:
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        # Free-form audit text is not safe to echo. The event metadata and
        # summary remain available without exposing an unstructured secret.
        return {"redacted": True}
    if isinstance(parsed, (dict, list)):
        return _redact_value(parsed)
    return {"value": _REDACTED}


def _source_filters(model: Any, hotel_id: int, from_date: date | None, to_date: date | None) -> list[Any]:
    filters: list[Any] = [model.hotel_id == hotel_id]
    if from_date is not None:
        filters.append(model.created_at >= from_date)
    if to_date is not None:
        filters.append(model.created_at < to_date + timedelta(days=1))
    return filters


def _safe_resource_id(source: str, resource_type: str | None, resource_id: str | None) -> str | None:
    if source == "security_event" and resource_type not in _SAFE_SECURITY_RESOURCE_TYPES:
        return None
    return resource_id


def _summary(source: str, action: str, resource_type: str | None, resource_id: str | None) -> str:
    target = resource_type or "registro"
    if resource_id is not None:
        target = f"{target} #{resource_id}"
    if source == "security_event":
        return f"Evento de seguridad: {action} ({target})"
    if source == "business_event":
        return f"Evento de negocio: {action} ({target})"
    return f"Mutación de fila: {action} ({target})"


def _details_for_row(row: Any) -> dict[str, Any]:
    source = row["source"]
    resource_id = _safe_resource_id(source, row["resource_type"], row["resource_id"])
    details: dict[str, Any] = {}
    if row["resource_type"] is not None:
        details["resource_type"] = row["resource_type"]
    if resource_id is not None:
        details["resource_id"] = resource_id

    if source == "security_event":
        parsed = _parse_redacted_json(row["details_text"])
        if parsed is not None:
            details["event_details"] = parsed
        return details

    before = _parse_redacted_json(row["before_payload"])
    after = _parse_redacted_json(row["after_payload"])
    if before is not None:
        details["before"] = before
    if after is not None:
        details["after"] = after
    return details


def list_audit_timeline(
    db: Session,
    *,
    hotel_id: int,
    limit: int,
    offset: int,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return a globally ordered, paginated projection of all audit sources.

    The three source queries fetch only their first ``offset + limit`` rows.
    That bounded prefix is sufficient to produce the global page, while
    avoiding a PostgreSQL UNION between timestamp columns with different
    timezone types.
    """

    candidate_limit = offset + limit
    source_rows: list[dict[str, Any]] = []
    total = 0

    audit_query = db.query(AuditLog).filter(*_source_filters(AuditLog, hotel_id, from_date, to_date))
    total += audit_query.count()
    source_rows.extend(
        {
            "source": "row_mutation",
            "source_id": event.id,
            "action": event.action.value if hasattr(event.action, "value") else str(event.action),
            "actor_user_id": event.actor_user_id,
            "created_at": event.created_at,
            "resource_type": event.table_name,
            "resource_id": str(event.record_id),
            "details_text": None,
            "before_payload": event.payload_before,
            "after_payload": event.payload_after,
        }
        for event in audit_query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(candidate_limit).all()
    )

    business_query = db.query(HotelAuditEvent).filter(
        *_source_filters(HotelAuditEvent, hotel_id, from_date, to_date)
    )
    total += business_query.count()
    source_rows.extend(
        {
            "source": "business_event",
            "source_id": event.id,
            "action": event.action_code,
            "actor_user_id": event.user_id,
            "created_at": event.created_at,
            "resource_type": event.entity_type,
            "resource_id": str(event.entity_id) if event.entity_id is not None else None,
            "details_text": None,
            "before_payload": event.before_json,
            "after_payload": event.after_json,
        }
        for event in business_query.order_by(HotelAuditEvent.created_at.desc(), HotelAuditEvent.id.desc())
        .limit(candidate_limit)
        .all()
    )

    security_query = db.query(SecurityAuditLog).filter(
        *_source_filters(SecurityAuditLog, hotel_id, from_date, to_date)
    )
    total += security_query.count()
    source_rows.extend(
        {
            "source": "security_event",
            "source_id": event.id,
            "action": event.action,
            "actor_user_id": event.user_id,
            "created_at": event.created_at,
            "resource_type": event.resource_type,
            "resource_id": event.resource_id,
            "details_text": event.details,
            "before_payload": None,
            "after_payload": None,
        }
        for event in security_query.order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc())
        .limit(candidate_limit)
        .all()
    )

    def sort_key(row: dict[str, Any]) -> tuple[datetime, str, int]:
        created_at = row["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)
        return created_at, row["source"], row["source_id"]

    rows = sorted(source_rows, key=sort_key, reverse=True)[offset : offset + limit]

    items: list[dict[str, Any]] = []
    for row in rows:
        safe_resource_id = _safe_resource_id(row["source"], row["resource_type"], row["resource_id"])
        created_at = row["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)
        items.append(
            {
                "source": row["source"],
                "action": row["action"],
                "actor_user_id": row["actor_user_id"],
                "created_at": created_at,
                "summary": _summary(row["source"], row["action"], row["resource_type"], safe_resource_id),
                "details": _details_for_row(row),
            }
        )
    return items, int(total)
