"""Tenant-scoped permission catalog, resolution, mutation, and audit services."""
from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from weakref import WeakSet

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.hotel_membership import HotelMembership
from app.models.permission import (
    HotelPermissionOverride,
    Permission,
    RolePermissionDefault,
    UserPermissionOverride,
)
from app.models.security_audit_log import SecurityAuditLog


logger = logging.getLogger(__name__)


ROLE_OWNER = "owner"
ROLE_CO_OWNER = "co_owner"
ROLE_MANAGER = "manager"
ROLE_RECEPTIONIST = "receptionist"
ROLE_HOUSEKEEPING = "housekeeping"
ROLE_CODES = (ROLE_OWNER, ROLE_CO_OWNER, ROLE_MANAGER, ROLE_RECEPTIONIST, ROLE_HOUSEKEEPING)

# Canonical v2 permissions. Names intentionally describe reads, writes, and
# higher-risk actions independently so UI visibility never implies mutation.
PERMISSION_PERMISSION_MANAGE = "permissions:manage"
PERMISSION_GUEST_READ = "guest:read"
PERMISSION_GUEST_CREATE = "guest:create"
PERMISSION_GUEST_UPDATE = "guest:update"
PERMISSION_GUEST_TAGS_MANAGE = "guest:tags_manage"
PERMISSION_GUEST_PROHIBITION_READ = "guest:prohibition_read"
PERMISSION_GUEST_PROHIBITION_MANAGE = "guest:prohibition_manage"
PERMISSION_GUEST_EXPORT = "guest:export"
PERMISSION_RESERVATION_READ = "reservation:read"
PERMISSION_RESERVATION_CREATE = "reservation:create"
PERMISSION_RESERVATION_UPDATE = "reservation:update"
PERMISSION_RESERVATION_CANCEL = "reservation:cancel"
PERMISSION_RESERVATION_CHARGE = "reservation:charge"
PERMISSION_RESERVATION_MOVE = "reservation:move"
PERMISSION_RESERVATION_MANUAL_RATE = "reservation:manual_rate"
PERMISSION_RESERVATION_PROHIBITION_OVERRIDE = "reservation:prohibition_override"
PERMISSION_ROOM_READ = "room:read"
PERMISSION_ROOM_STATUS_UPDATE = "room:status_update"
PERMISSION_ROOM_BLOCK_CREATE = "room:block_create"
PERMISSION_ROOM_BLOCK_RELEASE = "room:block_release"
PERMISSION_CHECKIN_PERFORM = "checkin:perform"
PERMISSION_CHECKOUT_PERFORM = "checkout:perform"
PERMISSION_CHECKOUT_FORCE = "checkout:force"
PERMISSION_STOCK_READ = "stock:read"
PERMISSION_STOCK_MOVE = "stock:movement"
PERMISSION_STOCK_ADJUST = "stock:adjust"
PERMISSION_STOCK_ADMIN = "stock:admin"
PERMISSION_LAUNDRY_READ = "laundry:read"
PERMISSION_LAUNDRY_MOVE = "laundry:movement"
PERMISSION_LAUNDRY_VENDOR_MANAGE = "laundry:vendor_manage"
PERMISSION_LAUNDRY_REMITO_MANAGE = "laundry:remito_manage"
PERMISSION_LAUNDRY_PRICE_MANAGE = "laundry:price_manage"
PERMISSION_RATES_READ = "rates:read"
PERMISSION_RATES_UPDATE = "rates:update"
PERMISSION_PROMOTIONS_READ = "promotions:read"
PERMISSION_PROMOTIONS_MANAGE = "promotions:manage"
PERMISSION_HOTEL_SETTINGS_READ = "hotel_settings:read"
PERMISSION_HOTEL_SETTINGS_UPDATE = "hotel_settings:update"
PERMISSION_HOTEL_PROPERTY_MANAGE = "hotel_settings:property_manage"
PERMISSION_HOTEL_SECURITY_MANAGE = "hotel_settings:security_manage"

# Existing capabilities outside the split modules stay canonical.
PERMISSION_COMPANY_MANAGE = "company:manage"
PERMISSION_CASH_OPERATE = "cash:operate"
PERMISSION_CASH_APPROVE_DIFFERENCE = "cash:approve_difference"
PERMISSION_REPORTS_VIEW = "reports:view"
PERMISSION_REPORTS_OPERATIONAL_VIEW = "reports:operational:view"
PERMISSION_REPORTS_FINANCIAL_VIEW = "reports:financial:view"
PERMISSION_APIKEY_MANAGE = "apikey:manage"

