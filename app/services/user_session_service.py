"""Normal-user server-side sessions alongside the legacy JWT contract.

The raw session and CSRF values are returned only at creation/rotation time.
Only SHA-256 digests are persisted, matching the proven master-admin pattern.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings, is_preview_qa_mode, is_production_mode
from app.models.user import User
from app.models.user_session import UserSession


USER_SESSION_COOKIE_NAME = "user_session"
USER_CSRF_COOKIE_NAME = "user_csrf"
USER_SESSION_COOKIE_PATH = "/api/"

# A 30-day absolute lifetime limits the damage of a long-lived stolen cookie;
# a 7-day idle lifetime removes dormant devices without interrupting active use.
USER_SESSION_ABSOLUTE_TTL = timedelta(days=30)
USER_SESSION_IDLE_TTL = timedelta(days=7)
USER_SESSION_COOKIE_MAX_AGE_SECONDS = int(USER_SESSION_ABSOLUTE_TTL.total_seconds())
UNKNOWN_DEVICE_LABEL = "Dispositivo desconocido"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _issue_token() -> str:
    return secrets.token_urlsafe(48)


def _session_cookie_secure() -> bool:
    settings = get_settings()
    configured = getattr(settings, "USER_SESSION_COOKIE_SECURE", None)
    if configured is not None:
        return bool(configured)
    return is_production_mode() or is_preview_qa_mode()


def _session_cookie_samesite() -> str:
    # Cross-origin SPA requests from Vercel to Render require SameSite=None in production.
    # Keep lax on local HTTP so localhost development still works without Secure cookies.
    return "none" if _session_cookie_secure() else "lax"


def _device_label_from_request(request: Request | None) -> str:
    """Derive a short display label without persisting the raw User-Agent."""

    raw_user_agent = request.headers.get("user-agent", "") if request else ""
    user_agent = "".join(character for character in raw_user_agent if character.isprintable())

    if "Edg/" in user_agent or "Edge/" in user_agent:
        browser = "Edge"
    elif "OPR/" in user_agent or "Opera" in user_agent:
        browser = "Opera"
    elif "Firefox/" in user_agent:
        browser = "Firefox"
    elif "Chrome/" in user_agent or "CriOS/" in user_agent:
        browser = "Chrome"
    elif "Safari/" in user_agent:
        browser = "Safari"
    else:
        browser = "Navegador desconocido"

    if "iPhone" in user_agent or "iPad" in user_agent or "iPod" in user_agent:
        platform = "iOS"
    elif "Android" in user_agent:
        platform = "Android"
    elif "Windows" in user_agent:
        platform = "Windows"
    elif "Macintosh" in user_agent or "Mac OS X" in user_agent:
        platform = "macOS"
    elif "Linux" in user_agent:
        platform = "Linux"
    else:
        platform = "dispositivo desconocido"

    label = f"{browser} en {platform}"
    return label[:120] or UNKNOWN_DEVICE_LABEL


def create_session(
    db: Session,
    user: User,
    request: Request | None = None,
) -> tuple[UserSession, str, str]:
    """Create a session and return raw values exactly once for cookie setup."""

    now = _now()
    session_token = _issue_token()
    csrf_token = _issue_token()
    session = UserSession(
        user_id=user.id,
        session_token_hash=_hash_value(session_token),
        csrf_token_hash=_hash_value(csrf_token),
        device_label=_device_label_from_request(request),
        created_at=now,
        last_seen_at=now,
        expires_at=now + USER_SESSION_ABSOLUTE_TTL,
    )
    db.add(session)
    db.flush()
    return session, session_token, csrf_token


def set_user_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    """Set the cross-site-compatible session and double-submit CSRF cookies."""

    cookie_kwargs = {
        "httponly": True,
        "secure": _session_cookie_secure(),
        "samesite": _session_cookie_samesite(),
        "path": USER_SESSION_COOKIE_PATH,
    }
    response.set_cookie(
        USER_SESSION_COOKIE_NAME,
        session_token,
        max_age=USER_SESSION_COOKIE_MAX_AGE_SECONDS,
        **cookie_kwargs,
    )
    response.set_cookie(
        USER_CSRF_COOKIE_NAME,
        csrf_token,
        max_age=USER_SESSION_COOKIE_MAX_AGE_SECONDS,
        httponly=False,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path=USER_SESSION_COOKIE_PATH,
    )


def clear_user_session_cookies(response: Response) -> None:
    response.delete_cookie(USER_SESSION_COOKIE_NAME, path=USER_SESSION_COOKIE_PATH)
    response.delete_cookie(USER_CSRF_COOKIE_NAME, path=USER_SESSION_COOKIE_PATH)


def csrf_double_submit_matches(header_value: str | None, cookie_value: str | None) -> bool:
    if not header_value or not cookie_value:
        return False
    return hmac.compare_digest(header_value, cookie_value)


def session_matches_token(session: UserSession, session_token: str | None) -> bool:
    if not session_token:
        return False
    return hmac.compare_digest(session.session_token_hash, _hash_value(session_token))


def validate_and_touch_session(
    db: Session,
    session_token: str,
    csrf_token_header: str | None,
    csrf_token_cookie: str | None = None,
) -> tuple[UserSession, str] | None:
    """Validate CSRF/expiry and atomically replace the session token.

    The return value is ``(session, new_session_token)`` because the caller
    must replace the HttpOnly cookie after every successful rotation. The
    optional cookie argument preserves a small direct-service API while API
    callers always provide the actual double-submit cookie.
    """

    if not session_token or not csrf_token_header:
        return None
    csrf_cookie = csrf_token_cookie if csrf_token_cookie is not None else csrf_token_header
    if not csrf_double_submit_matches(csrf_token_header, csrf_cookie):
        return None

    session_hash = _hash_value(session_token)
    session = (
        db.query(UserSession)
        .filter(UserSession.session_token_hash == session_hash)
        .with_for_update()
        .first()
    )
    if session is None or not hmac.compare_digest(session.session_token_hash, session_hash):
        return None
    if session.revoked_at is not None:
        return None

    now = _now()
    absolute_expiry = _as_aware(session.expires_at)
    idle_reference = _as_aware(session.last_seen_at or session.created_at)
    if (
        absolute_expiry is None
        or absolute_expiry <= now
        or idle_reference is None
        or idle_reference + USER_SESSION_IDLE_TTL <= now
    ):
        session.revoked_at = now
        db.flush()
        return None

    csrf_hash = _hash_value(csrf_cookie)
    if not hmac.compare_digest(session.csrf_token_hash, csrf_hash):
        return None

    new_session_token = _issue_token()
    session.session_token_hash = _hash_value(new_session_token)
    session.last_seen_at = now
    db.add(session)
    db.flush()
    return session, new_session_token


def revoke_session(db: Session, session_id: int, user_id: int) -> UserSession | None:
    """Revoke one owned session, returning None for missing/non-owned rows."""

    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.user_id == user_id)
        .first()
    )
    if session is None or session.revoked_at is not None:
        return None
    session.revoked_at = _now()
    db.add(session)
    db.flush()
    return session


def revoke_all_sessions(
    db: Session,
    user_id: int,
    except_session_id: int | None = None,
) -> int:
    """Revoke all sessions for a user, optionally preserving one current row."""

    query = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.revoked_at.is_(None),
    )
    if except_session_id is not None:
        query = query.filter(UserSession.id != except_session_id)
    sessions = query.all()
    now = _now()
    for session in sessions:
        session.revoked_at = now
        db.add(session)
    if sessions:
        db.flush()
    return len(sessions)


def list_active_sessions(db: Session, user_id: int) -> list[UserSession]:
    """Return only non-revoked sessions within both lifetime limits."""

    now = _now()
    sessions = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .order_by(UserSession.last_seen_at.desc(), UserSession.id.desc())
        .all()
    )
    return [
        session
        for session in sessions
        if (_as_aware(session.last_seen_at or session.created_at) or now)
        + USER_SESSION_IDLE_TTL
        > now
    ]
