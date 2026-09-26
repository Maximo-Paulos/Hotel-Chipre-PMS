import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.adapters.rate_limiter import invitation_accept_limiter, invitation_preview_limiter, login_limiter
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, MfaChallengeResponse
from app.services import audit_log_service
from app.services.invitation_service import (
    consume_invitation,
    find_by_token,
    hash_invitation_token,
    invitation_snapshot,
    is_expired,
    normalize_email,
)
from app.services.membership_service import MembershipInvariantError, validate_membership_change
from app.services.permission_service import (
    HotelRoleNotFound,
    clear_user_permission_grants_for_role_change,
    require_active_hotel_role,
)
from app.services.security import hash_password, needs_rehash, verify_password
from app.services.subscription_service import ensure_staff_within_limit
from app.services.user_lookup_service import find_user_by_email

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])
INVITABLE_ROLES = {"co_owner", "manager", "receptionist", "housekeeping"}


def _source_key(request: Request) -> str:
    return (request.client.host if request.client else None) or "unknown"


def _available_invitation(token: str, db: Session) -> StaffInvitation:
    invitation = find_by_token(db, token)
    if invitation is None or invitation.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    if is_expired(invitation):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")
    if invitation.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida")
    try:
        custom_role = require_active_hotel_role(db, invitation.hotel_id, invitation.role)
    except HotelRoleNotFound as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida") from exc
    if custom_role is None and invitation.role not in INVITABLE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida")
    return invitation


def _activate_invitation_for_user(
    db: Session,
    invitation: StaffInvitation,
    user: User,
    *,
    expected_token_hash: str | None = None,
) -> HotelMembership:
    """Consume a valid invitation and attach its role to an authenticated user."""
    if invitation.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida")
    try:
        require_active_hotel_role(db, invitation.hotel_id, invitation.role, lock=True)
    except HotelRoleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El rol de la invitación ya no está disponible",
        ) from exc
    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == invitation.hotel_id,
            HotelMembership.user_id == user.id,
        )
        .with_for_update()
        .first()
    )
    if membership is not None and membership.status == "revoked":
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
        )
    if not membership or membership.status != "active":
        try:
            ensure_staff_within_limit(
                db,
                invitation.hotel_id,
                exclude_membership_id=membership.id if membership and membership.status == "invited" else None,
            )
        except HTTPException:
            db.rollback()
            raise

    invitation_before = invitation_snapshot(invitation)
    if not consume_invitation(db, invitation, expected_token_hash=expected_token_hash):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La invitación ya fue utilizada, revocada o expiró.",
        )

    if invitation.user_id is None:
        invitation.user_id = user.id
    membership_before = audit_log_service.model_snapshot(membership)
    if membership is not None:
        try:
            validate_membership_change(
                db,
                membership,
                hotel_id=invitation.hotel_id,
                next_role=invitation.role,
                next_status="active",
            )
            clear_user_permission_grants_for_role_change(
                db,
                hotel_id=invitation.hotel_id,
                target_user_id=user.id,
                actor_user_id=user.id,
                previous_role=membership.role,
                next_role=invitation.role,
            )
            membership.role = invitation.role
            membership.status = "active"
        except MembershipInvariantError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    else:
        membership = HotelMembership(
            hotel_id=invitation.hotel_id,
            user_id=user.id,
            role=invitation.role,
            status="active",
        )
        db.add(membership)
    db.flush()

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=invitation.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.UPDATE if membership_before else AuditActionEnum.CREATE,
        actor_user_id=user.id,
        payload_before=membership_before,
        payload_after={
            **(audit_log_service.model_snapshot(membership) or {}),
            "event": "invitation.accepted",
        },
    )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=invitation.hotel_id,
        table_name="staff_invitations",
        record_id=invitation.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=user.id,
        payload_before={"event": "invitation.pending", **invitation_before},
        payload_after={"event": "invitation.accepted", **invitation_snapshot(invitation)},
    )
    return membership


class InvitationTokenPayload(BaseModel):
    token: str = Field(min_length=1, max_length=512)


def _invitation_info(token: str, request: Request, db: Session):
    key = _source_key(request)
    if not invitation_preview_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiadas consultas de invitación")
    db.commit()
    invitation = _available_invitation(token, db)
    hotel = db.get(HotelConfiguration, invitation.hotel_id)
    return {
        "email": invitation.email,
        "role": invitation.role,
        "hotel_id": invitation.hotel_id,
        "hotel_name": hotel.hotel_name if hotel else None,
        "inviter_email": invitation.inviter_email,
    }


