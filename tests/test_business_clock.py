"""Local hotel-scoped business clock API and date isolation coverage."""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.business_clock import HotelBusinessClock
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.services.timezones import hotel_business_now, hotel_today, local_today


@pytest.fixture
def local_clock_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'clock-gate-only.db'}")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_ENABLED", "true")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_HOTEL_ID", "1")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def business_clock_api():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    user = User(
        email="business-clock-owner@example.test",
        password_hash="synthetic-test-hash",
        role="owner",
        is_verified=True,
    )
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_timezone="America/Argentina/Buenos_Aires"),
            HotelConfiguration(id=2, hotel_timezone="America/Montevideo"),
            user,
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelBusinessClock(
                hotel_id=1,
                business_date=date(2041, 7, 8),
                advanced_at=datetime.now(timezone.utc),
                advanced_by_user_id=user.id,
            ),
            HotelBusinessClock(
                hotel_id=2,
                business_date=date(2042, 8, 9),
                advanced_at=datetime.now(timezone.utc),
                advanced_by_user_id=user.id,
            ),
        ]
    )
    db.commit()

    context = {"hotel_id": 1, "user_id": user.id, "user_role": "owner"}

    def override_get_db():
        yield db

    def override_auth_context():
        return AuthContext(
            hotel_id=context["hotel_id"],
            user_id=context["user_id"],
            user_email=user.email,
            user_role=context["user_role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth_context
    client = TestClient(fastapi_app)
    try:
        yield client, db, context
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_business_clock_read_is_available_to_members_and_scoped_to_selected_hotel(
    business_clock_api, local_clock_enabled
):
    client, _db, context = business_clock_api

    for role in ("owner", "co_owner", "manager", "receptionist", "housekeeping"):
        context["user_role"] = role
        response = client.get("/api/config/business-clock")
        assert response.status_code == 200, response.text
        assert response.json() == {
            "hotel_id": 1,
            "business_date": "2041-07-08",
            "hotel_timezone": "America/Argentina/Buenos_Aires",
            "simulation_enabled": True,
        }

    context.update(hotel_id=2, user_role="owner")
    other_hotel = client.get("/api/config/business-clock")
    assert other_hotel.status_code == 200, other_hotel.text
    assert other_hotel.json() == {
        "hotel_id": 2,
        "business_date": local_today("America/Montevideo").isoformat(),
        "hotel_timezone": "America/Montevideo",
        "simulation_enabled": False,
    }


def test_hotel_business_now_uses_simulated_date_and_real_local_time_only_for_selected_hotel(
    business_clock_api, local_clock_enabled, monkeypatch
):
    _client, db, _context = business_clock_api

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 17, 21, 30, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value

    monkeypatch.setattr("app.services.timezones.datetime", FixedDateTime)

    selected_hotel_now = hotel_business_now(db, 1)
    selected_hotel_local = selected_hotel_now.astimezone(ZoneInfo("America/Argentina/Buenos_Aires"))
    assert selected_hotel_local.date() == date(2041, 7, 8)
    assert selected_hotel_local.strftime("%H:%M:%S") == "18:30:12"

    other_hotel_now = hotel_business_now(db, 2)
    assert other_hotel_now == FixedDateTime(2026, 10, 17, 21, 30, 12, tzinfo=timezone.utc)


def test_business_clock_read_requires_auth_context(business_clock_api):
    client, _db, _context = business_clock_api
    fastapi_app.dependency_overrides.pop(get_auth_context)

    response = client.get("/api/config/business-clock")

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("app_env", "clock_flag", "database_url"),
    [
        ("development", "false", "sqlite:///local.db"),
        ("production", "true", "sqlite:///local.db"),
        ("development", "true", "postgresql://localhost/hotel"),
    ],
)
def test_disabled_or_production_clock_uses_real_hotel_date_and_cannot_advance(
    business_clock_api, local_clock_enabled, monkeypatch, app_env, clock_flag, database_url
):
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_ENABLED", clock_flag)
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    client, db, _context = business_clock_api

    response = client.get("/api/config/business-clock")
    assert response.status_code == 200, response.text
    assert response.json()["simulation_enabled"] is False
    assert response.json()["business_date"] == local_today("America/Argentina/Buenos_Aires").isoformat()

    before_dates = db.query(HotelBusinessClock).filter_by(hotel_id=1).one().business_date
    denied = client.post("/api/config/business-clock/advance")
    assert denied.status_code == 404
    assert db.query(HotelBusinessClock).filter_by(hotel_id=1).one().business_date == before_dates


def test_business_clock_is_disabled_when_external_effects_are_enabled(
    business_clock_api, local_clock_enabled, monkeypatch
):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    get_settings.cache_clear()
    client, db, _context = business_clock_api

    response = client.get("/api/config/business-clock")
    assert response.status_code == 200, response.text
    assert response.json()["simulation_enabled"] is False

    before_date = db.query(HotelBusinessClock).filter_by(hotel_id=1).one().business_date
    denied = client.post("/api/config/business-clock/advance")
    assert denied.status_code == 404
    assert db.query(HotelBusinessClock).filter_by(hotel_id=1).one().business_date == before_date


def test_business_clock_is_disabled_without_explicit_external_effects_configuration(monkeypatch):
    settings = SimpleNamespace(
        APP_ENV="development",
        model_fields_set={"APP_ENV", "LOCAL_SIMULATION_CLOCK_ENABLED"},
        LOCAL_SIMULATION_CLOCK_ENABLED=True,
        LOCAL_SIMULATION_CLOCK_HOTEL_ID=1,
        EXTERNAL_EFFECTS_ENABLED=None,
        DATABASE_URL="sqlite:///local.db",
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)

    from app.services.timezones import business_clock_enabled_for_hotel

    assert business_clock_enabled_for_hotel(1) is False


def test_postgres_business_clock_requires_exact_loopback_database_and_closed_connections(monkeypatch):
    from sqlalchemy.engine import make_url

    from app.services.timezones import business_clock_enabled_for_hotel

    database_url = "postgresql+psycopg2://pms:pms@127.0.0.1:55433/hotel_pms"
    settings = SimpleNamespace(
        APP_ENV="development",
        model_fields_set={
            "APP_ENV",
            "LOCAL_SIMULATION_CLOCK_ENABLED",
            "LOCAL_SIMULATION_CLOCK_HOTEL_ID",
            "LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE",
            "EXTERNAL_EFFECTS_ENABLED",
            "CONNECTIONS_ENABLED",
        },
        LOCAL_SIMULATION_CLOCK_ENABLED=True,
        LOCAL_SIMULATION_CLOCK_HOTEL_ID=1,
        LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE="hotel_pms",
        EXTERNAL_EFFECTS_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        DATABASE_URL=database_url,
    )
    bind = SimpleNamespace(
        dialect=SimpleNamespace(name="postgresql"),
        url=make_url(database_url),
    )
    db = SimpleNamespace(get_bind=lambda: bind)
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)

    assert business_clock_enabled_for_hotel(1, db) is True
    assert business_clock_enabled_for_hotel(2, db) is False

    settings.LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE = "another_database"
    assert business_clock_enabled_for_hotel(1, db) is False
    settings.LOCAL_SIMULATION_CLOCK_POSTGRES_DATABASE = "hotel_pms"
    settings.CONNECTIONS_ENABLED = True
    assert business_clock_enabled_for_hotel(1, db) is False
    settings.CONNECTIONS_ENABLED = False
    settings.DATABASE_URL = "postgresql+psycopg2://pms:pms@example.com:55433/hotel_pms"
    assert business_clock_enabled_for_hotel(1, db) is False
    settings.DATABASE_URL = "postgresql+psycopg2://pms:pms@127.0.0.1:55433/hotel_pms?hostaddr=203.0.113.4"
    assert business_clock_enabled_for_hotel(1, db) is False
    settings.DATABASE_URL = database_url
    bind.url = make_url("postgresql+psycopg2://pms:pms@127.0.0.1:55434/hotel_pms")
    assert business_clock_enabled_for_hotel(1, db) is False
    bind.url = make_url(database_url)
    monkeypatch.setenv("PGHOSTADDR", "203.0.113.4")
    assert business_clock_enabled_for_hotel(1, db) is False
    monkeypatch.setenv("PGHOSTADDR", "127.0.0.1")
    monkeypatch.setenv("PGSERVICE", "remote-host-service")
    assert business_clock_enabled_for_hotel(1, db) is False


