"""Shared staff membership and invitation provisioning path."""
from __future__ import annotations

import secrets
import unicodedata
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.invitation import StaffInvitation
from app.models.user import User
from app.services.invitation_service import issue_invitation, normalize_email
from app.services.membership_service import MembershipInvariantError, validate_membership_change
from app.services.security import hash_password
from app.services.subscription_service import ensure_staff_within_limit


ROLE_ALIASES = {
    "owner": "owner",
    "co_owner": "co_owner",
    "co-owner": "co_owner",
    "manager": "manager",
    "gerente": "manager",
    "reception": "receptionist",
    "receptionist": "receptionist",
    "front desk": "receptionist",
    "frontdesk": "receptionist",
    "recepcion": "receptionist",
    "recepcionista": "receptionist",
    "housekeeping": "housekeeping",
    "housekeeper": "housekeeping",
    "limpieza": "housekeeping",
}
VALID_STAFF_ROLES = {"owner", "co_owner", "manager", "receptionist", "housekeeping"}


@dataclass
class StaffInvitationProvision:
    user: User
    membership: HotelMembership
    invitation: StaffInvitation
    token: str
    reused: bool
    membership_before: dict | None
    invitation_before: dict | None


class StaffAliasConflict(ValueError):
    """The requested hotel alias is already in use by another membership."""


def normalize_staff_role(role: str | None) -> str:
    key = " ".join((role or "receptionist").strip().lower().replace("_", " ").split())
    normalized = ROLE_ALIASES.get(key, key)
    if normalized not in VALID_STAFF_ROLES:
        raise ValueError("Rol de staff inválido")
    return normalized


def normalize_staff_alias(alias: str | None) -> tuple[str | None, str | None]:
    """Return the trimmed display alias and a case-insensitive uniqueness key."""

    if alias is None:
        return None, None
    normalized = unicodedata.normalize("NFKC", " ".join(alias.split()))
    if not normalized:
        return None, None
    if len(normalized) > 80:
        raise ValueError("El alias no puede superar los 80 caracteres")
    key = normalized.casefold()
    if len(key) > 240:
        raise ValueError("El alias no puede superar los 80 caracteres")
    return normalized, key


def set_membership_alias(
    db: Session,
    *,
    hotel_id: int,
    membership: HotelMembership,
    alias: str | None,
) -> None:
    """Set one hotel's alias after checking that its normalized key is unique."""

    normalized, key = normalize_staff_alias(alias)
    if key is not None:
        duplicate = (
            db.query(HotelMembership.id)
            .filter(
                HotelMembership.hotel_id == hotel_id,
                HotelMembership.alias_key == key,
                HotelMembership.user_id != membership.user_id,
            )
            .first()
        )
        if duplicate is not None:
            raise StaffAliasConflict("Ese alias ya está en uso en este hotel")
    membership.alias = normalized
    membership.alias_key = key


def provision_staff_invitation(
    db: Session,
    *,
    hotel_id: int,
    email: str,
    role: str,
    inviter_user_id: int | None,
    inviter_email: str,
    alias: str | None = None,
    alias_provided: bool = False,
) -> StaffInvitationProvision:
    """Create/update the user, hotel membership, and pending invitation.

    This function deliberately does not send mail. Callers that explicitly
    expose an invitation flow may use the returned token to send it after the
    transaction is committed.
    """
    normalized_email = normalize_email(email)
    if not normalized_email:
        raise ValueError("Email requerido")
    normalized_role = normalize_staff_role(role)
    normalized_inviter_email = normalize_email(inviter_email)
    if not normalized_inviter_email:
        raise ValueError("Email del invitante requerido")

    ensure_staff_within_limit(db, hotel_id)
    user = db.query(User).filter(User.email.ilike(normalized_email)).first()
    if not user:
        user = User(
            email=normalized_email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            role=normalized_role,
            is_active=False,
            is_verified=False,
        )
        db.add(user)
        db.flush()

    membership = (
        db.query(HotelMembership)
        .filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == user.id)
        .first()
    )
    membership_before = None
    if membership:
        membership_before = {
            "id": membership.id,
            "hotel_id": membership.hotel_id,
            "user_id": membership.user_id,
            "role": membership.role,
            "status": membership.status,
        }
        try:
            validate_membership_change(
                db,
                membership,
                hotel_id=hotel_id,
                next_role=normalized_role,
                next_status="invited",
            )
        except MembershipInvariantError:
            raise
        membership.role = normalized_role
        membership.status = "invited"
    else:
        membership = HotelMembership(
            hotel_id=hotel_id,
            user_id=user.id,
            role=normalized_role,
            status="invited",
        )
        db.add(membership)

    if alias_provided:
        set_membership_alias(
            db,
            hotel_id=hotel_id,
            membership=membership,
            alias=alias,
        )

    db.flush()
    existing = (
        db.query(StaffInvitation)
        .filter(
            StaffInvitation.hotel_id == hotel_id,
            StaffInvitation.email == normalized_email,
            StaffInvitation.status == "pending",
        )
        .order_by(StaffInvitation.id.desc())
        .first()
    )
    invitation_before = None
    if existing:
        invitation_before = {
            "id": existing.id,
            "hotel_id": existing.hotel_id,
            "user_id": existing.user_id,
            "email": existing.email,
            "role": existing.role,
            "status": existing.status,
        }
    invitation, token, reused = issue_invitation(
        db,
        hotel_id=hotel_id,
        user_id=user.id,
        email=normalized_email,
        role=normalized_role,
        inviter_user_id=inviter_user_id,
        inviter_email=normalized_inviter_email,
    )
    return StaffInvitationProvision(
        user=user,
        membership=membership,
        invitation=invitation,
        token=token,
        reused=reused,
        membership_before=membership_before,
        invitation_before=invitation_before,
    )
