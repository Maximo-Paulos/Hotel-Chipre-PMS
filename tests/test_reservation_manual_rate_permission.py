"""Security gap: any role that can create a reservation (owner, co_owner,
manager, receptionist) could also send a manual total_amount/target_currency
in the POST /api/reservations payload, silently replacing the automatic
Tarifas quote -- the endpoint only gated reservation:create, never checking
who is allowed to override the price. Only owner/co_owner (or a role with an
explicit reservation:manual_rate override) should be able to do this.
"""
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.permission_service import set_override


def _override_auth(hotel_id: int, role: str):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=1,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _build_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    return client, db, engine


def _cleanup_client(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _seed_bookable_state(db, hotel_id: int):
    db.add(HotelConfiguration(id=hotel_id, owner_email="owner@test.com", subscription_active=True))
    guest = Guest(first_name="Manual", last_name="Rate", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name="Standard",
        code="STD",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    room = Room(hotel_id=hotel_id, room_number="101", floor=1, category=category, status=RoomStatusEnum.AVAILABLE)
    db.add_all([guest, category, room])
    db.flush()
    db.commit()
    return guest.id, category.id


def _payload(guest_id: int, category_id: int, **overrides):
    payload = {
        "guest_id": guest_id,
        "category_id": category_id,
        "check_in_date": date(2026, 11, 1).isoformat(),
        "check_out_date": date(2026, 11, 3).isoformat(),
    }
    payload.update(overrides)
    return payload


def test_receptionist_cannot_set_manual_total_amount():
    client, db, engine = _build_client()
    try:
        hotel_id = 501
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=250.0, target_currency="USD"),
        )

        assert response.status_code == 403, response.text
        assert "tarifa manual" in response.json()["detail"].lower()
    finally:
        _cleanup_client(db, engine)


def test_co_owner_cannot_set_manual_total_amount_by_default():
    """Owner explicitly asked that only the owner -- not even co_owner --
    override a reservation's price; everyone else must use Tarifas."""
    client, db, engine = _build_client()
    try:
        hotel_id = 506
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "co_owner")

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=250.0),
        )

        assert response.status_code == 403, response.text
    finally:
        _cleanup_client(db, engine)


def test_manager_cannot_set_manual_total_amount_by_default():
    client, db, engine = _build_client()
    try:
        hotel_id = 502
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=250.0),
        )

        assert response.status_code == 403, response.text
    finally:
        _cleanup_client(db, engine)


def test_owner_can_still_set_manual_total_amount():
    client, db, engine = _build_client()
    try:
        hotel_id = 503
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "owner")

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=250.0, target_currency="USD"),
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["total_amount"] == 250.0
        assert body["currency_code"] == "USD"
    finally:
        _cleanup_client(db, engine)


def test_receptionist_can_still_create_reservation_without_manual_rate():
    """No regression: the gate only fires when total_amount is actually sent."""
    client, db, engine = _build_client()
    try:
        hotel_id = 504
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

        quote_response = client.get(
            "/api/bookings/price-quote",
            params={
                "category_id": category_id,
                "check_in_date": "2026-11-01",
                "check_out_date": "2026-11-03",
            },
        )
        assert quote_response.status_code == 200, quote_response.text

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, quote_token=quote_response.json()["quote_token"]),
        )

        assert response.status_code == 201, response.text
        assert response.json()["total_amount"] == 200.0  # 2 nights x $100 auto-quote
    finally:
        _cleanup_client(db, engine)


def test_manager_can_set_manual_total_amount_with_explicit_override():
    client, db, engine = _build_client()
    try:
        hotel_id = 505
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        set_override(db, hotel_id, "manager", "reservation:manual_rate", True, user_id=1)
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=300.0),
        )

        assert response.status_code == 201, response.text
        assert response.json()["total_amount"] == 300.0
    finally:
        _cleanup_client(db, engine)
