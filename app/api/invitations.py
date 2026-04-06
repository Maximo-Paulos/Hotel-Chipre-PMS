from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.security import decode_signed_token, hash_password
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.dependencies.auth import get_auth_context, AuthContext
from app.schemas.auth import AuthResponse, UserInfo
from app.services.hotel_service import get_memberships_for_user, get_or_create_hotel_for_owner
from app.schemas.auth import LoginRequest

router = APIRouter(prefix="/api/invitations", tags=["Invitations"])


@router.get("/{token}")
def get_invitation(token: str):
    data = decode_signed_token(token)
    if data.get("type") != "invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    return {"email": data.get("email"), "role": data.get("role"), "hotel_id": data.get("hotel_id")}


class AcceptPayload(LoginRequest):
    pass


@router.post("/{token}/accept", response_model=AuthResponse)
def accept_invitation(token: str, payload: AcceptPayload, db: Session = Depends(get_db)):
    data = decode_signed_token(token)
    if data.get("type") != "invite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    email = data.get("email")
    role = data.get("role")
    hotel_id = data.get("hotel_id")
    if email.lower() != payload.email.lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El email no coincide con la invitación")

    user = db.query(User).filter(User.email.ilike(email)).first()
    if not user:
        user = User(email=email.lower(), password_hash=hash_password(payload.password), role=role, is_verified=True, is_active=True)
        db.add(user)
        db.flush()
    else:
        user.password_hash = hash_password(payload.password)
        user.is_verified = True
        user.is_active = True
        user.role = role
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == user.id)
        .first()
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
