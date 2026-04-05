"""
Hotel helper utilities (ownership + bootstrap).
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.hotel_config import HotelConfiguration


def get_or_create_hotel_for_owner(db: Session, owner_email: str) -> HotelConfiguration:
    """
    Find a hotel configuration owned by the given email, or create a new one.
    - Uses owner_email to ensure isolation per cuenta.
    - Assigns the next available hotel_id (max+1) when creating.
    """
    existing = (
        db.query(HotelConfiguration)
        .filter(HotelConfiguration.owner_email == owner_email)
        .order_by(HotelConfiguration.id.asc())
        .first()
    )
    if existing:
        return existing

    next_id = (db.query(func.max(HotelConfiguration.id)).scalar() or 0) + 1
    hotel = HotelConfiguration(
        id=next_id,
        owner_email=owner_email,
        hotel_name="Mi Hotel",
        subscription_active=True,
    )
    db.add(hotel)
    db.flush()
    return hotel
