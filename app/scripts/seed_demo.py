"""
Seed minimal demo data for local testing.

Usage:
    python -m app.scripts.seed_demo

It creates:
- HotelConfiguration id=1 with sensible defaults.
- Two room categories and three rooms.
- One verified owner user (email: demo@hotel.test, pass: Demo123!).
Existing data is left intact; objects are only created when missing.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import init_db, get_session_factory
from app.models import (
    HotelConfiguration,
    HotelMembership,
    RoomCategory,
    Room,
    CategoryPricing,
    OnboardingState,
    User,
)
from app.services.security import hash_password


def seed(db: Session):
    # Hotel configuration
    config = db.get(HotelConfiguration, 1)
    if not config:
        config = HotelConfiguration(
            id=1,
            deposit_percentage=30.0,
            enable_full_payment=True,
            enable_deposit_payment=True,
            enable_cash=True,
            enable_mercado_pago=False,
            enable_paypal=False,
            enable_credit_card=True,
            enable_debit_card=True,
            enable_bank_transfer=True,
            free_cancellation_hours=48,
            cancellation_penalty_percentage=50.0,
            allow_cancellation_after_checkin=False,
            enable_booking_sync=False,
            enable_expedia_sync=False,
            require_document_for_checkin=True,
            require_terms_acceptance=True,
            hotel_name="Hotel Chipre Demo",
            hotel_timezone="America/Argentina/Buenos_Aires",
            default_currency="ARS",
            extra_policies="Check-in 14:00, check-out 10:00",
            updated_at=datetime.now(timezone.utc),
        )
        db.add(config)

    # Categories
    categories = {
        "STD": {
            "name": "Standard Doble",
            "description": "Habitación doble estándar",
            "base_price_per_night": 100.0,
            "max_occupancy": 2,
        },
        "STE": {
            "name": "Suite",
            "description": "Suite con balcón",
            "base_price_per_night": 180.0,
            "max_occupancy": 4,
        },
    }
    cat_objs = {}
    for code, data in categories.items():
        cat = db.query(RoomCategory).filter_by(code=code, hotel_id=config.id).first()
        if not cat:
            cat = RoomCategory(code=code, hotel_id=config.id, **data)
            db.add(cat)
            db.flush()
        cat_objs[code] = cat
        if not db.query(CategoryPricing).filter_by(category_id=cat.id).first():
            db.add(CategoryPricing(category_id=cat.id))

    # Rooms
    rooms = [
        ("101", 1, "STD"),
        ("102", 1, "STD"),
        ("201", 2, "STE"),
    ]
    for number, floor, code in rooms:
        if not db.query(Room).filter_by(room_number=number, hotel_id=config.id).first():
            db.add(
                Room(
                    hotel_id=config.id,
                    room_number=number,
                    floor=floor,
                    category_id=cat_objs[code].id,
                    status="available",
                    is_active=True,
                )
            )

    # Demo user
    demo_email = "demo@hotel.test"
    demo_user = db.query(User).filter(User.email.ilike(demo_email)).first()
    if not demo_user:
        db.add(
            User(
                email=demo_email,
                password_hash=hash_password("Demo123!"),
                is_active=True,
                is_verified=True,
                role="owner",
            )
        )
        db.flush()
        demo_user = db.query(User).filter(User.email.ilike(demo_email)).first()

    if demo_user and not db.query(HotelMembership).filter_by(hotel_id=config.id, user_id=demo_user.id).first():
        db.add(
            HotelMembership(
                hotel_id=config.id,
                user_id=demo_user.id,
                role="owner",
                status="active",
            )
        )

    # Onboarding
    if not db.query(OnboardingState).filter_by(hotel_id=1).first():
        db.add(
            OnboardingState(
                hotel_id=1,
                owner_name="Demo Owner",
                owner_email=demo_email,
                owner_phone="01123461050",
                owner_role="owner",
                finished=True,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )

    db.commit()


def main():
    init_db()
    SessionFactory = get_session_factory()
    with SessionFactory() as db:
        seed(db)
    print("Demo data ready. User: demo@hotel.test / Demo123!")


if __name__ == "__main__":
    main()
