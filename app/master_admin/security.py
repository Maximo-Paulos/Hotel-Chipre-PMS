from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.adapters.rate_limiter import SimpleRateLimiter, mfa_code_guess_limiter
from app.config import get_settings, is_preview_qa_mode, is_production_mode
from app.models.user import User
from app.services import mfa_service
from app.services.security import create_signed_token, decode_signed_token, hash_password, verify_password
from app.services.tenant_context import set_master_admin_context
from .models import MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession

SESSION_COOKIE_NAME = "master_admin_session"
CSRF_COOKIE_NAME = "master_admin_csrf"
SESSION_HINT_COOKIE_NAME = "master_admin_session_hint"
# Absolute lifetime caps continuous access to the high-privilege control plane
# and forces periodic re-authentication even when the administrator is active.
DEFAULT_SESSION_TTL_MINUTES = 8 * 60
# This panel can access data from every hotel, so short idle expiry limits the
# exposure window when a master-admin workstation is left unattended.
DEFAULT_IDLE_TTL_MINUTES = 20
DEFAULT_LOCKOUT_THRESHOLD = 5
DEFAULT_LOCKOUT_MINUTES = 15
LOGIN_RATE_LIMITER = SimpleRateLimiter("master_admin_login", limit=5, window_seconds=15 * 60)
MASTER_ADMIN_MFA_LOGIN_PURPOSE = "master_admin_mfa_login"
MASTER_ADMIN_MFA_LOGIN_CHALLENGE_MINUTES = 5


@dataclass
class MasterAdminContext:
    user: User
    session: MasterAdminSession
    csrf_token: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_identifier(value: str) -> str:
    return (value or "").strip().lower()


def _normalize_pin(value: str) -> str:
    return "".join(ch for ch in (value or "").strip() if ch.isdigit())


def _bootstrap_master_credentials_match(email: str, password: str) -> bool:
    settings = get_settings()
    configured_email = _normalize_identifier(getattr(settings, "MASTER_ADMIN_EMAIL", ""))
    configured_password = str(getattr(settings, "MASTER_ADMIN_PASSWORD", "") or "")
    return bool(configured_email) and bool(configured_password) and _normalize_identifier(email) == configured_email and password == configured_password


def _pin_matches(pin: str) -> bool:
    settings = get_settings()
    expected = _normalize_pin(str(settings.MASTER_ADMIN_PIN or ""))
    return bool(expected) and hmac.compare_digest(_normalize_pin(pin), expected)


def _session_cookie_secure() -> bool:
    settings = get_settings()
    if is_production_mode(settings) or is_preview_qa_mode(settings):
        return True
    configured = getattr(settings, "MASTER_ADMIN_COOKIE_SECURE", None)
    if configured is not None:
        return bool(configured)
    return False


def _session_cookie_samesite() -> str:
    # Cross-origin SPA requests from Vercel to Render require SameSite=None in production.
    # Keep lax on local HTTP so localhost development still works without Secure cookies.
    return "none" if _session_cookie_secure() else "lax"


def _issue_token() -> str:
    return secrets.token_urlsafe(48)


def _session_expiry() -> datetime:
    settings = get_settings()
    ttl_minutes = int(getattr(settings, "MASTER_ADMIN_SESSION_TTL_MINUTES", DEFAULT_SESSION_TTL_MINUTES) or DEFAULT_SESSION_TTL_MINUTES)
    return _now() + timedelta(minutes=max(1, ttl_minutes))


def _session_max_age_seconds() -> int:
    settings = get_settings()
    ttl_minutes = int(getattr(settings, "MASTER_ADMIN_SESSION_TTL_MINUTES", DEFAULT_SESSION_TTL_MINUTES) or DEFAULT_SESSION_TTL_MINUTES)
    return max(1, ttl_minutes) * 60


def _idle_expiry(reference: datetime | None) -> datetime:
    settings = get_settings()
    ttl_minutes = int(getattr(settings, "MASTER_ADMIN_IDLE_TTL_MINUTES", DEFAULT_IDLE_TTL_MINUTES) or DEFAULT_IDLE_TTL_MINUTES)
    return _as_aware(reference) + timedelta(minutes=max(1, ttl_minutes)) if reference else _now() + timedelta(minutes=max(1, ttl_minutes))


