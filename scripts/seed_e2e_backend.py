"""Prepare the fixed local SQLite database used by Playwright E2E tests.

The safety check intentionally runs before importing Alembic or any ``app``
module.  An inherited PostgreSQL URL or any SQLite path other than the fixed
repository ``_e2e.db`` target is refused.
"""
from __future__ import annotations

import json
import os
import sys
from collections.abc import MutableMapping
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
E2E_DATABASE_PATH = ROOT_DIR / "_e2e.db"
E2E_DATABASE_URL = f"sqlite:///{E2E_DATABASE_PATH.as_posix()}"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class E2ESafetyError(RuntimeError):
    """Raised before any database-capable dependency is imported."""


def prepare_e2e_environment(env: MutableMapping[str, str] | None = None) -> str:
    """Validate and normalize the only database target allowed for local E2E.

    Both values must be explicit. Existing values are never overwritten before
    validation, so a missing or inherited production environment fails closed
    rather than being silently redirected.
    """

    target = os.environ if env is None else env
    app_env = target.get("APP_ENV")
    if app_env != "test":
        raise E2ESafetyError("local E2E requires APP_ENV=test")

    url = target.get("DATABASE_URL") or ""
    if not url.startswith("sqlite:///") or url.startswith("sqlite://///"):
        raise E2ESafetyError("local E2E requires the fixed SQLite database")
    if "?" in url or "#" in url:
        raise E2ESafetyError("local E2E SQLite URL cannot contain query or fragment")
    raw_path = url.removeprefix("sqlite:///").replace("\\", "/")
    if not raw_path or raw_path == ":memory:":
        raise E2ESafetyError("local E2E requires a persistent SQLite file")
    if len(raw_path) >= 3 and raw_path[0] == "/" and raw_path[2] == ":":
        raw_path = raw_path[1:]
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = ROOT_DIR / db_path
    if E2E_DATABASE_PATH.is_symlink():
        raise E2ESafetyError("local E2E database path cannot be a symlink")
    if db_path.resolve(strict=False) != E2E_DATABASE_PATH.resolve(strict=False):
        raise E2ESafetyError("local E2E database path must be the repository _e2e.db")

    target["APP_ENV"] = "test"
    target["DATABASE_URL"] = E2E_DATABASE_URL
    target.setdefault("JWT_SECRET", "e2e-local-jwt-secret-change-me-32chars")
    return E2E_DATABASE_URL


def _credentials(env: MutableMapping[str, str] | None = None) -> tuple[str, str]:
    target = os.environ if env is None else env
    return (
        target.get("E2E_OWNER_EMAIL", "owner@e2e.com"),
        target.get("E2E_OWNER_PASSWORD", "E2ePass1234!"),
    )


def run_migrations() -> None:
    prepare_e2e_environment()
    print("Running local E2E database migrations", file=sys.stderr, flush=True)
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(ROOT_DIR))
    command.upgrade(config, "head")


def upsert_seed_data() -> None:
    database_url = prepare_e2e_environment()
    owner_email, owner_password = _credentials()

    from app.database import get_session_factory, init_db
    from app.models import (
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
    from app.services.security import hash_password

    init_db(database_url)
    session_factory = get_session_factory()
    with session_factory() as db:
        now = datetime.now(timezone.utc)

        hotel = db.get(HotelConfiguration, 1)
        if hotel is None:
            hotel = HotelConfiguration(id=1)
            db.add(hotel)
        hotel.hotel_name = "Hotel Chipre E2E"
        hotel.owner_email = owner_email
        hotel.subscription_active = True
        hotel.default_currency = "ARS"
        hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
        hotel.updated_at = now

        owner = db.query(User).filter(User.email.ilike(owner_email)).first()
        if owner is None:
            owner = User(email=owner_email)
            db.add(owner)
        owner.password_hash = hash_password(owner_password)
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
        onboarding.owner_email = owner_email
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
        onboarding.payment_methods_json = '{"cash": {"enabled": true}, "mercado_pago": {"enabled": false}}'
        onboarding.ota_channels_json = '{"booking": {"enabled": false}, "expedia": {"enabled": false}}'
        onboarding.subscription_choice_json = '{"plan": "pro"}'
        onboarding.staff_json = json.dumps(
            [{"name": "Owner E2E", "email": owner_email, "role": "owner"}]
        )
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
    prepare_e2e_environment()
    run_migrations()
    upsert_seed_data()
    print("Local E2E database ready; credentials loaded from E2E_* environment/local defaults")


if __name__ == "__main__":
    main()
