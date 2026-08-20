"""Core lifecycle for tenant-scoped, one-time temporary action grants."""
from __future__ import annotations

import enum
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.permission import Permission
from app.models.security_audit_log import SecurityAuditLog
from app.models.temporary_action_grant import (
    TemporaryActionGrant,
    TemporaryActionGrantStatusEnum,
)
from app.services.mfa_service import consume_mfa_code
from app.services.permission_service import (
    PERMISSION_DEFINITIONS,
    canonical_permission_code,
    seed_default_permissions,
)
from app.services.security import hash_password, verify_password


TEMPORARY_GRANT_TTL = timedelta(minutes=15)
TEMPORARY_GRANT_APPROVER_ROLES = frozenset({"owner", "co_owner"})


@dataclass(frozen=True)
class TemporaryGrantActor:
    """Authenticated principal plus the hotel selected for this request."""

    user_id: int
    hotel_id: int


class TemporaryGrantError(RuntimeError):
    """Base error for invalid grant lifecycle operations."""


class TemporaryGrantNotFoundError(TemporaryGrantError):
    """The grant is not visible in the actor's hotel scope."""


class TemporaryGrantAuthorizationError(TemporaryGrantError):
    """The actor is not an active member or approver for the hotel."""


class TemporaryGrantStateError(TemporaryGrantError):
    """The requested transition is not valid for the current grant state."""


