"""
Subscription helpers: plan lookup, room limits, status checks and entitlements.
"""
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.subscription import (
    SubscriptionPlan,
    HotelSubscription,
    SubscriptionEntitlement,
    HotelEntitlementOverride,
)
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.room import Room
from app.models.subscription_v2 import Subscription
from app.services.hotel_service import ensure_plans_seeded
from app.services.subscription_entitlements import (
    PLAN_CATALOG,
    change_subscription_plan,
    clear_room_limit_override,
    ensure_subscription_seed,
    set_room_limit_override,
)

# Default entitlements per plan code (beyond room limit which mirrors room_limit)
DEFAULT_ENTITLEMENTS: dict[str, dict[str, Any]] = {
    "starter": {
        "reports.advanced": False,
        "ota.sync": False,
    },
    "pro": {
        "reports.advanced": True,
        "ota.sync": True,
    },
    "ultra": {
        "reports.advanced": True,
        "ota.sync": True,
    },
    "standard": {
        "reports.advanced": True,
        "ota.sync": True,
    },
}


def is_enforcement_enabled() -> bool:
    """Global toggle to make subscription checks hard-blocking."""
    settings = get_settings()
    if hasattr(settings, "SUBSCRIPTION_ENFORCEMENT"):
        return bool(getattr(settings, "SUBSCRIPTION_ENFORCEMENT"))
    return bool(getattr(settings, "SUBSCRIPTION_ENFORCEMENT_ENABLED", False))


def _infer_type(value: Any) -> str:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    return "str"


def _serialize_value(value: Any, value_type: str | None = None) -> tuple[str, str]:
    """Normalize values into (string, type) for portable storage."""
    value_type = value_type or _infer_type(value)
    if value_type == "bool":
        value = "true" if bool(value) else "false"
    elif value_type == "int":
        value = str(int(value))
    else:
        value = "" if value is None else str(value)
    return value, value_type


def _parse_value(raw: str | None, value_type: str) -> Any:
    if raw is None:
        return None
    if value_type == "int":
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    if value_type == "bool":
        return str(raw).lower() in {"1", "true", "yes", "y", "on"}
    return raw


def _upsert_plan_entitlement(
    db: Session,
    plan_id: int,
    code: str,
    value: Any,
    value_type: str | None = None,
    description: str | None = None,
):
    """Idempotent helper to add/update a plan entitlement row."""
    existing = (
        db.query(SubscriptionEntitlement)
        .filter(SubscriptionEntitlement.plan_id == plan_id, SubscriptionEntitlement.code == code)
        .first()
    )
    serialized, kind = _serialize_value(value, value_type)
    if existing:
        existing.value = serialized
        existing.value_type = kind
        if description:
            existing.description = description
        return existing
    ent = SubscriptionEntitlement(
        plan_id=plan_id,
        code=code,
        value=serialized,
        value_type=kind,
        description=description,
    )
    db.add(ent)
    return ent


def ensure_entitlements_seeded(db: Session):
    """
    Seed entitlement rows for known plans.
    Always keeps room entitlement aligned with plan.room_limit.
    """
    ensure_plans_seeded(db)
    for plan in db.query(SubscriptionPlan).all():
        # Room cap derived from plan limit (and later from overrides)
        _upsert_plan_entitlement(
            db,
            plan.id,
            "rooms.max_active",
            plan.room_limit,
            "int",
            "Cantidad máxima de habitaciones activas permitidas por plan.",
        )
        defaults = DEFAULT_ENTITLEMENTS.get(plan.code, {})
        for code, val in defaults.items():
            _upsert_plan_entitlement(db, plan.id, code, val)
    db.flush()


def ensure_subscription(db: Session, hotel_id: int) -> HotelSubscription:
    """Ensure a subscription record exists; create starter active if missing and seed entitlements."""
    ensure_entitlements_seeded(db)
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if sub:
        return sub

    # Route new subscription creation through the v2 service so the canonical
    # row and the legacy compatibility projection are created together.
    ensure_subscription_seed(db, hotel_id, plan_code="starter", status_value="active")
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if sub is None:
        raise RuntimeError("No se pudo inicializar la suscripción del hotel")
    db.flush()
    return sub


