"""
User management per hotel (owners/co-owners).
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_auth_context, AuthContext, require_roles
from app.models.audit_log import AuditActionEnum
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.schemas.auth import UserInfo
from app.services.security import hash_password, create_signed_token, verify_password
from app.services import mfa_service
from app.services.membership_service import (
    MembershipInvariantError,
    transfer_primary_owner,
    validate_membership_change,
)
from app.adapters.rate_limiter import invite_limiter
from app.config import get_settings
from app.master_admin.email_provider import MasterEmailConnectionError
from app.services.email_service import mailer
from app.models.hotel_config import HotelConfiguration
from app.services import audit_log_service

router = APIRouter(prefix="/api/users", tags=["Users"])


def _assert_assignable_role(actor_role: str | None, target_role: str) -> None:
    if target_role == "owner":
        raise HTTPException(
            status_code=400,
            detail="El rol owner no se asigna desde esta pantalla. Usa un flujo dedicado de transferencia.",
        )

    allowed_by_actor = {
        "owner": {"co_owner", "manager", "receptionist", "housekeeping"},
        "co_owner": {"manager", "receptionist", "housekeeping"},
    }
    if target_role not in allowed_by_actor.get(actor_role or "", set()):
        raise HTTPException(
            status_code=403,
            detail="No tenes permisos para asignar ese rol",
        )


def _assert_manageable_membership(actor_role: str | None, membership: HotelMembership, *, action: str) -> None:
    managed_roles = {
        "owner": {"co_owner", "manager", "receptionist", "housekeeping"},
        "co_owner": {"manager", "receptionist", "housekeeping"},
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


class PrimaryOwnerTransferPayload(BaseModel):
    password: str = Field(min_length=1)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


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
    if role not in {"owner", "co_owner", "manager", "receptionist", "housekeeping"}:
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
    before = audit_log_service.model_snapshot(membership)
    if membership:
        try:
            validate_membership_change(
                db,
                membership,
                hotel_id=context.hotel_id,
                next_role=role,
                next_status="invited",
            )
            membership.role = role
            membership.status = "invited"
        except MembershipInvariantError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        membership = HotelMembership(hotel_id=context.hotel_id, user_id=user.id, role=role, status="invited")
        db.add(membership)

    db.commit()
    db.refresh(user)
    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == context.hotel_id, HotelMembership.user_id == user.id)
        .first()
    )
    if membership:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="hotel_memberships",
            record_id=membership.id,
            action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(membership),
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
        try:
            mailer.send(user.email, subj, body)
        except MasterEmailConnectionError:
            pass

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
    before = audit_log_service.model_snapshot(membership)
    try:
        validate_membership_change(
            db,
            membership,
            hotel_id=context.hotel_id,
            next_role=membership.role,
            next_status="revoked",
        )
        membership.status = "revoked"
        db.flush()
    except MembershipInvariantError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(membership),
    )


@router.patch("/{user_id}/role", response_model=UserInfo)
def update_role(
    user_id: int,
    payload: UpdateRolePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    if payload.role not in {"owner", "co_owner", "manager", "receptionist", "housekeeping"}:
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
    before = audit_log_service.model_snapshot(membership)
    try:
        validate_membership_change(
            db,
            membership,
            hotel_id=context.hotel_id,
            next_role=payload.role,
            next_status="active",
        )
        membership.role = payload.role
        membership.status = "active"
        db.flush()
    except MembershipInvariantError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    user = db.get(User, user_id)
    db.commit()
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(membership),
    )
    if user:
        db.refresh(user)
        return _membership_user_info(user, membership.role)
    return _membership_user_info(membership.user, membership.role)


@router.post("/{user_id}/primary-owner")
def transfer_primary_owner_endpoint(
    user_id: int,
    payload: PrimaryOwnerTransferPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner")),
):
    """Transfer billing/property ownership after explicit account reauth."""
    current_user = db.get(User, context.user_id)
    if current_user is None or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Usuario no valido")
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Reautenticacion invalida")

    if mfa_service.get_active_mfa_secret(db, current_user.id):
        if not payload.mfa_code or not mfa_service.consume_mfa_code(db, current_user.id, payload.mfa_code):
            db.rollback()
            raise HTTPException(status_code=403, detail="Se requiere un codigo MFA valido")

    try:
        target = transfer_primary_owner(
            db,
            hotel_id=context.hotel_id,
            current_user_id=current_user.id,
            target_user_id=user_id,
        )
        db.commit()
    except MembershipInvariantError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "hotel_id": context.hotel_id,
        "primary_owner_user_id": target.user_id,
        "transferred": True,
    }
