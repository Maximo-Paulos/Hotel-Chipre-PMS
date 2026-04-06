"""
Subscription helpers: plan lookup, room limits, status checks.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from sqlalchemy import func

from app.models.subscription import SubscriptionPlan, HotelSubscription
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room


def get_effective_room_limit(db: Session, hotel_id: int) -> int:
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if not sub:
        # Default fail-safe: allow minimal rooms
        return 20
    if sub.room_limit_override is not None:
        return sub.room_limit_override
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.id == sub.plan_id).first()
    return plan.room_limit if plan else 20


def ensure_room_within_limit(db: Session, hotel_id: int):
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if not sub or sub.status != "active":
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

    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first()
    if not sub:
        sub = HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active")
        db.add(sub)
    else:
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