# Import-compatible legacy constants. Existing routes and the current frontend
# may keep requesting these during the expand/contract window; resolution
# canonicalizes them and effective responses include readable aliases.
PERMISSION_CONFIG_MANAGE = "config:manage"
PERMISSION_GUEST_VIEW = "guest:view"
PERMISSION_GUEST_EDIT = "guest:edit"
PERMISSION_GUEST_TAGS = "guest:tags"
PERMISSION_RESERVATION_ROOM_MOVE = "reservation:room_move"
PERMISSION_ROOM_CLEANING_STATUS = "room:cleaning_status"
PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO = "checkin:override_prohibido"
PERMISSION_STOCK_OPERATE = "stock:operate"
PERMISSION_LAUNDRY_MANAGE_VENDORS = "laundry:manage_vendors"
PERMISSION_LAUNDRY_OPERATE_REMITOS = "laundry:operate_remitos"

LEGACY_PERMISSION_ALIASES: dict[str, str] = {
    PERMISSION_CONFIG_MANAGE: PERMISSION_HOTEL_SETTINGS_UPDATE,
    PERMISSION_GUEST_VIEW: PERMISSION_GUEST_READ,
    PERMISSION_GUEST_EDIT: PERMISSION_GUEST_UPDATE,
    PERMISSION_GUEST_TAGS: PERMISSION_GUEST_TAGS_MANAGE,
    PERMISSION_RESERVATION_ROOM_MOVE: PERMISSION_RESERVATION_MOVE,
    PERMISSION_ROOM_CLEANING_STATUS: PERMISSION_ROOM_STATUS_UPDATE,
    "room_block:create": PERMISSION_ROOM_BLOCK_CREATE,
    "room_block:release": PERMISSION_ROOM_BLOCK_RELEASE,
    PERMISSION_CHECKIN_OVERRIDE_PROHIBIDO: PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
    PERMISSION_STOCK_OPERATE: PERMISSION_STOCK_MOVE,
    PERMISSION_LAUNDRY_MANAGE_VENDORS: PERMISSION_LAUNDRY_VENDOR_MANAGE,
    PERMISSION_LAUNDRY_OPERATE_REMITOS: PERMISSION_LAUNDRY_REMITO_MANAGE,
}

