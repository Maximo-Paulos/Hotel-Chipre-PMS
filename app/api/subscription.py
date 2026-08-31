"""
Subscription status and entitlements endpoints.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_platform_admin, require_roles, require_roles_and_permission
from app.master_admin.security import audit_master_action
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room
from app.schemas.subscription import (
    CompedOverrideRequest,
    EntitlementOverrideRequest,
    EntitlementsResponse,
    TrialRequest,
)
from app.services.subscription_entitlements import (
    change_subscription_plan,
    get_subscription_snapshot,
    grant_comped,
    plan_catalog,
    start_trial,
)
from app.services.subscription_service import (
    delete_entitlement_override,
    entitlements_payload,
    ensure_subscription,
    get_staff_usage,
    set_entitlement_override,
)
from app.services.room_service import active_rooms
from app.services.permission_service import PERMISSION_SETTINGS_SUBSCRIPTION_VIEW

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])
admin_router = APIRouter(prefix="/api/admin/subscription", tags=["Subscription Admin"])


def _remaining_trial_days(trial_end_at) -> int | None:
    if not trial_end_at:
        return None
    delta = trial_end_at - datetime.now(timezone.utc)
    if delta.total_seconds() <= 0:
        return 0
    return max(0, delta.days + (1 if delta.seconds > 0 else 0))


def _serialize_status_payload(db: Session, hotel_id: int) -> dict:
    snapshot = get_subscription_snapshot(db, hotel_id)
    rooms = active_rooms(db, hotel_id).filter(Room.is_active.is_(True)).count()
    staff = get_staff_usage(db, hotel_id)
    payload = {
        "hotel_id": hotel_id,
        "status": snapshot["status"],
        "plan": snapshot["plan"],
        "room_limit": snapshot["room_limit"],
        "staff_limit": snapshot.get("staff_limit"),
        "rooms_in_use": rooms,
        "staff_in_use": staff,
        "can_write": snapshot["can_write"],
        "enforcement_enabled": snapshot["enforcement_enabled"],
        "available_plans": plan_catalog(),
        "current_period_end": snapshot.get("current_period_end"),
        "trial_started_at": snapshot.get("trial_started_at"),
        "trial_end_at": snapshot.get("trial_end_at"),
        "trial_remaining_days": _remaining_trial_days(snapshot.get("trial_end_at")),
        "grace_until": snapshot.get("grace_until"),
        "source": "v2",
    }
    if snapshot.get("dirty"):
        db.commit()
    return payload


@router.get("/status")
def subscription_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_roles_and_permission(PERMISSION_SETTINGS_SUBSCRIPTION_VIEW, "owner", "co_owner")
    ),
):
    try:
        return _serialize_status_payload(db, context.hotel_id)
    except Exception:
        fallback_plan = {"code": "starter", "name": "Plan Inicial", "room_limit": 15, "staff_limit": 3, "price_month": None}
        return {
            "hotel_id": context.hotel_id,
            "status": "active",
            "plan": "starter",
            "room_limit": 15,
            "staff_limit": 3,
            "rooms_in_use": 0,
            "staff_in_use": 0,
            "available_plans": [fallback_plan],
            "can_write": True,
            "enforcement_enabled": False,
            "entitlements": [{"code": "rooms.max_active", "value": 15, "source": "fallback"}],
            "source": "fallback",
        }


@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_roles_and_permission(PERMISSION_SETTINGS_SUBSCRIPTION_VIEW, "owner", "co_owner")
    ),
):
    ensure_subscription(db, context.hotel_id)
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

    change_subscription_plan(db, context.hotel_id, selected_plan)
    db.commit()
    return _serialize_status_payload(db, context.hotel_id)


@router.post("/trial")
def start_subscription_trial(
    payload: TrialRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    start_trial(
        db,
        hotel_id=context.hotel_id,
        plan_code=payload.plan_code,
        actor={"user_id": context.user_id, "user_role": context.user_role},
    )
    db.commit()
    return _serialize_status_payload(db, context.hotel_id)


@router.get("/entitlements", response_model=EntitlementsResponse)
def get_entitlements(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_roles_and_permission(PERMISSION_SETTINGS_SUBSCRIPTION_VIEW, "owner", "co_owner")
    ),
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


@admin_router.post("/comped-override")
def admin_comped_override(
    payload: CompedOverrideRequest,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_platform_admin()),
):
    if db.get(HotelConfiguration, payload.hotel_id) is None:
        raise HTTPException(status_code=404, detail="Hotel no encontrado")

    grant_comped(
        db,
        hotel_id=payload.hotel_id,
        plan_code=payload.plan_code,
        reason=payload.reason,
        actor={"user_id": context.user_id, "user_role": context.user_role},
        valid_until=payload.valid_until,
        idempotency_key=payload.idempotency_key or request.headers.get("Idempotency-Key"),
    )
    audit_master_action(
        db,
        actor_user_id=context.user_id,
        action="comped_override_grant",
        target_type="hotel",
        target_id=str(payload.hotel_id),
        metadata={
            "hotel_id": payload.hotel_id,
            "plan_code": payload.plan_code,
            "reason": payload.reason,
            **({"valid_until": payload.valid_until.isoformat()} if payload.valid_until else {}),
            **({"idempotency_key": payload.idempotency_key} if payload.idempotency_key else {}),
        },
        request=request,
    )
    db.commit()
    return _serialize_status_payload(db, payload.hotel_id)
