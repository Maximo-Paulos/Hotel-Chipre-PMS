from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.api_key_auth import public_api_limiter
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_api_key import APIKeyPurposeEnum
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.hotel_api_key_service import issue_key, revoke_key


@pytest.fixture
def public_client_with_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    original_limit = public_api_limiter.limit
    original_window = public_api_limiter.window
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        public_api_limiter.limit = original_limit
        public_api_limiter.window = original_window
        db.close()
        engine.dispose()


def _seed_hotel(db, hotel_id: int):
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True, deposit_percentage=30.0)
    db.add(hotel)
    db.flush()
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    guest = Guest(first_name="Public", last_name=f"Guest {hotel_id}", email=f"guest{hotel_id}@test.com", hotel_id=hotel_id)
    db.add_all([category, guest])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return hotel, category, room, guest


def _issue_public_key(db, hotel_id: int, name: str = "Public key"):
    key, secret = issue_key(
        db,
        hotel_id=hotel_id,
        name=name,
        purpose=APIKeyPurposeEnum.WEB_ENGINE,
    )
    db.commit()
    return key, secret


def _headers(secret: str) -> dict[str, str]:
    return {"X-API-Key": secret}


def test_public_availability_requires_active_api_key(public_client_with_db):
    client, db = public_client_with_db
    _hotel, category, _room, _guest = _seed_hotel(db, 1)
    key, secret = _issue_public_key(db, 1)

    params = {
        "category_id": category.id,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-03",
    }
    missing = client.get("/api/public/booking/availability", params=params)
    assert missing.status_code == 401

    active = client.get("/api/public/booking/availability", params=params, headers=_headers(secret))
    assert active.status_code == 200, active.text
    assert active.json()["count"] == 1

    revoke_key(db, hotel_id=1, key_id=key.id)
    db.commit()
    revoked = client.get("/api/public/booking/availability", params=params, headers=_headers(secret))
    assert revoked.status_code == 401


def test_public_reservation_is_scoped_to_key_hotel(public_client_with_db):
    client, db = public_client_with_db
    _hotel_a, category_a, room_a, guest_a = _seed_hotel(db, 1)
    _hotel_b, category_b, room_b, guest_b = _seed_hotel(db, 2)
    _key, secret = _issue_public_key(db, 1)

    cross_hotel_payload = {
        "hotel_id": 2,
        "guest_id": guest_b.id,
        "category_id": category_b.id,
        "room_id": room_b.id,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-02",
        "num_adults": 1,
    }
    denied = client.post("/api/public/booking/reservations", json=cross_hotel_payload, headers=_headers(secret))
    assert denied.status_code == 400

    payload = {
        "hotel_id": 2,
        "guest_id": guest_a.id,
        "category_id": category_a.id,
        "room_id": room_a.id,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-02",
        "num_adults": 1,
    }
    created = client.post("/api/public/booking/reservations", json=payload, headers=_headers(secret))
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["category_id"] == category_a.id

    reservation = db.query(Reservation).filter(Reservation.id == body["id"]).one()
    assert reservation.hotel_id == 1
    assert reservation.hotel_id != 2


def test_revoked_key_is_rejected(public_client_with_db):
    client, db = public_client_with_db
    _hotel, _category, _room, _guest = _seed_hotel(db, 1)
    key, secret = _issue_public_key(db, 1)
    revoke_key(db, hotel_id=1, key_id=key.id)
    db.commit()

    response = client.get("/api/public/booking/categories", headers=_headers(secret))
    assert response.status_code == 401


def test_public_api_rate_limit_is_per_hotel_key(public_client_with_db):
    client, db = public_client_with_db
    _seed_hotel(db, 1)
    key_a, secret_a = _issue_public_key(db, 1, "Key A")
    _key_b, secret_b = _issue_public_key(db, 1, "Key B")
    public_api_limiter.limit = 2
    public_api_limiter.reset(f"hotel:1:key:{key_a.id}", db=db)
    db.commit()

    first = client.get("/api/public/booking/categories", headers=_headers(secret_a))
    second = client.get("/api/public/booking/categories", headers=_headers(secret_a))
    third = client.get("/api/public/booking/categories", headers=_headers(secret_a))
    other_key = client.get("/api/public/booking/categories", headers=_headers(secret_b))

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert other_key.status_code == 200
