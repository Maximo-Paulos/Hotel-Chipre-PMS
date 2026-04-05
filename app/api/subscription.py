"""
Subscription status endpoints.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import get_auth_context, AuthContext, require_roles
from app.services.subscription_service import get_effective_room_limit
from app.models.subscription import HotelSubscription, SubscriptionPlan
from app.models.room import Room

router = APIRouter(prefix="/api/subscription", tags=["Subscription"])


@router.get("/status")
def subscription_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    sub = db.query(HotelSubscription).filter(HotelSubscription.hotel_id == context.hotel_id).first()
    limit = get_effective_room_limit(db, context.hotel_id)
    rooms = db.query(Room).filter(Room.hotel_id == context.hotel_id).count()
    plans = [
        {"code": p.code, "name": p.name, "room_limit": p.room_limit, "price_month": p.price_month}
        for p in db.query(SubscriptionPlan).all()
    ]
    return {
        "hotel_id": context.hotel_id,
        "status": sub.status if sub else "inactive",
        "plan": sub.plan.code if sub and sub.plan else None,
        "room_limit": limit,
        "rooms_in_use": rooms,
        "available_plans": plans,
    }


@router.get("/plans")
def list_plans(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    return [
        {"code": p.code, "name": p.name, "room_limit": p.room_limit, "price_month": p.price_month}
        for p in db.query(SubscriptionPlan).all()
    ]