@router.post("/preview")
def get_invitation_preview(
    payload: InvitationTokenPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    return _invitation_info(payload.token, request, db)


class AcceptPayload(LoginRequest):
    token: str = Field(min_length=1, max_length=512)
    # Keep proof of an existing credential distinct from creating a new one.
    current_password: str | None = Field(default=None, max_length=256)
    password: str | None = Field(default=None, max_length=256)


class PathAcceptPayload(LoginRequest):
    """Request body retained for clients that historically put the token in the path."""

    current_password: str | None = Field(default=None, max_length=256)
    password: str | None = Field(default=None, max_length=256)


def _pending_invitation_claim(invitation: StaffInvitation) -> dict[str, object]:
    """Bind a challenge to one invitation without carrying its RLS token digest."""
    return {
        "id": invitation.id,
        "hotel_id": invitation.hotel_id,
        "fingerprint": hashlib.sha256(invitation.token_hash.encode("ascii")).hexdigest(),
    }


def _build_invitation_mfa_challenge(
    user: User,
    invitation: StaffInvitation,
    *,
    method: str,
    pending_google_identity: dict[str, str] | None = None,
) -> MfaChallengeResponse:
    from app.api.auth import MFA_LOGIN_CHALLENGE_MINUTES
    from app.services.security import create_signed_token

    claims: dict[str, object] = {
        "purpose": "invitation_accept_mfa",
        "user_id": user.id,
        "token_version": user.token_version or 0,
        "invitation": _pending_invitation_claim(invitation),
        "method": method,
    }
    if pending_google_identity is not None:
        claims["pending_google_identity"] = pending_google_identity
    return MfaChallengeResponse(
        mfa_token=create_signed_token(claims, expires_minutes=MFA_LOGIN_CHALLENGE_MINUTES),
        expires_in=MFA_LOGIN_CHALLENGE_MINUTES * 60,
    )


def _audit_invitation_mfa_challenge(
    db: Session,
    user: User,
    invitation: StaffInvitation,
    *,
    method: str,
) -> None:
    """Record the challenge in the target hotel even before membership activates."""
    db.add(
        SecurityAuditLog(
            hotel_id=invitation.hotel_id,
            user_id=user.id,
            action="google_auth.mfa_challenge" if method == "google" else "auth.mfa_challenge",
            resource_type="staff_invitation",
            resource_id=str(invitation.id),
            details=json.dumps({"method": method, "scope": "invitation_acceptance"}, sort_keys=True),
        )
    )


def _audit_invitation_accept_denial(
    db: Session,
    *,
    user_id: int,
    hotel_id: int,
    invitation_id: int,
    method: str,
    reason: str,
) -> None:
    from app.services.tenant_context import set_tenant_context

    set_tenant_context(db, user_id=user_id, hotel_id=hotel_id)
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="staff_invitation.accept_denied",
            resource_type="staff_invitation",
            resource_id=str(invitation_id),
            details=json.dumps({"method": method, "reason": reason}, sort_keys=True),
        )
    )
    db.commit()


def _raise_google_identity_integrity_conflict(
    db: Session,
    exc: IntegrityError,
    *,
    google_sub: str,
    email: str,
    expected_user_id: int | None,
) -> None:
    """Translate only an observed Google/email uniqueness race to a safe 409."""
    db.rollback()
    google_owner = db.query(User.id).filter(User.google_sub == google_sub).first()
    if google_owner is not None and google_owner[0] != expected_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La identidad de Google ya está vinculada a otra cuenta",
        ) from exc

    email_owner = find_user_by_email(db, email)
    if email_owner is not None and email_owner.id != expected_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está asociado a otra cuenta",
        ) from exc

    raise exc


