"""
Permission matrix resolution and mutation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.security_audit_log import SecurityAuditLog
from app.models.permission import HotelPermissionOverride, Permission, RolePermissionDefault


ROLE_OWNER = "owner"
ROLE_CO_OWNER = "co_owner"
ROLE_MANAGER = "manager"
ROLE_RECEPTIONIST = "receptionist"
ROLE_HOUSEKEEPING = "housekeeping"

ROLE_CODES = (ROLE_OWNER, ROLE_CO_OWNER, ROLE_MANAGER, ROLE_RECEPTIONIST, ROLE_HOUSEKEEPING)

PERMISSION_CONFIG_MANAGE = "config:manage"
PERMISSION_PERMISSION_MANAGE = "permissions:manage"
PERMISSION_GUEST_EDIT = "guest:edit"
PERMISSION_GUEST_TAGS = "guest:tags"
PERMISSION_RESERVATION_CREATE = "reservation:create"
PERMISSION_RESERVATION_ROOM_MOVE = "reservation:room_move"
PERMISSION_CHECKIN_PERFORM = "checkin:perform"
PERMISSION_ROOM_BLOCK = "room:block"
PERMISSION_COMPANY_MANAGE = "company:manage"
PERMISSION_CASH_OPERATE = "cash:operate"
PERMISSION_CASH_APPROVE_DIFFERENCE = "cash:approve_difference"
PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO = "checkin:override_prohibido"

PERMISSION_DEFINITIONS: dict[str, str] = {
    PERMISSION_CONFIG_MANAGE: "Manage hotel configuration",
    PERMISSION_PERMISSION_MANAGE: "Manage hotel role permission overrides",
    PERMISSION_GUEST_EDIT: "Edit guest profile data",
    PERMISSION_GUEST_TAGS: "Edit guest tags and segmentation",
    PERMISSION_RESERVATION_CREATE: "Create reservations",
    PERMISSION_RESERVATION_ROOM_MOVE: "Move reservations between rooms",
    PERMISSION_CHECKIN_PERFORM: "Perform guest check-in",
    PERMISSION_ROOM_BLOCK: "Create and resolve room blocks",
    PERMISSION_COMPANY_MANAGE: "Manage companies and company reservation documents",
    PERMISSION_CASH_OPERATE: "Operate cash register sessions and movements",
    PERMISSION_CASH_APPROVE_DIFFERENCE: "Approve cash close differences",
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: "Override prohibido_alojar check-in blocks",
}

DEFAULT_MATRIX: dict[str, dict[str, bool]] = {
    ROLE_OWNER: {code: True for code in PERMISSION_DEFINITIONS},
    ROLE_CO_OWNER: {code: True for code in PERMISSION_DEFINITIONS},
    ROLE_MANAGER: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: True,
        PERMISSION_GUEST_TAGS: True,
        PERMISSION_RESERVATION_CREATE: True,
        PERMISSION_RESERVATION_ROOM_MOVE: True,
        PERMISSION_CHECKIN_PERFORM: True,
        PERMISSION_ROOM_BLOCK: True,
        PERMISSION_COMPANY_MANAGE: True,
        PERMISSION_CASH_OPERATE: True,
        PERMISSION_CASH_APPROVE_DIFFERENCE: True,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: True,
    },
    ROLE_RECEPTIONIST: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: False,
        PERMISSION_GUEST_TAGS: False,
        PERMISSION_RESERVATION_CREATE: True,
        PERMISSION_RESERVATION_ROOM_MOVE: False,
        PERMISSION_CHECKIN_PERFORM: True,
        PERMISSION_ROOM_BLOCK: False,
        PERMISSION_COMPANY_MANAGE: False,
        PERMISSION_CASH_OPERATE: True,
        PERMISSION_CASH_APPROVE_DIFFERENCE: False,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: False,
    },
    ROLE_HOUSEKEEPING: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: False,
        PERMISSION_GUEST_TAGS: False,
        PERMISSION_RESERVATION_CREATE: False,
        PERMISSION_RESERVATION_ROOM_MOVE: False,
        PERMISSION_CHECKIN_PERFORM: False,
        PERMISSION_ROOM_BLOCK: False,
        PERMISSION_COMPANY_MANAGE: False,
        PERMISSION_CASH_OPERATE: False,
        PERMISSION_CASH_APPROVE_DIFFERENCE: False,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: False,
    },
}


def seed_default_permissions(db: Session) -> None:
    """Create or repair the built-in role permission matrix."""

    for code, description in PERMISSION_DEFINITIONS.items():
        permission = db.query(Permission).filter(Permission.code == code).one_or_none()
        if permission is None:
            db.add(Permission(code=code, description=description))
        elif permission.description != description:
            permission.description = description

    db.flush()

    for role, permissions in DEFAULT_MATRIX.items():
        for permission_code, allowed in permissions.items():
            default = (
                db.query(RolePermissionDefault)
                .filter(
                    RolePermissionDefault.role == role,
                    RolePermissionDefault.permission_code == permission_code,
                )
                .one_or_none()
            )
            if default is None:
                db.add(
                    RolePermissionDefault(
                        role=role,
                        permission_code=permission_code,
                        allowed=allowed,
                    )
                )
            else:
                default.allowed = allowed
    db.flush()


def resolve(db: Session, hotel_id: int, role: str | None, permission_code: str) -> bool:
    """Resolve override > default > deny for a hotel role permission."""

    if not role:
        return False

    seed_default_permissions(db)

    override = (
        db.query(HotelPermissionOverride)
        .filter(
            HotelPermissionOverride.hotel_id == hotel_id,
            HotelPermissionOverride.role == role,
            HotelPermissionOverride.permission_code == permission_code,
        )
        .one_or_none()
    )
    if override is not None:
        return bool(override.allowed)

    default = (
        db.query(RolePermissionDefault)
        .filter(
            RolePermissionDefault.role == role,
            RolePermissionDefault.permission_code == permission_code,
        )
        .one_or_none()
    )
    return bool(default.allowed) if default is not None else False


def set_override(
    db: Session,
    hotel_id: int,
    role: str,
    code: str,
    allowed: bool,
    user_id: int | None,
) -> HotelPermissionOverride:
    """Create or update a hotel-specific role permission override and audit it."""

    seed_default_permissions(db)
    override = (
        db.query(HotelPermissionOverride)
        .filter(
            HotelPermissionOverride.hotel_id == hotel_id,
            HotelPermissionOverride.role == role,
            HotelPermissionOverride.permission_code == code,
        )
        .one_or_none()
    )
    if override is None:
        override = HotelPermissionOverride(
            hotel_id=hotel_id,
            role=role,
            permission_code=code,
            allowed=allowed,
            updated_by_user_id=user_id,
        )
        db.add(override)
    else:
        override.allowed = allowed
        override.updated_by_user_id = user_id
        override.updated_at = datetime.now(timezone.utc)

    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="permission.override.updated",
            resource_type="permission_override",
            details=json.dumps(
                {"role": role, "permission_code": code, "allowed": allowed},
                sort_keys=True,
            ),
        )
    )
    db.flush()
    return override


def audit_permission_denied(
    db: Session,
    *,
    hotel_id: int,
    user_id: int | None,
    role: str | None,
    permission_code: str,
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="permission.denied",
            resource_type="permission",
            resource_id=permission_code,
            details=json.dumps(
                {"role": role, "permission_code": permission_code},
                sort_keys=True,
            ),
        )
    )
    db.commit()


def get_matrix(db: Session, hotel_id: int) -> dict[str, dict[str, dict[str, object]]]:
    """Return the resolved permission matrix for a hotel."""

    seed_default_permissions(db)

    defaults = {
        (row.role, row.permission_code): bool(row.allowed)
        for row in db.query(RolePermissionDefault).all()
    }
    overrides = {
        (row.role, row.permission_code): bool(row.allowed)
        for row in db.query(HotelPermissionOverride)
        .filter(HotelPermissionOverride.hotel_id == hotel_id)
        .all()
    }

    matrix: dict[str, dict[str, dict[str, object]]] = {}
    for role in ROLE_CODES:
        matrix[role] = {}
        for code, description in PERMISSION_DEFINITIONS.items():
            key = (role, code)
            if key in overrides:
                allowed = overrides[key]
                source = "override"
            else:
                allowed = defaults.get(key, False)
                source = "default" if key in defaults else "deny"
            matrix[role][code] = {
                "allowed": allowed,
                "source": source,
                "description": description,
            }
    return matrix
