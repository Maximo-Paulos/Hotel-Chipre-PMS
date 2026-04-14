"""
Subscription status and entitlements endpoints.
"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.subscription import EntitlementOverrideRequest, EntitlementsResponse
from app.services.subscription_service import (
    delete_entitlement_override,
    entitlements_payload,
    ensure_subscription,
    set_entitlement_override,
)
from app.services.subscription_entitlements import (
    change_subscription_plan,
    get_subscription_snapshot,
    plan_catalog,
)
from app.models.room import Room

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])


@router.get("/status")
def subscription_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        snapshot = get_subscription_snapshot(db, context.hotel_id)
        rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id, Room.is_active.is_(True)).count()
        payload = {
            "hotel_id": context.hotel_id,
            "status": snapshot["status"],
            "plan": snapshot["plan"],
            "room_limit": snapshot["room_limit"],
            "staff_limit": snapshot.get("staff_limit"),
            "rooms_in_use": rooms,
            "can_write": snapshot["can_write"],
            "enforcement_enabled": snapshot["enforcement_enabled"],
            "available_plans": plan_catalog(),
            "current_period_end": snapshot.get("current_period_end"),
            "grace_until": snapshot.get("grace_until"),
            "source": "v2",
        }
        if snapshot.get("dirty"):
            db.commit()
        return payload
    except Exception:
        # Fallback defensivo para evitar bloquear UI: responder starter por defecto
        fallback_plan = {"code": "starter", "name": "Plan Inicial", "room_limit": 20, "price_month": None}
        return {
            "hotel_id": context.hotel_id,
            "status": "active",
            "plan": "starter",
            "room_limit": 20,
            "rooms_in_use": 0,
            "available_plans": [fallback_plan],
            "can_write": True,
            "enforcement_enabled": False,
            "entitlements": [{"code": "rooms.max_active", "value": 20, "source": "fallback"}],
            "source": "fallback",
        }


@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    ensure_subscription(db, context.hotel_id)  # legacy seed for entitlement overrides
    return plan_catalog()


@router.post("/plan")
def change_plan(
    plan_code: str | None = Body(default=None, embed=True),
    plan_code_query: str | None = None,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    selected_plan = plan_code or plan_code_query
    if not selected_plan:
        raise HTTPException(status_code=400, detail="plan_code requerido")

    snapshot = change_subscription_plan(db, context.hotel_id, selected_plan)
    rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id, Room.is_active.is_(True)).count()
    db.commit()
    return {
        "hotel_id": context.hotel_id,
        "status": snapshot["status"],
        "plan": snapshot["plan"],
        "room_limit": snapshot["room_limit"],
        "staff_limit": snapshot.get("staff_limit"),
        "rooms_in_use": rooms,
        "can_write": snapshot["can_write"],
        "enforcement_enabled": snapshot["enforcement_enabled"],
        "available_plans": plan_catalog(),
        "current_period_end": snapshot.get("current_period_end"),
        "grace_until": snapshot.get("grace_until"),
        "source": "v2",
    }


@router.get("/entitlements", response_model=EntitlementsResponse)
def get_entitlements(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    return entitlements_payload(db, context.hotel_id)


@router.post("/entitlements/override", response_model=EntitlementsResponse)
def upsert_entitlement_override(
    override: EntitlementOverrideRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    set_entitlement_override(db, context.hotel_id, override.code, override.value, override.value_type)
    db.commit()
    return entitlements_payload(db, context.hotel_id)


@router.delete("/entitlements/override/{code}", response_model=EntitlementsResponse)
def delete_override(
    code: str,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    delete_entitlement_override(db, context.hotel_id, code)
    db.commit()
    return entitlements_payload(db, context.hotel_id)
