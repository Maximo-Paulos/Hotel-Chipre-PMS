"""
Pytest configuration and fixtures.
Uses an in-memory SQLite database for isolated, fast testing.
"""
import os
import re as _re
import pathlib as _pathlib

# The broad regression suite retains synchronous materialization assertions.
# Queue-specific tests opt out explicitly; production defaults to deferred SQL.
os.environ["ANALYTICS_FACTS_SYNC_ON_WRITE"] = "true"

from tests.postgres_test_safety import (
    PostgresTargetSafetyError,
    validate_postgres_test_target,
)

# ── Auto-derive DATABASE_URL_TEST (must happen before any test module loads) ──
# Priority: explicit env var > DATABASE_URL from .env with /postgres → /hotel_chipre_test.
# IMPORTANT: parse .env manually — do NOT load_dotenv() it. Exporting the full .env
# (production DATABASE_URL, GEMMA_*, JWT_SECRET...) changes app behavior under test.
def _derive_pg_test_dsn() -> str:
    prod_url = os.environ.get("DATABASE_URL", "")
    if not prod_url:
        search = _pathlib.Path(__file__).resolve()
        for _ in range(6):
            search = search.parent
            env_file = search / ".env"
            if env_file.exists():
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("DATABASE_URL="):
                        prod_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
                break
    if prod_url.startswith("postgresql"):
        derived = _re.sub(r"/postgres(\?.*)?$", "/hotel_chipre_test", prod_url)
        if derived != prod_url:
            return derived
    return ""


if not os.environ.get("DATABASE_URL_TEST"):
    _dsn = _derive_pg_test_dsn()
    if _dsn:
        os.environ["DATABASE_URL_TEST"] = _dsn

# The application intentionally loads .env in normal runtime.  Pytest owns its
# configuration instead, so make every Settings instance created by this test
# process use only explicit test values and process environment overrides.
# This runs before importing modules that call get_settings().
from app.config import Settings

Settings.model_config["env_file"] = None

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine, event, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker, Session

from app.database import Base


@pytest.fixture(autouse=True)
def _reject_unqualified_postgres_locks_over_outer_joins():
    """Catch PostgreSQL-invalid ORM locks even when the test DB is SQLite."""

    def _guard(orm_execute_state):
        statement = orm_execute_state.statement
        for_update = getattr(statement, "_for_update_arg", None)
        if for_update is None or for_update.of:
            return

        sql = str(statement.compile(dialect=postgresql.dialect()))
        if "LEFT OUTER JOIN" in sql.upper():
            pytest.fail(
                "PostgreSQL rejects FOR UPDATE without OF over nullable outer joins; "
                f"target a concrete model with lock_query(...): {sql}"
            )

    event.listen(Session, "do_orm_execute", _guard)
    try:
        yield
    finally:
        event.remove(Session, "do_orm_execute", _guard)


@pytest.fixture(autouse=True)
def _reset_durable_realtime_publish_cooldown(monkeypatch):
    """Keep the process-local delivery circuit independent between tests."""
    from app.services import domain_events

    monkeypatch.setattr(
        domain_events,
        "_outbox_publish_cooldown",
        domain_events._OutboxPublishCooldown(),
    )


# ── PostgreSQL fixtures (available when DATABASE_URL_TEST resolves to PG) ──

_PG_DSN = os.environ.get("DATABASE_URL_TEST", "")


def _validated_pg_dsn_or_skip() -> str:
    if not _PG_DSN or not _PG_DSN.startswith("postgresql"):
        pytest.skip("PostgreSQL test target is not configured")
    try:
        return validate_postgres_test_target(_PG_DSN, os.environ)
    except PostgresTargetSafetyError:
        pytest.skip("PostgreSQL test target is not explicitly proven isolated")


@pytest.fixture(scope="session")
def pg_engine():
    safe_dsn = _validated_pg_dsn_or_skip()
    engine = create_engine(safe_dsn, echo=False)
    try:
        Base.metadata.create_all(engine)
        yield engine
        # Refuse teardown mutations if the explicit provider evidence changed
        # while the session was running. Leaving disposable QA objects behind
        # is safer than dropping against an unproven target.
        validate_postgres_test_target(safe_dsn, os.environ)
        Base.metadata.drop_all(engine)
    finally:
        engine.dispose()


@pytest.fixture()
def pg_session(pg_engine):
    connection = pg_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(autouse=True)
