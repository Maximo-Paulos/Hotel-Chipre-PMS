"""Issue and validate short-lived, action-bound MFA step-up tickets."""

import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.action_step_up_ticket_use import ActionStepUpTicketUse
from app.services.permission_service import (
    canonical_permission_code,
    ensure_permission_matrix_seeded,
)
from app.services.security import create_signed_token, decode_signed_token

ACTION_STEP_UP_TICKET_TTL_SECONDS = 120
_ACTION_STEP_UP_TICKET_TTL_MINUTES = ACTION_STEP_UP_TICKET_TTL_SECONDS // 60
_ACTION_STEP_UP_PURPOSE = "action_step_up"


@dataclass(frozen=True)
class StepUpTicketAction:
    ticket: str
    user_id: int
    hotel_id: int
    token_version: int
    permission_code: str
    method: str
    path: str


def permission_requires_step_up(db: Session, permission_code: str) -> bool:
    """Read the canonical permission's seeded step-up policy from the catalog."""
    ensure_permission_matrix_seeded(db)
    canonical = canonical_permission_code(permission_code)
    required = (
        db.query(Permission.step_up_required)
        .filter(Permission.code == canonical)
        .scalar()
    )
    return bool(required)


def create_action_step_up_ticket(
    *,
    user_id: int,
    hotel_id: int,
    token_version: int,
    permission_code: str,
    method: str,
    path: str,
) -> str:
    """Sign a ticket scoped to one user, tenant, capability, and HTTP action."""
    return create_signed_token(
        {
            "purpose": _ACTION_STEP_UP_PURPOSE,
            "sub": str(user_id),
            "hotel_id": str(hotel_id),
            "token_version": str(token_version),
            "permission_code": canonical_permission_code(permission_code),
            "method": method.upper(),
            "path": path,
            "jti": secrets.token_hex(16),
        },
        expires_minutes=_ACTION_STEP_UP_TICKET_TTL_MINUTES,
    )


def action_step_up_ticket_matches(
    ticket: str,
    *,
    user_id: int,
    hotel_id: int,
    token_version: int,
    permission_code: str,
    method: str,
    path: str,
) -> bool:
    """Verify the JWT and compare every action binding without exposing errors."""
    if not ticket or len(ticket) > 8192:
        return False
    try:
        claims = decode_signed_token(ticket)
    except HTTPException:
        return False
    if not isinstance(claims, dict):
        return False
    ticket_id = claims.get("jti")
    if (
        not isinstance(ticket_id, str)
        or len(ticket_id) != 32
        or any(character not in "0123456789abcdef" for character in ticket_id)
    ):
        return False

    expected = {
        "purpose": _ACTION_STEP_UP_PURPOSE,
        "sub": str(user_id),
        "hotel_id": str(hotel_id),
        "token_version": str(token_version),
        "permission_code": canonical_permission_code(permission_code),
        "method": method.upper(),
        "path": path,
    }
    for name, expected_value in expected.items():
        actual_value = claims.get(name)
        if not isinstance(actual_value, str):
            return False
        if not hmac.compare_digest(
            actual_value.encode("utf-8"), expected_value.encode("utf-8")
        ):
            return False
    return True


def consume_action_step_up_tickets(db: Session, actions: list[StepUpTicketAction]) -> bool:
    """Atomically consume one distinct, correctly bound ticket per action.

    The random signed ``jti`` is inserted under a unique constraint. Concurrent
    workers racing the same ticket get exactly one winner. The insert commits
    before the guarded handler runs, so a failed/replayed request cannot roll
    back the MFA proof and reuse it for another mutation.
    """
    if not actions:
        return True

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rows: list[dict[str, object]] = []
    for action in actions:
        if not action_step_up_ticket_matches(
            action.ticket,
            user_id=action.user_id,
            hotel_id=action.hotel_id,
            token_version=action.token_version,
            permission_code=action.permission_code,
            method=action.method,
            path=action.path,
        ):
            return False
        try:
            claims = decode_signed_token(action.ticket)
            ticket_id = claims["jti"]
            expires_at = datetime.fromtimestamp(float(claims["exp"]), tz=timezone.utc).replace(tzinfo=None)
        except (HTTPException, KeyError, TypeError, ValueError, OverflowError):
            return False
        if expires_at <= now or any(row["ticket_id"] == ticket_id for row in rows):
            return False
        rows.append(
            {
                "ticket_id": ticket_id,
                "hotel_id": action.hotel_id,
                "user_id": action.user_id,
                "permission_code": canonical_permission_code(action.permission_code),
                "method": action.method.upper(),
                "path": action.path,
                "expires_at": expires_at,
                "used_at": now,
            }
        )

    db.execute(
        delete(ActionStepUpTicketUse).where(
            ActionStepUpTicketUse.hotel_id == actions[0].hotel_id,
            ActionStepUpTicketUse.expires_at <= now,
        )
    )
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(ActionStepUpTicketUse).values(rows)
    elif dialect == "postgresql":
        statement = postgresql_insert(ActionStepUpTicketUse).values(rows)
    else:
        raise RuntimeError(f"Unsupported database dialect for step-up replay protection: {dialect}")
    inserted = db.execute(
        statement.on_conflict_do_nothing(index_elements=["ticket_id"]).returning(ActionStepUpTicketUse.ticket_id)
    ).scalars().all()
    if len(inserted) != len(rows):
        db.rollback()
        return False
    db.commit()
    return True
