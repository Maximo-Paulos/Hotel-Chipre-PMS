from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.daily_rate import PricePeriod
from app.models.user import User


@pytest.fixture
def soft_delete_client(monkeypatch: pytest.MonkeyPatch):
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

    monkeypatch.setattr(db_module, "get_engine", lambda database_url=None: engine)
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
        db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
        db.add(User(id=1, email="owner@test.com", password_hash="test-hash", is_active=True, is_verified=True))
        db.commit()

    with TestClient(main_module.app) as client:
        yield client, SessionLocal

    main_module.app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _seed_category(db, *, name: str = "Soft Delete Cat") -> RoomCategory:
    category = RoomCategory(
        hotel_id=1,
        name=name,
        code=name.upper().replace(" ", "_")[:20],
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _delete_audit(db, *, table_name: str, record_id: int) -> AuditLog:
    return (
        db.query(AuditLog)
        .filter(
            AuditLog.hotel_id == 1,
            AuditLog.table_name == table_name,
            AuditLog.record_id == record_id,
            AuditLog.action == AuditActionEnum.DELETE,
        )
        .one()
    )


def test_reservation_delete_soft_deletes_hides_and_audits(soft_delete_client):
    client, SessionLocal = soft_delete_client
    today = date.today()

    with SessionLocal() as db:
        category = _seed_category(db)
        guest = Guest(first_name="Soft", last_name="Guest", hotel_id=1)
        room = Room(room_number="501", floor=5, category_id=category.id, status=RoomStatusEnum.AVAILABLE, hotel_id=1)
        db.add_all([guest, room])
        db.commit()
        payload = {
            "guest_id": guest.id,
            "category_id": category.id,
            "room_id": room.id,
            "check_in_date": today.isoformat(),
            "check_out_date": (today + timedelta(days=1)).isoformat(),
            "num_adults": 1,
        }

    quote = client.get(
        "/api/bookings/price-quote",
        params={
            "category_id": category.id,
            "check_in_date": payload["check_in_date"],
            "check_out_date": payload["check_out_date"],
            "occupancy": 1,
        },
    )
    assert quote.status_code == 200, quote.text
    payload["quote_token"] = quote.json()["quote_token"]

    created = client.post("/api/bookings/", json=payload)
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]

    deleted = client.delete(f"/api/bookings/{reservation_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted"] is True
    assert client.get("/api/bookings/").json() == []
    assert client.get(f"/api/bookings/{reservation_id}").status_code == 404

    with SessionLocal() as db:
        reservation = db.get(Reservation, reservation_id)
        assert reservation is not None
        assert reservation.deleted_at is not None
        assert reservation.deleted_by_user_id == 1
        audit = _delete_audit(db, table_name="reservations", record_id=reservation_id)
        assert audit.actor_user_id == 1
        assert audit.payload_after is not None


def test_room_delete_soft_deletes_hides_and_audits(soft_delete_client):
    client, SessionLocal = soft_delete_client
    with SessionLocal() as db:
        category = _seed_category(db, name="Soft Delete Room")
        db.commit()
        category_id = category.id

    created = client.post(
        "/api/rooms/",
        json={
            "room_number": "601",
            "floor": 6,
            "category_id": category_id,
            "status": RoomStatusEnum.AVAILABLE.value,
        },
    )
    assert created.status_code == 201, created.text
    room_id = created.json()["id"]

    deleted = client.delete(f"/api/rooms/{room_id}")
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/rooms/").json() == []
    assert client.get(f"/api/rooms/{room_id}").status_code == 404

    with SessionLocal() as db:
        room = db.get(Room, room_id)
        assert room is not None
        assert room.deleted_at is not None
        assert room.deleted_by_user_id == 1
        audit = _delete_audit(db, table_name="rooms", record_id=room_id)
        assert audit.actor_user_id == 1


def test_price_period_delete_soft_deletes_hides_and_audits(soft_delete_client):
    client, SessionLocal = soft_delete_client
    with SessionLocal() as db:
        category = _seed_category(db, name="Soft Delete Period")
        db.commit()
        category_id = category.id

    created = client.post(
        "/api/rates/periods",
        json={
            "category_id": category_id,
            "name": "Winter",
            "start_date": "2026-07-01",
            "end_date": "2026-07-10",
            "price_per_night": 150.0,
            "priority": 1,
            "is_active": True,
        },
    )
    assert created.status_code == 201, created.text
    period_id = created.json()["id"]

    deleted = client.delete(f"/api/rates/periods/{period_id}")
    assert deleted.status_code == 204, deleted.text
    assert client.get("/api/rates/periods").json() == []

    with SessionLocal() as db:
        period = db.get(PricePeriod, period_id)
        assert period is not None
        assert period.deleted_at is not None
        assert period.deleted_by_user_id == 1
        audit = _delete_audit(db, table_name="price_periods", record_id=period_id)
        assert audit.actor_user_id == 1
