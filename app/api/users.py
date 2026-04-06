"""
User management per hotel (owners/co-owners).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_auth_context, AuthContext, require_roles
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.schemas.auth import UserInfo
from app.services.security import hash_password, create_signed_token, decode_signed_token
from app.schemas.invitation import InvitationToken
from app.services.email_service import mailer
from app.config import get_settings
from fastapi import Body

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/", response_model=list[UserInfo])
def list_users(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    memberships = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id)
        .all()
    )
    users = [m.user for m in memberships if m.user and m.status == "active"]
    return [UserInfo.model_validate(u) for u in users]


class InvitePayload(BaseModel):
    email: str
    role: str
    password: str | None = None


@router.post("/invite", response_model=UserInfo, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InvitePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    role = payload.role
    if role not in {"owner", "co_owner", "manager", "housekeeping"}:
        raise HTTPException(status_code=400, detail="Rol inválido")

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user:
        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(payload.password or "changeme"),
            role=role,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()

    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user.id)
        .first()
    )
    if membership:
        membership.role = role
        membership.status = "active"
    else:
        db.add(HotelMembership(hotel_id=context.hotel_id, user_id=user.id, role=role, status="active"))

    db.commit()
    db.refresh(user)

    # Generate invitation token (JWT) with hotel_id/email/role
    token = create_signed_token(
        {"hotel_id": context.hotel_id, "email": user.email, "role": role, "type": "invite"},
        expires_minutes=60 * 24 * 7,
    )
    base = get_settings().PUBLIC_BASE_URL or "http://localhost:8000"
    invite_link = f"{base}/api/invitations/{token}"
    if mailer.configured:
        mailer.send(
            user.email,
            "Invitación al hotel",
            f"Te invitaron al hotel (ID {context.hotel_id}) con rol {role}. Aceptá aquí: {invite_link}",
        )
    return {"user": UserInfo.model_validate(user), "invite_token": token}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user(
    user_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este hotel")
    membership.status = "revoked"
    db.commit()