class TemporaryGrantMfaError(TemporaryGrantError):
    """Approval requires an active MFA factor and a valid one-time code."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _status_value(status: TemporaryActionGrantStatusEnum) -> str:
    return status.value if isinstance(status, enum.Enum) else str(status)


def _active_membership(db: Session, actor: TemporaryGrantActor) -> HotelMembership:
    membership = (
        db.query(HotelMembership)
        .filter_by(hotel_id=actor.hotel_id, user_id=actor.user_id, status="active")
        .one_or_none()
    )
    if membership is None:
        raise TemporaryGrantAuthorizationError("El usuario no tiene una membership activa en este hotel")
    return membership


def _grant_for_actor(db: Session, grant_id: int, actor: TemporaryGrantActor) -> TemporaryActionGrant:
    grant = (
        db.query(TemporaryActionGrant)
        .filter(
            TemporaryActionGrant.id == grant_id,
            TemporaryActionGrant.hotel_id == actor.hotel_id,
        )
        .one_or_none()
    )
    if grant is None:
        raise TemporaryGrantNotFoundError("Grant no encontrado")
    return grant


def _require_approver(db: Session, actor: TemporaryGrantActor) -> HotelMembership:
    membership = _active_membership(db, actor)
    if membership.role not in TEMPORARY_GRANT_APPROVER_ROLES:
        raise TemporaryGrantAuthorizationError("Solo owner o co_owner puede aprobar grants")
    return membership


def _audit(
    db: Session,
    grant: TemporaryActionGrant,
    *,
    action: str,
    actor_user_id: int | None,
    before: str | None = None,
) -> None:
    """Record lifecycle metadata without storing the token, hash, or reason."""
    details = {
        "permission_code": grant.permission_code,
        "resource_type": grant.resource_type,
        "resource_id": grant.resource_id,
        "status": _status_value(grant.status),
    }
    if before is not None:
        details["before"] = before
    db.add(
        SecurityAuditLog(
            hotel_id=grant.hotel_id,
            user_id=actor_user_id,
            action=action,
            resource_type="temporary_action_grant",
            resource_id=str(grant.id),
            details=json.dumps(details, sort_keys=True),
        )
    )


def request_grant(
    db: Session,
    hotel_id: int,
    requester: TemporaryGrantActor,
    permission_code: str,
    resource_type: str | None,
    resource_id: str | int | None,
    reason: str,
) -> TemporaryActionGrant:
    """Create a pending grant for one active requester in one hotel."""
    if requester.hotel_id != hotel_id:
        raise TemporaryGrantAuthorizationError("El grant debe pertenecer al hotel de la sesion")
    _active_membership(db, requester)

    canonical_code = canonical_permission_code((permission_code or "").strip())
    if canonical_code not in PERMISSION_DEFINITIONS:
        raise ValueError("Permiso invalido")
    normalized_reason = (reason or "").strip()
    if not normalized_reason:
        raise ValueError("El motivo es obligatorio")

    # The FK points at the catalog. Startup normally seeds it, while this
    # service also supports isolated test/worker databases before boot seeding.
    if db.query(Permission).filter(Permission.code == canonical_code).one_or_none() is None:
        seed_default_permissions(db)
    grant = TemporaryActionGrant(
        hotel_id=hotel_id,
        requester_user_id=requester.user_id,
        permission_code=canonical_code,
        resource_type=(resource_type or "").strip() or None,
        resource_id=None if resource_id is None else str(resource_id),
        reason=normalized_reason,
        status=TemporaryActionGrantStatusEnum.PENDING,
    )
    db.add(grant)
    db.flush()
    _audit(db, grant, action="temporary_grant.requested", actor_user_id=requester.user_id)
    return grant


def approve_grant(
    db: Session,
    grant_id: int,
    approver: TemporaryGrantActor,
    totp_code: str,
) -> tuple[TemporaryActionGrant, str]:
    """Approve a pending grant and return its plaintext token exactly once.

    MFA is mandatory for owner/co_owner approval. ``consume_mfa_code`` accepts
    either the current TOTP or an unused recovery code, preserving the account
    MFA service's replay protection and single-use semantics.
    """
    grant = _grant_for_actor(db, grant_id, approver)
    _require_approver(db, approver)
    if grant.status != TemporaryActionGrantStatusEnum.PENDING:
        raise TemporaryGrantStateError("El grant no esta pendiente")
    if not consume_mfa_code(db, approver.user_id, (totp_code or "").strip()):
        raise TemporaryGrantMfaError("El aprobador requiere MFA activo y un codigo valido")

    now = _utcnow()
    plaintext_token = secrets.token_urlsafe(32)
    result = db.execute(
        update(TemporaryActionGrant)
        .where(
            TemporaryActionGrant.id == grant.id,
            TemporaryActionGrant.hotel_id == approver.hotel_id,
            TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.PENDING,
        )
        .values(
            approver_user_id=approver.user_id,
            status=TemporaryActionGrantStatusEnum.APPROVED,
            token_hash=hash_password(plaintext_token),
            approved_at=now,
            expires_at=now + TEMPORARY_GRANT_TTL,
        )
    )
    if result.rowcount != 1:
        raise TemporaryGrantStateError("El grant dejo de estar pendiente")

    grant.approver_user_id = approver.user_id
    grant.status = TemporaryActionGrantStatusEnum.APPROVED
    grant.approved_at = now
    grant.expires_at = now + TEMPORARY_GRANT_TTL
    _audit(db, grant, action="temporary_grant.approved", actor_user_id=approver.user_id, before="pending")
    db.flush()
    return grant, plaintext_token


def deny_grant(db: Session, grant_id: int, approver: TemporaryGrantActor) -> TemporaryActionGrant:
    """Deny a pending grant; denial does not require an MFA step-up."""
    grant = _grant_for_actor(db, grant_id, approver)
    _require_approver(db, approver)
    if grant.status != TemporaryActionGrantStatusEnum.PENDING:
        raise TemporaryGrantStateError("El grant no esta pendiente")
    result = db.execute(
        update(TemporaryActionGrant)
        .where(
            TemporaryActionGrant.id == grant.id,
            TemporaryActionGrant.hotel_id == approver.hotel_id,
            TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.PENDING,
        )
        .values(status=TemporaryActionGrantStatusEnum.DENIED)
    )
    if result.rowcount != 1:
        raise TemporaryGrantStateError("El grant dejo de estar pendiente")
    grant.status = TemporaryActionGrantStatusEnum.DENIED
    _audit(db, grant, action="temporary_grant.denied", actor_user_id=approver.user_id, before="pending")
    db.flush()
    return grant


def revoke_grant(db: Session, grant_id: int, actor: TemporaryGrantActor) -> TemporaryActionGrant:
    """Revoke an approved but not-yet-used grant."""
    grant = _grant_for_actor(db, grant_id, actor)
    _require_approver(db, actor)
    if grant.status != TemporaryActionGrantStatusEnum.APPROVED:
        raise TemporaryGrantStateError("Solo se puede revocar un grant aprobado")
    result = db.execute(
        update(TemporaryActionGrant)
        .where(
            TemporaryActionGrant.id == grant.id,
            TemporaryActionGrant.hotel_id == actor.hotel_id,
            TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.APPROVED,
        )
        .values(status=TemporaryActionGrantStatusEnum.REVOKED)
    )
    if result.rowcount != 1:
        raise TemporaryGrantStateError("El grant dejo de estar aprobado")
    grant.status = TemporaryActionGrantStatusEnum.REVOKED
    _audit(db, grant, action="temporary_grant.revoked", actor_user_id=actor.user_id, before="approved")
    db.flush()
    return grant


def expire_stale_grants(
    db: Session,
    hotel_id: int | None = None,
    now: datetime | None = None,
) -> int:
    """Best-effort transition for approved grants whose short TTL elapsed."""
    current = now or _utcnow()
    query = db.query(TemporaryActionGrant).filter(
        TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.APPROVED,
        TemporaryActionGrant.expires_at.is_not(None),
        TemporaryActionGrant.expires_at <= current,
    )
    if hotel_id is not None:
        query = query.filter(TemporaryActionGrant.hotel_id == hotel_id)

    expired_count = 0
    for grant in query.all():
        result = db.execute(
            update(TemporaryActionGrant)
            .where(
                TemporaryActionGrant.id == grant.id,
                TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.APPROVED,
                TemporaryActionGrant.expires_at <= current,
            )
            .execution_options(synchronize_session=False)
            .values(status=TemporaryActionGrantStatusEnum.EXPIRED)
        )
        if result.rowcount != 1:
            continue
        grant.status = TemporaryActionGrantStatusEnum.EXPIRED
        _audit(db, grant, action="temporary_grant.expired", actor_user_id=None, before="approved")
        expired_count += 1
    if expired_count:
        db.flush()
    return expired_count


def consume_grant(db: Session, token: str, requester: TemporaryGrantActor) -> bool:
    """Atomically consume a matching approved token for its original requester."""
    if not (token or "").strip():
        return False
    _active_membership(db, requester)
    now = _utcnow()
    expire_stale_grants(db, hotel_id=requester.hotel_id, now=now)
    candidates = (
        db.query(TemporaryActionGrant)
        .filter(
            TemporaryActionGrant.hotel_id == requester.hotel_id,
            TemporaryActionGrant.requester_user_id == requester.user_id,
            TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.APPROVED,
            TemporaryActionGrant.expires_at > now,
        )
        .order_by(TemporaryActionGrant.created_at.asc())
        .all()
    )

    for grant in candidates:
        if not grant.token_hash or not verify_password(token.strip(), grant.token_hash):
            continue
        consumed = db.execute(
            update(TemporaryActionGrant)
            .where(
                TemporaryActionGrant.id == grant.id,
                TemporaryActionGrant.hotel_id == requester.hotel_id,
                TemporaryActionGrant.requester_user_id == requester.user_id,
                TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.APPROVED,
                TemporaryActionGrant.expires_at > now,
            )
            .execution_options(synchronize_session=False)
            .values(
                status=TemporaryActionGrantStatusEnum.USED,
                used_at=now,
            )
        )
        if consumed.rowcount != 1:
            continue
        grant.status = TemporaryActionGrantStatusEnum.USED
        grant.used_at = now
        _audit(db, grant, action="temporary_grant.consumed", actor_user_id=requester.user_id, before="approved")
        db.flush()
        return True
    return False


def list_pending_grants_for_hotel(db: Session, hotel_id: int) -> list[TemporaryActionGrant]:
    """Return only pending grant metadata for an owner's review queue."""
    return (
        db.query(TemporaryActionGrant)
        .filter(
            TemporaryActionGrant.hotel_id == hotel_id,
            TemporaryActionGrant.status == TemporaryActionGrantStatusEnum.PENDING,
        )
        .order_by(TemporaryActionGrant.created_at.asc(), TemporaryActionGrant.id.asc())
        .all()
    )
