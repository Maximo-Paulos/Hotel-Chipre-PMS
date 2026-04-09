from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

import app.database as db_module
import app.main as main_module
from app.database import Base, get_db
from app.models.hotel_config import HotelConfiguration
from app.models.ota import OTAReservationMapping
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.ota_service import OTAIntegrationService


@pytest.fixture(scope="function")
def db_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    db_dir = tmp_path_factory.mktemp("ota-hardening-db")
    return f"sqlite:///{(db_dir / 'ota.sqlite').as_posix()}"


@pytest.fixture(scope="function")
def engine(db_url: str):
    engine = create_engine(db_url, connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(engine) -> sessionmaker:
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def client(engine, db_url: str, monkeypatch: pytest.MonkeyPatch):
    def fake_get_engine(database_url: str | None = None):
        return engine

    monkeypatch.setattr(db_module, "get_engine", fake_get_engine)
    db_module.init_db(db_url)
    monkeypatch.setattr(main_module, "init_db", lambda: db_module.init_db(db_url))

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    main_module.app.dependency_overrides[get_db] = override_get_db

    with TestClient(main_module.app) as test_client:
        yield test_client

    main_module.app.dependency_overrides.clear()


def _seed_hotel(db, hotel_id: int, room_type_code: str) -> tuple[str, str]:
    db.add(HotelConfiguration(id=hotel_id, hotel_name=f"Hotel {hotel_id}", owner_email=f"owner{hotel_id}@test.local", subscription_active=True))
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=room_type_code,
        base_price_per_night=100.0 + hotel_id,
        max_occupancy=2,
        description=f"Category {room_type_code} for hotel {hotel_id}",
    )
    db.add(category)
    db.flush()

    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    db.add(room)
    db.flush()

    booking_secret = f"booking-secret-{hotel_id}"
    expedia_secret = f"expedia-secret-{hotel_id}"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="booking",
        webhook_secret=booking_secret,
        external_property_id=f"booking-{hotel_id}",
    )
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="expedia",
        webhook_secret=expedia_secret,
        external_property_id=f"expedia-{hotel_id}",
    )
    return booking_secret, expedia_secret


def test_booking_webhook_scopes_by_hotel_and_secret(client: TestClient, db):
    booking_secret_1, _ = _seed_hotel(db, 1, "STD_DBL")
    booking_secret_2, _ = _seed_hotel(db, 2, "STD_DBL")
    db.commit()

    payload = {
        "reservation_id": "BKG-2001",
        "guest_name": "Jane Doe",
        "guest_email": "jane@example.com",
        "checkin": "2026-04-10",
        "checkout": "2026-04-12",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 320.0,
        "currency": "ARS",
        "property_id": "booking-2",
    }

    response = client.post(f"/api/webhooks/booking/2/{booking_secret_2}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    db.expire_all()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=2,
        ota_name="booking",
        ota_reservation_id="BKG-2001",
    ).one()
    assert mapping.hotel_id == 2
    assert mapping.reservation is not None
    assert mapping.reservation.hotel_id == 2
    assert mapping.reservation.room is not None
    assert mapping.reservation.room.hotel_id == 2

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="booking",
        ota_reservation_id="BKG-2001",
    ).count() == 0


def test_expedia_webhook_scopes_by_hotel_and_secret(client: TestClient, db):
    _, expedia_secret_1 = _seed_hotel(db, 1, "STD_DBL")
    _, expedia_secret_2 = _seed_hotel(db, 2, "STD_DBL")
    db.commit()

    payload = {
        "booking_id": "EXP-2002",
        "guest": {"first_name": "Ana", "last_name": "Lopez", "email": "ana@example.com"},
        "stay": {"checkin": "2026-04-15", "checkout": "2026-04-17"},
        "room_type_id": "STD_DBL",
        "occupancy": {"adults": 2, "children": 0},
        "pricing": {"total": 280.0, "currency": "ARS"},
        "property_id": "expedia-1",
    }

    response = client.post(f"/api/webhooks/expedia/1/{expedia_secret_1}", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

    db.expire_all()
    mapping = db.query(OTAReservationMapping).filter_by(
        hotel_id=1,
        ota_name="expedia",
        ota_reservation_id="EXP-2002",
    ).one()
    assert mapping.hotel_id == 1
    assert mapping.reservation is not None
    assert mapping.reservation.hotel_id == 1
    assert mapping.reservation.room is not None
    assert mapping.reservation.room.hotel_id == 1

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=2,
        ota_name="expedia",
        ota_reservation_id="EXP-2002",
    ).count() == 0


def test_ota_webhook_rejects_invalid_secret(client: TestClient, db):
    _seed_hotel(db, 1, "STD_DBL")
    db.commit()

    payload = {
        "reservation_id": "BKG-2999",
        "guest_name": "Invalid Secret",
        "guest_email": "invalid@example.com",
        "checkin": "2026-04-20",
        "checkout": "2026-04-22",
        "room_type": "STD_DBL",
        "num_adults": 1,
        "num_children": 0,
        "total_price": 150.0,
        "currency": "ARS",
        "property_id": "booking-1",
    }

    response = client.post("/api/webhooks/booking/1/not-the-secret", json=payload)
    assert response.status_code == 401
    assert db.query(OTAReservationMapping).count() == 0