def _collect_plan_entitlements(plan: SubscriptionPlan) -> dict[str, dict[str, Any]]:
    entitlements: dict[str, dict[str, Any]] = {}
    for ent in plan.entitlements:
        entitlements[ent.code] = {
            "value": _parse_value(ent.value, ent.value_type),
            "source": "plan",
            "description": ent.description,
        }
    # Safety net in case migration missed room entitlement
    entitlements.setdefault(
        "rooms.max_active",
        {"value": plan.room_limit, "source": "plan", "description": "Habitaciones activas permitidas"},
    )
    return entitlements


def get_entitlements(db: Session, hotel_id: int) -> dict[str, dict[str, Any]]:
    """Return merged entitlements (plan + hotel overrides + room override)."""
    sub = ensure_subscription(db, hotel_id)
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    if not plan:
        return {}

    entitlements = _collect_plan_entitlements(plan)

    # Hotel-level overrides (including room_limit_override)
    overrides = (
        db.query(HotelEntitlementOverride)
        .filter(HotelEntitlementOverride.hotel_id == hotel_id)
        .all()
    )
    for override in overrides:
        entitlements[override.code] = {
            "value": _parse_value(override.value, override.value_type),
            "source": "override",
            "description": override.code,
        }
    if sub.room_limit_override is not None:
        entitlements["rooms.max_active"] = {
            "value": sub.room_limit_override,
            "source": "override",
            "description": "Override aplicado por hotel",
        }
    return entitlements


def get_effective_room_limit(db: Session, hotel_id: int) -> int:
    entitlements = get_entitlements(db, hotel_id)
    limit = entitlements.get("rooms.max_active", {}).get("value")
    return int(limit) if limit is not None else 15


def require_subscription_active(db: Session, hotel_id: int, action: str | None = None):
    """Raise 402 when enforcement is enabled and subscription is inactive."""
    if not is_enforcement_enabled():
        return
    sub = ensure_subscription(db, hotel_id)
    config = db.get(HotelConfiguration, hotel_id)
    inactive = (config and not config.subscription_active) or sub.status != "active"
    if inactive:
        detail = "Suscripción inactiva."
        if action:
            detail = f"Suscripción inactiva. Reactivá el plan para {action}."
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=detail)


def ensure_room_within_limit(db: Session, hotel_id: int):
    """Enforce room limit entitlement; honors enforcement flag."""
    require_subscription_active(db, hotel_id, "crear habitaciones")
    entitlements = get_entitlements(db, hotel_id)
    entry = entitlements.get("rooms.max_active")
    limit = entry["value"] if entry else None
    if limit is None:
        return
    current = (
        db.query(func.count())
        .select_from(Room)
        .filter(Room.hotel_id == hotel_id, Room.is_active.is_(True))
        .scalar()
    )
    if current >= int(limit):
        if is_enforcement_enabled():
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"Superás el límite de habitaciones de tu plan ({limit}). Actualizá el plan para agregar más.",
            )


def get_effective_staff_limit(db: Session, hotel_id: int) -> int | None:
    """Return the active plan's staff limit, with a legacy-table fallback."""
    subscription = (
        db.query(Subscription)
        .filter(Subscription.hotel_id == hotel_id)
        .first()
    )
    if subscription:
        if subscription.staff_limit is not None:
            return int(subscription.staff_limit)
        plan_code = subscription.plan
    else:
        legacy_subscription = (
            db.query(HotelSubscription)
            .filter(HotelSubscription.hotel_id == hotel_id)
            .first()
        )
        plan_code = legacy_subscription.plan.code if legacy_subscription and legacy_subscription.plan else "starter"

    plan = PLAN_CATALOG.get(plan_code) or PLAN_CATALOG["starter"]
    limit = plan.get("staff_limit")
    return int(limit) if limit is not None else None


