"""Per-person arrival recording, hotel policy, and tenant isolation."""
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
from app.models.reservation_guest_arrival import ReservationGuestArrival
from app.models.room import (
    Room,
    RoomCategory,
    RoomHousekeepingStatusEnum,
    RoomStatusEnum,
)
from app.models.user import User
from app.services import checkin_service

HOTEL_ID = 7341
FOREIGN_HOTEL_ID = 7342


def _override_auth(hotel_id: int = HOTEL_ID, user_role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=77,
            user_email="owner@test.invalid",
            user_role=user_role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _test_app():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = session_factory()
    db.add(
        User(
            id=77,
            email=f"owner-{id(db)}@test.invalid",
            password_hash="test-hash",
            role="owner",
            is_verified=True,
        )
    )
    db.commit()

    def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth()
    return TestClient(fastapi_app), db, engine


def _guest(hotel_id: int, first_name: str, document_number: str) -> Guest:
    return Guest(
        hotel_id=hotel_id,
        first_name=first_name,
        last_name="Huésped",
        document_type="DNI",
        document_number=document_number,
        nationality="Argentina",
        country="Argentina",
        birth_place="Córdoba",
        birth_country="Argentina",
        marital_status="single",
        occupation="Profesional",
        terms_accepted=True,
    )


def _seed_reservation(db, *, policy="partial_checkin", party_size=3, companion_count=2):
    hotel = HotelConfiguration(
        id=HOTEL_ID,
        hotel_name="Hotel arrivals",
        subscription_active=True,
        checkin_reservation_status_policy=policy,
    )
    db.add(hotel)
    db.flush()
    guests = [_guest(HOTEL_ID, f"Persona {index + 1}", f"7341{index + 1:04d}") for index in range(companion_count + 1)]
    db.add_all(guests)
    db.flush()
    category = RoomCategory(
        hotel_id=HOTEL_ID,
        name="Habitación familiar",
        code="ARRIVAL",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=party_size,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=HOTEL_ID,
        category_id=category.id,
        room_number="31",
        status=RoomStatusEnum.AVAILABLE,
        housekeeping_status=RoomHousekeepingStatusEnum.CLEAN,
    )
    db.add(room)
    db.flush()
    reservation = Reservation(
        hotel_id=HOTEL_ID,
        guest_id=guests[0].id,
        category_id=category.id,
        room_id=room.id,
        check_in_date=date(2026, 3, 1),
        check_out_date=date(2026, 3, 4),
        num_adults=party_size,
        num_children=0,
        total_amount=Decimal("300.00"),
        amount_paid=Decimal("300.00"),
        status=ReservationStatusEnum.FULLY_PAID,
        confirmation_code=f"ARR{HOTEL_ID}",
    )
    reservation.additional_guests.extend(guests[1:])
    db.add(reservation)
    db.flush()
    return reservation, room, guests


def _close(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_each_guest_arrival_is_idempotent_and_only_first_occupies_room(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, room, guests = _seed_reservation(db)
        original_paid = reservation.amount_paid
        first = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert first.status_code == 200, first.text
        assert first.json()["reservation_status"] == "partial_checkin"
        assert first.json()["arrived_guest_count"] == 1
        assert first.json()["arrival"]["actor_role"] == "owner"
        assert first.json()["arrival"]["actor_user_id"] == 77
        assert room.status == RoomStatusEnum.OCCUPIED
        assert reservation.amount_paid == original_paid

        retry = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert retry.status_code == 200, retry.text
        assert retry.json()["already_recorded"] is True
        assert retry.json()["arrival"]["id"] == first.json()["arrival"]["id"]
        assert retry.json()["arrival"]["arrived_at"] == first.json()["arrival"]["arrived_at"]
        assert db.query(ReservationGuestArrival).filter_by(reservation_id=reservation.id).count() == 1

        second = client.post(f"/api/checkin/{reservation.id}/guests/{guests[1].id}")
        assert second.status_code == 200, second.text
        assert second.json()["reservation_status"] == "partial_checkin"
        assert second.json()["arrived_guest_count"] == 2
        third = client.post(f"/api/checkin/{reservation.id}/guests/{guests[2].id}")
        assert third.status_code == 200, third.text
        assert third.json()["reservation_status"] == "checked_in"
        assert third.json()["arrived_guest_count"] == 3
        assert db.query(ReservationGuestArrival).filter_by(reservation_id=reservation.id).count() == 3
        assert reservation.amount_paid == original_paid
    finally:
        _close(db, engine)


def test_hotel_can_mark_reservation_checked_in_on_first_guest(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, room, guests = _seed_reservation(db, policy="checked_in_on_first_guest")
        first = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert first.status_code == 200, first.text
        assert first.json()["reservation_status"] == "checked_in"
        assert first.json()["status_policy"] == "checked_in_on_first_guest"
        assert room.status == RoomStatusEnum.OCCUPIED

        late_guest = client.post(f"/api/checkin/{reservation.id}/guests/{guests[1].id}")
        assert late_guest.status_code == 200, late_guest.text
        assert late_guest.json()["reservation_status"] == "checked_in"
        assert late_guest.json()["arrived_guest_count"] == 2
    finally:
        _close(db, engine)


def test_missing_guest_profiles_remain_visible_and_do_not_complete_party(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, _room, guests = _seed_reservation(db, party_size=3, companion_count=0)
        arrived = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["reservation_status"] == "partial_checkin"
        assert arrived.json()["expected_guest_count"] == 3
        assert arrived.json()["registered_guest_count"] == 1
        assert arrived.json()["missing_profile_count"] == 2
    finally:
        _close(db, engine)


def test_foreign_reservation_and_unlinked_guest_are_not_exposed(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, _room, _guests = _seed_reservation(db, party_size=1, companion_count=0)
        db.add(HotelConfiguration(id=FOREIGN_HOTEL_ID, hotel_name="Otro hotel", subscription_active=True))
        db.flush()
        foreign_guest = _guest(FOREIGN_HOTEL_ID, "Otro", "99999999")
        db.add(foreign_guest)
        db.flush()
        foreign_category = RoomCategory(
            hotel_id=FOREIGN_HOTEL_ID,
            name="Otra habitación",
            code="FOREIGNARR",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=1,
        )
        db.add(foreign_category)
        db.flush()
        foreign_room = Room(
            hotel_id=FOREIGN_HOTEL_ID,
            category_id=foreign_category.id,
            room_number="99",
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(foreign_room)
        db.flush()

        other_hotel_reservation = Reservation(
            hotel_id=FOREIGN_HOTEL_ID,
            guest_id=foreign_guest.id,
            category_id=foreign_category.id,
            room_id=foreign_room.id,
            check_in_date=date(2026, 3, 1),
            check_out_date=date(2026, 3, 2),
            num_adults=1,
            total_amount=Decimal("100.00"),
            amount_paid=Decimal("100.00"),
            status=ReservationStatusEnum.FULLY_PAID,
            confirmation_code="FOREIGNARR",
        )
        db.add(other_hotel_reservation)
        db.flush()

        foreign_reservation_read = client.get(f"/api/checkin/{other_hotel_reservation.id}/guest-arrivals")
        assert foreign_reservation_read.status_code == 404
        unlinked_guest = client.post(f"/api/checkin/{reservation.id}/guests/{foreign_guest.id}")
        assert unlinked_guest.status_code == 400
        assert "no está registrado" in unlinked_guest.json()["detail"]
        assert db.query(ReservationGuestArrival).count() == 0
    finally:
        _close(db, engine)


def test_first_arrival_keeps_assigned_and_ready_room_gate(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, room, guests = _seed_reservation(db, party_size=1, companion_count=0)
        room.housekeeping_status = RoomHousekeepingStatusEnum.DIRTY
        db.flush()
        response = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert response.status_code == 400
        assert "limpia o inspeccionada" in response.json()["detail"]
        assert room.status == RoomStatusEnum.AVAILABLE
        assert db.query(ReservationGuestArrival).filter_by(reservation_id=reservation.id).count() == 0
    finally:
        _close(db, engine)


def test_individual_arrival_requires_checkin_permission(monkeypatch):
    client, db, engine = _test_app()
    monkeypatch.setattr(checkin_service, "hotel_today", lambda *_: date(2026, 3, 1))
    try:
        reservation, room, guests = _seed_reservation(db, party_size=1, companion_count=0)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(user_role="housekeeping")
        response = client.post(f"/api/checkin/{reservation.id}/guests/{guests[0].id}")
        assert response.status_code == 403
        assert room.status == RoomStatusEnum.AVAILABLE
        assert db.query(ReservationGuestArrival).filter_by(reservation_id=reservation.id).count() == 0
    finally:
        _close(db, engine)
