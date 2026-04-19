"""
Hotel helper utilities (ownership + bootstrap).
"""
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.subscription import SubscriptionPlan, HotelSubscription
from app.config import get_settings


def ensure_plans_seeded(db: Session):
    """Seed default plans if missing."""
    defaults = [
        ("starter", "Starter", 15),
        ("pro", "Pro", 40),
        ("ultra", "Ultra", 80),
    ]
    for code, name, limit in defaults:
        exists = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == code).first()
        if exists:
            exists.name = name
            exists.room_limit = limit
            continue
        db.add(SubscriptionPlan(code=code, name=name, room_limit=limit))

    standard = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == "standard").first()
    if standard:
        standard.name = "Standard (legacy)"
        standard.room_limit = 40
    db.flush()


def get_or_create_hotel_for_owner(db: Session, owner_email: str) -> HotelConfiguration:
    """
    Find a hotel configuration owned by the given email, or create a new one.
    Also seeds a default subscription and membership (owner).
    """
    ensure_plans_seeded(db)

    existing = (
        db.query(HotelConfiguration)
        .filter(HotelConfiguration.owner_email == owner_email)
        .order_by(HotelConfiguration.id.asc())
        .first()
    )
    if existing:
        _ensure_membership_and_subscription(db, existing.id, owner_email)
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
    _ensure_membership_and_subscription(db, hotel.id, owner_email)
    return hotel


def _ensure_membership_and_subscription(db: Session, hotel_id: int, owner_email: str):
    """Create owner membership and starter subscription if missing."""
    from app.models.user import User

    owner = db.query(User).filter(User.email.ilike(owner_email)).first()
    if owner:
        if not db.query(HotelMembership).filter(HotelMembership.hotel_id == hotel_id, HotelMembership.user_id == owner.id).first():
            db.add(HotelMembership(hotel_id=hotel_id, user_id=owner.id, role="owner", status="active"))

    settings = get_settings()
    plan_code = settings.DEFAULT_SUBSCRIPTION_PLAN
    plan = db.query(SubscriptionPlan).filter(SubscriptionPlan.code == plan_code).first()
    if plan and not db.query(HotelSubscription).filter(HotelSubscription.hotel_id == hotel_id).first():
        db.add(HotelSubscription(hotel_id=hotel_id, plan_id=plan.id, status="active"))
    db.flush()


def get_memberships_for_user(db: Session, user_id: int):
    return db.query(HotelMembership).filter(HotelMembership.user_id == user_id, HotelMembership.status == "active").all()


def ensure_all_ota_webhook_secrets(db: Session) -> int:
    """
    Ensure every hotel has webhook secrets for the OTA providers used by the app.

    This keeps startup safe if a worker expects the helper to exist, and it is
    idempotent: existing active secrets are preserved.
    """
    from app.models.ota import OTAWebhookCredential
    from app.services.ota_service import OTAIntegrationService

    created = 0
    hotels = db.query(HotelConfiguration).all()
    for hotel in hotels:
        for provider in ("booking", "expedia"):
            existing = (
                db.query(OTAWebhookCredential)
                .filter(
                    OTAWebhookCredential.hotel_id == hotel.id,
                    OTAWebhookCredential.provider == provider,
                )
                .first()
            )
            if existing:
                continue
            secret = OTAIntegrationService.generate_webhook_secret()
            OTAIntegrationService.upsert_webhook_credential(
                db,
                hotel_id=hotel.id,
                provider=provider,
                webhook_secret=secret,
                is_active=True,
            )
            created += 1
    if created:
        db.flush()
    return created