_CANONICAL_DEFINITIONS: dict[str, tuple[str, str]] = {
    PERMISSION_PERMISSION_MANAGE: ("security", "Administer role and employee permissions"),
    PERMISSION_GUEST_READ: ("guests", "Read guest profile data"),
    PERMISSION_GUEST_CREATE: ("guests", "Create guest profiles"),
    PERMISSION_GUEST_UPDATE: ("guests", "Update guest profiles"),
    PERMISSION_GUEST_TAGS_MANAGE: ("guests", "Manage guest tags"),
    PERMISSION_GUEST_PROHIBITION_READ: ("guests", "Read lodging prohibition status"),
    PERMISSION_GUEST_PROHIBITION_MANAGE: ("guests", "Create and resolve lodging prohibitions"),
    PERMISSION_GUEST_EXPORT: ("guests", "Export guest ledger data"),
    PERMISSION_RESERVATION_READ: ("reservations", "Read reservations"),
    PERMISSION_RESERVATION_CREATE: ("reservations", "Create reservations"),
    PERMISSION_RESERVATION_UPDATE: ("reservations", "Update reservations"),
    PERMISSION_RESERVATION_CANCEL: ("reservations", "Cancel reservations"),
    PERMISSION_RESERVATION_CHARGE: ("reservations", "Add reservation charges"),
    PERMISSION_RESERVATION_MOVE: ("reservations", "Move reservations between rooms"),
    PERMISSION_RESERVATION_MANUAL_RATE: ("rates", "Override the quoted reservation rate"),
    PERMISSION_RESERVATION_PROHIBITION_OVERRIDE: ("guests", "Override a lodging prohibition with reason"),
    PERMISSION_ROOM_READ: ("rooms", "Read rooms and operational state"),
    PERMISSION_ROOM_STATUS_UPDATE: ("rooms", "Update room cleaning status"),
    PERMISSION_ROOM_BLOCK_CREATE: ("rooms", "Create room blocks"),
    PERMISSION_ROOM_BLOCK_RELEASE: ("rooms", "Release room blocks"),
    PERMISSION_CHECKIN_PERFORM: ("checkin", "Perform check-in"),
    PERMISSION_CHECKOUT_PERFORM: ("checkin", "Perform checkout"),
    PERMISSION_CHECKOUT_FORCE: ("checkin", "Force an exceptional checkout"),
    PERMISSION_STOCK_READ: ("stock", "Read stock"),
    PERMISSION_STOCK_MOVE: ("stock", "Record stock movements"),
    PERMISSION_STOCK_ADJUST: ("stock", "Adjust stock after a physical count"),
    PERMISSION_STOCK_ADMIN: ("stock", "Manage stock catalog and locations"),
    PERMISSION_LAUNDRY_READ: ("laundry", "Read laundry operation"),
    PERMISSION_LAUNDRY_MOVE: ("laundry", "Record linen movements"),
    PERMISSION_LAUNDRY_VENDOR_MANAGE: ("laundry", "Manage laundry vendors"),
    PERMISSION_LAUNDRY_REMITO_MANAGE: ("laundry", "Create and receive laundry remitos"),
    PERMISSION_LAUNDRY_PRICE_MANAGE: ("laundry", "Manage vendor prices"),
    PERMISSION_RATES_READ: ("rates", "Read hotel rates"),
    PERMISSION_RATES_UPDATE: ("rates", "Update hotel rates"),
    PERMISSION_PROMOTIONS_READ: ("promotions", "Read promotions"),
    PERMISSION_PROMOTIONS_MANAGE: ("promotions", "Manage promotions"),
    PERMISSION_HOTEL_SETTINGS_READ: ("hotel_settings", "Read hotel settings"),
    PERMISSION_HOTEL_SETTINGS_UPDATE: ("hotel_settings", "Update operational hotel settings"),
    PERMISSION_HOTEL_PROPERTY_MANAGE: ("hotel_settings", "Transfer or change property ownership"),
    PERMISSION_HOTEL_SECURITY_MANAGE: ("security", "Manage security secrets and connections"),
    PERMISSION_COMPANY_MANAGE: ("companies", "Manage companies and documents"),
    PERMISSION_CASH_OPERATE: ("cash", "Operate cash register sessions and movements"),
    PERMISSION_CASH_APPROVE_DIFFERENCE: ("cash", "Approve cash close differences"),
    PERMISSION_REPORTS_OPERATIONAL_VIEW: ("reports", "Read operational reports"),
    PERMISSION_REPORTS_FINANCIAL_VIEW: ("reports", "Read financial reports"),
    PERMISSION_APIKEY_MANAGE: ("security", "Manage public hotel API keys"),
}

PERMISSION_DEFINITIONS: dict[str, str] = {
    code: description for code, (_module, description) in _CANONICAL_DEFINITIONS.items()
}
for _legacy_code, _canonical_code in LEGACY_PERMISSION_ALIASES.items():
    PERMISSION_DEFINITIONS[_legacy_code] = f"Legacy alias for {_canonical_code}"
PERMISSION_DEFINITIONS.update(
    {
        PERMISSION_GUEST_VIEW: "View guest profile data",
        PERMISSION_GUEST_CREATE: "Create guest profiles",
        PERMISSION_GUEST_EDIT: "Edit guest profile data",
        PERMISSION_GUEST_TAGS: "Edit guest tags and segmentation",
    }
)


def canonical_permission_code(code: str) -> str:
    return LEGACY_PERMISSION_ALIASES.get(code, code)


def _role_permissions(*allowed_codes: str) -> dict[str, bool]:
    allowed = {canonical_permission_code(code) for code in allowed_codes}
    canonical = {code: code in allowed for code in _CANONICAL_DEFINITIONS}
    return {
        **canonical,
        **{legacy: canonical.get(target, False) for legacy, target in LEGACY_PERMISSION_ALIASES.items()},
    }


