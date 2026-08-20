"""
Auth endpoints: register, login, email verification and password reset.
Verification and reset codes are persisted in the database.
"""
import json
import logging
from datetime import datetime, timezone
import secrets

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.adapters.memory_tokens import token_store
from app.adapters.rate_limiter import (
    code_guess_limiter,
    login_limiter,
    mfa_code_guess_limiter,
    register_limiter,
    reset_request_limiter,
    verify_request_limiter,
)
from app.database import get_db
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    GoogleAuthRequest,
    LoginRequest,
    MfaChallengeResponse,
    MfaCodeRequest,
    MfaDisableRequest,
    MfaEnrollmentResponse,
    MfaLoginRequest,
    MfaRecoveryCodesResponse,
    RegisterRequest,
    RequestCode,
    ResetPasswordRequest,
    ResetCodeValidationResponse,
    UserSessionRead,
    UserInfo,
    VerifyCodeRequest,
)
from app.services.email_service import (
    send_reset_password_email,
    send_verification_email,
    send_verification_success_email,
)
from app.master_admin.email_provider import MasterEmailConnectionError
from app.services import onboarding_service
from app.services.hotel_service import get_or_create_hotel_for_owner, get_memberships_for_user
from app.services.security import create_access_token, hash_password, needs_rehash, verify_password
from app.services.security import create_signed_token, decode_signed_token
from app.dependencies.auth import AuthContext, get_auth_context, get_current_user
from app.config import get_settings
from app.services.external_effects_policy import (
    GoogleLoginDisabled,
    require_google_login,
)
from app.services.permission_service import get_effective_permissions
from app.services import mfa_service
from app.services.user_session_service import (
    USER_CSRF_COOKIE_NAME,
    USER_SESSION_COOKIE_NAME,
    clear_user_session_cookies,
    create_session,
    csrf_double_submit_matches,
    list_active_sessions,
    revoke_all_sessions,
    revoke_session,
    session_matches_token,
    set_user_session_cookies,
    validate_and_touch_session,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])
LOGGER = logging.getLogger(__name__)
MFA_LOGIN_CHALLENGE_MINUTES = 5


def _generate_code() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _mask_email(email: str) -> str:
    local_part, at, domain = email.partition("@")
    if not at:
        return "***"
    if len(local_part) <= 2:
        masked_local = f"{local_part[:1]}***"
    else:
        masked_local = f"{local_part[:2]}***"
    return f"{masked_local}@{domain}"


def _pick_default_hotel_id(db: Session, hotel_ids: list[int]) -> int:
    """
    Prefer a hotel whose onboarding is already complete.

    When a user belongs to multiple hotels, the auth response must not pick an
    arbitrary membership, because that can land the user in an unfinished hotel
    and send them to onboarding even if another active hotel is operational.
    """

    completed_hotels: list[int] = []
    fallback_hotels: list[int] = []
    for hotel_id in hotel_ids:
        try:
            status = onboarding_service.get_status(db, hotel_id=hotel_id)
        except Exception:
            fallback_hotels.append(hotel_id)
            continue
        if status.get("completed"):
            completed_hotels.append(hotel_id)
        else:
            fallback_hotels.append(hotel_id)

    if completed_hotels:
        return completed_hotels[0]
    return fallback_hotels[0]


def _build_auth_response(db: Session, user: User, requested_hotel_id: int | None = None) -> AuthResponse:
    memberships = get_memberships_for_user(db, user.id)
    memberships_by_hotel = {m.hotel_id: m for m in memberships if m.status == "active"}
    if not memberships_by_hotel:
        raise HTTPException(
            status_code=403,
            detail="La cuenta no tiene acceso a ningun hotel activo. Pedile al owner que te invite nuevamente.",
        )
    hotel_ids = sorted(memberships_by_hotel.keys())
    if requested_hotel_id is not None and requested_hotel_id not in memberships_by_hotel:
        raise HTTPException(status_code=403, detail="No tenes acceso al hotel solicitado")
    hotel_id = requested_hotel_id if requested_hotel_id is not None else _pick_default_hotel_id(db, hotel_ids)
    active_membership = memberships_by_hotel[hotel_id]
    effective_permissions = get_effective_permissions(
        db,
        hotel_id=hotel_id,
        role=active_membership.role,
        user_id=user.id,
    )
    token = create_access_token(
        subject=user.id,
        extra={
            "email": user.email,
            "role": active_membership.role,
            "verified": user.is_verified,
            "hotel_id": hotel_id,
            "hotel_ids": hotel_ids,
            "token_version": user.token_version or 0,
        },
    )
    return AuthResponse(
        access_token=token,
        hotel_id=hotel_id,
        user=UserInfo(
            id=user.id,
            email=user.email,
            role=active_membership.role,
            is_verified=user.is_verified,
            is_active=user.is_active,
            permissions=effective_permissions,
        ),
        permissions=effective_permissions,
        requires_verification=not user.is_verified,
        hotel_ids=hotel_ids,
    )


