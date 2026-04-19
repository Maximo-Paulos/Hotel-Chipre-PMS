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
from app.models.room import Room
from app.services.hotel_service import ensure_plans_seeded

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
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "starter").first()
    if not plan:
        plan = SubscriptionPlan(code="starter", name="Starter", room_limit=15)
        db.add(plan)
        db.flush()
        ensure_entitlements_seeded(db)
    sub = HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active")
    db.add(sub)
    config = db.get(HotelConfiguration, hotel_id)
    if config:
        config.subscription_active = True
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


def set_subscription_plan(db: Session, hotel_id: int, plan_code: str) -> dict:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    ensure_entitlements_seeded(db)
    rooms_in_use = (
        db.query(func.count())
        .select_from(Room)
        .filter(Room.hotel_id == hotel_id, Room.is_active.is_(True))
        .scalar()
    )
    if plan.room_limit < rooms_in_use and is_enforcement_enabled():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenés {rooms_in_use} habitaciones activas y el plan '{plan.code}' permite hasta {plan.room_limit}.",
        )

    sub = ensure_subscription(db, hotel_id)
    sub.plan_id = plan.id
    sub.status = "active"
    sub.room_limit_override = None

    config = db.get(HotelConfiguration, hotel_id)
    if config:
        config.subscription_active = True

    db.flush()
    return {
        "hotel_id": hotel_id,
        "status": sub.status,
        "plan": plan.code,
        "room_limit": plan.room_limit,
        "rooms_in_use": rooms_in_use,
    }


def set_entitlement_override(db: Session, hotel_id: int, code: str, value: Any, value_type: str | None = None):
    """Create/update a hotel-specific entitlement override and return merged payload."""
    serialized, kind = _serialize_value(value, value_type)
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