_OPERATIONS = tuple(
    code
    for code in _CANONICAL_DEFINITIONS
    if code
    not in {
        PERMISSION_PERMISSION_MANAGE,
        PERMISSION_HOTEL_PROPERTY_MANAGE,
        PERMISSION_HOTEL_SECURITY_MANAGE,
        PERMISSION_APIKEY_MANAGE,
        PERMISSION_RESERVATION_MANUAL_RATE,
    }
)
DEFAULT_MATRIX: dict[str, dict[str, bool]] = {
    ROLE_OWNER: _role_permissions(*_CANONICAL_DEFINITIONS),
    ROLE_CO_OWNER: _role_permissions(*_OPERATIONS),
    ROLE_MANAGER: _role_permissions(
        PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE, PERMISSION_GUEST_UPDATE,
        PERMISSION_GUEST_TAGS_MANAGE, PERMISSION_GUEST_PROHIBITION_READ,
        PERMISSION_GUEST_PROHIBITION_MANAGE, PERMISSION_GUEST_EXPORT,
        PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_CREATE,
        PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CANCEL,
        PERMISSION_RESERVATION_MOVE, PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
        PERMISSION_ROOM_READ, PERMISSION_ROOM_STATUS_UPDATE,
        PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_ROOM_BLOCK_RELEASE,
        PERMISSION_CHECKIN_PERFORM, PERMISSION_CHECKOUT_PERFORM,
        PERMISSION_STOCK_READ, PERMISSION_STOCK_MOVE, PERMISSION_STOCK_ADMIN,
        PERMISSION_LAUNDRY_READ, PERMISSION_LAUNDRY_MOVE,
        PERMISSION_LAUNDRY_VENDOR_MANAGE, PERMISSION_LAUNDRY_REMITO_MANAGE,
        PERMISSION_LAUNDRY_PRICE_MANAGE, PERMISSION_RATES_READ,
        PERMISSION_RATES_UPDATE, PERMISSION_PROMOTIONS_READ,
        PERMISSION_PROMOTIONS_MANAGE, PERMISSION_REPORTS_OPERATIONAL_VIEW,
        PERMISSION_COMPANY_MANAGE,
    ),
    ROLE_RECEPTIONIST: _role_permissions(
        PERMISSION_GUEST_READ, PERMISSION_GUEST_CREATE, PERMISSION_GUEST_UPDATE,
        PERMISSION_GUEST_TAGS_MANAGE, PERMISSION_GUEST_PROHIBITION_READ,
        PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_CREATE,
        PERMISSION_RESERVATION_UPDATE, PERMISSION_RESERVATION_CANCEL,
        PERMISSION_RESERVATION_CHARGE, PERMISSION_ROOM_READ,
        PERMISSION_ROOM_BLOCK_CREATE, PERMISSION_CHECKIN_PERFORM,
        PERMISSION_CHECKOUT_PERFORM, PERMISSION_CASH_OPERATE,
    ),
    ROLE_HOUSEKEEPING: _role_permissions(
        PERMISSION_ROOM_READ, PERMISSION_ROOM_STATUS_UPDATE, PERMISSION_LAUNDRY_READ,
        PERMISSION_LAUNDRY_MOVE, PERMISSION_LAUNDRY_REMITO_MANAGE,
    ),
}

# Product lanes limit configurable grants. Non-delegable invariants below are
# checked first even if a stale row is inserted by hand.
ROLE_PERMISSION_CEILINGS: dict[str, frozenset[str]] = {
    ROLE_OWNER: frozenset(_CANONICAL_DEFINITIONS),
    ROLE_CO_OWNER: frozenset(_OPERATIONS),
    ROLE_MANAGER: frozenset(code for code, allowed in DEFAULT_MATRIX[ROLE_MANAGER].items() if allowed),
    ROLE_RECEPTIONIST: frozenset(
        {
            *(code for code, allowed in DEFAULT_MATRIX[ROLE_RECEPTIONIST].items() if allowed),
            PERMISSION_GUEST_PROHIBITION_MANAGE,
            PERMISSION_RESERVATION_PROHIBITION_OVERRIDE,
            PERMISSION_RESERVATION_MOVE,
            PERMISSION_ROOM_BLOCK_RELEASE,
        }
    ),
    ROLE_HOUSEKEEPING: frozenset(code for code, allowed in DEFAULT_MATRIX[ROLE_HOUSEKEEPING].items() if allowed),
}

_OWNER_ONLY = frozenset(
    {
        PERMISSION_PERMISSION_MANAGE,
        PERMISSION_HOTEL_PROPERTY_MANAGE,
        PERMISSION_HOTEL_SECURITY_MANAGE,
        PERMISSION_APIKEY_MANAGE,
    }
)


