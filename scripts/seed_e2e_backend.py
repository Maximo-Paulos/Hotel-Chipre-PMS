"""Prepare the fixed local SQLite or explicitly isolated PostgreSQL E2E database.

The safety check intentionally runs before importing Alembic or any ``app``
module.  An inherited PostgreSQL URL or any SQLite path other than the fixed
repository ``_e2e.db`` target is refused.
"""
from __future__ import annotations

import json
import hmac
import os
import re
import sys
from collections.abc import MutableMapping
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT_DIR = Path(__file__).resolve().parents[1]
E2E_DATABASE_PATH = ROOT_DIR / "_e2e.db"
E2E_DATABASE_URL = f"sqlite:///{E2E_DATABASE_PATH.as_posix()}"
E2E_POSTGRES_DATABASE_URL_EXPLICIT = "E2E_POSTGRES_DATABASE_URL_EXPLICIT"
E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT = "E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT"
E2E_POSTGRES_ISOLATED = "E2E_POSTGRES_ISOLATED"
POSTGRES_E2E_DATABASE_PREFIX = "hotel_chipre_e2e_"
POSTGRES_E2E_ROLE_PREFIX = "hotel_chipre_e2e_"
_POSTGRES_E2E_MIGRATED_DATABASES: set[str] = set()
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


class E2ESafetyError(RuntimeError):
    """Raised before any database-capable dependency is imported."""


