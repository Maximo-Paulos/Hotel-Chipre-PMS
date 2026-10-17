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
