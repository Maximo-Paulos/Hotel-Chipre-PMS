"""
Subscription helpers: plan lookup, room limits, status checks.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.subscription import SubscriptionPlan, HotelSubscription


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

from sqlalchemy import func
from app.models.room import Room
