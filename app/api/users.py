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
from app.services.security import hash_password, create_signed_token
from app.adapters.rate_limiter import invite_limiter
from app.config import get_settings
from app.services.email_service import mailer
from app.models.hotel_config import HotelConfiguration

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


class InviteResponse(BaseModel):
    user: UserInfo
    invite_token: str


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InvitePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    key = f"user:{context.user_id}"
    if not invite_limiter.allow(key):
        raise HTTPException(status_code=429, detail="Demasiadas invitaciones en poco tiempo. Intentá más tarde.")

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
    # Invitation token and email
    token = create_signed_token(
        {"type": "invite", "hotel_id": context.hotel_id, "email": user.email, "role": role},
        expires_minutes=60 * 24 * 7,
    )
    settings = get_settings()
    base = getattr(settings, "PUBLIC_BASE_URL", None) or "http://localhost:8000"
    accept_url = f"{base}/accept-invitation/{token}"
    hotel = db.get(HotelConfiguration, context.hotel_id)
    if mailer.configured:
        subj = f"Invitación a {hotel.hotel_name if hotel else 'tu hotel'}"
        body = (
            f"Hola,\n\n"
            f"Te invitaron al hotel '{hotel.hotel_name if hotel else context.hotel_id}' con el rol {role}.\n"
            f"Aceptá la invitación y creá tu contraseña aquí: {accept_url}\n\n"
            f"Si no esperabas este correo, podés ignorarlo."
        )
        mailer.send(user.email, subj, body)
    return {"user": UserInfo.model_validate(user), "invite_token": token}


class UpdateRolePayload(BaseModel):
    role: str


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


@router.patch("/{user_id}/role", response_model=UserInfo)
def update_role(
    user_id: int,
    payload: UpdateRolePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    if payload.role not in {"owner", "co_owner", "manager", "housekeeping"}:
        raise HTTPException(status_code=400, detail="Rol inválido")
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este hotel")
    membership.role = payload.role
    membership.status = "active"
    user = db.get(User, user_id)
    if user:
        user.role = payload.role
        db.add(user)
    db.commit()
    if user:
        db.refresh(user)
        return UserInfo.model_validate(user)
    return UserInfo.model_validate(membership.user)