def test_only_owner_can_advance_exactly_one_day_and_audit_uses_real_utc(
    business_clock_api, local_clock_enabled
):
    client, db, context = business_clock_api

    context["user_role"] = "co_owner"
    denied = client.post("/api/config/business-clock/advance")
    assert denied.status_code == 403
    assert not db.query(AuditLog).filter_by(table_name="hotel_business_clock").count()

    context["user_role"] = "owner"
    first_before = datetime.now(timezone.utc)
    first = client.post("/api/config/business-clock/advance")
    first_after = datetime.now(timezone.utc)
    assert first.status_code == 200, first.text
    assert first.json()["business_date"] == "2041-07-09"

    second = client.post("/api/config/business-clock/advance")
    assert second.status_code == 200, second.text
    assert second.json()["business_date"] == "2041-07-10"

    audits = (
        db.query(AuditLog)
        .filter_by(hotel_id=1, table_name="hotel_business_clock", record_id=1)
        .order_by(AuditLog.id.asc())
        .all()
    )
    assert len(audits) == 2
    first_audit_at = audits[0].created_at
    advanced_at = db.query(HotelBusinessClock).filter_by(hotel_id=1).one().advanced_at
    if first_audit_at.tzinfo is None:
        first_audit_at = first_audit_at.replace(tzinfo=timezone.utc)
    if advanced_at.tzinfo is None:
        advanced_at = advanced_at.replace(tzinfo=timezone.utc)
    assert first_before <= first_audit_at <= first_after
    assert first_before <= advanced_at <= datetime.now(timezone.utc)
    assert first_audit_at.date() != date(2041, 7, 9)
    assert json.loads(audits[0].payload_before) == {"business_date": "2041-07-08"}
    assert json.loads(audits[0].payload_after) == {"business_date": "2041-07-09"}


