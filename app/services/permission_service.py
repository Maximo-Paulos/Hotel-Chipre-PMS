"""
Permission matrix resolution and mutation.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from weakref import WeakSet

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.security_audit_log import SecurityAuditLog
from app.models.permission import HotelPermissionOverride, Permission, RolePermissionDefault


ROLE_OWNER = "owner"
ROLE_CO_OWNER = "co_owner"
ROLE_MANAGER = "manager"
ROLE_RECEPTIONIST = "receptionist"
ROLE_HOUSEKEEPING = "housekeeping"

ROLE_CODES = (ROLE_OWNER, ROLE_CO_OWNER, ROLE_MANAGER, ROLE_RECEPTIONIST, ROLE_HOUSEKEEPING)


def _insert_if_missing(
    db: Session,
    table,
    values: dict[str, object] | list[dict[str, object]],
    conflict_columns: list[str],
) -> None:
    """Insert a seed row atomically across the supported SQLite/PostgreSQL backends.

    Permission resolution runs during authentication, so two concurrent first requests
    can initialize the matrix at the same time.  A read-then-insert sequence is not
    safe under that load; the unique constraint must arbitrate the race in the DB.
    """

    dialect_name = db.get_bind().dialect.name
    if dialect_name == "sqlite":
        statement = sqlite_insert(table).values(values).on_conflict_do_nothing(
            index_elements=conflict_columns
        )
    elif dialect_name == "postgresql":
        statement = postgresql_insert(table).values(values).on_conflict_do_nothing(
            index_elements=conflict_columns
        )
    else:
        raise RuntimeError(f"Unsupported database dialect for permission seeding: {dialect_name}")

    db.execute(statement)

PERMISSION_CONFIG_MANAGE = "config:manage"
PERMISSION_PERMISSION_MANAGE = "permissions:manage"
PERMISSION_GUEST_EDIT = "guest:edit"
PERMISSION_GUEST_TAGS = "guest:tags"
PERMISSION_GUEST_EXPORT = "guest:export"
PERMISSION_RESERVATION_CREATE = "reservation:create"
PERMISSION_RESERVATION_CHARGE = "reservation:charge"
PERMISSION_RESERVATION_ROOM_MOVE = "reservation:room_move"
PERMISSION_RESERVATION_MANUAL_RATE = "reservation:manual_rate"
PERMISSION_CHECKIN_PERFORM = "checkin:perform"
PERMISSION_ROOM_BLOCK = "room:block"
PERMISSION_ROOM_BLOCK_CREATE = "room_block:create"
PERMISSION_ROOM_BLOCK_RELEASE = "room_block:release"
PERMISSION_COMPANY_MANAGE = "company:manage"
PERMISSION_CASH_OPERATE = "cash:operate"
PERMISSION_CASH_APPROVE_DIFFERENCE = "cash:approve_difference"
PERMISSION_STOCK_OPERATE = "stock:operate"
PERMISSION_STOCK_ADJUST = "stock:adjust"
PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO = "checkin:override_prohibido"
PERMISSION_REPORTS_VIEW = "reports:view"
PERMISSION_APIKEY_MANAGE = "apikey:manage"
# Vendor/pricing setup is management-trust (billing terms with a third party);
# day-to-day remito creation/viewing is operational and, like stock:operate,
# also granted to housekeeping who already physically handle the linen
# baskets -- see app/api/laundry_vendor.py.
PERMISSION_LAUNDRY_MANAGE_VENDORS = "laundry:manage_vendors"
PERMISSION_LAUNDRY_OPERATE_REMITOS = "laundry:operate_remitos"

PERMISSION_DEFINITIONS: dict[str, str] = {
    PERMISSION_CONFIG_MANAGE: "Manage hotel configuration",
    PERMISSION_PERMISSION_MANAGE: "Manage hotel role permission overrides",
    PERMISSION_GUEST_EDIT: "Edit guest profile data",
    PERMISSION_GUEST_TAGS: "Edit guest tags and segmentation",
    PERMISSION_GUEST_EXPORT: "Export guest ledger data",
    PERMISSION_RESERVATION_CREATE: "Create reservations",
    PERMISSION_RESERVATION_CHARGE: "Add consumption and extra charges to active reservations",
    PERMISSION_RESERVATION_ROOM_MOVE: "Move reservations between rooms",
    PERMISSION_RESERVATION_MANUAL_RATE: "Set a manual rate that overrides the automatic Tarifas quote on a new reservation",
    PERMISSION_CHECKIN_PERFORM: "Perform guest check-in",
    PERMISSION_ROOM_BLOCK: "Create and resolve room blocks",
    PERMISSION_ROOM_BLOCK_CREATE: "Create room blocks (BRM §14.1)",
    PERMISSION_ROOM_BLOCK_RELEASE: "Release/resolve room blocks (BRM §14.1)",
    PERMISSION_COMPANY_MANAGE: "Manage companies and company reservation documents",
    PERMISSION_CASH_OPERATE: "Operate cash register sessions and movements",
    PERMISSION_CASH_APPROVE_DIFFERENCE: "Approve cash close differences",
    PERMISSION_STOCK_OPERATE: "Operate stock items, locations and movements",
    PERMISSION_STOCK_ADJUST: "Authorize stock adjustments",
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: "Override prohibido_alojar check-in blocks",
    PERMISSION_REPORTS_VIEW: "View operational and financial reports",
    PERMISSION_APIKEY_MANAGE: "Manage public hotel API keys",
    PERMISSION_LAUNDRY_MANAGE_VENDORS: "Manage laundry vendors and their pricing",
    PERMISSION_LAUNDRY_OPERATE_REMITOS: "Create and view laundry remitos (delivery notes)",
}

DEFAULT_MATRIX: dict[str, dict[str, bool]] = {
    ROLE_OWNER: {code: True for code in PERMISSION_DEFINITIONS},
    ROLE_CO_OWNER: {code: True for code in PERMISSION_DEFINITIONS},
    ROLE_MANAGER: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: True,
        PERMISSION_GUEST_TAGS: True,
        PERMISSION_GUEST_EXPORT: True,
        PERMISSION_RESERVATION_CREATE: True,
        PERMISSION_RESERVATION_CHARGE: True,
        PERMISSION_RESERVATION_ROOM_MOVE: True,
        PERMISSION_RESERVATION_MANUAL_RATE: False,
        PERMISSION_CHECKIN_PERFORM: True,
        PERMISSION_ROOM_BLOCK: True,
        PERMISSION_ROOM_BLOCK_CREATE: True,
        PERMISSION_ROOM_BLOCK_RELEASE: True,
        PERMISSION_COMPANY_MANAGE: True,
        PERMISSION_CASH_OPERATE: True,
        PERMISSION_CASH_APPROVE_DIFFERENCE: True,
        PERMISSION_STOCK_OPERATE: True,
        PERMISSION_STOCK_ADJUST: False,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: True,
        PERMISSION_REPORTS_VIEW: True,
        PERMISSION_APIKEY_MANAGE: False,
        PERMISSION_LAUNDRY_MANAGE_VENDORS: True,
        PERMISSION_LAUNDRY_OPERATE_REMITOS: True,
    },
    ROLE_RECEPTIONIST: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: False,
        PERMISSION_GUEST_TAGS: False,
        PERMISSION_GUEST_EXPORT: False,
        PERMISSION_RESERVATION_CREATE: True,
        PERMISSION_RESERVATION_CHARGE: True,
        PERMISSION_RESERVATION_ROOM_MOVE: False,
        PERMISSION_RESERVATION_MANUAL_RATE: False,
        PERMISSION_CHECKIN_PERFORM: True,
        PERMISSION_ROOM_BLOCK: False,
        PERMISSION_ROOM_BLOCK_CREATE: True,
        PERMISSION_ROOM_BLOCK_RELEASE: False,
        PERMISSION_COMPANY_MANAGE: False,
        PERMISSION_CASH_OPERATE: True,
        PERMISSION_CASH_APPROVE_DIFFERENCE: False,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: False,
        PERMISSION_REPORTS_VIEW: True,
        PERMISSION_APIKEY_MANAGE: False,
        PERMISSION_LAUNDRY_MANAGE_VENDORS: False,
        PERMISSION_LAUNDRY_OPERATE_REMITOS: False,
    },
    ROLE_HOUSEKEEPING: {
        PERMISSION_CONFIG_MANAGE: False,
        PERMISSION_PERMISSION_MANAGE: False,
        PERMISSION_GUEST_EDIT: False,
        PERMISSION_GUEST_TAGS: False,
        PERMISSION_GUEST_EXPORT: False,
        PERMISSION_RESERVATION_CREATE: False,
        PERMISSION_RESERVATION_CHARGE: False,
        PERMISSION_RESERVATION_ROOM_MOVE: False,
        PERMISSION_CHECKIN_PERFORM: False,
        PERMISSION_ROOM_BLOCK: False,
        PERMISSION_ROOM_BLOCK_CREATE: False,
        PERMISSION_ROOM_BLOCK_RELEASE: False,
        PERMISSION_COMPANY_MANAGE: False,
        PERMISSION_CASH_OPERATE: False,
        PERMISSION_CASH_APPROVE_DIFFERENCE: False,
        PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: False,
        PERMISSION_REPORTS_VIEW: False,
        PERMISSION_LAUNDRY_MANAGE_VENDORS: False,
        PERMISSION_LAUNDRY_OPERATE_REMITOS: True,
    },
}


def seed_default_permissions(db: Session) -> None:
    """Create or repair the built-in role permission matrix."""

    _insert_if_missing(
        db,
        Permission.__table__,
        [{"code": code, "description": description} for code, description in PERMISSION_DEFINITIONS.items()],
        ["code"],
    )
    permissions_by_code = {
        permission.code: permission
        for permission in db.query(Permission)
        .filter(Permission.code.in_(PERMISSION_DEFINITIONS))
        .all()
    }
    for code, description in PERMISSION_DEFINITIONS.items():
        permission = permissions_by_code[code]
        if permission.description != description:
            permission.description = description

    db.flush()

    default_rows = [
        {"role": role, "permission_code": permission_code, "allowed": allowed}
        for role, permissions in DEFAULT_MATRIX.items()
        for permission_code, allowed in permissions.items()
    ]
    _insert_if_missing(
        db,
        RolePermissionDefault.__table__,
        default_rows,
        ["role", "permission_code"],
    )
    defaults_by_key = {
        (default.role, default.permission_code): default
        for default in db.query(RolePermissionDefault).all()
    }
    for role, permissions in DEFAULT_MATRIX.items():
        for permission_code, allowed in permissions.items():
            default = defaults_by_key[(role, permission_code)]
            default.allowed = allowed
    db.flush()


# A1 fix: seed_default_permissions() above is idempotent but not cheap (~120
# rows inserted/repaired + a full RolePermissionDefault scan + 2 flushes). It
# used to run on every resolve()/set_override()/get_matrix() call, i.e. on
# every authenticated request via require_permission. Each process/worker now
# seeds at most once per DB engine: app/main.py's startup does it eagerly so
# normal request traffic never pays for it, and _ensure_seeded() below is a
# cheap fallback for callers that never went through app startup (tests,
# scripts). Keyed by engine identity (not a plain bool) so pytest's per-test
# engines each get seeded exactly once, without needing an explicit reset —
# only long-lived engines shared across tests would need one, and none do
# today (see reset_permission_seed_cache() for that case).
_seeded_engines: "WeakSet" = WeakSet()
_seed_lock = threading.Lock()


def _engine_key(db: Session):
    bind = db.get_bind()
    return getattr(bind, "engine", bind)


def ensure_permission_matrix_seeded(db: Session) -> None:
    """Seed the permission matrix for this DB engine, at most once.

    Commits right away. The whole point of the once-per-engine cache is that
    every later resolve()/get_matrix()/set_override() call on any session
    sharing this engine trusts the seed already landed — a plain flush() is
    not enough, since a caller-side db.rollback() later in the *same* session
    (e.g. an unrelated business error handled a few requests later) would
    silently wipe the seeded rows while the cache still says "done".
    """

    key = _engine_key(db)
    if key in _seeded_engines:
        return
    with _seed_lock:
        if key in _seeded_engines:
            return
        seed_default_permissions(db)
        db.commit()
        _seeded_engines.add(key)


def reset_permission_seed_cache() -> None:
    """Test-only hook: forget which engines were already seeded.

    Needed only if a test reuses one long-lived engine across cases where the
    seeded rows themselves get wiped out between them (e.g. a session-scoped
    Postgres fixture); per-test SQLite engines already reseed for free since
    each test gets a brand new engine object.
    """
    _seeded_engines.clear()


def resolve(db: Session, hotel_id: int, role: str | None, permission_code: str) -> bool:
    """Resolve override > default > deny for a hotel role permission."""

    if not role:
        return False

    ensure_permission_matrix_seeded(db)

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

    ensure_permission_matrix_seeded(db)
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

    ensure_permission_matrix_seeded(db)

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