def _json_or_null(value: Any) -> str | None:
    if value is None:
        return None
    def _default(obj: Any) -> str:
        if isinstance(obj, datetime):
            return obj.astimezone(timezone.utc).isoformat()
        return str(obj)

    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=_default)


_AUDIT_EMAIL_KEYS = frozenset(
    {
        "email",
        "recipient",
        "sender_email",
        "reply_to",
        "connected_account_email",
        "account_email",
        "owner_email",
        "user_email",
        "actor_email",
        "from_email",
        "to_email",
    }
)
_AUDIT_REDACTED_KEYS = frozenset(
    {
        "password",
        "pin",
        "token",
        "secret",
        "code",
        "otp",
        "api_key",
        "access_token",
        "refresh_token",
        "session_token",
        "csrf_token",
        "webhook_secret",
        "stripe_secret_key",
        "verification_code",
        "reset_code",
        "confirmation_code",
    }
)
_AUDIT_REDACTED_VALUE = "[REDACTED]"


def _normalize_audit_metadata_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def _mask_audit_email(value: Any) -> str:
    email = str(value)
    local, separator, domain = email.partition("@")
    if not separator or not local or not domain:
        return _AUDIT_REDACTED_VALUE
    return f"{local[0]}***@{domain}"


def redact_master_admin_audit_metadata(value: Any) -> Any:
    """Redact the small, known set of sensitive audit metadata fields."""
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            normalized_key = _normalize_audit_metadata_key(key)
            if normalized_key in _AUDIT_EMAIL_KEYS:
                redacted[key] = _mask_audit_email(item)
            elif normalized_key in _AUDIT_REDACTED_KEYS:
                redacted[key] = _AUDIT_REDACTED_VALUE
            else:
                redacted[key] = redact_master_admin_audit_metadata(item)
        return redacted
    if isinstance(value, list):
        return [redact_master_admin_audit_metadata(item) for item in value]
    if isinstance(value, tuple):
        return [redact_master_admin_audit_metadata(item) for item in value]
    return value


def redact_master_admin_audit_metadata_json(value: str | None) -> str | None:
    """Redact valid persisted audit JSON before returning it to an API caller."""
    if value is None:
        return None
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return _AUDIT_REDACTED_VALUE
    return _json_or_null(redact_master_admin_audit_metadata(parsed))


def create_master_session(db: Session, user: User, request: Request | None = None) -> tuple[MasterAdminSession, str, str]:
    session_token = _issue_token()
    csrf_token = _issue_token()
    session = MasterAdminSession(
        user_id=user.id,
        session_token_hash=_hash_value(session_token),
        csrf_token_hash=_hash_value(csrf_token),
        expires_at=_session_expiry(),
        last_seen_at=_now(),
        ip_address=getattr(request.client, "host", None) if request and request.client else None,
        user_agent=request.headers.get("user-agent")[:255] if request and request.headers.get("user-agent") else None,
    )
    db.add(session)
    db.flush()
    return session, session_token, csrf_token


def set_master_session_cookies(response: Response, session_token: str, csrf_token: str) -> None:
    cookie_path = "/api/"
    cookie_kwargs = {
        "httponly": True,
        "secure": _session_cookie_secure(),
        "samesite": _session_cookie_samesite(),
        "path": cookie_path,
    }
    response.set_cookie(SESSION_COOKIE_NAME, session_token, max_age=_session_max_age_seconds(), **cookie_kwargs)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=_session_max_age_seconds(),
        httponly=False,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path=cookie_path,
    )
    response.set_cookie(
        SESSION_HINT_COOKIE_NAME,
        "1",
        max_age=_session_max_age_seconds(),
        httponly=False,
        secure=_session_cookie_secure(),
        samesite=_session_cookie_samesite(),
        path="/",
    )


def clear_master_session_cookies(response: Response) -> None:
    cookie_path = "/api/"
    response.delete_cookie(SESSION_COOKIE_NAME, path=cookie_path)
    response.delete_cookie(CSRF_COOKIE_NAME, path=cookie_path)
    response.delete_cookie(SESSION_HINT_COOKIE_NAME, path="/")


