"""Atomic invariants and lifecycle operations for hotel memberships."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.security_audit_log import SecurityAuditLog
from app.services import audit_log_service


class MembershipInvariantError(ValueError):
    """Raised when a membership mutation would violate hotel ownership rules."""


def _lock_active_owner_memberships(db: Session, hotel_id: int) -> list[HotelMembership]:
    """Lock the current owner set for the duration of the caller's transaction."""
    return (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.role == "owner",
            HotelMembership.status == "active",
        )
        .order_by(HotelMembership.id.asc())
        .with_for_update()
        .all()
    )


def ensure_active_owner(db: Session, hotel_id: int) -> list[HotelMembership]:
    """Require at least one active owner while holding the owner-row lock."""
    owners = _lock_active_owner_memberships(db, hotel_id)
    if not owners:
        raise MembershipInvariantError("El hotel debe conservar al menos un owner activo")
    return owners


def validate_membership_change(
    db: Session,
    membership: HotelMembership,
    *,
    hotel_id: int,
    next_role: str,
    next_status: str,
) -> None:
    """Validate a role/status mutation before changing the membership row.

    The owner rows are locked before the decision, so concurrent requests that
    try to remove the last owner serialize on the same hotel owner set.
    """
    if membership.hotel_id != hotel_id:
        raise MembershipInvariantError("La membership no pertenece a este hotel")

    removes_owner = (
        membership.role == "owner"
        and membership.status == "active"
        and (next_role != "owner" or next_status != "active")
    )
    if not removes_owner:
        return

    owners = _lock_active_owner_memberships(db, hotel_id)
    if len(owners) <= 1:
        raise MembershipInvariantError("No se puede dejar al hotel sin un owner activo")
    if membership.is_primary_owner:
        raise MembershipInvariantError("Transferí el Primary Owner antes de modificar esta membership")

    # Owner changes are intentionally reserved for the explicit transfer flow;
    # this closes invitation/replay paths without broadening existing staff
    # management permissions.
    raise MembershipInvariantError("La membership owner sólo puede cambiarse mediante transferencia")


def transfer_primary_owner(
    db: Session,
    *,
    hotel_id: int,
    current_user_id: int,
    target_user_id: int,
) -> HotelMembership:
    """Transfer the single billing/property owner inside one transaction."""
    owners = _lock_active_owner_memberships(db, hotel_id)
    actor = next((row for row in owners if row.user_id == current_user_id), None)
    target = next((row for row in owners if row.user_id == target_user_id), None)

    if actor is None or not actor.is_primary_owner:
        raise MembershipInvariantError("Sólo el Primary Owner actual puede transferir la titularidad")
    if target is None:
        raise MembershipInvariantError("El destinatario debe ser un owner activo del hotel")
    if target.user_id == current_user_id:
        raise MembershipInvariantError("El destinatario ya es el Primary Owner actual")

    previous_primary_ids = [row.user_id for row in owners if row.is_primary_owner]
    for row in owners:
        if row.is_primary_owner:
            row.is_primary_owner = False
    # Flush the demotion before promotion so the partial unique index cannot
    # observe two active primary owners in the same statement batch.
    db.flush()
    target.is_primary_owner = True
    db.flush()
    ensure_active_owner(db, hotel_id)
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None or target.user is None:
        raise MembershipInvariantError("No se pudo resolver el hotel o el usuario destinatario")
    # Keep the legacy billing/contact projection aligned until the wider
    # billing domain adopts the membership field as its sole source of truth.
    hotel.owner_email = target.user.email
    db.flush()

    details = json.dumps(
        {
            "previous_primary_owner_user_ids": previous_primary_ids,
            "new_primary_owner_user_id": target.user_id,
        },
        sort_keys=True,
    )
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=current_user_id,
            action="membership.primary_owner.transferred",
            resource_type="hotel_membership",
            resource_id=str(target.id),
            details=details,
        )
    )
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=hotel_id,
        table_name="hotel_memberships",
        record_id=target.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=current_user_id,
        payload_before={"primary_owner_user_ids": previous_primary_ids},
        payload_after={"primary_owner_user_id": target.user_id},
    )
    return target
