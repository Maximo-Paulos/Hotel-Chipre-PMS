"""Domain helpers for secure, auditable staff invitation lifecycle."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.invitation import StaffInvitation


INVITATION_TTL = timedelta(days=7)
INVITATION_TOKEN_BYTES = 32


def utcnow() -> datetime:
    """Return a naive UTC timestamp, matching the current SQLAlchemy models."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def hash_invitation_token(token: str) -> str:
    """Hash a high-entropy bearer token before it is persisted."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_invitation(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    email: str,
    role: str,
    inviter_user_id: int | None,
    inviter_email: str,
) -> tuple[StaffInvitation, str, bool]:
    """Create or refresh the sole pending invitation for a hotel/email pair."""

    normalized_email = normalize_email(email)
    now = utcnow()
    invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.hotel_id == hotel_id,
            StaffInvitation.email == normalized_email,
            StaffInvitation.status == "pending",
        )
        .order_by(StaffInvitation.id.desc())
        .first()
    )
    reused = invitation is not None and invitation.expires_at > now
    if invitation is not None and not reused:
        invitation.status = "expired"

    raw_token = secrets.token_urlsafe(INVITATION_TOKEN_BYTES)
    expires_at = now + INVITATION_TTL
    if invitation is None or not reused:
        invitation = StaffInvitation(
            hotel_id=hotel_id,
            user_id=user_id,
            email=normalized_email,
            role=role,
            inviter_user_id=inviter_user_id,
            inviter_email=normalize_email(inviter_email),
            token_hash=hash_invitation_token(raw_token),
            status="pending",
            expires_at=expires_at,
        )
        db.add(invitation)
    else:
        invitation.user_id = user_id
        invitation.role = role
        invitation.inviter_user_id = inviter_user_id
        invitation.inviter_email = normalize_email(inviter_email)
        invitation.token_hash = hash_invitation_token(raw_token)
        invitation.expires_at = expires_at
        invitation.updated_at = now
        invitation.consumed_at = None
        invitation.revoked_at = None

    db.flush()
    return invitation, raw_token, reused


def find_by_token(db: Session, raw_token: str) -> StaffInvitation | None:
    return (
        db.query(StaffInvitation)
        .filter(StaffInvitation.token_hash == hash_invitation_token(raw_token))
        .first()
    )


def is_expired(invitation: StaffInvitation, *, now: datetime | None = None) -> bool:
    return invitation.expires_at <= (now or utcnow())


def consume_invitation(db: Session, invitation: StaffInvitation) -> bool:
    """Atomically transition a pending invitation to accepted exactly once."""

    now = utcnow()
    consumed = db.execute(
        update(StaffInvitation)
        .where(
            StaffInvitation.id == invitation.id,
            StaffInvitation.status == "pending",
            StaffInvitation.consumed_at.is_(None),
            StaffInvitation.revoked_at.is_(None),
            StaffInvitation.expires_at > now,
        )
        .values(status="accepted", consumed_at=now, updated_at=now)
    )
    if consumed.rowcount != 1:
        return False
    db.flush()
    db.refresh(invitation)
    return True


def invitation_snapshot(invitation: StaffInvitation) -> dict[str, object]:
    """Return an audit-safe snapshot that never includes the token hash."""

    return {
        "id": invitation.id,
        "hotel_id": invitation.hotel_id,
        "user_id": invitation.user_id,
        "email": invitation.email,
        "role": invitation.role,
        "inviter_user_id": invitation.inviter_user_id,
        "inviter_email": invitation.inviter_email,
        "status": invitation.status,
        "expires_at": invitation.expires_at,
        "consumed_at": invitation.consumed_at,
        "revoked_at": invitation.revoked_at,
        "created_at": invitation.created_at,
        "updated_at": invitation.updated_at,
    }