def immutable_permission_decision(role: str | None, code: str) -> tuple[bool, str] | None:
    canonical = canonical_permission_code(code)
    if canonical in _OWNER_ONLY:
        return role == ROLE_OWNER, "owner_only"
    return None


def can_role_hold_permission(role: str | None, permission_code: str) -> bool:
    canonical = canonical_permission_code(permission_code)
    invariant = immutable_permission_decision(role, canonical)
    if invariant is not None:
        return invariant[0]
    return canonical in ROLE_PERMISSION_CEILINGS.get(role or "", frozenset())


def _insert_if_missing(db: Session, table, values, conflict_columns: list[str]) -> None:
    dialect = db.get_bind().dialect.name
    if dialect == "sqlite":
        statement = sqlite_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    elif dialect == "postgresql":
        statement = postgresql_insert(table).values(values).on_conflict_do_nothing(index_elements=conflict_columns)
    else:
        raise RuntimeError(f"Unsupported database dialect for permission seeding: {dialect}")
    db.execute(statement)


def seed_default_permissions(db: Session) -> None:
    _insert_if_missing(
        db,
        Permission.__table__,
        [{"code": code, "description": description} for code, description in PERMISSION_DEFINITIONS.items()],
        ["code"],
    )
    rows = {row.code: row for row in db.query(Permission).filter(Permission.code.in_(PERMISSION_DEFINITIONS)).all()}
    for code, description in PERMISSION_DEFINITIONS.items():
        rows[code].description = description
    db.flush()
    values = [
        {"role": role, "permission_code": code, "allowed": allowed}
        for role, permissions in DEFAULT_MATRIX.items()
        for code, allowed in permissions.items()
    ]
    _insert_if_missing(db, RolePermissionDefault.__table__, values, ["role", "permission_code"])
    # Defaults are deployment data, not runtime configuration. The migration
    # may have backfilled a safer decision from a legacy permission and an
    # operator may already rely on that persisted value. Runtime seeding only
    # fills missing rows; explicit override APIs are the sole mutation path.
    db.flush()


_seeded_engines: WeakSet = WeakSet()
_seed_lock = threading.Lock()


def _engine_key(db: Session):
    bind = db.get_bind()
    return getattr(bind, "engine", bind)


def ensure_permission_matrix_seeded(db: Session) -> None:
    engine = _engine_key(db)
    if engine in _seeded_engines:
        return
    with _seed_lock:
        if engine in _seeded_engines:
            return
        seed_default_permissions(db)
        db.commit()
        _seeded_engines.add(engine)


def reset_permission_seed_cache() -> None:
    _seeded_engines.clear()


def invalidate_effective_permission_cache(db: Session, hotel_id: int, user_id: int | None = None) -> None:
    """Explicit invalidation boundary for callers and future cache adapters.

    Effective authorization is intentionally not cached in-process: a
    revocation committed by another worker must be visible on the very next
    protected request. Mutation paths still call this hook so a distributed
    cache can be introduced without changing their security contract.
    """


def publish_permission_invalidation(hotel_id: int) -> None:
    """Best-effort tenant signal after commit; never roll back the RBAC write."""

    try:
        from app.services.domain_events import RealtimeEventsUnavailable, publish_domain_event

        publish_domain_event(
            hotel_id=hotel_id,
            domain="security",
            event_type="permissions.changed",
            payload={"family": "effective_permissions"},
        )
    except RealtimeEventsUnavailable:
        logger.warning("permission_invalidation.realtime_unavailable", extra={"hotel_id": hotel_id})
    except Exception:
        logger.exception("permission_invalidation.failed", extra={"hotel_id": hotel_id})


