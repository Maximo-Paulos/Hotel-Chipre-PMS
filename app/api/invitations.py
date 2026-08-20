from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.services.security import decode_signed_token, hash_password
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.models.hotel_config import HotelConfiguration
from app.schemas.auth import AuthResponse
from app.schemas.auth import LoginRequest

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])


@router.get("/{token}")
def get_invitation(token: str, db: Session = Depends(get_db)):
    data = decode_signed_token(token)
    if data.get("type") != "invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    hotel = db.get(HotelConfiguration, data.get("hotel_id"))
    return {
        "email": data.get("email"),
        "role": data.get("role"),
        "hotel_id": data.get("hotel_id"),
        "hotel_name": data.get("hotel_name") or (hotel.hotel_name if hotel else None),
        "inviter_email": data.get("inviter_email"),
    }


class AcceptPayload(LoginRequest):
    # LoginRequest.password has no min_length -- correct there (must accept
    # existing passwords predating any length policy change), but this class
    # sets a *new* credential and must enforce the current minimum itself.
    password: str = Field(min_length=12)


@router.post("/{token}/accept", response_model=AuthResponse)
def accept_invitation(
    token: str,
    payload: AcceptPayload,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    data = decode_signed_token(token)
    if data.get("type") != "invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    email = data.get("email")
    role = data.get("role")
    hotel_id = data.get("hotel_id")
    if email.lower() != payload.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El email no coincide con la invitación")

    user = db.query(User).filter(User.email.ilike(email)).first()
    membership = None
    is_unclaimed_invitation = False
    if user:
        membership = (
            db.query(HotelMembership)
            .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == user.id)
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

    if not user:
        user = User(
            email=email.lower(),
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
    if membership is None:
        membership = (
            db.query(HotelMembership)
            .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == user.id)
            .first()
        )
    if membership and membership.status == "revoked":
        # An old accept link stays valid for up to 7 days after issuance and is
        # independent of membership state. Without this check, an authenticated
        # owner of the account could replay it to self-reactivate access the
        # hotel owner explicitly revoked. Reactivation must come from a fresh
        # invite, not a stale accept token.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este acceso fue revocado. Pedí una nueva invitación al hotel.",
        )
    if membership:
        membership.role = role
        membership.status = "active"
    else:
        db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role=role, status="active"))

    db.commit()
    db.refresh(user)
    # Build auth response
    from app.api.auth import _build_auth_response

    return _build_auth_response(db, user, requested_hotel_id=hotel_id)