def test_hotel_today_ignores_persisted_dates_unless_every_local_gate_matches(
    business_clock_api, local_clock_enabled, monkeypatch
):
    _client, db, _context = business_clock_api

    assert hotel_today(db, 1) == date(2041, 7, 8)
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_HOTEL_ID", "2")
    get_settings.cache_clear()
    assert hotel_today(db, 1) == local_today("America/Argentina/Buenos_Aires")
    assert hotel_today(db, 2) == date(2042, 8, 9)


def test_implicit_development_default_does_not_open_the_clock_gate(
    business_clock_api, monkeypatch, tmp_path
):
    _client, _db, _context = business_clock_api
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'default-gate.db'}")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_ENABLED", "true")
    monkeypatch.setenv("LOCAL_SIMULATION_CLOCK_HOTEL_ID", "1")
    get_settings.cache_clear()

    assert get_settings().APP_ENV == "development"
    assert get_settings().LOCAL_SIMULATION_CLOCK_ENABLED is True
    assert hotel_today(_db, 1) == local_today("America/Argentina/Buenos_Aires")


def test_first_advance_initializes_from_hotel_today(
    business_clock_api, local_clock_enabled, monkeypatch
):
    from app.services import timezones

    client, db, _context = business_clock_api
    initial_date = date(2027, 3, 14)
    monkeypatch.setattr(timezones, "local_today", lambda _timezone: initial_date)
    db.query(HotelBusinessClock).filter_by(hotel_id=1).delete()
    db.commit()

    response = client.post("/api/config/business-clock/advance")

    assert response.status_code == 200, response.text
    assert response.json()["business_date"] == "2027-03-15"


def _fix_operational_clock_time(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = cls(2026, 10, 17, 21, 30, 12, tzinfo=timezone.utc)
            return value.astimezone(tz) if tz else value

    monkeypatch.setattr("app.services.timezones.datetime", FixedDateTime)
    return datetime(2041, 7, 8, 21, 30, 12)


def test_stock_and_linen_ledger_timestamps_use_hotel_business_clock(
    business_clock_api, local_clock_enabled, monkeypatch
):
    from decimal import Decimal

    from app.models.laundry_vendor import LaundryRemitoLine
    from app.models.linen import LinenMovement
    from app.models.security_audit_log import SecurityAuditLog
    from app.services.laundry_missing_followup_service import update_missing_follow_up
    from app.services.linen_service import (
        create_linen_item,
        create_location as create_linen_location,
        register_opening_counts,
    )
    from app.services.laundry_vendor_service import (
        create_remito,
        create_vendor,
        mark_vendor_settlement_paid,
        set_vendor_price,
    )
    from app.services.stock_service import create_location, create_stock_item, register_movement

    _client, db, _context = business_clock_api
    expected = _fix_operational_clock_time(monkeypatch)

    stock_item = create_stock_item(
        db,
        hotel_id=1,
        name="Detergente QA",
        unit="litro",
        min_quantity=None,
    )
    stock_location = create_location(db, hotel_id=1, name="Depósito QA")
    stock_movement = register_movement(
        db,
        hotel_id=1,
        item_id=stock_item.id,
        location_id=stock_location.id,
        movement_type="in",
        quantity=Decimal("4"),
        reason="Ingreso simulado",
    )

    linen_item = create_linen_item(db, hotel_id=1, name="Sábanas QA", unit="unidad")
    linen_location = create_linen_location(db, hotel_id=1, name="Ropería QA")
    linen_movement = register_opening_counts(
        db,
        hotel_id=1,
        counts=[{"linen_item_id": linen_item.id, "location_id": linen_location.id, "quantity": Decimal("6")}],
        reason="Conteo simulado",
        created_by_user_id=None,
    )[0]
    vendor = create_vendor(db, hotel_id=1, name="Lavadero QA")
    set_vendor_price(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        linen_item_id=linen_item.id,
        unit_price=Decimal("12.50"),
        effective_from=date(2041, 7, 8),
    )
    outbound = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="outbound",
        remito_number="QA-20410708-01",
        remito_date=datetime(2041, 7, 8, 10, 0),
        house_location_id=linen_location.id,
        lines=[{"linen_item_id": linen_item.id, "quantity": Decimal("2")}],
    )
    inbound = create_remito(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        direction="inbound",
        remito_number="QA-20410708-02",
        remito_date=datetime(2041, 7, 8, 15, 0),
        house_location_id=linen_location.id,
        lines=[
            {
                "linen_item_id": linen_item.id,
                "quantity": Decimal("1"),
                "missing_quantity": Decimal("1"),
            }
        ],
    )
    missing_line = db.query(LaundryRemitoLine).filter_by(remito_id=inbound.id).one()
    update_missing_follow_up(
        db=db,
        hotel_id=1,
        remito_line_id=missing_line.id,
        changes={"follow_up_note": "Seguimiento en la fecha simulada"},
        actor_user_id=None,
    )
    db.flush()
    follow_up_audit = (
        db.query(SecurityAuditLog)
        .filter_by(hotel_id=1, action="laundry.missing_follow_up.updated", resource_id=str(missing_line.id))
        .one()
    )
    settlement = mark_vendor_settlement_paid(
        db,
        hotel_id=1,
        vendor_id=vendor.id,
        period_start=date(2041, 7, 1),
        paid=True,
    )

    assert stock_movement.created_at == expected
    assert linen_movement.created_at == expected
    assert outbound.created_at == expected
    assert inbound.created_at == expected
    assert missing_line.follow_up_updated_at == expected
    assert settlement.paid_at == expected
    assert follow_up_audit.created_at.year != expected.year
    assert all(movement.created_at == expected for movement in db.query(LinenMovement).all())
    assert stock_movement.created_at.tzinfo is None
    assert linen_movement.created_at.tzinfo is None