def get_effective_permission_details(
    db: Session,
    hotel_id: int,
    role: str | None,
    *,
    user_id: int | None = None,
) -> dict[str, dict[str, object]]:
    if role not in ROLE_CODES:
        return {}
    ensure_permission_matrix_seeded(db)
    defaults = {
        row.permission_code: bool(row.allowed)
        for row in db.query(RolePermissionDefault).filter(RolePermissionDefault.role == role).all()
    }
    role_overrides = {
        row.permission_code: bool(row.allowed)
        for row in db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role).all()
    }
    user_overrides = {}
    if user_id is not None:
        user_overrides = {
            row.permission_code: bool(row.allowed)
            for row in db.query(UserPermissionOverride).filter_by(hotel_id=hotel_id, user_id=user_id).all()
        }

    details: dict[str, dict[str, object]] = {}
    for code in _CANONICAL_DEFINITIONS:
        invariant = immutable_permission_decision(role, code)
        if invariant is not None:
            allowed, reason = invariant
            details[code] = {"allowed": allowed, "source": "invariant", "locked": True, "lock_reason": reason}
        elif not can_role_hold_permission(role, code):
            details[code] = {"allowed": False, "source": "invariant", "locked": True, "lock_reason": "role_ceiling"}
        elif code in user_overrides:
            details[code] = {"allowed": user_overrides[code], "source": "user_override", "locked": False, "lock_reason": None}
        elif code in role_overrides:
            details[code] = {"allowed": role_overrides[code], "source": "role_override", "locked": False, "lock_reason": None}
        elif code in defaults:
            details[code] = {"allowed": defaults[code], "source": "role_default", "locked": False, "lock_reason": None}
        else:
            details[code] = {"allowed": False, "source": "deny", "locked": False, "lock_reason": None}

    return details


def resolve(
    db: Session,
    hotel_id: int,
    role: str | None,
    permission_code: str,
    user_id: int | None = None,
) -> bool:
    canonical = canonical_permission_code(permission_code)
    return bool(get_effective_permission_details(db, hotel_id, role, user_id=user_id).get(canonical, {}).get("allowed"))


def _audit(db: Session, *, hotel_id: int, actor_user_id: int | None, action: str, resource_type: str,
           resource_id: str, before: object, after: object) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=json.dumps({"before": before, "after": after}, sort_keys=True),
        )
    )


def _validate_mutable(role: str, code: str, allowed: bool) -> str:
    canonical = canonical_permission_code(code)
    if canonical not in _CANONICAL_DEFINITIONS:
        raise ValueError("Permiso invalido")
    invariant = immutable_permission_decision(role, canonical)
    if invariant is not None:
        raise ValueError("El permiso esta bloqueado por una regla de seguridad")
    if allowed and not can_role_hold_permission(role, canonical):
        raise ValueError("El permiso excede el techo de seguridad del rol")
    return canonical


def set_role_override(
    db: Session, hotel_id: int, role: str, code: str, allowed: bool, actor_user_id: int | None,
) -> HotelPermissionOverride:
    canonical = _validate_mutable(role, code, allowed)
    ensure_permission_matrix_seeded(db)
    row = db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role, permission_code=canonical).one_or_none()
    before = None if row is None else {"allowed": bool(row.allowed)}
    if row is None:
        row = HotelPermissionOverride(hotel_id=hotel_id, role=role, permission_code=canonical, allowed=allowed)
        db.add(row)
    row.allowed = allowed
    row.updated_by_user_id = actor_user_id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.override.updated", resource_type="permission_override",
        resource_id=f"{role}:{canonical}", before=before,
        after={"role": role, "permission_code": canonical, "allowed": allowed},
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id)
    return row


def set_override(db: Session, hotel_id: int, role: str, code: str, allowed: bool, user_id: int | None):
    """Backward-compatible alias for the role-override mutation."""
    return set_role_override(db, hotel_id, role, code, allowed, actor_user_id=user_id)


def _active_membership(db: Session, hotel_id: int, user_id: int) -> HotelMembership | None:
    return db.query(HotelMembership).filter_by(hotel_id=hotel_id, user_id=user_id, status="active").one_or_none()


def set_user_override(
    db: Session, hotel_id: int, target_user_id: int, target_role: str | None,
    code: str, allowed: bool, actor_user_id: int | None,
) -> UserPermissionOverride:
    membership = _active_membership(db, hotel_id, target_user_id)
    if membership is None or (target_role is not None and membership.role != target_role):
        raise LookupError("Usuario no encontrado")
    canonical = _validate_mutable(membership.role, code, allowed)
    ensure_permission_matrix_seeded(db)
    row = db.query(UserPermissionOverride).filter_by(
        hotel_id=hotel_id, user_id=target_user_id, permission_code=canonical
    ).one_or_none()
    before = None if row is None else {"allowed": bool(row.allowed)}
    if row is None:
        row = UserPermissionOverride(hotel_id=hotel_id, user_id=target_user_id, permission_code=canonical, allowed=allowed)
        db.add(row)
    row.allowed = allowed
    row.updated_by_user_id = actor_user_id
    row.updated_at = datetime.now(timezone.utc)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.user_override.updated", resource_type="user_permission_override",
        resource_id=f"{target_user_id}:{canonical}", before=before,
        after={"user_id": target_user_id, "permission_code": canonical, "allowed": allowed},
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id, target_user_id)
    return row


