"""
Subscription entitlements and enforcement helpers built on v2 tables.
Keeps legacy tables loosely in sync to avoid breaking existing flows.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.hotel_config import HotelConfiguration
from app.models.subscription import SubscriptionPlan, HotelSubscription
from app.models.subscription_v2 import Subscription, SubscriptionEvent

# Minimal catalog for the new plans
PLAN_CATALOG: Dict[str, Dict[str, Any]] = {
    "starter": {"name": "Starter", "room_limit": 20, "staff_limit": 10, "price_month": 0},
    "pro": {"name": "Pro", "room_limit": 80, "staff_limit": 30, "price_month": 49},
    "ultra": {"name": "Ultra", "room_limit": 200, "staff_limit": 80, "price_month": 99},
}

WRITE_OK_STATUSES = {"active", "trialing", "demo"}
GRACE_STATUSES = {"past_due"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _plan_defaults(plan_code: str) -> Dict[str, Any]:
    return PLAN_CATALOG.get(plan_code, PLAN_CATALOG["starter"])


def plan_catalog() -> list[Dict[str, Any]]:
    """Return the available plan catalog as a list for API responses."""
    return [
        {"code": code, **data}
        for code, data in PLAN_CATALOG.items()
    ]


def _is_enforcement_enabled() -> bool:
    settings = get_settings()
    if hasattr(settings, "SUBSCRIPTION_ENFORCEMENT"):
        return bool(getattr(settings, "SUBSCRIPTION_ENFORCEMENT"))
    return bool(getattr(settings, "SUBSCRIPTION_ENFORCEMENT_ENABLED", False))


def _compute_can_write(sub: Subscription | None, enforcement_enabled: bool) -> bool:
    if not enforcement_enabled:
        return True
    if not sub:
        return False
    if sub.status in WRITE_OK_STATUSES:
        return True
    if sub.status in GRACE_STATUSES and sub.grace_until and sub.grace_until >= _now():
        return True
    return False


def _sync_legacy_tables(db: Session, hotel_id: int, plan_code: str, room_limit: int) -> None:
    """
    Keep legacy subscription tables populated so existing checks (room limit, etc.) keep working.
    """
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    if not plan:
        plan = SubscriptionPlan(code=plan_code, name=plan_code.title(), room_limit=room_limit)
        db.add(plan)
        db.flush()

    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if not sub:
        sub = HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active", room_limit_override=room_limit)
        db.add(sub)
    else:
        sub.plan_id = plan.id
        sub.status = "active"
        sub.room_limit_override = room_limit

    config = db.get(HotelConfiguration, hotel_id)
    if config:
        config.subscription_active = True


def _record_event(db: Session, sub: Subscription, event_type: str, payload: Dict[str, Any] | None = None) -> None:
    event = SubscriptionEvent(
        subscription_id=sub.id,
        hotel_id=sub.hotel_id,
        event_type=event_type,
        payload=json.dumps(payload) if payload is not None else None,
    )
    db.add(event)


def ensure_subscription_seed(db: Session, hotel_id: int, plan_code: str = "starter", status_value: str = "active") -> Tuple[Subscription | None, bool]:
    """
    Ensure a Subscription row exists for the hotel. Returns (subscription, seeded_flag).
    Only seeds when enforcement is disabled or when the caller explicitly wants it.
    """
    sub = db.query(Subscription).filter(Subscription.hotel_id == hotel_id).first()
    if sub:
        return sub, False
    defaults = _plan_defaults(plan_code)
    sub = Subscription(
        hotel_id=hotel_id,
        plan=plan_code if plan_code in PLAN_CATALOG else "starter",
        status=status_value,
        room_limit=defaults["room_limit"],
        staff_limit=defaults["staff_limit"],
        can_write_cache=True,
    )
    db.add(sub)
    db.flush()
    _sync_legacy_tables(db, hotel_id, sub.plan, defaults["room_limit"])
    return sub, True


def get_subscription_snapshot(db: Session, hotel_id: int) -> Dict[str, Any]:
    """
    Return a normalized snapshot for API/middleware:
    plan, status, limits, can_write, and whether DB needs a commit (dirty flag).
    """
    enforcement_enabled = _is_enforcement_enabled()

    sub = db.query(Subscription).filter(Subscription.hotel_id == hotel_id).first()
    seeded = False
    if not sub and not enforcement_enabled:
        sub, seeded = ensure_subscription_seed(db, hotel_id)

    if not sub:
        defaults = _plan_defaults("starter")
        return {
            "hotel_id": hotel_id,
            "plan": "starter",
            "status": "suspended" if enforcement_enabled else "demo",
            "room_limit": defaults["room_limit"],
            "staff_limit": defaults["staff_limit"],
            "can_write": not enforcement_enabled,
            "current_period_end": None,
            "grace_until": None,
            "enforcement_enabled": enforcement_enabled,
            "dirty": False,
            "subscription": None,
        }

    defaults = _plan_defaults(sub.plan)
    room_limit = sub.room_limit or defaults["room_limit"]
    staff_limit = sub.staff_limit or defaults["staff_limit"]
    can_write = _compute_can_write(sub, enforcement_enabled)
    dirty = seeded
    if sub.can_write_cache != can_write:
        sub.can_write_cache = can_write
        dirty = True

    return {
        "hotel_id": hotel_id,
        "plan": sub.plan,
        "status": sub.status,
        "room_limit": room_limit,
        "staff_limit": staff_limit,
        "can_write": can_write,
        "current_period_end": sub.current_period_end,
        "grace_until": sub.grace_until,
        "enforcement_enabled": enforcement_enabled,
        "dirty": dirty,
        "subscription": sub,
    }


def change_subscription_plan(db: Session, hotel_id: int, plan_code: str) -> Dict[str, Any]:
    if plan_code not in PLAN_CATALOG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    sub = db.query(Subscription).filter(Subscription.hotel_id == hotel_id).first()
    if not sub:
        sub, _ = ensure_subscription_seed(db, hotel_id, plan_code=plan_code, status_value="active")
    defaults = _plan_defaults(plan_code)

    sub.plan = plan_code
    sub.status = "active"
    sub.room_limit = defaults["room_limit"]
    sub.staff_limit = defaults["staff_limit"]
    sub.grace_until = None
    sub.can_write_cache = _compute_can_write(sub, _is_enforcement_enabled())

    _sync_legacy_tables(db, hotel_id, plan_code, defaults["room_limit"])
    _record_event(db, sub, "plan_changed", {"plan": plan_code})

    snapshot = get_subscription_snapshot(db, hotel_id)
    snapshot["dirty"] = True  # reflect plan change + event
    return snapshot


def entitlements_for_hotel(db: Session, hotel_id: int) -> Dict[str, Any]:
    """Alias to expose the snapshot in a name aligned with the spec wording."""
    return get_subscription_snapshot(db, hotel_id)