def _attach_user_session_cookies(
    db: Session,
    user: User,
    request: Request,
    response: Response,
) -> str:
    """Set the session cookies and return the raw CSRF token.

    The caller must put the return value on the JSON response
    (``AuthResponse.csrf_token``): the API and the SPA are cross-site, so
    the frontend can never read the CSRF cookie itself via
    ``document.cookie`` -- the response body is the only channel it has.
    """
    _session, session_token, csrf_token = create_session(db, user, request)
    set_user_session_cookies(response, session_token, csrf_token)
    db.commit()
    return csrf_token


def _audit_security_event(
    db: Session,
    *,
    user: User,
    action: str,
    details: dict[str, object],
) -> None:
    """Project a global identity event into every hotel the user actively belongs to."""
    details_json = json.dumps(details, sort_keys=True)
    memberships = get_memberships_for_user(db, user.id)
    # Identity events have no single hotel; skip users without an active
    # membership because SecurityAuditLog.hotel_id is intentionally required.
    for membership in memberships:
        db.add(
            SecurityAuditLog(
                hotel_id=membership.hotel_id,
                user_id=user.id,
                action=action,
                resource_type="user",
                resource_id=str(user.id),
                details=details_json,
            )
        )


def _issue_auth_response(
    db: Session,
    user: User,
    request: Request | None = None,
    response: Response | None = None,
    *,
    audit_action: str | None = None,
    audit_details: dict[str, object] | None = None,
) -> AuthResponse:
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    if audit_action is not None:
        _audit_security_event(
            db,
            user=user,
            action=audit_action,
            details=audit_details or {},
        )
    db.commit()
    db.refresh(user)
    auth_response = _build_auth_response(db, user)
    if request is not None and response is not None:
        auth_response.csrf_token = _attach_user_session_cookies(db, user, request, response)
    return auth_response


def _build_login_response(
    db: Session,
    user: User,
    request: Request | None = None,
    response: Response | None = None,
    *,
    audit_action: str | None = None,
    audit_details: dict[str, object] | None = None,
) -> AuthResponse | MfaChallengeResponse:
    """Return a session only after the required account MFA factor succeeds."""
    if mfa_service.get_active_mfa_secret(db, user.id):
        challenge = create_signed_token(
            {
                "purpose": "mfa_login",
                "user_id": user.id,
                "token_version": user.token_version or 0,
            },
            expires_minutes=MFA_LOGIN_CHALLENGE_MINUTES,
        )
        return MfaChallengeResponse(
            mfa_token=challenge,
            expires_in=MFA_LOGIN_CHALLENGE_MINUTES * 60,
        )

    return _issue_auth_response(
        db,
        user,
        request=request,
        response=response,
        audit_action=audit_action,
        audit_details=audit_details,
    )


def _mfa_attempt_key(action: str, user_id: int) -> str:
    return f"{action}:{user_id}"


