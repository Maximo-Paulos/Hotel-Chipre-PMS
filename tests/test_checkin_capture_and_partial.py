"""B3: check-in must capture the guest's missing profile data (birth place/
country, marital status, occupation) in the same request that performs the
check-in, and PRE_CHECK_IN (B3.1) must be reachable and gate on the same
mandatory data (B3.3). Companions (B3.5) ride the existing capacity-checked
endpoint -- no new backend, just a regression guard here.
"""
from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum

HOTEL_ID = 7301


def _override_auth(hotel_id: int, role: str = "owner", user_id: int = 1):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(HOTEL_ID)
    client = TestClient(fastapi_app)
    return client, db, engine


def _seed_fully_paid_reservation(db, *, guest_kwargs=None, max_occupancy=2) -> Reservation:
    hotel = HotelConfiguration(id=HOTEL_ID, hotel_name="Hotel Capture", subscription_active=True)
    db.add(hotel)
    db.flush()
    guest = Guest(
        hotel_id=HOTEL_ID,
        first_name="Marta",
        last_name="Suarez",
        document_type="DNI",
        document_number="40111222",
        terms_accepted=True,
        **(guest_kwargs or {}),
    )
    db.add(guest)
    db.flush()
    category = RoomCategory(
        hotel_id=HOTEL_ID, name="Standard", code="STDCAP",
        base_price_per_night=Decimal("100.00"), max_occupancy=max_occupancy,
    )
    db.add(category)
    db.flush()
    room = Room(hotel_id=HOTEL_ID, category_id=category.id, room_number="201", status=RoomStatusEnum.AVAILABLE)
    db.add(room)
    db.flush()
    reservation = Reservation(
        hotel_id=HOTEL_ID, guest_id=guest.id, category_id=category.id, room_id=room.id,
        check_in_date=date(2026, 3, 1), check_out_date=date(2026, 3, 3), num_adults=1,
        total_amount=Decimal("200.00"), amount_paid=Decimal("200.00"),
        status=ReservationStatusEnum.FULLY_PAID, confirmation_code="CAP001",
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_checkin_without_new_fields_fails_with_clear_message():
    """Red case: guest missing the 4 new mandatory fields cannot check in."""
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db)
        response = client.post(f"/api/checkin/{reservation.id}")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "Birth place is required" in detail
        assert "Birth country is required" in detail
        assert "Marital status is required" in detail
        assert "Occupation is required" in detail
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_checkin_captures_missing_fields_in_same_request():
    """Green case: same endpoint, now with `guest` in the payload, succeeds once."""
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db)
        response = client.post(
            f"/api/checkin/{reservation.id}",
            json={
                "guest": {
                    "birth_place": "Cordoba",
                    "birth_country": "Argentina",
                    "marital_status": "married",
                    "occupation": "Arquitecta",
                }
            },
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == ReservationStatusEnum.CHECKED_IN.value

        db.refresh(reservation)
        guest = db.query(Guest).filter(Guest.id == reservation.guest_id).first()
        assert guest.birth_place == "Cordoba"
        assert guest.occupation == "Arquitecta"
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_partial_checkin_reaches_pre_check_in_then_final_checkin():
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db)
        guest_patch = {
            "guest": {
                "birth_place": "Rosario",
                "birth_country": "Argentina",
                "marital_status": "single",
                "occupation": "Chef",
            }
        }

        partial = client.post(f"/api/checkin/{reservation.id}/partial", json=guest_patch)
        assert partial.status_code == 200, partial.text
        assert partial.json()["status"] == ReservationStatusEnum.PRE_CHECK_IN.value

        db.refresh(reservation)
        assert reservation.pre_check_in_at is not None

        final = client.post(f"/api/checkin/{reservation.id}")
        assert final.status_code == 200, final.text
        assert final.json()["status"] == ReservationStatusEnum.CHECKED_IN.value
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_partial_checkin_requires_fully_paid():
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db)
        reservation.status = ReservationStatusEnum.DEPOSIT_PAID
        db.flush()

        response = client.post(f"/api/checkin/{reservation.id}/partial")
        assert response.status_code == 400
        assert "fully_paid" in response.json()["detail"]
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_add_companion_during_checkin_flow_appears_in_additional_guests():
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db, max_occupancy=2)
        response = client.post(
            f"/api/reservations/{reservation.id}/guests",
            json=[{"first_name": "Luis", "last_name": "Suarez", "document_number": "40999888"}],
        )
        assert response.status_code == 200, response.text
        names = {g["first_name"] for g in response.json()["additional_guests"]}
        assert "Luis" in names
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_add_companion_exceeding_capacity_returns_clear_400():
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db, max_occupancy=1)
        response = client.post(
            f"/api/reservations/{reservation.id}/guests",
            json=[{"first_name": "Luis", "last_name": "Suarez", "document_number": "40999888"}],
        )
        assert response.status_code == 400
        assert "capacity" in response.json()["detail"].lower()
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
