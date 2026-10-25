"""B3: check-in must capture the guest's missing profile data (birth place/
country, marital status, occupation) in the same request that performs the
check-in, and PRE_CHECK_IN (B3.1) must be reachable and gate on the same
mandatory data (B3.3). Companions (B3.5) ride the existing capacity-checked
endpoint -- no new backend, just a regression guard here.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.api import bookings as bookings_api
from app.api import checkin as checkin_api
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services import checkin_service
from app.services.checkin_service import CheckOutConflictError

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


def _assert_reservation_response(response, reservation, *, status, balance_due):
    assert response.status_code == 200, response.text
    payload = response.json()
    expected_contract = {
        "id",
        "confirmation_code",
        "guest_id",
        "check_in_date",
        "check_out_date",
        "status",
        "balance_due",
        "nights",
    }
    assert expected_contract <= payload.keys()
    assert payload["id"] == reservation.id
    assert payload["confirmation_code"] == reservation.confirmation_code
    assert payload["guest_id"] == reservation.guest_id
    assert payload["status"] == status.value
    assert payload["balance_due"] == float(balance_due)
    assert payload["nights"] == 2


def test_checkin_without_new_fields_fails_with_clear_message(monkeypatch):
    """Red case: guest missing the 4 new mandatory fields cannot check in."""
    client, db, engine = _client_with_db()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation = _seed_fully_paid_reservation(db)
        response = client.post(f"/api/checkin/{reservation.id}")
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "El lugar de nacimiento es obligatorio" in detail
        assert "El país de nacimiento es obligatorio" in detail
        assert "El estado civil es obligatorio" in detail
        assert "La ocupación es obligatoria" in detail
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_checkin_captures_missing_fields_in_same_request(monkeypatch):
    """Green case: same endpoint, now with `guest` in the payload, succeeds once."""
    client, db, engine = _client_with_db()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
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
        _assert_reservation_response(
            response,
            reservation,
            status=ReservationStatusEnum.CHECKED_IN,
            balance_due=Decimal("0.00"),
        )

        db.refresh(reservation)
        guest = db.query(Guest).filter(Guest.id == reservation.guest_id).first()
        assert guest.birth_place == "Cordoba"
        assert guest.occupation == "Arquitecta"
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_partial_checkin_reaches_pre_check_in_then_final_checkin(monkeypatch):
    client, db, engine = _client_with_db()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
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
        _assert_reservation_response(
            partial,
            reservation,
            status=ReservationStatusEnum.PRE_CHECK_IN,
            balance_due=Decimal("0.00"),
        )

        db.refresh(reservation)
        assert reservation.pre_check_in_at is not None

        final = client.post(f"/api/checkin/{reservation.id}")
        _assert_reservation_response(
            final,
            reservation,
            status=ReservationStatusEnum.CHECKED_IN,
            balance_due=Decimal("0.00"),
        )

        reservation.amount_paid = Decimal("175.00")
        db.commit()
        checkout = client.post(f"/api/checkin/checkout/{reservation.id}?force=true")
        _assert_reservation_response(
            checkout,
            reservation,
            status=ReservationStatusEnum.CHECKED_OUT,
            balance_due=Decimal("25.00"),
        )
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


@pytest.mark.parametrize(
    ("route_name", "api_module"),
    [("checkin", checkin_api), ("legacy_bookings", bookings_api)],
)
def test_checkout_room_lock_conflict_returns_409_and_rolls_back(monkeypatch, route_name, api_module):
    client, db, engine = _client_with_db()
    try:
        reservation = _seed_fully_paid_reservation(db)
        reservation.status = ReservationStatusEnum.CHECKED_IN
        db.commit()
        rollback = db.rollback
        rollback_calls = []

        def tracked_rollback():
            rollback_calls.append(True)
            rollback()

        def conflicting_checkout(session, reservation_id, **_kwargs):
            target = session.get(Reservation, reservation_id)
            target.status = ReservationStatusEnum.CHECKED_OUT
            session.flush()
            raise CheckOutConflictError("La habitación está ocupada por otra operación; reintentá el check-out.")

        monkeypatch.setattr(db, "rollback", tracked_rollback)
        monkeypatch.setattr(api_module, "perform_checkout", conflicting_checkout)

        path = (
            f"/api/checkin/checkout/{reservation.id}?force=true"
            if route_name == "checkin"
            else f"/api/bookings/{reservation.id}/checkout"
        )
        response = client.post(path)

        assert response.status_code == 409
        assert "reintentá el check-out" in response.json()["detail"]
        assert rollback_calls == [True]
        db.refresh(reservation)
        assert reservation.status == ReservationStatusEnum.CHECKED_IN
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_partial_checkin_requires_full_payment_under_default_policy(monkeypatch):
    client, db, engine = _client_with_db()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation = _seed_fully_paid_reservation(db)
        reservation.status = ReservationStatusEnum.DEPOSIT_PAID
        reservation.deposit_amount = Decimal("60.00")
        reservation.amount_paid = Decimal("0.00")
        db.flush()

        response = client.post(f"/api/checkin/{reservation.id}/partial")
        assert response.status_code == 400
        assert "importe total de la reserva" in response.json()["detail"]
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