def _allow_mfa_attempt(db: Session, action: str, user_id: int) -> None:
    if not mfa_code_guess_limiter.allow(_mfa_attempt_key(action, user_id), db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
    db.commit()


def _reset_mfa_attempts(db: Session, action: str, user_id: int) -> None:
    mfa_code_guess_limiter.reset(_mfa_attempt_key(action, user_id), db=db)


def _issue_email_token(db: Session, email: str, token_type: str) -> str:
    code = _generate_code()
    token_store.issue(db, token_type=token_type, subject_key=email, code=code, ttl_minutes=15)
    return code


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    # Registration always uses a fresh, distinct email, so the duplicate-email
    # check below cannot throttle repeated farming/spam from one source the
    # way it can for login/reset. Rate limit by source IP instead.
    source = (request.client.host if request.client else None) or "unknown"
    if not register_limiter.allow(source, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados registros. Espera unos minutos.")
    db.commit()

    existing = db.query(User).filter(User.email.ilike(payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un usuario con ese email")

    # Self-registration always creates a plain owner account. `payload.role`
    # is never trusted here: `require_platform_admin()` authorizes purely on
    # `User.role`, so honoring a client-supplied role would let anyone
    # self-escalate to platform_admin by sending it in the register body.
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role="owner",
        is_verified=False,
    )
    db.add(user)
    db.flush()
    get_or_create_hotel_for_owner(db, user.email)
    code = _issue_email_token(db, payload.email, "email_verification")
    try:
        send_verification_email(payload.email, code)
        db.commit()
        db.refresh(user)
    except MasterEmailConnectionError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    auth_response = _build_auth_response(db, user)
    auth_response.csrf_token = _attach_user_session_cookies(db, user, request, response)
    return auth_response


@router.post("/request-verify")
def request_verify(payload: RequestCode, db: Session = Depends(get_db)):
    key = payload.email.lower()
    if not verify_request_limiter.allow(key, db=db):
        db.commit()
        LOGGER.warning("request_verify rate limit hit email=%s", _mask_email(key))
        raise HTTPException(status_code=429, detail="Demasiados intentos de verificacion. Espera unos minutos.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or user.is_verified:
        reason = "not_found" if not user else "already_verified"
        LOGGER.info("request_verify no-op email=%s reason=%s", _mask_email(key), reason)
        return {"sent": True}

    code = _issue_email_token(db, payload.email, "email_verification")
    try:
        send_verification_email(payload.email, code)
        db.commit()
    except MasterEmailConnectionError as exc:
        db.rollback()
        LOGGER.warning("request_verify mail delivery failed email=%s error=%s", _mask_email(key), exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"sent": True}


@router.post("/login", response_model=AuthResponse | MfaChallengeResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    key = payload.email.lower()
    settings = get_settings()
    login_limiter.limit = getattr(settings, "LOGIN_RATE_LIMIT", 5)
    if not login_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera e intenta de nuevo.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales invalidas")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)

    db.add(user)
    db.commit()
    login_limiter.reset(key, db=db)
    db.commit()
    return _build_login_response(
        db,
        user,
        request=request,
        response=response,
        audit_action="auth.login.success",
        audit_details={"method": "password"},
    )


@router.post("/login/mfa", response_model=AuthResponse)
def complete_mfa_login(
    payload: MfaLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    challenge = decode_signed_token(payload.mfa_token)
    if challenge.get("purpose") != "mfa_login":
        raise HTTPException(status_code=401, detail="Desafio MFA invalido")

    try:
        user_id = int(challenge.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Desafio MFA invalido") from exc

    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no valido")
    if int(challenge.get("token_version", user.token_version or 0)) != (user.token_version or 0):
        raise HTTPException(status_code=401, detail="Desafio MFA revocado")
    if not mfa_service.get_active_mfa_secret(db, user.id):
        raise HTTPException(status_code=401, detail="MFA no esta activo")

    _allow_mfa_attempt(db, "login", user.id)
    try:
        valid = mfa_service.consume_mfa_code(db, user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if not valid:
        db.commit()
        raise HTTPException(status_code=401, detail="Codigo MFA invalido o ya utilizado")

    _reset_mfa_attempts(db, "login", user.id)
    return _issue_auth_response(
        db,
        user,
        request=request,
        response=response,
        audit_action="auth.login.success",
        audit_details={"method": "password+mfa"},
    )


@router.post("/google", response_model=AuthResponse | MfaChallengeResponse)
def google_login(
    payload: GoogleAuthRequest,
    request: Request = None,
    response: Response = None,
    db: Session = Depends(get_db),
):
    """
    "Sign in with Google" via Google Identity Services' ID-token flow: the
    frontend never talks to our backend during the OAuth dance, it just hands
    us the signed JWT Google issued. We verify that signature against
    GOOGLE_CLIENT_ID (env var, public, same value as frontend's
    VITE_GOOGLE_CLIENT_ID -- no client secret exists or is needed for this
    flow). Google Cloud Console: create an OAuth Client ID (type "Web
    application") with authorized JavaScript origins for the real app
    domains (no redirect URI needed, this flow doesn't use one).
    """
    try:
        # Before constructing Google's request transport, verifying the token,
        # querying a user, or creating an account.
        require_google_login()
    except GoogleLoginDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    settings = get_settings()
    client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
    if not client_id:
        raise HTTPException(status_code=503, detail="Login con Google no esta configurado")

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.id_token, google_requests.Request(), client_id
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Token de Google invalido")

    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="El email de Google no esta verificado")

    raw_email = claims.get("email")
    if not isinstance(raw_email, str) or not raw_email.strip():
        raise HTTPException(status_code=401, detail="Token de Google invalido")
    email = raw_email.strip().lower()

    raw_google_sub = claims.get("sub")
    if not isinstance(raw_google_sub, str) or not raw_google_sub.strip():
        raise HTTPException(status_code=401, detail="Token de Google invalido")
    google_sub = raw_google_sub.strip()

    # The Google subject is the identity key. Never let an email-only match
    # silently select an account: a password registration can exist before
    # its owner proves control of that email.
    # A hit is case (a): the provider subject is already bound, so the
    # account is logged in directly without changing its password or link.
    user = db.query(User).filter(User.google_sub == google_sub).first()
    google_audit_action = "google_auth.linked"
    google_audit_details: dict[str, object] = {
        "account_state": "existing",
        "provider": "google",
    }
    if user is None:
        user = db.query(User).filter(User.email.ilike(email)).first()
        if user is None:
            # Case (c): no account is associated with either the subject or
            # email. Create the same Google-owned account as before, now
            # retaining the subject for future re-logins. The random password
            # is required by the schema but is never given to the user.
            user = User(
                email=email,
                password_hash=hash_password(secrets.token_urlsafe(32)),
                google_sub=google_sub,
                role="owner",
                is_verified=True,  # Google already verified this email
            )
            db.add(user)
            db.flush()
            get_or_create_hotel_for_owner(db, user.email)
            google_audit_details["account_state"] = "created"
        elif not user.is_active:
            raise HTTPException(status_code=403, detail="Usuario deshabilitado")
        elif user.google_sub is None:
            # Case (b): Google has now proved control of an email that was
            # previously used to create a password account without
            # verification. Bind the stable subject, replace the password
            # that may have been chosen by an email squatter, and revoke JWTs
            # issued before this proof. Google has also verified the email for
            # this account.
            user.google_sub = google_sub
            user.password_hash = hash_password(secrets.token_urlsafe(32))
            user.token_version = (user.token_version or 0) + 1
            user.is_verified = True
            google_audit_action = "google_auth.account_reclaimed"
            google_audit_details = {
                "password_invalidated": True,
                "provider": "google",
            }
        else:
            # A different Google subject must never overwrite an existing
            # link or fall back to email-only login. Fail closed on this
            # inconsistent or already-claimed identity state.
            raise HTTPException(status_code=409, detail="El email ya esta vinculado a otra cuenta de Google")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario deshabilitado")

    # Keep one normal Google event per successful provider login, including
    # re-logins with the same subject; it is a confirmed identity-use trace.
    _audit_security_event(
        db,
        user=user,
        action=google_audit_action,
        details=google_audit_details,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_login_response(db, user, request=request, response=response)


@router.post("/verify-email", response_model=AuthResponse)
def verify_email(
    payload: VerifyCodeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    key = payload.email.lower()
    if not code_guess_limiter.allow(f"email_verification:{key}", db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not token_store.verify(db, "email_verification", payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado")
    code_guess_limiter.reset(f"email_verification:{key}", db=db)
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    db.add(user)
    try:
        send_verification_success_email(user.email)
    except MasterEmailConnectionError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    db.commit()
    db.refresh(user)
    auth_response = _build_auth_response(db, user)
    auth_response.csrf_token = _attach_user_session_cookies(db, user, request, response)
    return auth_response


@router.post("/request-reset")
def request_reset(payload: RequestCode, db: Session = Depends(get_db)):
    key = payload.email.lower()
    settings = get_settings()
    reset_request_limiter.limit = getattr(settings, "RESET_RATE_LIMIT", reset_request_limiter.limit)
    if not reset_request_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos de reset. Espera unos minutos.")
    db.commit()

    response: dict = {"sent": True}
    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if user and user.is_verified:
        code = _issue_email_token(db, payload.email, "password_reset")
        try:
            send_reset_password_email(payload.email, code)
            db.commit()
        except MasterEmailConnectionError as exc:
            db.rollback()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return response


@router.post("/validate-reset", response_model=ResetCodeValidationResponse)
def validate_reset(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Validate reset code without changing password (paso previo en UI)."""
    key = payload.email.lower()
    # Shares its attempt budget with /reset-password: both guess the same
    # password_reset code, so an attacker could otherwise brute force it here
    # for free (this endpoint never consumes the code) before cashing it in.
    if not code_guess_limiter.allow(f"password_reset:{key}", db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
    db.commit()
    is_valid = token_store.verify(db, "password_reset", payload.email, payload.code, consume=False)
    return ResetCodeValidationResponse(valid=is_valid)


@router.post("/reset-password", response_model=AuthResponse | MfaChallengeResponse)
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    key = payload.email.lower()
    if not code_guess_limiter.allow(f"password_reset:{key}", db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiados intentos. Espera unos minutos.")
    db.commit()

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user or not token_store.verify(db, "password_reset", payload.email, payload.code):
        raise HTTPException(status_code=400, detail="Codigo invalido o expirado")
    code_guess_limiter.reset(f"password_reset:{key}", db=db)
    user.password_hash = hash_password(payload.new_password)
    user.is_verified = True
    user.last_login = datetime.now(timezone.utc)
    # Revoke every token issued before this reset (see users.token_version).
    user.token_version = (user.token_version or 0) + 1
    # Password reset is also a session-compromise recovery event: old browser
    # sessions must not survive even though this endpoint issues a fresh one.
    revoke_all_sessions(db, user.id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _build_login_response(db, user, request=request, response=response)


@router.post("/mfa/enroll", response_model=MfaEnrollmentResponse)
def enroll_mfa(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        _mfa_secret, secret = mfa_service.enroll_user(db, user.id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    issuer = (get_settings().HOTEL_NAME or "Hotel PMS").strip() or "Hotel PMS"
    otpauth_uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)
    return MfaEnrollmentResponse(secret=secret, otpauth_uri=otpauth_uri)


@router.post("/mfa/enroll/confirm", response_model=MfaRecoveryCodesResponse)
def confirm_mfa_enrollment(
    payload: MfaCodeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _allow_mfa_attempt(db, "enroll", user.id)
    try:
        recovery_codes = mfa_service.confirm_enrollment(db, user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if recovery_codes is None:
        db.commit()
        raise HTTPException(status_code=400, detail="Codigo TOTP invalido o enrolamiento inexistente")
    _reset_mfa_attempts(db, "enroll", user.id)
    _audit_security_event(
        db,
        user=user,
        action="mfa.enrolled",
        details={"factor": "totp"},
    )
    db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=recovery_codes)


@router.post("/mfa/disable")
def disable_mfa(
    payload: MfaDisableRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not mfa_service.get_active_mfa_secret(db, user.id):
        raise HTTPException(status_code=400, detail="MFA no esta activo")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Reautenticacion invalida")

    _allow_mfa_attempt(db, "disable", user.id)
    try:
        valid = mfa_service.consume_mfa_code(db, user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if not valid:
        db.commit()
        raise HTTPException(status_code=401, detail="Codigo MFA invalido o ya utilizado")

    mfa_service.disable_user_mfa(db, user.id)
    _reset_mfa_attempts(db, "disable", user.id)
    _audit_security_event(
        db,
        user=user,
        action="mfa.disabled",
        details={"factor": "totp"},
    )
    db.commit()
    return {"disabled": True}


@router.post("/mfa/recovery-codes/regenerate", response_model=MfaRecoveryCodesResponse)
def regenerate_mfa_recovery_codes(
    payload: MfaCodeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mfa_secret = mfa_service.get_active_mfa_secret(db, user.id)
    if not mfa_secret:
        raise HTTPException(status_code=400, detail="MFA no esta activo")

    _allow_mfa_attempt(db, "regenerate", user.id)
    try:
        valid = mfa_service.consume_mfa_code(db, user.id, payload.code)
    except mfa_service.MfaSecretUnavailableError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="MFA no esta disponible temporalmente") from exc
    if not valid:
        db.commit()
        raise HTTPException(status_code=401, detail="Codigo MFA invalido o ya utilizado")

    recovery_codes = mfa_service.replace_recovery_codes(db, user.id, mfa_secret)
    _reset_mfa_attempts(db, "regenerate", user.id)
    _audit_security_event(
        db,
        user=user,
        action="mfa.recovery_codes_regenerated",
        details={"factor": "totp"},
    )
    db.commit()
    return MfaRecoveryCodesResponse(recovery_codes=recovery_codes)


@router.post("/session/refresh", response_model=AuthResponse)
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Rotate a valid browser session and issue a fresh short-lived JWT."""

    session_token = request.cookies.get(USER_SESSION_COOKIE_NAME)
    csrf_cookie = request.cookies.get(USER_CSRF_COOKIE_NAME)
    if not session_token or not csrf_cookie:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada")

    validated = validate_and_touch_session(
        db,
        session_token,
        request.headers.get("X-CSRF-Token"),
        csrf_cookie,
    )
    if validated is None:
        raise HTTPException(status_code=401, detail="Sesion invalida o expirada")

    session, new_session_token = validated
    user = db.get(User, session.user_id)
    if user is None or not user.is_active:
        revoke_session(db, session.id, session.user_id)
        db.commit()
        raise HTTPException(status_code=401, detail="Usuario no valido")

    auth_response = _build_auth_response(db, user)
    db.commit()
    set_user_session_cookies(response, new_session_token, csrf_cookie)
    # The CSRF token itself doesn't rotate on refresh (only the session
    # token does) -- return it anyway so a fresh page load that only has
    # the access token in memory can still recover it.
    auth_response.csrf_token = csrf_cookie
    return auth_response


@router.get("/sessions", response_model=list[UserSessionRead])
def list_sessions(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List active sessions owned by the Bearer-authenticated user."""

    current_token = request.cookies.get(USER_SESSION_COOKIE_NAME)
    return [
        UserSessionRead(
            id=session.id,
            created_at=session.created_at,
            last_seen_at=session.last_seen_at,
            device_label=session.device_label,
            current=session_matches_token(session, current_token),
        )
        for session in list_active_sessions(db, user.id)
    ]


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = revoke_session(db, session_id, user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesion no encontrada")
    db.commit()
    return {"revoked": True, "session_id": session_id}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Revoke the current cookie session and clear both browser cookies."""

    session_token = request.cookies.get(USER_SESSION_COOKIE_NAME)
    csrf_cookie = request.cookies.get(USER_CSRF_COOKIE_NAME)
    csrf_header = request.headers.get("X-CSRF-Token")
    if session_token and not csrf_double_submit_matches(csrf_header, csrf_cookie):
        raise HTTPException(status_code=403, detail="CSRF invalido")

    if session_token:
        validated = validate_and_touch_session(db, session_token, csrf_header, csrf_cookie)
        if validated is not None:
            session, _new_session_token = validated
            revoke_session(db, session.id, session.user_id)
            db.commit()

    clear_user_session_cookies(response)
    return {"logged_out": True}


@router.get("/me", response_model=UserInfo)
def me(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    current_user = db.get(User, context.user_id)
    if current_user is None:
        raise HTTPException(status_code=401, detail="Usuario no valido")
    effective_permissions = get_effective_permissions(
        db,
        hotel_id=context.hotel_id,
        role=context.user_role,
        user_id=context.user_id,
    )
    return UserInfo(
        id=current_user.id,
        email=current_user.email,
        role=context.user_role or (current_user.role or "owner"),
        is_verified=current_user.is_verified,
        is_active=current_user.is_active,
        permissions=effective_permissions,
    )
