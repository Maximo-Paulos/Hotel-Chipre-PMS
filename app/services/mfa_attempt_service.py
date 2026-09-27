"""Shared persistent rate-limit buckets for account MFA proofs."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.adapters.rate_limiter import mfa_code_guess_limiter
from app.models.rate_limit_event import RateLimitEvent


_LEGACY_ACTIONS_BY_BUCKET = {
    "totp": (
        "login",
        "step_up",
        "enroll",
        "disable",
        "regenerate",
        "temporary_grant_approval",
        "primary_owner_transfer",
        "privacy_retention_release",
    ),
    "reauth": (
        "enroll_reauth",
        "disable_reauth",
        "primary_owner_transfer_reauth",
        "master_admin_enroll_reauth",
        "master_admin_disable_reauth",
        "privacy_retention_release_reauth",
    ),
}


def mfa_attempt_key(action: str, user_id: int) -> str:
    """Use one OTP bucket and one reauthentication bucket per account.

    Surface-specific action names must not create fresh budgets. Reauthentication
    actions are explicitly suffixed so password/linked-identity guesses share a
    budget across application and master-admin surfaces; every other factor
    attempt uses the account's shared TOTP/recovery-code budget.
    """
    bucket = "reauth" if action.strip().casefold().endswith("_reauth") else "totp"
    return f"{bucket}:{user_id}"


def check_mfa_attempt(db: Session, action: str, user_id: int) -> bool:
    """Record and commit one persistent account proof attempt before checking it.

    Re-key attempts from the previous action-specific buckets during the active
    window so a deployment cannot reset a user's remaining guess budget.
    """
    bucket = "reauth" if action.strip().casefold().endswith("_reauth") else "totp"
    key = mfa_attempt_key(action, user_id)
    legacy_keys = [
        f"{legacy_action}:{user_id}"
        for legacy_action in _LEGACY_ACTIONS_BY_BUCKET[bucket]
    ]
    cutoff = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - mfa_code_guess_limiter.window
    )
    db.query(RateLimitEvent).filter(
        RateLimitEvent.scope == mfa_code_guess_limiter.scope,
        RateLimitEvent.subject_key.in_(legacy_keys),
        RateLimitEvent.created_at >= cutoff,
    ).update(
        {RateLimitEvent.subject_key: key},
        synchronize_session=False,
    )

    allowed = mfa_code_guess_limiter.allow(key, db=db)
    db.commit()
    return allowed


def reset_mfa_attempts(db: Session, action: str, user_id: int) -> None:
    """Clear the shared account bucket after that category of proof succeeds."""
    mfa_code_guess_limiter.reset(mfa_attempt_key(action, user_id), db=db)
