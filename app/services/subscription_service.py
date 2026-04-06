"""
Subscription helpers: plan lookup, room limits, status checks.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy import func

from app.models.subscription import SubscriptionPlan, HotelSubscription
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room
from app.services.hotel_service import ensure_plans_seeded


def ensure_subscription(db: Session, hotel_id: int) -> HotelSubscription:
    """Ensure a subscription record exists; create starter active if missing."""
    ensure_plans_seeded(db)
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if sub:
        return sub
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "starter").first()
    if not plan:
        plan = SubscriptionPlan(code="starter", name="Plan Inicial", room_limit=20)
        db.add(plan)
        db.flush()
    sub = HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active")
    db.add(sub)
    config = db.get(HotelConfiguration, hotel_id)
    if config:
        config.subscription_active = True
    db.flush()
    return sub


def get_effective_room_limit(db: Session, hotel_id: int) -> int:
    sub = ensure_subscription(db, hotel_id)
    if sub.room_limit_override is not None:
        return sub.room_limit_override
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    return plan.room_limit if plan else 20


def ensure_room_within_limit(db: Session, hotel_id: int):
    sub = ensure_subscription(db, hotel_id)
    if sub.status != "active":
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá tu plan para crear habitaciones.",
        )
    limit = get_effective_room_limit(db, hotel_id)
    current = db.query(func.count()).select_from(Room).filter(Room.hotel_id == hotel_id).scalar()
    if current >= limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Superás el límite de habitaciones de tu plan ({limit}). Actualizá el plan para agregar más.",
        )


def set_subscription_plan(db: Session, hotel_id: int, plan_code: str) -> dict:
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan no encontrado")

    rooms_in_use = db.query(func.count()).select_from(Room).filter(Room.hotel_id == hotel_id).scalar()
    if plan.room_limit < rooms_in_use:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tenés {rooms_in_use} habitaciones y el plan '{plan.code}' permite hasta {plan.room_limit}.",
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
