from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.master_admin.models import PrivacyRetentionHold
from app.master_admin.security import (
    allow_master_admin_mfa_attempt,
    audit_master_action,
    require_master_admin,
    reset_master_admin_mfa_attempts,
)
from app.models.marketing import MarketingLead
from app.models.public_inquiry import PublicInquiry
from app.services import mfa_service
from app.services.security import verify_password


router = APIRouter(prefix="/privacy-retention", tags=["Master Admin"])

ResourceType = Literal["marketing_lead", "public_inquiry"]
HoldReason = Literal["litigation", "regulatory", "contractual", "other"]
ReleaseReason = Literal["litigation_concluded", "obligation_ended", "entered_in_error", "other"]
_CASE_REFERENCE_RE = re.compile(
    r"^(?:CASE|MATTER|LEGAL|REG|CONTRACT|EXP)(?:-|\.|_|/)\d{4}(?:-|\.|_|/)\d{1,6}(?:(?:-|\.|_|/)\d{1,4})?$",
    re.IGNORECASE,
)


def _validate_case_reference(value: str) -> str:
    value = value.strip()
    if not _CASE_REFERENCE_RE.fullmatch(value):
        raise ValueError("Use an opaque reference such as CASE-2026-41; personal names, contact details, and government identifiers are not allowed")
    return value


class RetentionHoldCreate(BaseModel):
    resource_type: ResourceType
    record_id: int = Field(gt=0)
    reason_code: HoldReason
    case_reference: str = Field(min_length=1, max_length=120)
    hold_until: datetime | None = None

    @field_validator("case_reference")
    @classmethod
    def validate_case_reference(cls, value: str) -> str:
        return _validate_case_reference(value)

    @field_validator("hold_until")
    @classmethod
    def require_timezone_for_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("hold_until must include a timezone")
        return value.astimezone(timezone.utc) if value is not None else None


class RetentionHoldRelease(BaseModel):
    reason_code: ReleaseReason
    case_reference: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)
    mfa_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")

    @field_validator("case_reference")
    @classmethod
    def validate_case_reference(cls, value: str) -> str:
        return _validate_case_reference(value)


class RetentionTargetSearch(BaseModel):
    resource_type: ResourceType
    query: str = Field(min_length=1, max_length=320)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(character) < 32 for character in value):
            raise ValueError("query must be non-empty and contain no control characters")
        if not value.isdecimal() and "@" not in value:
            raise ValueError("Search by record ID or exact email")
        return value


class RetentionHoldRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    resource_type: ResourceType
    record_id: int
    reason_code: str
    case_reference: str
    hold_until: datetime | None
    placed_by_user_id: int | None
    placed_at: datetime
    released_at: datetime | None
    released_by_user_id: int | None
    release_reason_code: str | None
    release_reference: str | None


class RetentionTargetRead(BaseModel):
    resource_type: ResourceType
    record_id: int
    masked_email: str
    retention_anchor_at: datetime


