from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.adapters.rate_limiter import invitation_accept_limiter, invitation_preview_limiter
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.user import User
from app.schemas.auth import AuthResponse, LoginRequest
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


def _source_key(request: Request) -> str:
    return (request.client.host if request.client else None) or "unknown"


def _available_invitation(token: str, db: Session) -> StaffInvitation:
    invitation = find_by_token(db, token)
    if invitation is None or invitation.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    if is_expired(invitation):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token expirado")
    return invitation


@router.get("/{token}")
def get_invitation(token: str, request: Request, db: Session = Depends(get_db)):
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


class AcceptPayload(LoginRequest):
    # Existing accounts authenticate with their own bearer token and do not
    # reset their password. New accounts still require the current password
    # minimum before a credential is created.
    password: str | None = Field(default=None, min_length=12)


@router.post("/{token}/accept", response_model=AuthResponse)
def accept_invitation(
    token: str,
    payload: AcceptPayload,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    key = _source_key(request)
    if not invitation_accept_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Demasiados intentos de invitación")
    db.commit()
    invitation = _available_invitation(token, db)
    email = invitation.email
    role = invitation.role
    if normalize_email(payload.email) != email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El email no coincide con la invitación",
        )

    user = db.query(User).filter(User.email.ilike(email)).first()
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

    if membership and membership.status == "revoked":
        # A fresh invitation must be issued after membership revocation. This
        # also protects against an old valid token being replayed by the user.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
        )

    if not membership or membership.status != "active":
        ensure_staff_within_limit(
            db,
            invitation.hotel_id,
            exclude_membership_id=membership.id if membership and membership.status == "invited" else None,
        )

    if user is None and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")
    if is_unclaimed_invitation and not payload.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Contraseña requerida")

    invitation_before = invitation_snapshot(invitation)
    # Do this only after identity and membership checks. A rejected attempt by
    # another account must not burn the legitimate recipient's invitation.
    if not consume_invitation(db, invitation):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La invitación ya fue utilizada, revocada o expiró.",
        )

    if user is None:
        user = User(
            email=email,
            password_hash=hash_password(payload.password),
            role=role,
            is_verified=True,
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif is_unclaimed_invitation:
        user.password_hash = hash_password(payload.password)
        user.is_verified = True
        user.is_active = True

    if invitation.user_id is None:
        invitation.user_id = user.id
    if membership is None:
        membership = (
            db.query(HotelMembership)
            .filter(
                HotelMembership.hotel_id == invitation.hotel_id,
                HotelMembership.user_id == user.id,
            )
            .first()
        )

    membership_before = audit_log_service.model_snapshot(membership)
    if membership:
        try:
            validate_membership_change(
                db,
                membership,
                hotel_id=invitation.hotel_id,
                next_role=role,
                next_status="active",
            )
            membership.role = role
            membership.status = "active"
        except MembershipInvariantError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    else:
        membership = HotelMembership(
            hotel_id=invitation.hotel_id,
            user_id=user.id,
            role=role,
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
    db.commit()
    db.refresh(user)

    from app.api.auth import _build_auth_response

    return _build_auth_response(db, user, requested_hotel_id=invitation.hotel_id)
