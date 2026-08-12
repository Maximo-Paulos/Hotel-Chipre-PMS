from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory


@pytest.fixture
def client_with_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    ctx = {"hotel_id": 1, "role": "receptionist"}

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=ctx["hotel_id"],
            user_id=1,
            user_email="receptionist@test.com",
            user_role=ctx["role"],
            is_verified=True,
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db, ctx
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.flush()
    guest = Guest(first_name="Api", last_name="Guest", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Api Room {hotel_id}",
        code=f"API{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 2),
        total_amount=100,
        deposit_amount=30,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.commit()
    return reservation


def test_payment_links_api_create_list_and_cancel(client_with_db):
    client, db, _ctx = client_with_db
    reservation = _reservation(db, 1, "API-1")

    created = client.post(
        "/api/payment-links",
        json={"reservation_id": reservation.id, "requested_amount": "25.00", "recipient_email": "api@example.com"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["requested_amount"] == "25.00"

    listed = client.get(f"/api/payment-links?reservation_id={reservation.id}")
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [body["id"]]

    cancelled = client.post(f"/api/payment-links/{body['id']}/cancel", json={"reason": "guest_request"})
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"


def test_payment_links_api_cross_hotel_isolation(client_with_db):
    client, db, ctx = client_with_db
    reservation_b = _reservation(db, 2, "API-2")
    ctx["hotel_id"] = 2
    created = client.post(
        "/api/payment-links",
        json={"reservation_id": reservation_b.id, "requested_amount": "25.00", "recipient_email": "api-b@example.com"},
    )
    assert created.status_code == 201, created.text
    link_id = created.json()["id"]

    ctx["hotel_id"] = 1
    listed = client.get(f"/api/payment-links?reservation_id={reservation_b.id}")
    assert listed.status_code == 200
    assert listed.json() == []
    cancelled = client.post(f"/api/payment-links/{link_id}/cancel", json={"reason": "wrong_hotel"})
    assert cancelled.status_code == 404


def test_payment_links_api_rejects_manager_without_cash_operate(client_with_db):
    client, db, ctx = client_with_db
    reservation = _reservation(db, 1, "API-MANAGER-DENIED")
    ctx["role"] = "manager"

    response = client.post(
        "/api/payment-links",
        json={"reservation_id": reservation.id, "requested_amount": "25.00"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "No tenes permisos para esta accion"