def test_laundry_batch_uses_business_date_for_timestamps_and_batch_code(
    business_clock_api, local_clock_enabled, monkeypatch
):
    from app.services.laundry_service import create_batch, transition_status

    _client, db, _context = business_clock_api
    expected = _fix_operational_clock_time(monkeypatch)

    batch = create_batch(db, hotel_id=1, notes="Retiro simulado")
    sent = transition_status(db, hotel_id=1, batch_id=batch.id, new_status="sent")
    received = transition_status(db, hotel_id=1, batch_id=batch.id, new_status="received")

    assert batch.batch_code == "L20410708-0001"
    assert batch.created_at == expected
    assert sent.sent_at == expected
    assert received.received_at == expected


def test_task_events_and_shift_handoffs_use_business_clock(
    business_clock_api, local_clock_enabled, monkeypatch
):
    from app.models.hotel_membership import HotelMembership
    from app.models.operational_task import (
        OperationalTaskPriorityEnum,
        OperationalTaskStatusEnum,
        OperationalTaskTypeEnum,
    )
    from app.models.user import User
    from app.services.operational_task_service import acknowledge_handoff, create_handoff, create_task, update_task

    _client, db, _context = business_clock_api
    expected = _fix_operational_clock_time(monkeypatch)
    user = db.query(User).filter_by(email="business-clock-owner@example.test").one()
    db.add(HotelMembership(hotel_id=1, user_id=user.id, role="owner", status="active"))
    db.flush()

    task = create_task(
        db,
        hotel_id=1,
        task_type=OperationalTaskTypeEnum.GENERAL,
        priority=OperationalTaskPriorityEnum.MEDIUM,
        title="Revisar depósito",
        created_by_user_id=user.id,
    )
    assert task.created_at == expected
    assert task.updated_at == expected
    assert task.events[0].created_at == expected

    task = update_task(
        db,
        hotel_id=1,
        task_id=task.id,
        actor_user_id=user.id,
        client_version=task.version,
        status=OperationalTaskStatusEnum.RESOLVED,
        comment="Revisión completada",
    )
    assert task.resolved_at == expected
    assert task.updated_at == expected
    assert task.events[-1].created_at == expected

    handoff = create_handoff(
        db,
        hotel_id=1,
        delivered_by_user_id=user.id,
        task_ids=[task.id],
        notes="Pase simulado",
    )
    assert handoff.created_at == expected
    assert handoff.delivered_at == expected

    acknowledged = acknowledge_handoff(
        db,
        hotel_id=1,
        handoff_id=handoff.id,
        received_by_user_id=user.id,
        client_version=handoff.version,
    )
    assert acknowledged.acknowledged_at == expected
