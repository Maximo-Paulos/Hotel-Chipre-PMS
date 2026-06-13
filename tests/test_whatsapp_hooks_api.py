from datetime import date
from decimal import Decimal

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
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationChannelCodeEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.hotel_api_key_service import issue_key


@pytest.fixture
def whatsapp_client_with_db():
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
        name=f"WhatsApp Standard {hotel_id}",
        code=f"WSTD{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    guest = Guest(
        hotel_id=hotel_id,
        first_name="WhatsApp",
        last_name=f"Guest {hotel_id}",
        email=f"whatsapp{hotel_id}@example.com",
        phone=f"+549110000{hotel_id}",
    )
    db.add_all([category, guest])
    db.flush()
    room = Room(
        hotel_id=hotel_id,
        room_number=f"W{hotel_id}01",
        floor=1,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    return category, room, guest


def _issue_key(db, hotel_id: int):
    _key, secret = issue_key(
        db,
        hotel_id=hotel_id,
        name=f"WhatsApp key {hotel_id}",
        purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
    )
    db.commit()
    return secret


def _headers(secret: str) -> dict[str, str]:
    return {"X-API-Key": secret}


def test_whatsapp_availability_uses_api_key_hotel_scope(whatsapp_client_with_db):
    client, db = whatsapp_client_with_db
    category_a, _room_a, _guest_a = _seed_hotel(db, 1)
    category_b, _room_b, _guest_b = _seed_hotel(db, 2)
    secret = _issue_key(db, 1)

    params = {
        "category_id": category_a.id,
        "check_in_date": "2026-09-01",
        "check_out_date": "2026-09-03",
    }
    missing = client.get("/api/public/whatsapp/availability", params=params)
    assert missing.status_code == 401

    allowed = client.get("/api/public/whatsapp/availability", params=params, headers=_headers(secret))
    assert allowed.status_code == 200, allowed.text
    assert allowed.json()["count"] == 1

    cross_hotel = client.get(
        "/api/public/whatsapp/availability",
        params={**params, "category_id": category_b.id},
        headers=_headers(secret),
    )
    assert cross_hotel.status_code == 400


def test_whatsapp_create_reservation_sets_channel_code_whatsapp(whatsapp_client_with_db):
    client, db = whatsapp_client_with_db
    category, room, guest = _seed_hotel(db, 1)
    secret = _issue_key(db, 1)

    response = client.post(
        "/api/public/whatsapp/reservations",
        json={
            "guest_id": guest.id,
            "category_id": category.id,
            "room_id": room.id,
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-02",
            "num_adults": 1,
        },
        headers=_headers(secret),
    )

    assert response.status_code == 201, response.text
    reservation = db.query(Reservation).filter_by(id=response.json()["id"]).one()
    assert reservation.hotel_id == 1
    assert reservation.channel_code == ReservationChannelCodeEnum.WHATSAPP


def test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(whatsapp_client_with_db):
    client, db = whatsapp_client_with_db
    category, room, guest = _seed_hotel(db, 1)
    secret = _issue_key(db, 1)
    created = client.post(
        "/api/public/whatsapp/reservations",
        json={
            "guest_id": guest.id,
            "category_id": category.id,
            "room_id": room.id,
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-02",
            "num_adults": 1,
        },
        headers=_headers(secret),
    )
    assert created.status_code == 201, created.text

    response = client.post(
        "/api/public/whatsapp/payment-links",
        json={
            "reservation_id": created.json()["id"],
            "requested_amount": "100.00",
            "recipient_email": "wa-pay@example.com",
            "recipient_phone": "+5491111111111",
        },
        headers=_headers(secret),
    )

    assert response.status_code == 201, response.text
    link = db.query(PaymentLink).filter_by(id=response.json()["id"]).one()
    assert link.sent_via_whatsapp is True


def test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(whatsapp_client_with_db):
    client, db = whatsapp_client_with_db
    _category_a, _room_a, _guest_a = _seed_hotel(db, 1)
    category_b, room_b, guest_b = _seed_hotel(db, 2)
    secret = _issue_key(db, 1)

    denied_create = client.post(
        "/api/public/whatsapp/reservations",
        json={
            "guest_id": guest_b.id,
            "category_id": category_b.id,
            "room_id": room_b.id,
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-02",
            "num_adults": 1,
        },
        headers=_headers(secret),
    )
    assert denied_create.status_code == 400

    reservation_b = Reservation(
        hotel_id=2,
        confirmation_code="WA-H2-API",
        guest_id=guest_b.id,
        room_id=room_b.id,
        category_id=category_b.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 2),
        total_amount=Decimal("100.00"),
        deposit_amount=Decimal("30.00"),
    )
    db.add(reservation_b)
    db.flush()

    denied_link = client.post(
        "/api/public/whatsapp/payment-links",
        json={
            "reservation_id": reservation_b.id,
            "requested_amount": "100.00",
            "recipient_email": "cross@example.com",
        },
        headers=_headers(secret),
    )
    assert denied_link.status_code == 400
    assert db.query(PaymentLink).count() == 0
