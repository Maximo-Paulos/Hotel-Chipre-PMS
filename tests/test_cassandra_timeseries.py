from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.daily_rate import DailyRate
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.services.timeseries_projection import (
    _daily_rate_change_row,
    _room_state_event_row,
    _schema_statements,
    project_daily_rate_change,
    project_room_state_event,
)


@pytest.fixture
def timeseries_api_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.timeseries_projection.get_cassandra_session", lambda: None)
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_auth_context():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    main_module.app.dependency_overrides[get_db] = override_get_db
    main_module.app.dependency_overrides[get_auth_context] = override_auth_context

    with SessionLocal() as db:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True),
                User(id=1, email="owner@test.com", password_hash="test", is_active=True, is_verified=True),
            ]
        )
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def test_cassandra_off_room_status_and_daily_rate_still_write_postgres(timeseries_api_client):
    client, SessionLocal = timeseries_api_client
    with SessionLocal() as db:
        category = RoomCategory(
            hotel_id=1,
            name="Projected Standard",
            code="PROJ_STD",
            base_price_per_night=100,
            max_occupancy=2,
        )
        db.add(category)
        db.flush()
        room = Room(
            hotel_id=1,
            room_number="901",
            floor=9,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(room)
        db.commit()
        category_id = category.id
        room_id = room.id

    status_response = client.patch(
        f"/api/rooms/{room_id}/status",
        json={"status": RoomStatusEnum.MAINTENANCE.value, "notes": "Projection no-op"},
    )
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["room"]["status"] == RoomStatusEnum.MAINTENANCE.value

    rate_response = client.post(
        f"/api/rates/category/{category_id}/daily",
        json={"date": "2026-09-01", "price": 175.5},
    )
    assert rate_response.status_code == 200, rate_response.text
    assert rate_response.json()["price"] == 175.5

    with SessionLocal() as db:
        room = db.get(Room, room_id)
        rate = db.query(DailyRate).filter(DailyRate.category_id == category_id).one()
        assert room.status == RoomStatusEnum.MAINTENANCE
        assert rate.date == date(2026, 9, 1)
        assert rate.price == 175.5


def test_project_functions_noop_when_cassandra_session_is_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("app.services.timeseries_projection.get_cassandra_session", lambda: None)

    project_room_state_event(1, 10, "maintenance", datetime.now(timezone.utc), {"note": "off"})
    project_daily_rate_change(1, 20, date(2026, 9, 1), 123.45, datetime.now(timezone.utc))


def test_cassandra_partition_keys_and_row_shape():
    occurred_at = datetime(2026, 9, 1, 15, 30, tzinfo=timezone.utc)
    room_row = _room_state_event_row(
        1,
        10,
        "maintenance",
        occurred_at,
        {"reason": "paint"},
    )
    rate_row = _daily_rate_change_row(
        1,
        20,
        date(2026, 9, 2),
        222.0,
        occurred_at,
    )
    cql = "\n".join(_schema_statements("hotel_pms"))

    assert room_row == {
        "hotel_id": 1,
        "event_date": date(2026, 9, 1),
        "occurred_at": occurred_at,
        "room_id": 10,
        "event_type": "maintenance",
        "payload": '{"reason": "paint"}',
    }
    assert rate_row == {
        "hotel_id": 1,
        "rate_date": date(2026, 9, 2),
        "changed_at": occurred_at,
        "category_id": 20,
        "price": 222.0,
    }
    assert "PRIMARY KEY ((hotel_id, event_date), occurred_at, room_id)" in cql
    assert "PRIMARY KEY ((hotel_id, rate_date), changed_at, category_id)" in cql