def _lockout_query(db: Session, login_identifier: str) -> MasterAdminAuthLockout | None:
    return db.query(MasterAdminAuthLockout).filter(MasterAdminAuthLockout.login_identifier == login_identifier).first()


def is_login_locked(db: Session, login_identifier: str) -> bool:
    lockout = _lockout_query(db, login_identifier)
    if not lockout or not lockout.locked_until:
        return False
    return _as_aware(lockout.locked_until) > _now()


def register_login_failure(db: Session, login_identifier: str, reason: str) -> None:
    normalized = _normalize_identifier(login_identifier)
    lockout = _lockout_query(db, normalized)
    if not lockout:
        lockout = MasterAdminAuthLockout(login_identifier=normalized)
        db.add(lockout)
    lockout.failed_attempts = (lockout.failed_attempts or 0) + 1
    lockout.last_failed_at = _now()
    lockout.last_failure_reason = reason
    settings = get_settings()
    lockout_threshold = int(getattr(settings, "MASTER_ADMIN_MAX_ATTEMPTS", DEFAULT_LOCKOUT_THRESHOLD) or DEFAULT_LOCKOUT_THRESHOLD)
    lockout_minutes = int(getattr(settings, "MASTER_ADMIN_LOCKOUT_MINUTES", DEFAULT_LOCKOUT_MINUTES) or DEFAULT_LOCKOUT_MINUTES)
    if lockout.failed_attempts >= lockout_threshold:
        lockout.locked_until = _now() + timedelta(minutes=max(1, lockout_minutes))
        lockout.failed_attempts = lockout_threshold
    db.flush()


def reset_login_lockout(db: Session, login_identifier: str) -> None:
    normalized = _normalize_identifier(login_identifier)
    lockout = _lockout_query(db, normalized)
    if not lockout:
        return
    lockout.failed_attempts = 0
    lockout.locked_until = None
    lockout.last_failure_reason = None
    db.flush()


def _authorize_user_for_master_panel(user: User) -> None:
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario deshabilitado")
    if user.role != "platform_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para el panel master")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifica tu email para usar el panel master")


def authenticate_master_login(db: Session, email: str, password: str, pin: str) -> User:
    normalized = _normalize_identifier(email)
    if is_login_locked(db, normalized):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Espera y vuelve a intentar.")

    settings = get_settings()
    login_limiter = LOGIN_RATE_LIMITER
    login_limiter.limit = getattr(settings, "MASTER_ADMIN_MAX_ATTEMPTS", getattr(settings, "LOGIN_RATE_LIMIT", login_limiter.limit))
    if not login_limiter.allow(f"master:{normalized}", db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos. Espera unos minutos.")

    user = db.query(User).filter(User.email.ilike(email)).first()
    bootstrap_master = _bootstrap_master_credentials_match(email, password)
    if bootstrap_master:
        # MASTER_ADMIN_EMAIL colliding with a real tenant's login email is an
        # operator config mistake, but a plausible one. Never let bootstrap
        # login silently overwrite that tenant's password and promote them
        # to platform_admin - fail closed instead of hijacking the account.
        if user and user.role != "platform_admin":
            register_login_failure(db, normalized, "bootstrap_email_collision")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales invalidas",
            )
        if not user:
            user = User(
                email=_normalize_identifier(email),
                password_hash=hash_password(password),
                is_active=True,
                is_verified=True,
                role="platform_admin",
            )
            db.add(user)
            db.flush()
        user.email = _normalize_identifier(email)
        user.password_hash = hash_password(password)
        user.is_active = True
        user.is_verified = True
        user.role = "platform_admin"
    else:
        if not user:
            register_login_failure(db, normalized, "user_not_found")
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")

        _authorize_user_for_master_panel(user)

        if not verify_password(password, user.password_hash):
            register_login_failure(db, normalized, "bad_password")
            db.commit()
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")

    if not _pin_matches(pin):
        register_login_failure(db, normalized, "bad_pin")
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="PIN invalido")

    reset_login_lockout(db, normalized)
    login_limiter.reset(f"master:{normalized}", db=db)
    return user


