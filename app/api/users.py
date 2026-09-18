"""
User management per hotel (owners/co-owners).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission, require_roles_and_permission
from app.models.audit_log import AuditActionEnum
from app.models.user import User
from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.schemas.auth import UserInfo
from app.services.security import verify_password
from app.services import mfa_service
from app.services.permission_service import (
    PERMISSION_HOTEL_PROPERTY_MANAGE,
    PERMISSION_SETTINGS_USERS_MANAGE,
    PERMISSION_SETTINGS_USERS_VIEW,
)
from app.services.invitation_service import (
    invitation_snapshot,
    issue_invitation,
    normalize_email,
    utcnow,
)
from app.services.membership_service import (
    MembershipInvariantError,
    transfer_primary_owner,
    validate_membership_change,
)
from app.services.user_session_service import revoke_all_sessions
from app.adapters.rate_limiter import invite_limiter
from app.config import get_settings
from app.services.email_service import mailer
from app.models.hotel_config import HotelConfiguration
from app.services import audit_log_service
from app.services.staff_invitation_service import (
    StaffAliasConflict,
    provision_staff_invitation,
    set_membership_alias,
)

router = APIRouter(prefix="/api/users", tags=["Users"])
_MANAGE_STAFF = require_roles_and_permission(PERMISSION_SETTINGS_USERS_MANAGE, "owner", "co_owner")


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
    context: AuthContext = Depends(require_roles_and_permission(PERMISSION_SETTINGS_USERS_VIEW, "owner", "co_owner")),
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
    alias: str | None = Field(default=None, max_length=80)


class InviteResponse(BaseModel):
    user: UserInfo
    invitation_id: int
    invite_token: str
    accept_url: str
    email_delivery: Literal["sent", "failed", "not_configured"]


class StaffAliasItem(BaseModel):
    user_id: int
    email: str
    role: str
    status: Literal["active", "invited"]
    alias: str | None = None


class StaffAliasRosterResponse(BaseModel):
    items: list[StaffAliasItem]


class UpdateStaffAliasPayload(BaseModel):
    alias: str | None = Field(max_length=80)


class PrimaryOwnerTransferPayload(BaseModel):
    password: str = Field(min_length=1)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=32)


def _send_invitation_email(
    *,
    email: str,
    hotel_name: str,
    role: str,
    inviter_email: str,
    token: str,
) -> tuple[str, Literal["sent", "failed", "not_configured"]]:
    settings = get_settings()
    base = settings.FRONTEND_URL.rstrip("/")
    # Fragments are not sent in HTTP requests or access logs; the SPA forwards
    # the capability to invitation endpoints in a JSON body.
    accept_url = f"{base}/invitations/accept#token={token}"
    subj = f"Invitación a {hotel_name}"
    body = (
        f"Hola,\n\n"
        f"Te invitaron al hotel '{hotel_name}' con el rol {role}.\n"
        f"Ingresá con Google o con tu cuenta aquí: {accept_url}\n\n"
        f"Invitó: {inviter_email}\n"
        f"Si no esperabas este correo, podés ignorarlo."
    )
    try:
        configured = mailer.configured
    except Exception:
        return accept_url, "failed"
    if not configured:
        return accept_url, "not_configured"
    try:
        sent = mailer.send(email, subj, body)
    except Exception:
        # The invite is already committed. Keep the provider's diagnostic
        # private and let the operator retry through the existing resend path.
        return accept_url, "failed"
    return accept_url, "sent" if sent else "failed"


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
def invite_user(
    payload: InvitePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
):
    key = f"user:{context.user_id}"
    if not invite_limiter.allow(key, db=db):
        db.commit()
        raise HTTPException(status_code=429, detail="Demasiadas invitaciones en poco tiempo. Intentá más tarde.")
    db.commit()

    email = normalize_email(payload.email)
    if not email:
        raise HTTPException(status_code=400, detail="Email requerido")

    role = payload.role
    if role not in {"owner", "co_owner", "manager", "receptionist", "housekeeping"}:
        raise HTTPException(status_code=400, detail="Rol inválido")
    _assert_assignable_role(context.user_role, role)
    try:
        provision = provision_staff_invitation(
            db,
            hotel_id=context.hotel_id,
            email=email,
            role=role,
            inviter_user_id=context.user_id,
            inviter_email=context.user_email or "",
            alias=payload.alias,
            alias_provided="alias" in payload.model_fields_set,
        )
    except StaffAliasConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except MembershipInvariantError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo reservar el alias en este hotel") from exc

    user = provision.user
    membership = provision.membership
    invitation = provision.invitation
    token = provision.token
    reused = provision.reused
    before = provision.membership_before
    invitation_before = provision.invitation_before
    if membership:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="hotel_memberships",
            record_id=membership.id,
            action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after={
                **(audit_log_service.model_snapshot(membership) or {}),
                "event": "staff.invited",
            },
        )

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="staff_invitations",
        record_id=invitation.id,
        action=(
            AuditActionEnum.UPDATE
            if invitation_before and invitation_before.get("id") == invitation.id
            else AuditActionEnum.CREATE
        ),
        actor_user_id=context.user_id,
        payload_before=invitation_before,
        payload_after={"event": "invitation.resend" if reused else "invitation.created", **invitation_snapshot(invitation)},
    )
    db.commit()
    db.refresh(user)

    hotel = db.get(HotelConfiguration, context.hotel_id)
    hotel_name = hotel.hotel_name if hotel else f"Hotel {context.hotel_id}"
    accept_url, email_delivery = _send_invitation_email(
        email=user.email,
        hotel_name=hotel_name,
        role=role,
        inviter_email=context.user_email or "",
        token=token,
    )

    return InviteResponse(
        user=_membership_user_info(user, membership.role if membership else role),
        invitation_id=invitation.id,
        invite_token=token,
        accept_url=accept_url,
        email_delivery=email_delivery,
    )


@router.post("/invitations/{invitation_id}/resend", response_model=InviteResponse)
def resend_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
):
    invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.id == invitation_id,
            StaffInvitation.hotel_id == context.hotel_id,
        )
        .first()
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    if invitation.status != "pending" or invitation.expires_at <= utcnow():
        raise HTTPException(status_code=409, detail="La invitación ya no está pendiente")

    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == context.hotel_id,
            HotelMembership.user_id == invitation.user_id,
        )
        .first()
        if invitation.user_id is not None
        else None
    )
    if membership is None or membership.status != "invited":
        raise HTTPException(status_code=409, detail="La invitación ya no está pendiente")
    _assert_manageable_membership(context.user_role, membership, action="reenviar")

    before = invitation_snapshot(invitation)
    refreshed, token, _reused = issue_invitation(
        db,
        hotel_id=context.hotel_id,
        user_id=invitation.user_id,
        email=invitation.email,
        role=invitation.role,
        inviter_user_id=invitation.inviter_user_id,
        inviter_email=invitation.inviter_email,
    )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="staff_invitations",
        record_id=refreshed.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after={"event": "invitation.resend", **invitation_snapshot(refreshed)},
    )
    db.commit()

    user = db.get(User, invitation.user_id)
    hotel = db.get(HotelConfiguration, context.hotel_id)
    hotel_name = hotel.hotel_name if hotel else f"Hotel {context.hotel_id}"
    accept_url, email_delivery = _send_invitation_email(
        email=refreshed.email,
        hotel_name=hotel_name,
        role=refreshed.role,
        inviter_email=refreshed.inviter_email,
        token=token,
    )
    return InviteResponse(
        user=_membership_user_info(user, refreshed.role),
        invitation_id=refreshed.id,
        invite_token=token,
        accept_url=accept_url,
        email_delivery=email_delivery,
    )


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_invitation(
    invitation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
):
    invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.id == invitation_id,
            StaffInvitation.hotel_id == context.hotel_id,
        )
        .first()
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitación no encontrada")
    if invitation.status != "pending":
        raise HTTPException(status_code=409, detail="La invitación ya no está pendiente")

    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == context.hotel_id,
            HotelMembership.user_id == invitation.user_id,
        )
        .first()
        if invitation.user_id is not None
        else None
    )
    if membership is not None:
        _assert_manageable_membership(context.user_role, membership, action="revocar")

    before_invitation = invitation_snapshot(invitation)
    invitation.status = "revoked"
    invitation.revoked_at = utcnow()
    if membership is not None and membership.status == "invited":
        before_membership = audit_log_service.model_snapshot(membership)
        membership.status = "revoked"
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="hotel_memberships",
            record_id=membership.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before_membership,
            payload_after={
                **(audit_log_service.model_snapshot(membership) or {}),
                "event": "invitation.revoked",
            },
        )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="staff_invitations",
        record_id=invitation.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before_invitation,
        payload_after={"event": "invitation.revoked", **invitation_snapshot(invitation)},
    )
    db.commit()


class UpdateRolePayload(BaseModel):
    role: str


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user(
    user_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
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
    user = db.get(User, user_id)
    if user:
        user.token_version = (user.token_version or 0) + 1
        revoke_all_sessions(db, user.id)
    pending_invitations = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.hotel_id == context.hotel_id,
            StaffInvitation.user_id == user_id,
            StaffInvitation.status == "pending",
        )
        .all()
    )
    for invitation in pending_invitations:
        before_invitation = invitation_snapshot(invitation)
        invitation.status = "revoked"
        invitation.revoked_at = utcnow()
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="staff_invitations",
            record_id=invitation.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before_invitation,
            payload_after={"event": "invitation.revoked", **invitation_snapshot(invitation)},
        )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after={
            **(audit_log_service.model_snapshot(membership) or {}),
            "event": "staff.revoked",
        },
    )
    db.commit()


@router.patch("/{user_id}/role", response_model=UserInfo)
def update_role(
    user_id: int,
    payload: UpdateRolePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
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
    pending_invitation = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.hotel_id == context.hotel_id,
            StaffInvitation.user_id == user_id,
            StaffInvitation.status == "pending",
        )
        .first()
    )
    if pending_invitation is not None:
        before_invitation = invitation_snapshot(pending_invitation)
        pending_invitation.status = "revoked"
        pending_invitation.revoked_at = utcnow()
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="staff_invitations",
            record_id=pending_invitation.id,
            action=AuditActionEnum.STATUS_CHANGE,
            actor_user_id=context.user_id,
            payload_before=before_invitation,
            payload_after={"event": "invitation.invalidated_by_role_change", **invitation_snapshot(pending_invitation)},
        )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after={
            **(audit_log_service.model_snapshot(membership) or {}),
            "event": "staff.role_changed",
        },
    )
    db.commit()
    if user:
        db.refresh(user)
        return _membership_user_info(user, membership.role)
    return _membership_user_info(membership.user, membership.role)


@router.get("/aliases", response_model=StaffAliasRosterResponse)
def list_staff_aliases(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
):
    """Expose only the current hotel's roster fields needed to edit aliases."""

    rows = (
        db.query(HotelMembership, User.email)
        .join(User, User.id == HotelMembership.user_id)
        .filter(
            HotelMembership.hotel_id == context.hotel_id,
            HotelMembership.status.in_(("active", "invited")),
        )
        .order_by(User.email.asc(), HotelMembership.user_id.asc())
        .all()
    )
    return StaffAliasRosterResponse(
        items=[
            StaffAliasItem(
                user_id=membership.user_id,
                email=email,
                role=membership.role,
                status=membership.status,
                alias=membership.alias,
            )
            for membership, email in rows
        ]
    )


@router.patch("/{user_id}/alias", response_model=StaffAliasItem)
def update_staff_alias(
    user_id: int,
    payload: UpdateStaffAliasPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(_MANAGE_STAFF),
):
    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == context.hotel_id,
            HotelMembership.user_id == user_id,
        )
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado en este hotel")
    if membership.status not in {"active", "invited"}:
        raise HTTPException(status_code=409, detail="Solo se puede editar el alias de un usuario activo o invitado")

    before_alias = membership.alias
    try:
        set_membership_alias(
            db,
            hotel_id=context.hotel_id,
            membership=membership,
            alias=payload.alias,
        )
        db.flush()
    except StaffAliasConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="No se pudo reservar el alias en este hotel") from exc

    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_memberships",
        record_id=membership.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before={"alias": before_alias},
        payload_after={"alias": membership.alias, "event": "staff.alias_changed"},
    )
    db.commit()
    return StaffAliasItem(
        user_id=membership.user_id,
        email=membership.user.email,
        role=membership.role,
        status=membership.status,
        alias=membership.alias,
    )


@router.post("/{user_id}/primary-owner")
def transfer_primary_owner_endpoint(
    user_id: int,
    payload: PrimaryOwnerTransferPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_PROPERTY_MANAGE)),
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