def _activate_invitation_for_user_audited(
    db: Session,
    invitation: StaffInvitation,
    user: User,
    *,
    expected_token_hash: str,
    method: str,
) -> HotelMembership:
    invitation_id = invitation.id
    hotel_id = invitation.hotel_id
    user_id = user.id
    try:
        return _activate_invitation_for_user(
            db,
            invitation,
            user,
            expected_token_hash=expected_token_hash,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            db.rollback()
            _audit_invitation_accept_denial(
                db,
                user_id=user_id,
                hotel_id=hotel_id,
                invitation_id=invitation_id,
                method=method,
                reason="activation_conflict",
            )
        raise


def _accept_invitation(
    payload: AcceptPayload,
    token: str,
    request: Request,
    response: Response,
    db: Session,
    current_user: User | None,
):
    key = _source_key(request)
    if not invitation_accept_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos de invitación")
    db.commit()
    invitation = _available_invitation(token, db)
    email = normalize_email(invitation.email)
    if normalize_email(payload.email) != email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email no coincide con la invitación",
        )

    user = find_user_by_email(db, email)
    if invitation.user_id is not None and (user is None or invitation.user_id != user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La invitación ya está asociada a otra cuenta")
    membership = None
    is_unclaimed_invitation = False
    if user:
        membership = (
            db.query(HotelMembership)
            .filter(
                HotelMembership.hotel_id == invitation.hotel_id,
                HotelMembership.user_id == user.id,
            )
            .first()
        )
        # /api/users/invite creates an inactive/unverified placeholder before
        # the recipient claims a new account. It is not an established account
        # and must remain claimable without a bearer token. Every other User,
        # including a revoked membership, must authenticate as that same user.
        is_unclaimed_invitation = (
            not user.is_active
            and not user.is_verified
            and membership is not None
            and membership.status == "invited"
        )
        if membership is not None and membership.status == "revoked":
            _audit_invitation_accept_denial(
                db,
                user_id=user.id,
                hotel_id=invitation.hotel_id,
                invitation_id=invitation.id,
                method="session" if current_user is not None and current_user.id == user.id else "password",
                reason="membership_revoked",
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
            )
        if not is_unclaimed_invitation and (current_user is None or current_user.id != user.id):
            if not user.is_active:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario deshabilitado")
            if not user.password_login_enabled:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Esta cuenta usa Google. Iniciá sesión con Google para aceptar la invitación.",
                )
            current_password = payload.current_password or payload.password
            if not current_password:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Esta invitación corresponde a una cuenta existente. "
                        "Ingresá tu contraseña actual o iniciá sesión con esa cuenta."
                    ),
                )

            from app.config import get_settings

            login_key = email.lower()
            login_limiter.limit = getattr(get_settings(), "LOGIN_RATE_LIMIT", 5)
            if not login_limiter.allow(login_key, db=db):
                db.commit()
                raise HTTPException(status_code=429, detail="Demasiados intentos. Espera e intenta de nuevo.")
            if not verify_password(current_password, user.password_hash):
                db.commit()
                raise HTTPException(status_code=401, detail="Credenciales invalidas")
            if needs_rehash(user.password_hash):
                user.password_hash = hash_password(current_password)
                db.add(user)
            login_limiter.reset(login_key, db=db)
            db.commit()

            from app.services import mfa_service
            from app.services.tenant_context import set_tenant_context

            set_tenant_context(db, user_id=user.id, hotel_id=invitation.hotel_id)
            if mfa_service.get_active_mfa_secret(db, user.id) is not None:
                _audit_invitation_mfa_challenge(db, user, invitation, method="password")
                db.commit()
                challenge = _build_invitation_mfa_challenge(
                    user,
                    invitation,
                    method="password",
                )
                return challenge

            _activate_invitation_for_user_audited(
                db,
                invitation,
                user,
                expected_token_hash=hash_invitation_token(token),
                method="password",
            )
            from app.api.auth import _issue_auth_response

            return _issue_auth_response(
                db,
                user,
                request=request,
                response=response,
                audit_action="auth.login.success",
                audit_details={"method": "password+invitation"},
                requested_hotel_id=invitation.hotel_id,
            )

    if user is None and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")
    if is_unclaimed_invitation and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")
    if (user is None or is_unclaimed_invitation) and payload.password and len(payload.password) < 12:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="La contraseña debe tener al menos 12 caracteres")

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(payload.password),
            role=invitation.role,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif is_unclaimed_invitation:
        user.password_hash = hash_password(payload.password)
        user.password_login_enabled = True
        user.is_verified = True
        user.is_active = True

    _activate_invitation_for_user_audited(
        db,
        invitation,
        user,
        expected_token_hash=hash_invitation_token(token),
        method="password",
    )

    from app.api.auth import _issue_auth_response

    return _issue_auth_response(
        db,
        user,
        request=request,
        response=response,
        requested_hotel_id=invitation.hotel_id,
    )


