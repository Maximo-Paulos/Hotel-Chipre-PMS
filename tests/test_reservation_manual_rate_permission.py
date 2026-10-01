"""Security gap: any role that can create a reservation (owner, co_owner,
manager, receptionist) could also send a manual total_amount/target_currency
in the POST /api/reservations payload, silently replacing the automatic
Tarifas quote -- the endpoint only gated reservation:create, never checking
who is allowed to override the price. Only owner/co_owner (or a role with an
explicit reservation:manual_rate override) should be able to do this.
"""
from __future__ import annotations

from datetime import date
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.security_audit_log import SecurityAuditLog
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


def _seed_bookable_state(db, hotel_id: int, *, min_adjustment=None, max_adjustment=None):
    db.add(
        HotelConfiguration(
            id=hotel_id,
            owner_email="owner@test.com",
            subscription_active=True,
            manual_rate_min_adjustment_pct=min_adjustment,
            manual_rate_max_adjustment_pct=max_adjustment,
        )
    )
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


def _manual_ota_payload(guest_id: int, category_id: int, **overrides):
    payload = {
        "guest_id": guest_id,
        "category_id": category_id,
        "check_in_date": date(2026, 11, 1).isoformat(),
        "check_out_date": date(2026, 11, 3).isoformat(),
        "channel": "booking",
        "external_id": "BKG-PERMISSION-TEST",
        "total_amount": 391000,
        "target_currency": "ARS",
        "quoted_amount_ars": 391000,
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


def test_co_owner_uses_confirmed_owner_level_manual_rate_access():
    client, db, engine = _build_client()
    try:
        hotel_id = 506
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "co_owner")

        response = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=170.0,
                manual_rate_reason="Acuerdo comercial autorizado",
            ),
        )

        assert response.status_code == 201, response.text
        assert response.json()["total_amount"] == 170.0
        created = db.query(Reservation).filter(Reservation.id == response.json()["id"]).one()
        assert created.manual_rate_scope == "unbounded"
    finally:
        _cleanup_client(db, engine)


def test_manager_uses_bounded_manual_rate_and_needs_owner_policy():
    client, db, engine = _build_client()
    try:
        hotel_id = 502
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=170.0,
                manual_rate_reason="Acuerdo comercial autorizado",
            ),
        )

        assert response.status_code == 422, response.text
        assert "configurar el rango" in response.json()["detail"].lower()
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
            json=_payload(
                guest_id,
                category_id,
                total_amount=250.0,
                target_currency="USD",
                manual_rate_reason="Precio acordado con el huésped",
            ),
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["total_amount"] == 250.0
        assert body["currency_code"] == "USD"
        assert body["manual_rate_reason"] == "Precio acordado con el huésped"
        reservation = db.query(Reservation).filter_by(hotel_id=hotel_id).one()
        assert reservation.manual_rate_scope == "unbounded"
    finally:
        _cleanup_client(db, engine)


def test_manager_can_set_a_direct_rate_inside_owner_configured_bounds():
    client, db, engine = _build_client()
    try:
        hotel_id = 510
        guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=170,
                target_currency="ARS",
                manual_rate_reason="Descuento por estadía de dos noches",
            ),
        )

        assert response.status_code == 201, response.text
        assert response.json()["total_amount"] == 170.0
        assert response.json()["manual_rate_reason"] == "Descuento por estadía de dos noches"
        reservation = db.query(Reservation).filter_by(hotel_id=hotel_id).one()
        assert reservation.manual_rate_scope == "bounded"
        assert reservation.manual_rate_reason == "Descuento por estadía de dos noches"
        pricing_snapshot = json.loads(reservation.pricing_snapshot)
        assert pricing_snapshot["manual_rate"]["scope"] == "bounded"
        assert pricing_snapshot["manual_rate"]["minimum_total"] == "150.00"
        assert pricing_snapshot["manual_rate"]["maximum_total"] == "220.00"
    finally:
        _cleanup_client(db, engine)


@pytest.mark.parametrize("amount", [149.99, 220.01])
def test_manager_cannot_exceed_manual_rate_bounds(amount):
    client, db, engine = _build_client()
    try:
        hotel_id = 511
        guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=amount,
                target_currency="ARS",
                manual_rate_reason="Acuerdo con el huésped",
            ),
        )

        assert response.status_code == 422, response.text
        assert "entre 150.00 y 220.00" in response.json()["detail"]
        assert db.query(Reservation).filter_by(hotel_id=hotel_id).count() == 0
    finally:
        _cleanup_client(db, engine)


