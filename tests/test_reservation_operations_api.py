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
from app.models.operations import ReservationAdjustment, ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum
from app.models.ota_core import OTAProvider, OTAReservationLink, OTAReservationLifecycleEnum
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum


def _override_auth(hotel_id: int, role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=1,
            user_email="owner@test.com",
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


def _seed_operational_state(db, hotel_id: int, suffix: str):
    db.add(HotelConfiguration(id=hotel_id, owner_email=f"owner-{suffix}@test.com", subscription_active=True))
    guest = Guest(first_name=f"Guest {suffix}", last_name="Test", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {suffix}",
        code=f"STD_{suffix}",
        base_price_per_night=100.0,
        max_occupancy=2,
    )
    room = Room(
        hotel_id=hotel_id,
        room_number=f"{hotel_id}01",
        floor=1,
        category=category,
        status=RoomStatusEnum.AVAILABLE,
    )
    db.add_all([guest, category, room])
    db.flush()

    reservation = Reservation(
        confirmation_code=f"OPS-{suffix}",
        hotel_id=hotel_id,
        guest_id=guest.id,
        room_id=None,
        category_id=category.id,
        check_in_date=date(2026, 10, 1),
        check_out_date=date(2026, 10, 3),
        total_amount=200.0,
        subtotal_amount=200.0,
        net_amount=200.0,
        amount_paid=0.0,
        deposit_amount=60.0,
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
        source=ReservationSourceEnum.BOOKING,
        source_provider_code="booking",
        external_id=f"booking-{suffix}",
        num_adults=2,
        num_children=0,
        requires_manual_review=True,
        allocation_status="manual_review",
        payment_collection_model="ota_prepaid",
        settlement_status="manual_resolution_required",
    )
    db.add(reservation)
    db.flush()

    provider = OTAProvider(code=f"booking_{suffix}", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    db.add(provider)
    db.flush()
    link = OTAReservationLink(
        hotel_id=hotel_id,
        provider_id=provider.id,
        reservation_id=reservation.id,
        external_reservation_id=f"booking-{suffix}",
        provider_state=OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED,
        sync_status="manual_resolution_required",
        error_message="Cancelar en canal",
    )
    db.add(link)
    db.flush()

    adjustment = ReservationAdjustment(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        ota_reservation_link_id=link.id,
        kind=ReservationAdjustmentKindEnum.OTA_CANCEL_AND_REBOOK,
        status=ReservationAdjustmentStatusEnum.APPLIED,
        reason_code="ota_rebook_direct",
        request_source="hotel",
        notes="Pendiente cancelar en OTA",
        amount_delta=90.0,
        currency_code="ARS",
        external_resolution_status="pending_hotel_action",
    )
    db.add(adjustment)
    db.commit()
    return reservation


def test_reservation_operations_summary_endpoint_exposes_pending_operational_actions():
    client, db, engine = _build_client()
    try:
        reservation = _seed_operational_state(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

        resp = client.get(f"/api/reservations/{reservation.id}/operations-summary")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["reservation_id"] == reservation.id
        codes = {item["code"] for item in body["pending_actions"]}
        assert "manual_review_required" in codes
        assert "resolve_external_channel" in codes
        assert "resolve_adjustment_external_action" in codes
        assert body["ota_link"]["provider_state"] == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED.value
    finally:
        _cleanup_client(db, engine)


def test_pending_actions_endpoint_is_hotel_scoped():
    client, db, engine = _build_client()
    try:
        reservation_h1 = _seed_operational_state(db, 1, "H1")
        _seed_operational_state(db, 2, "H2")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")

        resp = client.get("/api/reservations/actions/pending")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body
        assert {item["reservation_id"] for item in body} == {reservation_h1.id}
        assert all(item["priority"] in {"critical", "high", "medium", "low"} for item in body)
    finally:
        _cleanup_client(db, engine)


def test_reservation_operations_resolution_endpoints_close_followups():
    client, db, engine = _build_client()
    try:
        reservation = _seed_operational_state(db, 1, "H1")
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        clear_review_resp = client.post(
            f"/api/reservations/{reservation.id}/operations/clear-manual-review",
            json={"notes": "Recepcion valido el caso"},
        )
        assert clear_review_resp.status_code == 200, clear_review_resp.text
        assert clear_review_resp.json()["requires_manual_review"] is False

        resolve_external_resp = client.post(
            f"/api/reservations/{reservation.id}/operations/resolve-external",
            json={"notes": "Cancelado manualmente en Booking"},
        )
        assert resolve_external_resp.status_code == 200, resolve_external_resp.text
        body = resolve_external_resp.json()
        assert body["ota_link_resolved"] is True
        assert body["settlement_status"] == "resolved"

        summary_resp = client.get(f"/api/reservations/{reservation.id}/operations-summary")
        assert summary_resp.status_code == 200, summary_resp.text
        summary = summary_resp.json()
        assert "manual_review_required" not in {item["code"] for item in summary["pending_actions"]}
        assert summary["settlement_status"] == "resolved"
        assert summary["ota_link"]["sync_status"] == "resolved"
    finally:
        _cleanup_client(db, engine)