def _enabled(value: str | None) -> bool:
    return (value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _postgres_e2e_connection(url: str, env: MutableMapping[str, str]) -> dict[str, object]:
    """Validate and decode the narrowly allowlisted loopback PostgreSQL target."""
    if not _enabled(env.get(E2E_POSTGRES_ISOLATED)):
        raise E2ESafetyError("PostgreSQL E2E requires explicit isolated-target opt-in")
    explicit_url = (env.get(E2E_POSTGRES_DATABASE_URL_EXPLICIT) or "").strip()
    if not explicit_url or not hmac.compare_digest(url.encode("utf-8"), explicit_url.encode("utf-8")):
        raise E2ESafetyError("PostgreSQL E2E requires a matching explicit database URL")

    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as exc:
        raise E2ESafetyError("PostgreSQL E2E database URL is malformed") from exc

    host = (parsed.hostname or "").casefold()
    if parsed.scheme not in {"postgresql", "postgresql+psycopg2"}:
        raise E2ESafetyError("PostgreSQL E2E requires the psycopg2 PostgreSQL driver")
    if host not in {"localhost", "127.0.0.1", "::1"} or port != 5432:
        raise E2ESafetyError("PostgreSQL E2E target must use the local PostgreSQL 16 endpoint")
    if parsed.query or parsed.fragment:
        raise E2ESafetyError("PostgreSQL E2E database URL cannot contain query or fragment")

    database = unquote(parsed.path.lstrip("/"))
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    if not re.fullmatch(r"hotel_chipre_e2e_[a-z0-9_]+", database) or database == POSTGRES_E2E_DATABASE_PREFIX:
        raise E2ESafetyError("PostgreSQL E2E requires a dedicated disposable database name")
    if not username.startswith(POSTGRES_E2E_ROLE_PREFIX) or not username.endswith(("_app_runner", "_seed_runner")):
        raise E2ESafetyError("PostgreSQL E2E requires a dedicated disposable role name")
    if not password:
        raise E2ESafetyError("PostgreSQL E2E requires a password for the disposable role")

    return {"host": host, "port": port, "dbname": database, "user": username, "password": password}


def _postgres_e2e_seed_connection(
    runtime_url: str,
    runtime_parameters: dict[str, object],
    env: MutableMapping[str, str],
) -> tuple[str, dict[str, object]]:
    """Validate the separate local role used only to load synthetic fixtures.

    The API/browser process always uses the regular app role so PostgreSQL RLS
    remains active during user flows. The seed role is a disposable local test
    role with BYPASSRLS because fixtures intentionally create system and
    cross-tenant setup rows before any request context exists.
    """
    seed_url = (env.get("E2E_POSTGRES_SEED_DATABASE_URL") or "").strip()
    explicit_seed_url = (env.get(E2E_POSTGRES_SEED_DATABASE_URL_EXPLICIT) or "").strip()
    if not seed_url or not hmac.compare_digest(seed_url.encode("utf-8"), explicit_seed_url.encode("utf-8")):
        raise E2ESafetyError("PostgreSQL E2E requires a matching explicit seed database URL")

    seed_env = dict(env)
    seed_env["DATABASE_URL"] = seed_url
    seed_env[E2E_POSTGRES_DATABASE_URL_EXPLICIT] = seed_url
    seed_parameters = _postgres_e2e_connection(seed_url, seed_env)
    expected_seed_user = str(runtime_parameters["user"]).removesuffix("_app_runner") + "_seed_runner"
    if (
        seed_url == runtime_url
        or seed_parameters["host"] != runtime_parameters["host"]
        or seed_parameters["port"] != runtime_parameters["port"]
        or seed_parameters["dbname"] != runtime_parameters["dbname"]
        or seed_parameters["user"] != expected_seed_user
    ):
        raise E2ESafetyError("PostgreSQL E2E seed role must be distinct and target the same local test database")
    return seed_url, seed_parameters


def _is_postgres_e2e_target(env: MutableMapping[str, str] | None = None) -> bool:
    target = os.environ if env is None else env
    return (target.get("DATABASE_URL") or "").startswith(("postgresql://", "postgresql+psycopg2://"))


def _assert_postgres_e2e_database_empty() -> str:
    """Refuse migrations unless the dedicated database has no user objects."""
    target = os.environ
    url = target.get("DATABASE_URL") or ""
    connection_parameters = _postgres_e2e_connection(url, target)
    import psycopg2

    try:
        connection = psycopg2.connect(**connection_parameters, connect_timeout=5)
    except Exception as exc:
        raise E2ESafetyError("isolated local PostgreSQL E2E database is not reachable") from exc
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_class AS relation
                    JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                    WHERE namespace.nspname = 'public'
                      AND relation.relkind IN ('r', 'p', 'v', 'm', 'S', 'f')
                )
                """
            )
            has_user_objects = bool(cursor.fetchone()[0])
        if has_user_objects:
            raise E2ESafetyError("PostgreSQL E2E target must be empty before migrations")
    finally:
        connection.close()
    return str(connection_parameters["dbname"])


def prepare_e2e_environment(env: MutableMapping[str, str] | None = None) -> str:
    """Validate and normalize the only database target allowed for local E2E.

    Database URLs must be explicit. Existing values are never overwritten
    before validation, so a missing or inherited production environment fails
    closed rather than being silently redirected.
    """

    target = os.environ if env is None else env
    app_env = target.get("APP_ENV")
    if app_env != "test":
        raise E2ESafetyError("local E2E requires APP_ENV=test")

    url = target.get("DATABASE_URL") or ""
    if url.startswith(("postgresql://", "postgresql+psycopg2://")):
        runtime_parameters = _postgres_e2e_connection(url, target)
        if not str(runtime_parameters["user"]).endswith("_app_runner"):
            raise E2ESafetyError("PostgreSQL E2E DATABASE_URL must use the regular app role")
        _postgres_e2e_seed_connection(url, runtime_parameters, target)
        target["APP_ENV"] = "test"
        target.setdefault("JWT_SECRET", "e2e-local-jwt-secret-change-me-32chars")
        return url
    if not url.startswith("sqlite:///") or url.startswith("sqlite://///"):
        raise E2ESafetyError("local E2E requires the fixed SQLite database or an explicitly isolated loopback PostgreSQL 16 database")
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


def reset_e2e_database() -> None:
    """Remove only the generated repository E2E database when explicitly requested."""

    if _is_postgres_e2e_target():
        prepare_e2e_environment()
        return
    if os.environ.get("E2E_RESET_DATABASE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    if E2E_DATABASE_PATH.is_symlink():
        raise E2ESafetyError("local E2E database path cannot be a symlink")
    for suffix in ("", "-wal", "-shm"):
        target = Path(f"{E2E_DATABASE_PATH}{suffix}")
        if target.exists():
            target.unlink()


def _credentials(env: MutableMapping[str, str] | None = None) -> tuple[str, str]:
    target = os.environ if env is None else env
    return (
        target.get("E2E_OWNER_EMAIL", "owner@e2e.com"),
        target.get("E2E_OWNER_PASSWORD", "E2ePass1234!"),
    )


def _role_credentials(env: MutableMapping[str, str] | None = None) -> dict[str, tuple[str, str]]:
    target = os.environ if env is None else env
    return {
        "manager": (
            target.get("E2E_MANAGER_EMAIL", "manager@e2e.com"),
            target.get("E2E_MANAGER_PASSWORD", "E2eManager1234!"),
        ),
        "receptionist": (
            target.get("E2E_RECEPTIONIST_EMAIL", "receptionist@e2e.com"),
            target.get("E2E_RECEPTIONIST_PASSWORD", "E2eReception1234!"),
        ),
        "housekeeping": (
            target.get("E2E_HOUSEKEEPING_EMAIL", "housekeeping@e2e.com"),
            target.get("E2E_HOUSEKEEPING_PASSWORD", "E2eHousekeeping1234!"),
        ),
    }


def _step_up_test_projects() -> tuple[str, ...]:
    return (
        "chromium",
        "webkit-iphone-15-business",
        "webkit-iphone-se-business",
        "webkit-iphone-15-pro-max-business",
    )


def run_migrations() -> None:
    database_url = prepare_e2e_environment()
    if database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        database_name = _assert_postgres_e2e_database_empty()
    else:
        database_name = ""
    print("Running local E2E database migrations", file=sys.stderr, flush=True)
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT_DIR / "alembic"))
    config.set_main_option("prepend_sys_path", str(ROOT_DIR))
    command.upgrade(config, "head")
    if database_name:
        runtime_parameters = _postgres_e2e_connection(os.environ["DATABASE_URL"], os.environ)
        _, seed_parameters = _postgres_e2e_seed_connection(
            os.environ["DATABASE_URL"], runtime_parameters, os.environ
        )
        seed_role = str(seed_parameters["user"])
        if not re.fullmatch(r"hotel_chipre_e2e_[a-z0-9_]+_seed_runner", seed_role):
            raise E2ESafetyError("PostgreSQL E2E seed role name is invalid")
        import psycopg2

        try:
            with psycopg2.connect(**runtime_parameters, connect_timeout=5) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{seed_role}"')
                    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{seed_role}"')
                    cursor.execute(f'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO "{seed_role}"')
        except Exception:
            raise E2ESafetyError("could not grant disposable local seed-role access to migrated E2E tables") from None
        _POSTGRES_E2E_MIGRATED_DATABASES.add(database_name)


def upsert_seed_data() -> None:
    database_url = prepare_e2e_environment()
    seed_engine = None
    if database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        runtime_parameters = _postgres_e2e_connection(database_url, os.environ)
        _, seed_parameters = _postgres_e2e_seed_connection(database_url, runtime_parameters, os.environ)
        database_name = str(runtime_parameters["dbname"])
        if database_name not in _POSTGRES_E2E_MIGRATED_DATABASES:
            raise E2ESafetyError("PostgreSQL E2E seed requires fresh migrations in this process")
        from app.database import get_engine
        from sqlalchemy import text
        from sqlalchemy.orm import sessionmaker

        seed_engine = get_engine(str(os.environ["E2E_POSTGRES_SEED_DATABASE_URL"]))
        with seed_engine.connect() as connection:
            bypasses_rls = connection.execute(
                text("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            ).scalar_one_or_none()
        if bypasses_rls is not True:
            seed_engine.dispose()
            raise E2ESafetyError("PostgreSQL E2E seed role must be a dedicated local BYPASSRLS fixture role")
        session_factory = sessionmaker(autocommit=False, autoflush=False, bind=seed_engine)
    else:
        from app.database import get_session_factory, init_db

        init_db(database_url)
        session_factory = get_session_factory()
    owner_email, owner_password = _credentials()
    role_credentials = _role_credentials()

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
        Subscription,
        User,
        UserMfaSecret,
    )
    from app.services.mfa_service import MFA_ACTIVE, encrypt_totp_secret
    from app.services.security import hash_password

    with session_factory() as db:
        now = datetime.now(timezone.utc)

        hotel = db.get(HotelConfiguration, 1)
        if hotel is None:
            hotel = HotelConfiguration(id=1)
            db.add(hotel)
        hotel.hotel_name = "Hotel Chipre E2E con un nombre operacionalmente largo"
        hotel.owner_email = owner_email
        hotel.subscription_active = True
        hotel.default_currency = "ARS"
        hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
        hotel.enable_bank_transfer = True
        hotel.updated_at = now

        subscription = db.query(Subscription).filter(Subscription.hotel_id == 1).first()
        if subscription is None:
            subscription = Subscription(hotel_id=1)
            db.add(subscription)
        subscription.plan = "pro"
        subscription.status = "active"
        subscription.room_limit = 40
        subscription.staff_limit = 8
        subscription.can_write_cache = True
        subscription.updated_at = now

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

        # Keep the normal owner fixture MFA-free for broad UI journeys. Give
        # each MFA-sensitive E2E flow and Playwright project a separate owner
        # so concurrent workers cannot race the same TOTP replay counter.
        step_up_password = os.environ.get("E2E_STEP_UP_OWNER_PASSWORD", "E2eStepUp1234!")
        step_up_secret = os.environ.get(
            "E2E_STEP_UP_OWNER_TOTP_SECRET",
            "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP",
        )
        for purpose in ("cash", "cash-business", "rbac", "rbac-info", "rate-policy"):
            for project_name in _step_up_test_projects():
                step_up_email = f"owner-stepup-{purpose}+{project_name}@e2e.com"
                step_up_user = db.query(User).filter(User.email.ilike(step_up_email)).first()
                if step_up_user is None:
                    step_up_user = User(email=step_up_email)
                    db.add(step_up_user)
                step_up_user.password_hash = hash_password(step_up_password)
                step_up_user.is_active = True
                step_up_user.is_verified = True
                step_up_user.role = "owner"
                db.flush()

                step_up_membership = (
                    db.query(HotelMembership)
                    .filter(HotelMembership.hotel_id == 1, HotelMembership.user_id == step_up_user.id)
                    .first()
                )
                if step_up_membership is None:
                    step_up_membership = HotelMembership(hotel_id=1, user_id=step_up_user.id)
                    db.add(step_up_membership)
                step_up_membership.role = "owner"
                step_up_membership.status = "active"

                step_up_mfa = db.query(UserMfaSecret).filter(UserMfaSecret.user_id == step_up_user.id).first()
                if step_up_mfa is None:
                    step_up_mfa = UserMfaSecret(user_id=step_up_user.id, encrypted_secret="")
                    db.add(step_up_mfa)
                step_up_mfa.encrypted_secret = encrypt_totp_secret(step_up_secret)
                step_up_mfa.status = MFA_ACTIVE
                step_up_mfa.confirmed_at = step_up_mfa.confirmed_at or now

        staff_members = [{"name": "Owner E2E", "email": owner_email, "role": "owner"}]
        for role, (email, password) in role_credentials.items():
            staff_user = db.query(User).filter(User.email.ilike(email)).first()
            if staff_user is None:
                staff_user = User(email=email)
                db.add(staff_user)
            staff_user.password_hash = hash_password(password)
            staff_user.is_active = True
            staff_user.is_verified = True
            staff_user.role = role
            db.flush()

            staff_membership = (
                db.query(HotelMembership)
                .filter(HotelMembership.hotel_id == 1, HotelMembership.user_id == staff_user.id)
                .first()
            )
            if staff_membership is None:
                staff_membership = HotelMembership(hotel_id=1, user_id=staff_user.id)
                db.add(staff_membership)
            staff_membership.role = role
            staff_membership.status = "active"
            staff_members.append({"name": role.title(), "email": email, "role": role})

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
        onboarding.staff_json = json.dumps(staff_members)
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

        # The master panel refuses to operate without TOTP (TECH-0023). Enroll
        # the bootstrap master admin with a fixed test secret so Playwright can
        # compute codes; the enrollment flow itself is covered by
        # tests/test_master_admin_panel.py.
        master_email = os.environ.get("MASTER_ADMIN_EMAIL", "").strip().lower()
        master_password = os.environ.get("MASTER_ADMIN_PASSWORD", "")
        master_totp_secret = os.environ.get("E2E_MASTER_ADMIN_TOTP_SECRET", "")
        if master_email and master_password and master_totp_secret:
            master = db.query(User).filter(User.email.ilike(master_email)).first()
            if master is None:
                master = User(email=master_email)
                db.add(master)
            master.password_hash = hash_password(master_password)
            master.is_active = True
            master.is_verified = True
            master.role = "platform_admin"
            db.flush()
            master_mfa = db.query(UserMfaSecret).filter(UserMfaSecret.user_id == master.id).first()
            if master_mfa is None:
                master_mfa = UserMfaSecret(user_id=master.id, encrypted_secret="")
                db.add(master_mfa)
            master_mfa.encrypted_secret = encrypt_totp_secret(master_totp_secret)
            master_mfa.status = MFA_ACTIVE
            master_mfa.confirmed_at = master_mfa.confirmed_at or now

        db.commit()
    if seed_engine is not None:
        seed_engine.dispose()


def main() -> None:
    prepare_e2e_environment()
    reset_e2e_database()
    run_migrations()
    upsert_seed_data()
    print("Local E2E database ready; credentials loaded from E2E_* environment/local defaults")


if __name__ == "__main__":
    main()