@router.post("/accept", response_model=AuthResponse | MfaChallengeResponse)
def accept_invitation(
    payload: AcceptPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    if not payload.token:
        raise HTTPException(status_code=422, detail="Token de invitación requerido")
    return _accept_invitation(payload, payload.token, request, response, db, current_user)


@router.post("/{token}/accept", response_model=AuthResponse | MfaChallengeResponse, include_in_schema=True)
def accept_invitation_legacy_path(
    token: str,
    payload: PathAcceptPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """Compatibility endpoint; first-party clients should use the static body-token route."""
    return _accept_invitation(
        AcceptPayload(
            token=token,
            email=payload.email,
            password=payload.password,
            current_password=payload.current_password,
        ),
        token,
        request,
        response,
        db,
        current_user,
    )


class InvitationMfaAcceptPayload(BaseModel):
    token: str = Field(min_length=1, max_length=512)
    mfa_token: str = Field(min_length=1)
    code: str = Field(min_length=1, max_length=64)


def _invitation_matches_challenge(invitation: StaffInvitation, claims: dict[str, object]) -> bool:
    expected = _pending_invitation_claim(invitation)
    try:
        same_row = (
            int(claims.get("id")) == expected["id"]
            and int(claims.get("hotel_id")) == expected["hotel_id"]
        )
    except (TypeError, ValueError):
        return False
    fingerprint = claims.get("fingerprint")
    return (
        same_row
        and isinstance(fingerprint, str)
        and secrets.compare_digest(fingerprint, str(expected["fingerprint"]))
    )


@router.post("/accept/mfa", response_model=AuthResponse)
def complete_invitation_mfa_acceptance(
    payload: InvitationMfaAcceptPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Complete a separately scoped MFA proof and consume exactly its invitation."""
    key = _source_key(request)
    if not invitation_accept_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos de invitación")
    db.commit()

    from app.api.auth import (
        _allow_mfa_attempt,
        _issue_auth_response,
        _reset_mfa_attempts,
    )
    from app.services import mfa_service
    from app.services.security import decode_signed_token
    from app.services.tenant_context import set_tenant_context

    challenge = decode_signed_token(payload.mfa_token)
    if challenge.get("purpose") != "invitation_accept_mfa":
        raise HTTPException(status_code=401, detail="Desafio MFA de invitación invalido")
    try:
        user_id = int(challenge.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Desafio MFA de invitación invalido") from exc
    user = db.get(User, user_id)
    if (
        not user
        or not user.is_active
        or int(challenge.get("token_version", user.token_version or 0)) != (user.token_version or 0)
    ):
        raise HTTPException(status_code=401, detail="Desafio MFA revocado o usuario no valido")

    invitation = _available_invitation(payload.token, db)
    invitation_claim = challenge.get("invitation")
    method = challenge.get("method")
    if (
        not isinstance(invitation_claim, dict)
        or method not in {"password", "google"}
        or not _invitation_matches_challenge(invitation, invitation_claim)
        or invitation.user_id not in (None, user.id)
        or normalize_email(invitation.email) != normalize_email(user.email)
    ):
        raise HTTPException(status_code=409, detail="La invitación no corresponde a este desafío MFA")

    pending_google_identity = challenge.get("pending_google_identity")
    if pending_google_identity is not None:
        if method != "google" or not isinstance(pending_google_identity, dict):
            raise HTTPException(status_code=401, detail="Desafio MFA de invitación invalido")
        pending_email = pending_google_identity.get("email")
        pending_sub = pending_google_identity.get("sub")
        if (
            not isinstance(pending_email, str)
            or normalize_email(pending_email) != normalize_email(user.email)
            or not isinstance(pending_sub, str)
            or not pending_sub
            or len(pending_sub) > 255
            or user.google_sub not in (None, pending_sub)
        ):
            raise HTTPException(status_code=409, detail="La identidad de Google no corresponde a esta cuenta")
        owner_of_google_identity = db.query(User.id).filter(User.google_sub == pending_sub).first()
        if owner_of_google_identity is not None and owner_of_google_identity[0] != user.id:
            raise HTTPException(status_code=409, detail="La identidad de Google ya está vinculada a otra cuenta")

    set_tenant_context(db, user_id=user.id, hotel_id=invitation.hotel_id)
    if mfa_service.get_active_mfa_secret(db, user.id) is None:
        raise HTTPException(status_code=401, detail="MFA no esta activo")
    # Share the same challenge budget as ordinary login. Otherwise an actor
    # could alternate endpoints to multiply guesses against the same account.
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
    # Commit the one-time factor before activation: activation may intentionally
    # roll back if the owner revoked the invite or a hotel invariant fails.
    db.commit()

    db.refresh(user)
    invitation = _available_invitation(payload.token, db)
    set_tenant_context(db, user_id=user.id, hotel_id=invitation.hotel_id)
    if (
        not _invitation_matches_challenge(invitation, invitation_claim)
        or invitation.user_id not in (None, user.id)
        or normalize_email(invitation.email) != normalize_email(user.email)
        or not user.is_active
        or int(challenge.get("token_version", user.token_version or 0)) != (user.token_version or 0)
        or mfa_service.get_active_mfa_secret(db, user.id) is None
    ):
        raise HTTPException(status_code=409, detail="La invitación o la verificación ya no está disponible")

    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == invitation.hotel_id,
            HotelMembership.user_id == user.id,
        )
        .with_for_update()
        .first()
    )
    if membership is not None and membership.status == "revoked":
        _audit_invitation_accept_denial(
            db,
            user_id=user.id,
            hotel_id=invitation.hotel_id,
            invitation_id=invitation.id,
            method=str(method),
            reason="membership_revoked",
        )
        raise HTTPException(
            status_code=409,
            detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
        )
    try:
        _activate_invitation_for_user_audited(
            db,
            invitation,
            user,
            expected_token_hash=hash_invitation_token(payload.token),
            method=str(method),
        )

        if pending_google_identity is not None and user.google_sub is None:
            user.google_sub = pending_google_identity["sub"]
            user.is_verified = True
            user.token_version = (user.token_version or 0) + 1
            from app.services.user_session_service import revoke_all_sessions

            revoke_all_sessions(db, user.id)
            audit_action = "google_auth.linked"
            audit_details = {"account_state": "linked_after_mfa_invitation", "provider": "google"}
        elif method == "google":
            audit_action = "google_auth.login.success"
            audit_details = {"method": "google+invitation+mfa"}
        else:
            audit_action = "auth.login.success"
            audit_details = {"method": "password+invitation+mfa"}

        return _issue_auth_response(
            db,
            user,
            request=request,
            response=response,
            audit_action=audit_action,
            audit_details=audit_details,
            requested_hotel_id=invitation.hotel_id,
        )
    except IntegrityError as exc:
        if method == "google":
            google_sub = (
                pending_google_identity["sub"]
                if pending_google_identity is not None
                else str(user.google_sub or "")
            )
            if google_sub:
                _raise_google_identity_integrity_conflict(
                    db,
                    exc,
                    google_sub=google_sub,
                    email=user.email,
                    expected_user_id=user.id,
                )
        raise


class GoogleInvitationAcceptPayload(GoogleAuthRequest):
    token: str = Field(min_length=1, max_length=512)


def _accept_invitation_with_google(
    token: str,
    payload: GoogleInvitationAcceptPayload,
    request: Request,
    response: Response,
    db: Session,
):
    """Claim a hotel invitation with the invited user's verified Google identity."""
    key = _source_key(request)
    if not invitation_accept_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos de invitación")
    db.commit()
    invitation = _available_invitation(token, db)

    from app.api.auth import (
        _issue_auth_response,
        _verify_google_claims,
    )
    from app.config import get_settings
    from app.services.external_effects_policy import GoogleLoginDisabled, require_google_login
    from app.services import mfa_service

    try:
        require_google_login()
    except GoogleLoginDisabled as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    claims, email, google_sub = _verify_google_claims(payload.id_token, get_settings())
    if email != normalize_email(invitation.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email de Google no coincide con la invitación",
        )

    user_by_sub = db.query(User).filter(User.google_sub == google_sub).first()
    user = user_by_sub or find_user_by_email(db, email)
    if invitation.user_id is not None and (user is None or invitation.user_id != user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La invitación ya está asociada a otra cuenta")

    membership = None
    if user is not None:
        membership = (
            db.query(HotelMembership)
            .filter(
                HotelMembership.hotel_id == invitation.hotel_id,
                HotelMembership.user_id == user.id,
            )
            .first()
        )
    if membership is not None and membership.status == "revoked":
        _audit_invitation_accept_denial(
            db,
            user_id=user.id,
            hotel_id=invitation.hotel_id,
            invitation_id=invitation.id,
            method="google",
            reason="membership_revoked",
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
        )
    is_unclaimed_invitation = (
        user is not None
        and not user.is_active
        and not user.is_verified
        and membership is not None
        and membership.status == "invited"
    )
    pending_google_identity = None
    has_active_mfa = user is not None and mfa_service.get_active_mfa_secret(db, user.id) is not None
    if has_active_mfa and is_unclaimed_invitation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Iniciá sesión con tu contraseña y MFA antes de aceptar esta invitación.",
        )
    if has_active_mfa and user is not None and user.is_active and user.google_sub is None:
        # Link only after the invitee proves control of the existing account's
        # second factor. Completing this challenge preserves its local password.
        pending_google_identity = {"email": email, "sub": google_sub}
        account_state = "pending_mfa_link"
    elif user is not None and user.is_active and user.google_sub is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Este email ya tiene una cuenta. Iniciá sesión con esa cuenta para aceptar la invitación; "
                "después podés vincular Google desde Configuración > Seguridad."
            ),
        )

    if pending_google_identity is not None:
        pass
    elif user is None:
        user = User(
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            google_sub=google_sub,
            password_login_enabled=False,
            role=invitation.role,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError as exc:
            _raise_google_identity_integrity_conflict(
                db,
                exc,
                google_sub=google_sub,
                email=email,
                expected_user_id=None,
            )
        account_state = "created_invited"
    elif not user.is_active and not is_unclaimed_invitation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario deshabilitado")
    elif user.google_sub is not None and user.google_sub != google_sub:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya está vinculado a otra cuenta de Google",
        )
    elif is_unclaimed_invitation:
        user.google_sub = google_sub
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.password_login_enabled = False
        user.is_verified = True
        user.is_active = True
        account_state = "claimed_invited"
    elif user.google_sub is None:
        # Active accounts without MFA were rejected above; an unclaimed
        # placeholder was handled in the preceding branch.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Iniciá sesión con la cuenta existente para aceptar esta invitación.",
        )
    else:
        account_state = "existing"

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario deshabilitado")
    if normalize_email(user.email) != email:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La identidad no coincide con la cuenta")
    audit_details = {"account_state": account_state, "provider": "google"}
    from app.services.tenant_context import set_tenant_context

    set_tenant_context(db, user_id=user.id, hotel_id=invitation.hotel_id)
    if mfa_service.get_active_mfa_secret(db, user.id):
        db.add(user)
        _audit_invitation_mfa_challenge(db, user, invitation, method="google")
        db.commit()
        db.refresh(user)
        challenge = _build_invitation_mfa_challenge(
            user,
            invitation,
            method="google",
            pending_google_identity=pending_google_identity,
        )
        return challenge

    try:
        _activate_invitation_for_user_audited(
            db,
            invitation,
            user,
            expected_token_hash=hash_invitation_token(token),
            method="google",
        )
        return _issue_auth_response(
            db,
            user,
            request=request,
            response=response,
            audit_action="google_auth.linked",
            audit_details=audit_details,
            requested_hotel_id=invitation.hotel_id,
        )
    except IntegrityError as exc:
        _raise_google_identity_integrity_conflict(
            db,
            exc,
            google_sub=google_sub,
            email=email,
            expected_user_id=user.id,
        )


@router.post("/accept/google", response_model=AuthResponse | MfaChallengeResponse)
def accept_invitation_with_google(
    payload: GoogleInvitationAcceptPayload,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if not payload.token:
        raise HTTPException(status_code=422, detail="Token de invitación requerido")
    return _accept_invitation_with_google(payload.token, payload, request, response, db)


@router.post("/{token}/accept/google", response_model=AuthResponse | MfaChallengeResponse, include_in_schema=True)
def accept_invitation_with_google_legacy_path(
    token: str,
    payload: GoogleAuthRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Compatibility endpoint; first-party clients should use the static body-token route."""
    return _accept_invitation_with_google(
        token,
        GoogleInvitationAcceptPayload(token=token, id_token=payload.id_token),
        request,
        response,
        db,
    )
