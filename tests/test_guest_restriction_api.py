from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.guest_restriction import GuestRestriction
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
from app.models.user import User


def _auth(hotel_id: int, role: str, user_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}-{user_id}@example.test",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=7201, subscription_active=True),
            HotelConfiguration(id=7202, subscription_active=True),
            User(id=201, email="owner-7201@example.test", password_hash="synthetic", is_verified=True),
            User(id=202, email="reception-7201@example.test", password_hash="synthetic", is_verified=True),
            User(id=203, email="housekeeping-7201@example.test", password_hash="synthetic", is_verified=True),
            User(id=204, email="owner-7202@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=7201, user_id=201, role="owner", status="active"),
            HotelMembership(hotel_id=7201, user_id=202, role="receptionist", status="active"),
            HotelMembership(hotel_id=7201, user_id=203, role="housekeeping", status="active"),
            HotelMembership(hotel_id=7202, user_id=204, role="owner", status="active"),
        ]
    )
    guest_a = Guest(
        hotel_id=7201,
        first_name="API",
        last_name="Guest A",
        document_type="DNI",
        document_number="API-A",
        phone="0000000000",
        terms_accepted=True,
        birth_place="Buenos Aires",
        birth_country="Argentina",
        marital_status="single",
        occupation="Tester",
    )
    guest_b = Guest(
        hotel_id=7202,
        first_name="API",
        last_name="Guest B",
        document_type="DNI",
        document_number="API-B",
        phone="0000000000",
        terms_accepted=True,
    )
    category = RoomCategory(
        hotel_id=7201,
        name="Standard",
        code="API-STD",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all([guest_a, guest_b, category])
    db.flush()
    room = Room(
        hotel_id=7201,
        category_id=category.id,
        room_number="101",
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add(room)
    db.flush()
    reservation = Reservation(
        hotel_id=7201,
        guest_id=guest_a.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="API-CHECKIN",
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=1),
        total_amount=Decimal("100.00"),
        amount_paid=Decimal("100.00"),
        num_adults=1,
        status=ReservationStatusEnum.FULLY_PAID,
    )
    db.add(reservation)
    db.commit()

    def override_db():
        yield db

    fastapi_app.dependency_overrides[get_db] = override_db
    return TestClient(fastapi_app), db, engine, guest_a, guest_b, category, room, reservation


def test_restriction_api_permissions_tenant_isolation_and_event(monkeypatch):
    client, db, engine, guest_a, guest_b, _, _, reservation = _client()
    published: list[dict] = []

    def capture_event(**kwargs):
        published.append(kwargs)
        return None

    monkeypatch.setattr("app.services.domain_events.publish_domain_event", capture_event)
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "owner", 201)
        created = client.post(
            f"/api/guests/{guest_a.id}/restrictions",
            json={"reason": "Internal restriction", "detail": "Never public"},
        )
        assert created.status_code == 201
        restriction_id = created.json()["id"]
        assert reservation.status is ReservationStatusEnum.FULLY_PAID
        assert reservation.requires_manual_review is True
        restriction_events = [
            event for event in published if event["event_type"] == "guest.restriction.created"
        ]
        assert restriction_events
        restriction_event = restriction_events[-1]
        assert "reason" not in restriction_event["payload"]
        assert "detail" not in restriction_event["payload"]

        fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "receptionist", 202)
        readable = client.get(f"/api/guests/{guest_a.id}/restrictions", params={"active_only": True})
        assert readable.status_code == 200
        assert readable.json()[0]["reason"] == "Internal restriction"
        assert client.post(
            f"/api/guests/{guest_a.id}/restrictions",
            json={"reason": "Not permitted"},
        ).status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "housekeeping", 203)
        assert client.get(f"/api/guests/{guest_a.id}/restrictions").status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _auth(7202, "owner", 204)
        cross_hotel = client.post(
            f"/api/guests/{guest_b.id}/restrictions/{restriction_id}/resolve",
            json={"resolution_note": "Cross hotel"},
        )
        assert cross_hotel.status_code == 404
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override():
    client, db, engine, guest, _, category, room, _ = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "owner", 201)
    try:
        created = client.post(
            f"/api/guests/{guest.id}/restrictions",
            json={"reason": "Private reason", "detail": "Private detail"},
        )
        assert created.status_code == 201
        restriction_id = created.json()["id"]

        quote = client.get(
            "/api/bookings/price-quote",
            params={
                "guest_id": guest.id,
                "category_id": category.id,
                "check_in_date": (date.today() + timedelta(days=10)).isoformat(),
                "check_out_date": (date.today() + timedelta(days=12)).isoformat(),
            },
        )
        assert quote.status_code == 409
        assert quote.json()["detail"]["code"] == "GUEST_PROHIBITED"
        assert "Private reason" not in quote.text
        assert "Private detail" not in quote.text

        payload = {
            "guest_id": guest.id,
            "category_id": category.id,
            "room_id": room.id,
            "check_in_date": (date.today() + timedelta(days=10)).isoformat(),
            "check_out_date": (date.today() + timedelta(days=12)).isoformat(),
            "total_amount": "200.00",
        }
        blocked = client.post("/api/reservations", json=payload)
        assert blocked.status_code == 409
        assert blocked.json()["detail"] == {
            "code": "GUEST_PROHIBITED",
            "message": "Guest has an active lodging restriction",
            "restriction_id": restriction_id,
        }
        assert "Private reason" not in blocked.text
        assert "Private detail" not in blocked.text

        allowed = client.post(
            "/api/reservations",
            json={
                **payload,
                "restriction_override": {
                    "restriction_id": restriction_id,
                    "reason": "Owner reviewed the restriction",
                },
            },
        )
        assert allowed.status_code == 201
        audit = db.query(SecurityAuditLog).filter_by(action="guest.restriction.override").one()
        details = json.loads(audit.details)
        assert details["reservation_id"] == allowed.json()["id"]
        assert details["restriction_id"] == restriction_id
        assert details["actor_user_id"] == 201
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_checkin_reuses_explicit_override_contract_and_never_discloses_reason():
    client, db, engine, guest, _, _, _, reservation = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "owner", 201)
    try:
        created = client.post(
            f"/api/guests/{guest.id}/restrictions",
            json={"reason": "Private check-in reason", "detail": "Private check-in detail"},
        )
        restriction_id = created.json()["id"]

        blocked = client.post(f"/api/checkin/{reservation.id}", json={})
        assert blocked.status_code == 409
        assert blocked.json()["detail"]["code"] == "GUEST_PROHIBITED"
        assert "Private check-in reason" not in blocked.text
        assert "Private check-in detail" not in blocked.text

        fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "receptionist", 202)
        denied = client.post(
            f"/api/checkin/{reservation.id}",
            json={
                "restriction_override": {
                    "restriction_id": restriction_id,
                    "reason": "Reception attempted override",
                }
            },
        )
        assert denied.status_code == 403
        assert reservation.status is ReservationStatusEnum.FULLY_PAID

        fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "owner", 201)
        allowed = client.post(
            f"/api/checkin/{reservation.id}",
            json={
                "restriction_override": {
                    "restriction_id": restriction_id,
                    "reason": "Owner accepted responsibility",
                }
            },
        )
        assert allowed.status_code == 200
        assert allowed.json()["status"] == "checked_in"
        audit = db.query(SecurityAuditLog).filter_by(action="guest.restriction.override").one()
        assert json.loads(audit.details)["operation"] == "checkin"
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_restriction_override_reason_rejects_whitespace():
    client, db, engine, guest, _, category, room, _ = _client()
    fastapi_app.dependency_overrides[get_auth_context] = _auth(7201, "owner", 201)
    try:
        restriction = client.post(
            f"/api/guests/{guest.id}/restrictions",
            json={"reason": "Private reason"},
        ).json()
        response = client.post(
            "/api/reservations",
            json={
                "guest_id": guest.id,
                "category_id": category.id,
                "room_id": room.id,
                "check_in_date": (date.today() + timedelta(days=10)).isoformat(),
                "check_out_date": (date.today() + timedelta(days=12)).isoformat(),
                "total_amount": "200.00",
                "restriction_override": {"restriction_id": restriction["id"], "reason": "   "},
            },
        )
        assert response.status_code == 422
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