def test_manual_rate_requires_reason_and_bounded_rate_keeps_quote_currency():
    client, db, engine = _build_client()
    try:
        hotel_id = 512
        guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        missing_reason = client.post(
            "/api/reservations/",
            json=_payload(guest_id, category_id, total_amount=170, target_currency="ARS"),
        )
        assert missing_reason.status_code == 422, missing_reason.text
        assert "motivo" in missing_reason.json()["detail"].lower()

        wrong_currency = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=170,
                target_currency="USD",
                manual_rate_reason="Acuerdo con el huésped",
            ),
        )
        assert wrong_currency.status_code == 422, wrong_currency.text
        assert "misma moneda" in wrong_currency.json()["detail"].lower()
        assert db.query(Reservation).filter_by(hotel_id=hotel_id).count() == 0
    finally:
        _cleanup_client(db, engine)


def test_bounded_manual_rate_rejects_ota_and_company_reservations():
    client, db, engine = _build_client()
    try:
        hotel_id = 513
        guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/reservations/",
            json=_payload(
                guest_id,
                category_id,
                source="booking",
                total_amount=170,
                target_currency="ARS",
                manual_rate_reason="Precio informado por OTA",
            ),
        )

        assert response.status_code == 422, response.text
        assert "reserva directa" in response.json()["detail"].lower()
        assert db.query(Reservation).filter_by(hotel_id=hotel_id).count() == 0
    finally:
        _cleanup_client(db, engine)


def test_legacy_booking_endpoint_cannot_bypass_bounded_manual_rate_policy():
    client, db, engine = _build_client()
    try:
        hotel_id = 514
        guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")

        response = client.post(
            "/api/bookings/",
            json=_payload(
                guest_id,
                category_id,
                total_amount=170,
                target_currency="ARS",
                manual_rate_reason="Ajuste para cliente recurrente",
            ),
        )

        assert response.status_code == 201, response.text
        reservation = db.query(Reservation).filter_by(hotel_id=hotel_id).one()
        assert reservation.manual_rate_scope == "bounded"
        assert reservation.manual_rate_reason == "Ajuste para cliente recurrente"
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


def test_manual_rate_quote_exposes_limits_only_to_roles_with_bounded_permission():
    client, db, engine = _build_client()
    try:
        hotel_id = 515
        _guest_id, category_id = _seed_bookable_state(
            db, hotel_id, min_adjustment=-25, max_adjustment=10
        )
        quote_params = {
            "category_id": category_id,
            "check_in_date": "2026-11-01",
            "check_out_date": "2026-11-03",
        }

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "manager")
        manager_quote = client.get("/api/bookings/price-quote", params=quote_params)
        assert manager_quote.status_code == 200, manager_quote.text
        assert manager_quote.json()["manual_rate_min_adjustment_pct"] == "-25.00"
        assert manager_quote.json()["manual_rate_max_adjustment_pct"] == "10.00"

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")
        receptionist_quote = client.get("/api/bookings/price-quote", params=quote_params)
        assert receptionist_quote.status_code == 200, receptionist_quote.text
        assert "manual_rate_min_adjustment_pct" not in receptionist_quote.json()
        assert "manual_rate_max_adjustment_pct" not in receptionist_quote.json()
    finally:
        _cleanup_client(db, engine)


def test_owner_can_grant_manager_manual_rate_override():
    client, db, engine = _build_client()
    try:
        hotel_id = 505
        _seed_bookable_state(db, hotel_id)
        set_override(db, hotel_id, "manager", "reservation:manual_rate", True, user_id=1)
    finally:
        _cleanup_client(db, engine)


@pytest.mark.parametrize("role", ["manager", "receptionist"])
def test_manager_and_receptionist_can_record_an_audited_ota_reported_price(role: str):
    client, db, engine = _build_client()
    try:
        hotel_id = 507 if role == "manager" else 508
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, role)

        response = client.post(
            "/api/reservations/manual-ota",
            json=_manual_ota_payload(guest_id, category_id, external_id=f"BKG-{role.upper()}"),
        )

        assert response.status_code == 201, response.text
        assert response.json()["total_amount"] == 391000.0
        assert response.json()["quoted_amount_ars"] == 391000.0
        assert response.json()["amount_paid"] == 0.0
        audit = db.query(SecurityAuditLog).filter_by(
            hotel_id=hotel_id,
            action="ota.manual_reservation.created",
        ).one()
        assert audit.user_id == 1
        assert json.loads(audit.details)["external_id"] == f"BKG-{role.upper()}"
    finally:
        _cleanup_client(db, engine)


def test_receptionist_ota_record_permission_can_be_revoked_without_granting_direct_manual_rate():
    client, db, engine = _build_client()
    try:
        hotel_id = 509
        guest_id, category_id = _seed_bookable_state(db, hotel_id)
        set_override(
            db,
            hotel_id,
            "receptionist",
            "reservation:ota_record",
            False,
            user_id=1,
        )
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(hotel_id, "receptionist")

        response = client.post(
            "/api/reservations/manual-ota",
            json=_manual_ota_payload(guest_id, category_id),
        )

        assert response.status_code == 403, response.text
        assert db.query(SecurityAuditLog).filter_by(
            hotel_id=hotel_id,
            user_id=1,
            action="permission.denied",
        ).count() == 1
    finally:
        _cleanup_client(db, engine)