def _stub_transactional_auth_email(request, monkeypatch):
    """No real mail transport in tests — stub auth email senders.

    Endpoints raise 503 (MasterEmailConnectionError) in production when mail is down;
    that production path is intentionally exercised by test_auth_security.py, which is
    excluded here so its 503 assertions still hold.
    """
    if request.node.path.name == "test_auth_security.py":
        yield
        return
    monkeypatch.setattr("app.api.auth.send_verification_email", lambda *a, **k: True)
    monkeypatch.setattr("app.api.auth.send_verification_success_email", lambda *a, **k: True)
    monkeypatch.setattr("app.api.auth.send_reset_password_email", lambda *a, **k: True)
    monkeypatch.setattr("app.api.auth.send_generic_auth_notice_email", lambda *a, **k: True)
    yield
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.guest import Guest, GuestCompanion, DocumentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum, ReservationSourceEnum
from app.models.transaction import Transaction
from app.models.hotel_config import HotelConfiguration
from app.models.ota import OTAReservationMapping
from app.models.pricing import CategoryPricing
from app.models.security_token import SecurityToken
from app.models.rate_limit_event import RateLimitEvent
from app.models.commercial import TaxPolicy


# â”€â”€ SQLite in-memory engine for tests â”€â”€

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def _isolate_object_storage(tmp_path, monkeypatch):
    """Route every test's object storage (payment proofs, analytics exports)
    to a per-test tmp dir instead of the real ./var/object-storage default,
    so the test suite never writes disposable files under the repo.

    get_settings() is lru_cache'd, so the env var alone is not enough --
    cache_clear() on both sides is required (same pattern as
    test_auth_security.py's _enable_mocked_auth_providers).
    """
    from app.config import get_settings

    monkeypatch.setenv("OBJECT_STORAGE_LOCAL_DIR", str(tmp_path / "object-storage"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _reset_permission_seed_cache():
    """A1: permission_service seeds the matrix once per DB engine, not per
    request. Each test's engine is a brand new object already, so this is
    just defensive cleanup against any long-lived/session-scoped engine
    reusing stale seeded state across tests.
    """
    from app.services.permission_service import reset_permission_seed_cache

    reset_permission_seed_cache()
    yield
    reset_permission_seed_cache()


@pytest.fixture(scope="function")
def db_engine():
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Ensure all mapped tables (including CategoryPricing) exist for tests
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db(db_engine) -> Session:
    """Provide a transactional database session for each test."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


_TEST_PENDING_HOTELS_KEY = "test_hotels_needing_explicit_zero_tax_policy"


def _remember_test_hotels(session, _flush_context, _instances):
    """Give synthetic hotels an explicit baseline policy and track their IDs.

    Production-created hotels remain unconfirmed until an owner saves the
    hotel's deposit and cancellation rules. Legacy tests that create hotels
    without specifying a policy need an explicit synthetic setup to exercise
    reservation flows; tests for the missing-policy gate pass False directly.
    """
    new_hotel_ids = set()
    for hotel in session.new:
        if not isinstance(hotel, HotelConfiguration):
            continue
        if hotel.deposit_policy_configured is None:
            hotel.deposit_percentage = 30.0 if hotel.deposit_percentage is None else hotel.deposit_percentage
            hotel.free_cancellation_hours = (
                48 if hotel.free_cancellation_hours is None else hotel.free_cancellation_hours
            )
            hotel.cancellation_penalty_percentage = (
                0.0
                if hotel.cancellation_penalty_percentage is None
                else hotel.cancellation_penalty_percentage
            )
            hotel.deposit_policy_configured = True
        if hotel.id is not None:
            new_hotel_ids.add(hotel.id)
    session.info[_TEST_PENDING_HOTELS_KEY] = {
        *session.info.get(_TEST_PENDING_HOTELS_KEY, set()),
        *new_hotel_ids,
    }


def _insert_explicit_zero_tax_test_policies(session, _flush_context):
    """Give legacy test hotels an explicit no-tax setup after the parent row exists.

    Production intentionally has no implicit tax-policy default. The shared
    pytest process uses this synthetic policy for hotels inserted by all test
    sessions, including module-local clients. Missing-policy tests delete it.
    """
    hotel_ids = session.info.pop(_TEST_PENDING_HOTELS_KEY, set())
    if not hotel_ids:
        return
    connection = session.connection()
    if not connection.dialect.has_table(connection, TaxPolicy.__tablename__):
        return
    for hotel_id in hotel_ids:
        existing_policy = connection.execute(
            select(TaxPolicy.id).where(TaxPolicy.hotel_id == hotel_id).limit(1)
        ).first()
        if existing_policy is None:
            connection.execute(
                TaxPolicy.__table__.insert().values(
                    hotel_id=hotel_id,
                    code="TEST_NO_TAX",
                    name="Explicit zero-tax test policy",
                    taxes_included=True,
                    apply_vat_by_default=False,
                    vat_rate=0.0,
                    foreign_guest_tax_exempt=False,
                    is_active=True,
                )
            )


event.listen(Session, "before_flush", _remember_test_hotels)
event.listen(Session, "after_flush_postexec", _insert_explicit_zero_tax_test_policies)


@pytest.fixture(autouse=True)
def _clear_process_local_read_model_cache():
    """Keep tests isolated from cached reports produced by earlier fixtures."""
    from app.services import read_model_cache

    def clear_cache():
        with read_model_cache._local_read_model_lock:
            read_model_cache._local_read_model_cache.clear()
            read_model_cache._local_read_model_inflight.clear()

    clear_cache()
    yield
    clear_cache()


# â”€â”€ Seed data fixtures â”€â”€

@pytest.fixture
def sample_categories(db: Session) -> list[RoomCategory]:
    """Create sample room categories for hotel 1."""
    # Ensure hotel configuration exists for FK integrity
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()
    if config is None:
        config = HotelConfiguration(
            id=1,
            deposit_percentage=30.0,
            deposit_policy_configured=True,
            enable_full_payment=True,
            enable_deposit_payment=True,
            enable_cash=True,
            enable_mercado_pago=True,
            enable_paypal=True,
            enable_credit_card=True,
            enable_debit_card=True,
            subscription_active=True,
        )
        db.add(config)
        db.flush()
    else:
        config.deposit_policy_configured = True
    _ensure_explicit_zero_tax_policy(db, hotel_id=1)

    categories = [
        RoomCategory(
            name="Standard Double",
            code="STD_DBL",
            base_price_per_night=100.0,
            max_occupancy=2,
            description="Standard room with double bed",
            hotel_id=1,
        ),
        RoomCategory(
            name="Superior Double",
            code="SUP_DBL",
            base_price_per_night=150.0,
            max_occupancy=3,
            description="Superior room with king bed and city view",
            hotel_id=1,
        ),
        RoomCategory(
            name="Suite Premium",
            code="SUITE_P",
            base_price_per_night=250.0,
            max_occupancy=4,
            description="Premium suite with living area and balcony",
            hotel_id=1,
        ),
    ]
    db.add_all(categories)
    db.flush()
    return categories


@pytest.fixture
def sample_categories_hotel2(db: Session) -> list[RoomCategory]:
    """Minimal categories for a second hotel to verify isolation."""
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == 2).first()
    if config is None:
        db.add(
            HotelConfiguration(
                id=2,
                deposit_percentage=20.0,
                deposit_policy_configured=True,
                subscription_active=True,
            )
        )
        db.flush()
    else:
        config.deposit_policy_configured = True
    _ensure_explicit_zero_tax_policy(db, hotel_id=2)

    cats = [
        RoomCategory(
            name="Standard H2",
            code="STD_H2",
            base_price_per_night=80.0,
            max_occupancy=2,
            description="Standard room hotel 2",
            hotel_id=2,
        ),
        RoomCategory(
            name="Suite H2",
            code="STE_H2",
            base_price_per_night=180.0,
            max_occupancy=4,
            description="Suite hotel 2",
            hotel_id=2,
        ),
    ]
    db.add_all(cats)
    db.flush()
    return cats


@pytest.fixture
def sample_rooms(db: Session, sample_categories: list[RoomCategory]) -> list[Room]:
    """Create the 38-room hotel layout for hotel 1."""
    rooms = []
    cat_std = sample_categories[0]  # STD_DBL
    cat_sup = sample_categories[1]  # SUP_DBL
    cat_suite = sample_categories[2]  # SUITE_P

    # Floor 1: 10 Standard rooms (101-110)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"1{i:02d}",
            floor=1,
            category_id=cat_std.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    # Floor 2: 10 Standard rooms (201-210)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"2{i:02d}",
            floor=2,
            category_id=cat_std.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    # Floor 3: 10 Superior rooms (301-310)
    for i in range(1, 11):
        rooms.append(Room(
            room_number=f"3{i:02d}",
            floor=3,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    # Floor 4: 5 Superior rooms (401-405) + 3 Suites (406-408)
    for i in range(1, 6):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_sup.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))
    for i in range(6, 9):
        rooms.append(Room(
            room_number=f"4{i:02d}",
            floor=4,
            category_id=cat_suite.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        ))

    db.add_all(rooms)
    db.flush()
    assert len(rooms) == 38
    return rooms


@pytest.fixture
def sample_rooms_hotel2(db: Session, sample_categories_hotel2: list[RoomCategory]) -> list[Room]:
    """Create a small room layout for hotel 2 to test multi-hotel isolation."""
    rooms = [
        Room(room_number="201", floor=2, category_id=sample_categories_hotel2[0].id, status=RoomStatusEnum.AVAILABLE, hotel_id=2),
        Room(room_number="202", floor=2, category_id=sample_categories_hotel2[1].id, status=RoomStatusEnum.AVAILABLE, hotel_id=2),
    ]
    db.add_all(rooms)
    db.flush()
    return rooms


@pytest.fixture
def sample_guest(db: Session) -> Guest:
    """Create a sample guest with full check-in data."""
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first():
        db.add(HotelConfiguration(id=1, deposit_policy_configured=True, subscription_active=True))
        db.flush()
    guest = Guest(
        first_name="Carlos",
        last_name="Pérez",
        document_type=DocumentTypeEnum.DNI,
        document_number="30456789",
        nationality="Argentina",
        date_of_birth=date(1990, 4, 12),
        email="carlos@email.com",
        phone="+54111234567",
        birth_place="Buenos Aires",
        birth_country="Argentina",
        marital_status="single",
        occupation="Contador",
        terms_accepted=True,
        hotel_id=1,
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def sample_guest_incomplete(db: Session) -> Guest:
    """Create a guest WITHOUT identity documents (for check-in validation tests)."""
    if not db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first():
        db.add(HotelConfiguration(id=1, deposit_policy_configured=True, subscription_active=True))
        db.flush()
    guest = Guest(
        first_name="María",
        last_name="López",
        email="maria@email.com",
        terms_accepted=False,
        hotel_id=1,
        # No document_type, no document_number
    )
    db.add(guest)
    db.flush()
    return guest


@pytest.fixture
def hotel_config(db: Session) -> HotelConfiguration:
    """Create default hotel configuration."""
    existing = db.query(HotelConfiguration).filter(HotelConfiguration.id == 1).first()
    if existing:
        # Normalize to expected test defaults
        existing.deposit_percentage = 30.0
        existing.deposit_policy_configured = True
        existing.enable_full_payment = True
        existing.enable_deposit_payment = True
        existing.enable_cash = True
        existing.enable_mercado_pago = True
        existing.enable_paypal = True
        existing.enable_credit_card = True
        existing.enable_debit_card = True
        existing.require_document_for_checkin = True
        existing.require_terms_acceptance = True
        existing.subscription_active = True
        _ensure_explicit_zero_tax_policy(db, hotel_id=existing.id)
        db.flush()
        return existing

    config = HotelConfiguration(
        id=1,
        deposit_percentage=30.0,
        deposit_policy_configured=True,
        enable_full_payment=True,
        enable_deposit_payment=True,
        enable_cash=True,
        enable_mercado_pago=True,
        enable_paypal=True,
        enable_credit_card=True,
        enable_debit_card=True,
        require_document_for_checkin=True,
        require_terms_acceptance=True,
        subscription_active=True,
    )
    db.add(config)
    db.flush()
    _ensure_explicit_zero_tax_policy(db, hotel_id=config.id)
    return config


def _ensure_explicit_zero_tax_policy(db: Session, *, hotel_id: int) -> None:
    policy = (
        db.query(TaxPolicy)
        .filter(TaxPolicy.hotel_id == hotel_id, TaxPolicy.code == "TEST_NO_TAX")
        .first()
    )
    if policy is None:
        db.add(
            TaxPolicy(
                hotel_id=hotel_id,
                code="TEST_NO_TAX",
                name="Explicit zero-tax test policy",
                taxes_included=True,
                apply_vat_by_default=False,
                vat_rate=0.0,
                is_active=True,
            )
        )
        db.flush()
