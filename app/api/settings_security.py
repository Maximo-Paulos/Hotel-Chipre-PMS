"""Tenant-scoped security overview and current-user session revocation."""

import csv
import json
from datetime import date, datetime, timedelta, timezone
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.hotel_membership import HotelMembership
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.settings_security import (
    RevokeAllSessionsResponse,
    AuditTimelineRead,
    SecurityCurrentUserRead,
    SecurityEventRead,
    SecurityEventsRead,
    SecurityOverviewRead,
)
from app.services.user_session_service import revoke_all_sessions
from app.services.audit_timeline_service import list_audit_timeline


router = APIRouter(prefix="/api/settings/security", tags=["Settings Security"])
_SECURITY_ROLES = ("owner", "co_owner")
_AUDIT_TIMELINE_EXPORT_MAX_ROWS = 5_000
_AUDIT_TIMELINE_CSV_FIELDS = (
    "source",
    "action",
    "actor_user_id",
    "created_at",
    "summary",
    "details",
)


def _current_user(db: Session, context: AuthContext) -> User:
    user = db.get(User, context.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no valido")
    return user


def _safe_resource_id(event: SecurityAuditLog) -> str | None:
    """Keep useful internal references while never exposing free-form details."""

    if event.resource_type in {
        "permission",
        "permission_override",
        "reservation",
        "company_document",
        "room_movement_group",
    }:
        return event.resource_id
    return None


def _validate_audit_timeline_range(from_date: date | None, to_date: date | None) -> None:
    if from_date is not None and to_date is not None and to_date < from_date:
        raise HTTPException(status_code=422, detail="to must be greater than or equal to from")


def _build_audit_timeline_csv(items: list[dict]) -> str:
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=_AUDIT_TIMELINE_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "source": item["source"],
                "action": item["action"],
                "actor_user_id": item["actor_user_id"],
                "created_at": item["created_at"].isoformat(),
                "summary": item["summary"],
                # ``list_audit_timeline`` has already applied the shared
                # redaction policy before this serializer sees the details.
                "details": json.dumps(item["details"], ensure_ascii=False, sort_keys=True),
            }
        )
    return output.getvalue()


@router.get("/overview", response_model=SecurityOverviewRead)
def security_overview(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_SECURITY_ROLES)),
):
    user = _current_user(db, context)
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    membership_scope = db.query(HotelMembership).filter(
        HotelMembership.hotel_id == context.hotel_id
    )
    event_scope = db.query(SecurityAuditLog).filter(
        SecurityAuditLog.hotel_id == context.hotel_id,
        SecurityAuditLog.created_at >= since,
    )
    settings = get_settings()
    return SecurityOverviewRead(
        hotel_id=context.hotel_id,
        session_timeout_minutes=int(getattr(settings, "JWT_EXPIRES_MINUTES", 60)),
        active_members=membership_scope.filter(HotelMembership.status == "active").count(),
        pending_invitations=membership_scope.filter(HotelMembership.status == "invited").count(),
        security_events_24h=event_scope.count(),
        permission_denials_24h=event_scope.filter(
            SecurityAuditLog.action == "permission.denied"
        ).count(),
        current_user=SecurityCurrentUserRead(
            id=user.id,
            email=user.email,
            role=context.user_role or "unknown",
            last_login=user.last_login,
            token_version=user.token_version or 0,
        ),
    )


@router.get("/events", response_model=SecurityEventsRead)
def recent_security_events(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_SECURITY_ROLES)),
):
    rows = (
        db.query(SecurityAuditLog)
        .filter(SecurityAuditLog.hotel_id == context.hotel_id)
        .order_by(SecurityAuditLog.created_at.desc(), SecurityAuditLog.id.desc())
        .limit(limit)
        .all()
    )
    return SecurityEventsRead(
        hotel_id=context.hotel_id,
        events=[
            SecurityEventRead(
                id=row.id,
                action=row.action,
                actor_user_id=row.user_id,
                resource_type=row.resource_type,
                resource_id=_safe_resource_id(row),
                created_at=row.created_at,
            )
            for row in rows
        ],
    )


@router.get("/audit-timeline", response_model=AuditTimelineRead)
def audit_timeline(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10_000),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_SECURITY_ROLES)),
):
    _validate_audit_timeline_range(from_date, to_date)

    items, total = list_audit_timeline(
        db,
        hotel_id=context.hotel_id,
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
    )
    return AuditTimelineRead(
        hotel_id=context.hotel_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )


@router.get(
    "/audit-timeline/export",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def export_audit_timeline(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_SECURITY_ROLES)),
):
    """Export the redacted unified timeline, capped at 5,000 rows per request."""

    _validate_audit_timeline_range(from_date, to_date)
    items, _total = list_audit_timeline(
        db,
        hotel_id=context.hotel_id,
        limit=_AUDIT_TIMELINE_EXPORT_MAX_ROWS,
        offset=0,
        from_date=from_date,
        to_date=to_date,
    )
    return Response(
        content=_build_audit_timeline_csv(items),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="audit-timeline-{context.hotel_id}.csv"'},
    )


@router.post("/revoke-all", response_model=RevokeAllSessionsResponse)
def revoke_current_user_sessions(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_SECURITY_ROLES)),
):
    """Invalidate every access token previously issued to the caller."""

    user = _current_user(db, context)
    user.token_version = (user.token_version or 0) + 1
    # Keep the legacy JWT invalidation and the new browser-session plane in
    # lockstep for the existing "close all sessions" control.
    revoke_all_sessions(db, user.id)
    db.add(
        SecurityAuditLog(
            hotel_id=context.hotel_id,
            user_id=user.id,
            action="security.sessions.revoked_all",
            resource_type="user_session",
            resource_id=None,
            details=None,
        )
    )
    db.commit()
    db.refresh(user)
    return RevokeAllSessionsResponse(
        revoked=True,
        user_id=user.id,
        token_version=user.token_version,
        reauthentication_required=True,
    )