def get_staff_usage(db: Session, hotel_id: int, *, include_pending: bool = False) -> int:
    """Count tenant-scoped staff memberships without counting revoked access."""
    statuses = ["active", "invited"] if include_pending else ["active"]
    return int(
        db.query(func.count())
        .select_from(HotelMembership)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.status.in_(statuses),
        )
        .scalar()
        or 0
    )


def ensure_staff_within_limit(
    db: Session,
    hotel_id: int,
    *,
    exclude_membership_id: int | None = None,
) -> None:
    """Enforce the plan staff cap for new memberships and invitations."""
    require_subscription_active(db, hotel_id, "invitar personal")
    limit = get_effective_staff_limit(db, hotel_id)
    if limit is None or not is_enforcement_enabled():
        return

    staff_query = (
        db.query(HotelMembership.id)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.status.in_(["active", "invited"]),
        )
    )
    if exclude_membership_id is not None:
        staff_query = staff_query.filter(HotelMembership.id != exclude_membership_id)

    current = staff_query.count()
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Superás el límite de staff de tu plan ({limit}). Actualizá el plan para invitar más integrantes.",
        )


def set_subscription_plan(db: Session, hotel_id: int, plan_code: str) -> dict:
    # Keep this compatibility entry point on the same v2 write path as the
    # active API/onboarding flows. It used to mutate HotelSubscription only.
    if plan_code not in PLAN_CATALOG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    rooms_in_use = (
        db.query(func.count())
        .select_from(Room)
        .filter(Room.hotel_id == hotel_id, Room.is_active.is_(True))
        .scalar()
    )
    if PLAN_CATALOG[plan_code]["room_limit"] < rooms_in_use and is_enforcement_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenés {rooms_in_use} habitaciones activas y el plan '{plan_code}' permite hasta {PLAN_CATALOG[plan_code]['room_limit']}.",
        )

    snapshot = change_subscription_plan(db, hotel_id, plan_code)
    plan = PLAN_CATALOG[plan_code]
    return {
        "hotel_id": hotel_id,
        "status": snapshot["status"],
        "plan": plan_code,
        "room_limit": plan["room_limit"],
        "rooms_in_use": rooms_in_use,
    }


def set_entitlement_override(db: Session, hotel_id: int, code: str, value: Any, value_type: str | None = None):
    """Create/update a hotel-specific entitlement override and return merged payload."""
    serialized, kind = _serialize_value(value, value_type)
    if code == "rooms.max_active":
        try:
            room_limit = int(value)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El límite de habitaciones debe ser entero")
        set_room_limit_override(db, hotel_id, room_limit)
    override = (
        db.query(HotelEntitlementOverride)
        .filter(HotelEntitlementOverride.hotel_id == hotel_id, HotelEntitlementOverride.code == code)
        .first()
    )
    if override:
        override.value = serialized
        override.value_type = kind
    else:
        override = HotelEntitlementOverride(hotel_id=hotel_id, code=code, value=serialized, value_type=kind)
        db.add(override)
    db.flush()
    return get_entitlements(db, hotel_id)


def delete_entitlement_override(db: Session, hotel_id: int, code: str):
    if code == "rooms.max_active":
        clear_room_limit_override(db, hotel_id)
    override = (
        db.query(HotelEntitlementOverride)
        .filter(HotelEntitlementOverride.hotel_id == hotel_id, HotelEntitlementOverride.code == code)
        .first()
    )
    if override:
        db.delete(override)
        db.flush()
    return get_entitlements(db, hotel_id)


def entitlements_payload(db: Session, hotel_id: int) -> dict:
    sub = ensure_subscription(db, hotel_id)
    entitlements = get_entitlements(db, hotel_id)
    ent_list = [
        {"code": code, "value": data.get("value"), "source": data.get("source", "plan")}
        for code, data in sorted(entitlements.items())
    ]
    return {
        "hotel_id": hotel_id,
        "plan": sub.plan.code if sub and sub.plan else None,
        "status": sub.status if sub else "inactive",
        "enforcement_enabled": is_enforcement_enabled(),
        "entitlements": ent_list,
    }