def create_master_admin_mfa_challenge(user: User) -> str:
    """Issue a short-lived, purpose-bound token without creating a session."""
    return create_signed_token(
        {
            "purpose": MASTER_ADMIN_MFA_LOGIN_PURPOSE,
            "user_id": user.id,
            "token_version": user.token_version or 0,
        },
        expires_minutes=MASTER_ADMIN_MFA_LOGIN_CHALLENGE_MINUTES,
    )


def _master_admin_mfa_attempt_key(action: str, user_id: int) -> str:
    return f"master_admin:{action}:{user_id}"


def allow_master_admin_mfa_attempt(db: Session, action: str, user_id: int) -> None:
    if not mfa_code_guess_limiter.allow(_master_admin_mfa_attempt_key(action, user_id), db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
    db.commit()


def reset_master_admin_mfa_attempts(db: Session, action: str, user_id: int) -> None:
    mfa_code_guess_limiter.reset(_master_admin_mfa_attempt_key(action, user_id), db=db)


def authenticate_master_mfa_login(db: Session, mfa_token: str, code: str) -> User:
    """Verify a master-admin MFA challenge before a master session is issued."""
    challenge = decode_signed_token(mfa_token)
    if challenge.get("purpose") != MASTER_ADMIN_MFA_LOGIN_PURPOSE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Desafio MFA invalido")

    try:
        user_id = int(challenge["user_id"])
        token_version = int(challenge["token_version"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Desafio MFA invalido") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no valido")
    _authorize_user_for_master_panel(user)
    if token_version != (user.token_version or 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Desafio MFA revocado")
    if not mfa_service.get_active_mfa_secret(db, user.id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="MFA no esta activo")

    allow_master_admin_mfa_attempt(db, "login", user.id)
    try:
        valid = mfa_service.consume_mfa_code(db, user.id, code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if not valid:
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codigo MFA invalido o ya utilizado")

    reset_master_admin_mfa_attempts(db, "login", user.id)
    return user


def _load_session(db: Session, session_token: str) -> MasterAdminSession | None:
    if not session_token:
        return None
    session = db.query(MasterAdminSession).filter(MasterAdminSession.session_token_hash == _hash_value(session_token)).first()
    if not session:
        return None
    if session.revoked_at is not None:
        return None
    now = _now()
    absolute_expiry = _as_aware(session.expires_at)
    idle_expiry = _idle_expiry(session.last_seen_at or session.created_at)
    if absolute_expiry <= now or idle_expiry <= now:
        session.revoked_at = _now()
        db.flush()
        return None
    return session


def require_master_admin(
    request: Request,
    db: Session,
    csrf_header: str | None = None,
    write: bool = False,
) -> MasterAdminContext:
    session_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion master requerida")

    session = _load_session(db, session_token)
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion master invalida o expirada")

    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesion master invalida")
    _authorize_user_for_master_panel(user)

    expected_csrf = request.cookies.get(CSRF_COOKIE_NAME)
    if write:
        if not csrf_header or not expected_csrf or not hmac.compare_digest(csrf_header, expected_csrf):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF invalido")
        if not hmac.compare_digest(session.csrf_token_hash, _hash_value(expected_csrf)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF invalido")

    # Verified platform_admin cookie session, CSRF/lockout checks passed:
    # safe to let this transaction bypass hotel-scoped RLS on the
    # subscriptions/subscription_events/hotel_subscriptions tables the
    # panel reads across every hotel (see f3bdaadd3d15_master_admin_rls_bypass).
    set_master_admin_context(db)

    session.last_seen_at = _now()
    db.flush()
    return MasterAdminContext(user=user, session=session, csrf_token=expected_csrf or "")


def audit_master_action(
    db: Session,
    *,
    actor_user_id: int | None,
    action: str,
    outcome: str = "success",
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> None:
    event = MasterAdminAuditEvent(
        actor_user_id=actor_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        outcome=outcome,
        request_path=request.url.path if request else None,
        request_method=request.method if request else None,
        request_id=request.headers.get("X-Request-Id") if request else None,
        metadata_json=_json_or_null(redact_master_admin_audit_metadata(metadata)),
    )
    db.add(event)
    db.flush()