def restore_role_defaults(db: Session, hotel_id: int, role: str, actor_user_id: int | None) -> int:
    rows = db.query(HotelPermissionOverride).filter_by(hotel_id=hotel_id, role=role).all()
    before = [{"permission_code": row.permission_code, "allowed": bool(row.allowed)} for row in rows]
    for row in rows:
        db.delete(row)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.role_overrides.restored", resource_type="permission_override",
        resource_id=role, before=before, after=[],
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id)
    return len(rows)


def restore_user_defaults(db: Session, hotel_id: int, target_user_id: int, actor_user_id: int | None) -> int:
    if _active_membership(db, hotel_id, target_user_id) is None:
        raise LookupError("Usuario no encontrado")
    rows = db.query(UserPermissionOverride).filter_by(hotel_id=hotel_id, user_id=target_user_id).all()
    before = [{"permission_code": row.permission_code, "allowed": bool(row.allowed)} for row in rows]
    for row in rows:
        db.delete(row)
    _audit(
        db, hotel_id=hotel_id, actor_user_id=actor_user_id,
        action="permission.user_overrides.restored", resource_type="user_permission_override",
        resource_id=str(target_user_id), before=before, after=[],
    )
    db.flush()
    invalidate_effective_permission_cache(db, hotel_id, target_user_id)
    return len(rows)


def get_permission_catalog() -> list[dict[str, object]]:
    result = []
    for code, (module, description) in _CANONICAL_DEFINITIONS.items():
        result.append(
            {
                "code": code,
                "module": module,
                "description": description,
                "legacy_aliases": sorted(alias for alias, target in LEGACY_PERMISSION_ALIASES.items() if target == code),
                "locked": code in _OWNER_ONLY,
                "lock_reason": "owner_only" if code in _OWNER_ONLY else None,
            }
        )
    return sorted(result, key=lambda row: (str(row["module"]), str(row["code"])))


def get_matrix(db: Session, hotel_id: int) -> dict[str, dict[str, dict[str, object]]]:
    matrix = {}
    for role in ROLE_CODES:
        canonical = get_effective_permission_details(db, hotel_id, role)
        role_result = {}
        for code, description in PERMISSION_DEFINITIONS.items():
            detail = dict(canonical[canonical_permission_code(code)])
            source = detail["source"]
            if source == "role_override":
                source = "override"
            elif source == "role_default":
                source = "default"
            elif source == "invariant" and detail.get("lock_reason") == "role_ceiling":
                source = "ceiling"
            role_result[code] = {"allowed": detail["allowed"], "source": source, "description": description}
        matrix[role] = role_result
    return matrix


def get_role_profiles(db: Session, hotel_id: int) -> dict[str, dict[str, dict[str, object]]]:
    """Canonical role profiles with UI-ready source and immutable metadata."""

    profiles = {}
    for role in ROLE_CODES:
        details = get_effective_permission_details(db, hotel_id, role)
        profiles[role] = {
            code: {
                **detail,
                "description": _CANONICAL_DEFINITIONS[code][1],
                "module": _CANONICAL_DEFINITIONS[code][0],
            }
            for code, detail in details.items()
        }
    return profiles


def get_effective_permissions(db: Session, hotel_id: int, role: str | None, user_id: int | None = None) -> list[str]:
    details = get_effective_permission_details(db, hotel_id, role, user_id=user_id)
    allowed = {code for code, detail in details.items() if detail["allowed"]}
    allowed.update(alias for alias, target in LEGACY_PERMISSION_ALIASES.items() if target in allowed)
    return sorted(allowed)


def audit_permission_denied(
    db: Session, *, hotel_id: int, user_id: int | None, role: str | None, permission_code: str,
) -> None:
    db.add(
        SecurityAuditLog(
            hotel_id=hotel_id,
            user_id=user_id,
            action="permission.denied",
            resource_type="permission",
            resource_id=canonical_permission_code(permission_code),
            details=json.dumps(
                {
                    "role": role,
                    "permission_code": permission_code,
                    "canonical_permission_code": canonical_permission_code(permission_code),
                },
                sort_keys=True,
            ),
        )
    )
    db.commit()
