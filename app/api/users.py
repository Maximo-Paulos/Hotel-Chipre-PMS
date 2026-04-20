"""
User management per hotel (owners/co-owners).
"""
import secrets

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


def _assert_assignable_role(actor_role: str | None, target_role: str) -> None:
    if target_role == "owner":
        raise HTTPException(
            status_code=400,
            detail="El rol owner no se asigna desde esta pantalla. Usa un flujo dedicado de transferencia.",
        )

    allowed_by_actor = {
        "owner": {"co_owner", "manager", "housekeeping"},
        "co_owner": {"manager", "housekeeping"},
    }
    if target_role not in allowed_by_actor.get(actor_role or "", set()):
        raise HTTPException(
            status_code=403,
            detail="No tenes permisos para asignar ese rol",
        )


def _assert_manageable_membership(actor_role: str | None, membership: HotelMembership, *, action: str) -> None:
    managed_roles = {
        "owner": {"co_owner", "manager", "housekeeping"},
        "co_owner": {"manager", "housekeeping"},
    }
    if membership.role not in managed_roles.get(actor_role or "", set()):
        raise HTTPException(
            status_code=403,
            detail=f"No tenes permisos para {action} este usuario",
        )



def _membership_user_info(user: User, role: str) -> UserInfo:
    return UserInfo(
        id=user.id,
        email=user.email,
        role=role,
        is_verified=user.is_verified,
        is_active=user.is_active,
    )


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
    users = [m for m in memberships if m.user and m.status == "active"]
    return [_membership_user_info(m.user, m.role) for m in users]


class InvitePayload(BaseModel):
    email: str
    role: str
    password: str | None = None


class InviteResponse(BaseModel):
    user: UserInfo
    invite_token: str
    accept_url: str


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InvitePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    key = f"user:{context.user_id}"
    if not invite_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiadas invitaciones en poco tiempo. Intentá más tarde.")
    db.commit()

    role = payload.role
    if role not in {"owner", "co_owner", "manager", "housekeeping"}:
        raise HTTPException(status_code=400, detail="Rol inválido")
    _assert_assignable_role(context.user_role, role)

    user = db.query(User).filter(User.email.ilike(payload.email)).first()
    if not user:
        user = User(
            email=payload.email.lower(),
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=role,
            is_active=False,
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
        membership.status = "invited"
    else:
        db.add(HotelMembership(hotel_id=context.hotel_id, user_id=user.id, role=role, status="invited"))

    db.commit()
    db.refresh(user)
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user.id)
        .first()
    )

    hotel = db.get(HotelConfiguration, context.hotel_id)
    hotel_name = hotel.hotel_name if hotel else f"Hotel {context.hotel_id}"

    token = create_signed_token(
        {
            "type": "invite",
            "hotel_id": context.hotel_id,
            "email": user.email,
            "role": role,
            "hotel_name": hotel_name,
            "inviter_email": context.user_email,
        },
        expires_minutes=60 * 24 * 7,
    )
    settings = get_settings()
    base = settings.FRONTEND_URL.rstrip("/")
    accept_url = f"{base}/invitations/accept?token={token}"

    subj = f"Invitación a {hotel_name}"
    body = (
        f"Hola,\n\n"
        f"Te invitaron al hotel '{hotel_name}' con el rol {role}.\n"
        f"Aceptá la invitación y creá tu contraseña aquí: {accept_url}\n\n"
        f"Invitó: {context.user_email}\n"
        f"Si no esperabas este correo, podés ignorarlo."
    )
    if mailer.configured:
        mailer.send(user.email, subj, body)

    return InviteResponse(
        user=_membership_user_info(user, membership.role if membership else role),
        invite_token=token,
        accept_url=accept_url,
    )


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
    if membership.user_id == context.user_id:
        raise HTTPException(status_code=400, detail="No puedes revocar tu propio acceso")
    _assert_manageable_membership(context.user_role, membership, action="revocar")
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
    _assert_assignable_role(context.user_role, payload.role)
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user_id)
        .first()
    )
    if not membership:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este hotel")
    if membership.user_id == context.user_id:
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol")
    _assert_manageable_membership(context.user_role, membership, action="modificar")
    membership.role = payload.role
    membership.status = "active"
    user = db.get(User, user_id)
    db.commit()
    if user:
        db.refresh(user)
        return _membership_user_info(user, membership.role)
    return _membership_user_info(membership.user, membership.role)