def _lock_hold_table_for_write(db: Session) -> None:
    """Use a consistent table-lock order with the scheduled purge function."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(text("LOCK TABLE public.privacy_retention_holds IN ROW EXCLUSIVE MODE"))


def _target_model(resource_type: ResourceType):
    return MarketingLead if resource_type == "marketing_lead" else PublicInquiry


def _mask_email(value: str) -> str:
    local, separator, domain = (value or "").partition("@")
    if not separator or not local or not domain:
        return "[redacted]"
    domain_parts = domain.split(".")
    if not domain_parts[0]:
        return "[redacted]"
    masked_domain = f"{domain_parts[0][0]}***.{'.'.join(domain_parts[1:])}" if len(domain_parts) > 1 else "***"
    return f"{local[0]}***@{masked_domain}"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _effective(hold: PrivacyRetentionHold, now: datetime) -> bool:
    hold_until = hold.hold_until
    if hold_until is not None and hold_until.tzinfo is None:
        hold_until = hold_until.replace(tzinfo=timezone.utc)
    return hold.released_at is None and (hold_until is None or hold_until > now)


@router.get("/holds", response_model=list[RetentionHoldRead])
def list_retention_holds(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0, le=100_000),
    db: Session = Depends(get_db),
):
    require_master_admin(request=request, db=db, write=False)
    return (
        db.query(PrivacyRetentionHold)
        .order_by(
            PrivacyRetentionHold.released_at.is_(None).desc(),
            PrivacyRetentionHold.placed_at.desc(),
            PrivacyRetentionHold.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("/targets/search", response_model=list[RetentionTargetRead])
def search_retention_targets(
    payload: RetentionTargetSearch,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(
        request=request,
        db=db,
        csrf_header=request.headers.get("X-CSRF-Token"),
        write=True,
    )
    model = _target_model(payload.resource_type)
    retention_anchor_column = model.updated_at if model is MarketingLead else model.created_at
    query = db.query(model.id, model.email, retention_anchor_column.label("retention_anchor_at"))
    if payload.query.isdecimal():
        query = query.filter(model.id == int(payload.query))
        search_kind = "id"
    else:
        query = query.filter(func.lower(model.email) == payload.query.lower())
        search_kind = "exact_email"
    rows = query.order_by(model.created_at.desc(), model.id.desc()).limit(20).all()
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="privacy_retention_target_search",
        outcome="success",
        target_type=payload.resource_type,
        metadata={"search_kind": search_kind, "result_count": len(rows)},
        request=request,
    )
    db.commit()
    return [
        RetentionTargetRead(
            resource_type=payload.resource_type,
            record_id=row.id,
            masked_email=_mask_email(row.email),
            retention_anchor_at=_as_utc(row.retention_anchor_at),
        )
        for row in rows
    ]


@router.post("/holds", response_model=RetentionHoldRead, status_code=status.HTTP_201_CREATED)
def create_retention_hold(
    payload: RetentionHoldCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(
        request=request,
        db=db,
        csrf_header=request.headers.get("X-CSRF-Token"),
        write=True,
    )
    now = datetime.now(timezone.utc)
    if payload.hold_until is not None and payload.hold_until <= now:
        raise HTTPException(status_code=422, detail="hold_until must be in the future")

    # The cron routine takes SHARE on this table before deleting. Taking this
    # conflicting lock before locking the target row prevents a purge/hold
    # deadlock and makes either the hold or the purge win atomically.
    _lock_hold_table_for_write(db)
    target = (
        db.query(_target_model(payload.resource_type))
        .filter(_target_model(payload.resource_type).id == payload.record_id)
        .with_for_update()
        .first()
    )
    target_id = f"{payload.resource_type}:{payload.record_id}"
    if target is None:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_place",
            outcome="not_found",
            target_type="privacy_retention_hold",
            target_id=target_id,
            metadata={"reason_code": payload.reason_code, "case_reference": payload.case_reference},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Retention target not found")

    hold = (
        db.query(PrivacyRetentionHold)
        .filter(
            PrivacyRetentionHold.resource_type == payload.resource_type,
            PrivacyRetentionHold.record_id == payload.record_id,
        )
        .with_for_update()
        .one_or_none()
    )
    if hold is not None and _effective(hold, now):
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_place",
            outcome="conflict",
            target_type="privacy_retention_hold",
            target_id=target_id,
            metadata={"hold_id": hold.id, "reason_code": payload.reason_code},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="An effective retention hold already exists")

    if hold is None:
        hold = PrivacyRetentionHold(resource_type=payload.resource_type, record_id=payload.record_id)
        db.add(hold)
    hold.reason_code = payload.reason_code
    hold.case_reference = payload.case_reference
    hold.hold_until = payload.hold_until
    hold.placed_by_user_id = context.user.id
    hold.placed_at = now
    hold.released_at = None
    hold.released_by_user_id = None
    hold.release_reason_code = None
    hold.release_reference = None
    db.flush()
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="privacy_retention_hold_place",
        target_type="privacy_retention_hold",
        target_id=target_id,
        metadata={
            "hold_id": hold.id,
            "reason_code": hold.reason_code,
            "case_reference": hold.case_reference,
            "hold_until": hold.hold_until,
        },
        request=request,
    )
    db.commit()
    db.refresh(hold)
    return hold


@router.post("/holds/{hold_id}/release", response_model=RetentionHoldRead)
def release_retention_hold(
    hold_id: int,
    payload: RetentionHoldRelease,
    request: Request,
    db: Session = Depends(get_db),
):
    context = require_master_admin(
        request=request,
        db=db,
        csrf_header=request.headers.get("X-CSRF-Token"),
        write=True,
    )
    if not mfa_service.get_active_mfa_secret(db, context.user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="MFA no está activo")
    # Spend the same persistent attempt budget for password and TOTP guesses.
    # Otherwise a stolen privileged session could brute-force the reauth
    # password before the code-specific limiter is reached.
    allow_master_admin_mfa_attempt(db, "privacy_retention_release", context.user.id)
    if not verify_password(payload.password, context.user.password_hash):
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_release",
            outcome="failure",
            target_type="privacy_retention_hold",
            target_id=str(hold_id),
            metadata={"reason": "reauth_failed"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Reautenticación inválida")

    try:
        valid_mfa = mfa_service.consume_mfa_code(db, context.user.id, payload.mfa_code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="MFA no está disponible temporalmente") from exc
    if not valid_mfa:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_release",
            outcome="failure",
            target_type="privacy_retention_hold",
            target_id=str(hold_id),
            metadata={"reason": "invalid_or_replayed_mfa_code"},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código MFA inválido o ya utilizado")
    reset_master_admin_mfa_attempts(db, "privacy_retention_release", context.user.id)

    _lock_hold_table_for_write(db)
    hold = db.query(PrivacyRetentionHold).filter(PrivacyRetentionHold.id == hold_id).with_for_update().first()
    if hold is None:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_release",
            outcome="not_found",
            target_type="privacy_retention_hold",
            target_id=str(hold_id),
            metadata={"reason_code": payload.reason_code, "case_reference": payload.case_reference},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=404, detail="Retention hold not found")
    if hold.released_at is not None:
        audit_master_action(
            db,
            actor_user_id=context.user.id,
            action="privacy_retention_hold_release",
            outcome="conflict",
            target_type="privacy_retention_hold",
            target_id=f"{hold.resource_type}:{hold.record_id}",
            metadata={"hold_id": hold.id, "reason_code": payload.reason_code},
            request=request,
        )
        db.commit()
        raise HTTPException(status_code=409, detail="Retention hold is already released")

    now = datetime.now(timezone.utc)
    hold.released_at = now
    hold.released_by_user_id = context.user.id
    hold.release_reason_code = payload.reason_code
    hold.release_reference = payload.case_reference
    audit_master_action(
        db,
        actor_user_id=context.user.id,
        action="privacy_retention_hold_release",
        target_type="privacy_retention_hold",
        target_id=f"{hold.resource_type}:{hold.record_id}",
        metadata={
            "hold_id": hold.id,
            "reason_code": payload.reason_code,
            "case_reference": payload.case_reference,
        },
        request=request,
    )
    db.commit()
    db.refresh(hold)
    return hold
