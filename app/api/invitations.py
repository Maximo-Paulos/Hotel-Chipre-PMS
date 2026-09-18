import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.adapters.rate_limiter import invitation_accept_limiter, invitation_preview_limiter
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.user import User
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, MfaChallengeResponse
from app.services import audit_log_service
from app.services.invitation_service import (
    consume_invitation,
    find_by_token,
    invitation_snapshot,
    is_expired,
    normalize_email,
)
from app.services.membership_service import MembershipInvariantError, validate_membership_change
from app.services.security import hash_password
from app.services.subscription_service import ensure_staff_within_limit

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
    if invitation.role not in INVITABLE_ROLES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invitación inválida")
    return invitation


def _activate_invitation_for_user(
    db: Session,
    invitation: StaffInvitation,
    user: User,
) -> HotelMembership:
    """Consume a valid invitation and attach its role to an authenticated user."""
    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == invitation.hotel_id,
            HotelMembership.user_id == user.id,
        )
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
    if not consume_invitation(db, invitation):
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
    # Existing accounts authenticate with their own bearer token and do not
    # reset their password. New accounts still require the current password
    # minimum before a credential is created.
    password: str | None = Field(default=None, min_length=12)


class PathAcceptPayload(LoginRequest):
    """Request body retained for clients that historically put the token in the path."""

    password: str | None = Field(default=None, min_length=12)


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

    user = db.query(User).filter(User.email.ilike(email)).first()
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
        if not is_unclaimed_invitation and (current_user is None or current_user.id != user.id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Esta invitación corresponde a una cuenta existente. "
                    "Inicia sesión con esa cuenta y vuelve a aceptar la invitación."
                ),
            )

    if user is None and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")
    if is_unclaimed_invitation and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")

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

    _activate_invitation_for_user(db, invitation, user)

    from app.api.auth import _issue_auth_response

    return _issue_auth_response(
        db,
        user,
        request=request,
        response=response,
        requested_hotel_id=invitation.hotel_id,
    )


@router.post("/accept", response_model=AuthResponse)
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


@router.post("/{token}/accept", response_model=AuthResponse, include_in_schema=True)
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
        AcceptPayload(token=token, email=payload.email, password=payload.password),
        token,
        request,
        response,
        db,
        current_user,
    )


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
        _audit_security_event,
        _build_login_response,
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
    user = user_by_sub or db.query(User).filter(User.email.ilike(email)).first()
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
        db.flush()
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
    if mfa_service.get_active_mfa_secret(db, user.id):
        db.add(user)
        _audit_security_event(
            db,
            user=user,
            action="google_auth.mfa_challenge",
            details=audit_details,
        )
        db.commit()
        db.refresh(user)
        challenge = _build_login_response(
            db,
            user,
            request=request,
            response=response,
            pending_google_identity=pending_google_identity,
        )
        if not isinstance(challenge, MfaChallengeResponse):
            raise HTTPException(status_code=503, detail="No se pudo iniciar el desafío MFA")
        return challenge

    _activate_invitation_for_user(db, invitation, user)
    return _issue_auth_response(
        db,
        user,
        request=request,
        response=response,
        audit_action="google_auth.linked",
        audit_details=audit_details,
        requested_hotel_id=invitation.hotel_id,
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
