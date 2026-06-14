"""
Prepare the SQLite database used by Playwright E2E tests.

Usage:
    DATABASE_URL=sqlite:///./_e2e.db python scripts/seed_e2e_backend.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite:///./_e2e.db")
os.environ.setdefault("JWT_SECRET", "e2e-local-jwt-secret-change-me-32chars")


def normalize_sqlite_url() -> None:
    url = os.environ["DATABASE_URL"]
    if not url.startswith("sqlite:///"):
        return
    raw_path = url.replace("sqlite:///", "", 1).replace("\\", "/")
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    if not db_path.parent.exists():
        db_path = ROOT_DIR / "_e2e.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve().as_posix()}"

from app.database import get_session_factory, init_db  # noqa: E402
from app.models import (  # noqa: E402
    CategoryPricing,
    Guest,
    GuestTag,
    HotelConfiguration,
    HotelMembership,
    IntegrationCatalog,
    OnboardingState,
    Room,
    RoomCategory,
    StockItem,
    StockLocation,
    User,
)
from app.services.security import hash_password  # noqa: E402


OWNER_EMAIL = "owner@e2e.com"
OWNER_PASSWORD = "E2ePass1234!"


def run_migrations() -> None:
    normalize_sqlite_url()
    print(f"Running alembic with DATABASE_URL={os.environ['DATABASE_URL']}", file=sys.stderr, flush=True)
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(ROOT_DIR))
    command.upgrade(config, "head")


def upsert_seed_data() -> None:
    normalize_sqlite_url()
    init_db(os.environ["DATABASE_URL"])
    session_factory = get_session_factory()
    with session_factory() as db:
        now = datetime.now(timezone.utc)

        hotel = db.get(HotelConfiguration, 1)
        if hotel is None:
            hotel = HotelConfiguration(id=1)
            db.add(hotel)
        hotel.hotel_name = "Hotel Chipre E2E"
        hotel.owner_email = OWNER_EMAIL
        hotel.subscription_active = True
        hotel.default_currency = "ARS"
        hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
        hotel.updated_at = now

        owner = db.query(User).filter(User.email.ilike(OWNER_EMAIL)).first()
        if owner is None:
            owner = User(email=OWNER_EMAIL)
            db.add(owner)
        owner.password_hash = hash_password(OWNER_PASSWORD)
        owner.is_active = True
        owner.is_verified = True
        owner.role = "owner"

        db.flush()

        membership = (
            db.query(HotelMembership)
            .filter(HotelMembership.hotel_id == 1, HotelMembership.user_id == owner.id)
            .first()
        )
        if membership is None:
            membership = HotelMembership(hotel_id=1, user_id=owner.id)
            db.add(membership)
        membership.role = "owner"
        membership.status = "active"

        onboarding = db.get(OnboardingState, 1)
        if onboarding is None:
            onboarding = OnboardingState(hotel_id=1)
            db.add(onboarding)
        onboarding.owner_name = "Owner E2E"
        onboarding.owner_email = OWNER_EMAIL
        onboarding.owner_phone = "1111111111"
        onboarding.owner_role = "owner"
        onboarding.identity_set = True
        onboarding.policy_set = True
        onboarding.payments_set = True
        onboarding.ota_set = True
        onboarding.subscription_set = True
        onboarding.finished = True
        # completed status requires the JSON payloads present (not just the flags)
        onboarding.hotel_identity_json = '{"name": "Hotel E2E", "address": "Calle 1", "city": "BA", "country": "AR"}'
        onboarding.deposit_policy_json = '{"deposit_percentage": 30, "enable_full_payment": true}'
        onboarding.payment_methods_json = '{"cash": {"enabled": true}, "mercado_pago": {"enabled": true, "credentials": {"access_token": "TEST-TOKEN"}}}'
        onboarding.ota_channels_json = '{"booking": {"enabled": false}, "expedia": {"enabled": false}}'
        onboarding.subscription_choice_json = '{"plan": "pro"}'
        onboarding.staff_json = '[{"name": "Owner E2E", "email": "owner@e2e.com", "role": "owner"}]'
        onboarding.updated_at = now

        category = (
            db.query(RoomCategory)
            .filter(RoomCategory.hotel_id == 1, RoomCategory.code == "STD")
            .first()
        )
        if category is None:
            category = RoomCategory(
                hotel_id=1,
                code="STD",
                name="Standard E2E",
                base_price_per_night=100,
                max_occupancy=2,
            )
            db.add(category)
            db.flush()

        if db.get(CategoryPricing, category.id) is None:
            db.add(CategoryPricing(category_id=category.id, price_cash=100))

        for number in ("101", "102"):
            room = db.query(Room).filter(Room.hotel_id == 1, Room.room_number == number).first()
            if room is None:
                db.add(
                    Room(
                        hotel_id=1,
                        room_number=number,
                        floor=1,
                        category_id=category.id,
                        status="available",
                        is_active=True,
                    )
                )

        guest = (
            db.query(Guest)
            .filter(Guest.hotel_id == 1, Guest.document_type == "DNI", Guest.document_number == "E2E-1")
            .first()
        )
        if guest is None:
            guest = Guest(
                hotel_id=1,
                first_name="Huesped",
                last_name="E2E",
                document_type="DNI",
                document_number="E2E-1",
                email="guest@e2e.com",
                phone="1111111111",
                terms_accepted=True,
            )
            db.add(guest)
            db.flush()

        if not db.query(GuestTag).filter(GuestTag.hotel_id == 1, GuestTag.guest_id == guest.id).first():
            db.add(
                GuestTag(
                    hotel_id=1,
                    guest_id=guest.id,
                    tag_type="vip",
                    note="Seed E2E",
                    created_by_user_id=owner.id,
                )
            )

        if not db.query(StockLocation).filter(StockLocation.hotel_id == 1, StockLocation.name == "Deposito").first():
            db.add(StockLocation(hotel_id=1, name="Deposito"))
        if not db.query(StockItem).filter(StockItem.hotel_id == 1, StockItem.name == "Toallas").first():
            db.add(StockItem(hotel_id=1, name="Toallas", sku="TOW-E2E", unit="unidad", min_quantity=5))

        for provider, display_name, auth_type in (
            ("whatsapp", "WhatsApp Business", "token"),
            ("booking", "Booking.com", "credentials"),
            ("expedia", "Expedia", "credentials"),
        ):
            integration = db.query(IntegrationCatalog).filter(IntegrationCatalog.provider == provider).first()
            if integration is None:
                db.add(IntegrationCatalog(provider=provider, display_name=display_name, auth_type=auth_type))

        db.commit()


def main() -> None:
    run_migrations()
    upsert_seed_data()
    print(f"E2E database ready at {os.environ['DATABASE_URL']} ({OWNER_EMAIL} / {OWNER_PASSWORD})")


if __name__ == "__main__":
    main()
