from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.api import checkin as checkin_api
from app.api import bookings as bookings_api
from app.services import reservation_service
from app.services.reservation_service import ReservationPricingResult
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.daily_rate import DailyRate
from app.models.laundry import LaundryBatch
from app.models.operations import ReservationStatusHistory
from app.models.payment import PaymentLink
from app.models.audit_log import AuditLog
from app.models.commercial import SellableProduct
from app.models.company import Company
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.stock import StockItem
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.reservation import ReservationUpdate
from app.services.permission_service import set_role_override, set_user_override


def _client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    db.add(HotelConfiguration(id=1, hotel_name="RBAC routes", subscription_active=True))
    db.add_all(
        [
            User(id=10, email="owner-routes@example.test", password_hash="synthetic", is_verified=True),
            User(id=20, email="reception-routes@example.test", password_hash="synthetic", is_verified=True),
            User(id=30, email="manager-routes@example.test", password_hash="synthetic", is_verified=True),
        ]
    )
    db.flush()
    db.add_all(
        [
            HotelMembership(hotel_id=1, user_id=10, role="owner", status="active"),
            HotelMembership(hotel_id=1, user_id=20, role="receptionist", status="active"),
            HotelMembership(hotel_id=1, user_id=30, role="manager", status="active"),
        ]
    )
    category = RoomCategory(
        hotel_id=1, name="Standard", code="STD", base_price_per_night=Decimal("100.00"), max_occupancy=2
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=1, category_id=category.id, room_number="101", floor=1, status=RoomStatusEnum.AVAILABLE
    )
    guest = Guest(hotel_id=1, first_name="Ana", last_name="RBAC")
    db.add_all([room, guest])
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="RBAC-ROUTE-1",
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=2),
        status=ReservationStatusEnum.PENDING,
        total_amount=Decimal("200.00"),
        num_adults=1,
    )
    stock_item = StockItem(hotel_id=1, name="Soap", unit="unit", active=True)
    db.add_all([reservation, stock_item])
    db.commit()

    auth = {"user_id": 20, "role": "receptionist"}

    def override_db():
        yield db

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=auth["user_id"],
            user_email="synthetic@example.test",
            user_role=auth["role"],
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    return TestClient(fastapi_app), db, engine, auth, reservation, stock_item


def _close(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _patch_legacy_booking(client, reservation, payload):
    versioned_payload = dict(payload)
    versioned_payload.setdefault("client_version", reservation.version)
    return client.patch(f"/api/bookings/{reservation.id}", json=versioned_payload)


def test_daily_rate_snapshot_retains_original_pricing_channel():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        check_in = date.today() + timedelta(days=15)
        pricing = reservation_service.calculate_reservation_pricing(
            db,
            category_id=reservation.category_id,
            check_in=check_in,
            check_out=check_in + timedelta(days=2),
            hotel_id=1,
            pricing_channel_code="website_direct",
            occupancy=1,
        )

        import json

        snapshot = json.loads(pricing.pricing_snapshot)
        assert pricing.pricing_source == "daily_rates"
        assert snapshot["pricing_channel_code"] == "website_direct"
    finally:
        _close(db, engine)


def test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak():
    client, db, engine, auth, reservation, _stock_item = _client()
    try:
        assert client.get("/api/reservations/").status_code == 200
        set_user_override(db, 1, 20, "receptionist", "reservation:read", False, actor_user_id=10)
        db.commit()

        denied_list = client.get("/api/reservations/")
        denied_detail = client.get(f"/api/reservations/{reservation.id}")
        assert denied_list.status_code == denied_detail.status_code == 403
        assert "RBAC-ROUTE-1" not in denied_list.text
        assert "RBAC-ROUTE-1" not in denied_detail.text

        set_user_override(db, 1, 20, "receptionist", "reservation:read", True, actor_user_id=10)
        set_user_override(db, 1, 20, "receptionist", "reservation:update", False, actor_user_id=10)
        db.commit()
        denied_update = client.patch(f"/api/reservations/{reservation.id}", json={"notes": "must not persist"})
        assert denied_update.status_code == 403
        db.refresh(reservation)
        assert reservation.notes is None

        set_user_override(db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10)
        db.commit()
        allowed_update = client.patch(
            f"/api/reservations/{reservation.id}",
            json={"notes": "allowed", "client_version": reservation.version},
        )
        assert allowed_update.status_code == 200
        db.refresh(reservation)
        assert reservation.notes == "allowed"

        set_user_override(db, 1, 20, "receptionist", "reservation:cancel", False, actor_user_id=10)
        db.commit()
        denied_cancel = client.post(f"/api/reservations/{reservation.id}/cancel")
        assert denied_cancel.status_code == 403
        db.refresh(reservation)
        assert reservation.status == ReservationStatusEnum.PENDING

        set_user_override(db, 1, 20, "receptionist", "reservation:cancel", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/reservations/{reservation.id}/cancel").status_code == 200
    finally:
        _close(db, engine)


def test_primary_reservation_patch_requires_version_and_skips_noop_audits():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        set_user_override(
            db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10
        )
        db.commit()
        original_version = reservation.version
        audit_count = db.query(AuditLog).filter_by(
            table_name="reservations", record_id=reservation.id
        ).count()

        noop = client.patch(f"/api/reservations/{reservation.id}", json={})
        assert noop.status_code == 200, noop.text
        db.refresh(reservation)
        assert reservation.version == original_version
        assert db.query(AuditLog).filter_by(
            table_name="reservations", record_id=reservation.id
        ).count() == audit_count

        missing_version = client.patch(
            f"/api/reservations/{reservation.id}", json={"notes": "must not persist"}
        )
        assert missing_version.status_code == 428, missing_version.text
        db.refresh(reservation)
        assert reservation.notes is None
        assert reservation.version == original_version

        stale_version = client.patch(
            f"/api/reservations/{reservation.id}",
            json={"notes": "must not persist", "client_version": original_version - 1},
        )
        assert stale_version.status_code == 409, stale_version.text
        db.refresh(reservation)
        assert reservation.notes is None
        assert reservation.version == original_version

        updated = client.patch(
            f"/api/reservations/{reservation.id}",
            json={"notes": "versioned update", "client_version": original_version},
        )
        assert updated.status_code == 200, updated.text
        db.refresh(reservation)
        assert reservation.notes == "versioned update"
        assert reservation.version == original_version + 1
    finally:
        _close(db, engine)


def test_reservation_update_rechecks_version_from_database_not_stale_orm_object():
    _client_app, db, engine, _auth, reservation, _stock_item = _client()
    try:
        original_version = reservation.version
        db.query(Reservation).filter(Reservation.id == reservation.id).update(
            {Reservation.version: Reservation.version + 1},
            synchronize_session=False,
        )

        with pytest.raises(reservation_service.ReservationVersionConflict):
            reservation_service.update_reservation_fields(
                db,
                reservation,
                ReservationUpdate(notes="must not persist"),
                hotel_id=1,
                client_version=original_version,
            )

        db.refresh(reservation)
        assert reservation.version == original_version + 1
        assert reservation.notes is None
    finally:
        _close(db, engine)


def test_reservation_extension_requires_update_charge_and_cash_permissions_independently():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        request = {
            "new_checkout_date": (date.today() + timedelta(days=3)).isoformat(),
            "client_version": reservation.version,
            "pricing_mode": "original_average",
            "payment_action": "payment_link",
            "payment_link": {
                "reservation_id": reservation.id,
                "requested_amount": "100.00",
                "recipient_email": "guest@example.com",
            },
        }
        for permission in ("reservation:update", "reservation:charge", "cash:operate"):
            set_user_override(
                db, 1, 20, "receptionist", permission, False, actor_user_id=10
            )
            db.commit()

            denied = client.post(f"/api/reservations/{reservation.id}/extend", json=request)

            assert denied.status_code == 403, (permission, denied.text)
            db.refresh(reservation)
            assert reservation.check_out_date == date.today() + timedelta(days=2)
            assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0

            set_user_override(
                db, 1, 20, "receptionist", permission, True, actor_user_id=10
            )
            db.commit()

        reservation.status = ReservationStatusEnum.FULLY_PAID
        reservation.amount_paid = reservation.total_amount
        db.commit()

        allowed = client.post(f"/api/reservations/{reservation.id}/extend", json=request)

        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["payment_link"]["reservation_id"] == reservation.id
        assert db.query(AuditLog).filter_by(
            table_name="reservations", record_id=reservation.id
        ).count() >= 1
    finally:
        _close(db, engine)


def test_legacy_booking_patch_rejects_status_changes_but_preserves_field_updates():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        set_user_override(
            db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:cancel", False, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "checkin:perform", False, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "checkout:perform", False, actor_user_id=10
        )
        db.commit()

        ordinary_update = _patch_legacy_booking(
            client, reservation, {"notes": "front-desk note"}
        )
        assert ordinary_update.status_code == 200, ordinary_update.text
        db.refresh(reservation)
        assert reservation.notes == "front-desk note"
        assert reservation.status == ReservationStatusEnum.PENDING

        for current_status, requested_status in (
            (ReservationStatusEnum.PENDING, ReservationStatusEnum.FULLY_PAID),
            (ReservationStatusEnum.PENDING, ReservationStatusEnum.CANCELLED),
            (ReservationStatusEnum.FULLY_PAID, ReservationStatusEnum.CHECKED_IN),
            (ReservationStatusEnum.CHECKED_IN, ReservationStatusEnum.CHECKED_OUT),
        ):
            reservation.status = current_status
            db.commit()
            denied = _patch_legacy_booking(
                client, reservation, {"status": requested_status.value}
            )
            assert denied.status_code == 400, denied.text
            db.refresh(reservation)
            assert reservation.status == current_status

        assert reservation.amount_paid == 0
        assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    finally:
        _close(db, engine)


def test_legacy_booking_room_assignment_requires_move_permission():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        target_room = Room(
            hotel_id=1,
            category_id=reservation.category_id,
            room_number="102",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        db.flush()
        set_user_override(
            db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", False, actor_user_id=10
        )
        db.commit()

        denied = _patch_legacy_booking(client, reservation, {"room_id": target_room.id})

        assert denied.status_code == 403, denied.text
        db.refresh(reservation)
        assert reservation.room_id != target_room.id

        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", True, actor_user_id=10
        )
        db.commit()
        allowed = _patch_legacy_booking(client, reservation, {"room_id": target_room.id})
        assert allowed.status_code == 200, allowed.text
        db.refresh(reservation)
        assert reservation.room_id == target_room.id
    finally:
        _close(db, engine)


@pytest.mark.parametrize("target_capacity", [2, 4])
@pytest.mark.parametrize("include_room_id", [False, True])
def test_legacy_booking_category_change_cannot_bypass_move_permission_tier(target_capacity, include_room_id):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.room_id = None
        target_category = RoomCategory(
            hotel_id=1,
            name=f"Target {target_capacity}",
            code=f"TGT{target_capacity}",
            base_price_per_night=Decimal("150.00"),
            max_occupancy=target_capacity,
        )
        db.add(target_category)
        db.flush()
        target_room = Room(
            hotel_id=1,
            category_id=target_category.id,
            room_number=f"20{target_capacity}",
            floor=2,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", True, actor_user_id=10
        )
        for permission in ("reservation:move_category", "reservation:move_capacity"):
            set_user_override(
                db, 1, 20, "receptionist", permission, False, actor_user_id=10
            )
        db.commit()

        payload = {"category_id": target_category.id}
        if include_room_id:
            payload["room_id"] = target_room.id
        denied = _patch_legacy_booking(client, reservation, payload)

        assert denied.status_code == 403, denied.text
        db.refresh(reservation)
        assert reservation.category_id != target_category.id
        assert reservation.room_id is None
    finally:
        _close(db, engine)


def test_legacy_booking_pricing_error_rolls_back_pending_field_mutations(monkeypatch):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        original_check_in = reservation.check_in_date
        original_check_out = reservation.check_out_date
        original_version = reservation.version
        reservation.pricing_snapshot = '{"pricing_source":"daily_rates"}'
        db.commit()

        def reject_pricing(*args, **kwargs):
            raise bookings_api.ReservationError("pricing unavailable")

        monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", reject_pricing)
        response = _patch_legacy_booking(
            client,
            reservation,
            {"check_in_date": (original_check_in + timedelta(days=1)).isoformat()},
        )

        assert response.status_code == 400, response.text
        db.refresh(reservation)
        assert reservation.check_in_date == original_check_in
        assert reservation.check_out_date == original_check_out
        assert reservation.version == original_version
    finally:
        _close(db, engine)


@pytest.mark.parametrize(("target_capacity", "expected_status"), [(2, 200), (4, 403)])
def test_legacy_booking_move_tier_distinguishes_category_from_capacity(
    target_capacity, expected_status
):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.room_id = None
        target_category = RoomCategory(
            hotel_id=1,
            name=f"Tier target {target_capacity}",
            code=f"TIER{target_capacity}",
            base_price_per_night=Decimal("150.00"),
            max_occupancy=target_capacity,
        )
        db.add(target_category)
        db.flush()
        target_room = Room(
            hotel_id=1,
            category_id=target_category.id,
            room_number=f"30{target_capacity}",
            floor=3,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move_category", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move_capacity", False, actor_user_id=10
        )
        db.commit()

        response = _patch_legacy_booking(
            client, reservation, {"category_id": target_category.id, "room_id": target_room.id}
        )

        assert response.status_code == expected_status, response.text
        db.refresh(reservation)
        if expected_status == 200:
            assert reservation.category_id == target_category.id
            assert reservation.room_id == target_room.id
        else:
            assert reservation.category_id != target_category.id
            assert reservation.room_id is None
    finally:
        _close(db, engine)


def test_legacy_booking_category_only_patch_uses_commercial_pricing_context(monkeypatch):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.room_id = None
        reservation.currency_code = "USD"
        reservation.source_provider_code = "booking"
        target_category = RoomCategory(
            hotel_id=1,
            name="Category-only target",
            code="CATONLY",
            base_price_per_night=Decimal("150.00"),
            max_occupancy=2,
        )
        db.add(target_category)
        reservation.pricing_snapshot = (
            '{"pricing_source":"daily_rates","payment_method":"card",'
            '"pricing_channel_code":"website_direct"}'
        )
        db.flush()
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move_category", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move_capacity", False, actor_user_id=10
        )
        db.commit()

        pricing_context = {}
        pricing = ReservationPricingResult(
            nights=2,
            nightly_rate=123.0,
            total_amount=246.0,
            deposit_amount=73.8,
            subtotal_amount=200.0,
            tax_amount=46.0,
            fee_amount=2.0,
            commission_amount=4.0,
            net_amount=194.0,
            currency_code="USD",
            fx_rate_snapshot=1.0,
            pricing_source="rate_plan_quote",
            sellable_product_id=None,
            rate_plan_id=None,
            tax_policy_id=None,
            pricing_snapshot='{"source":"canonical-test"}',
        )

        def calculate_pricing(_db, **kwargs):
            pricing_context.update(kwargs)
            return pricing

        monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", calculate_pricing)
        response = _patch_legacy_booking(
            client, reservation, {"category_id": target_category.id, "num_adults": 2}
        )

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.category_id == target_category.id
        assert pricing_context["category_id"] == target_category.id
        assert pricing_context["hotel_id"] == 1
        assert pricing_context["pricing_channel_code"] == "website_direct"
        assert pricing_context["pricing_payment_method"] == "card"
        assert pricing_context["target_currency"] == "USD"
        assert pricing_context["occupancy"] == reservation.num_adults + reservation.num_children
        assert reservation.total_amount == Decimal("246.0")
        assert reservation.tax_amount == Decimal("46.0")
        assert reservation.fee_amount == Decimal("2.0")
        assert reservation.commission_amount == Decimal("4.0")
        assert reservation.net_amount == Decimal("194.0")
        assert reservation.currency_code == "USD"
        assert reservation.pricing_snapshot == '{"source":"canonical-test"}'
    finally:
        _close(db, engine)


def test_legacy_booking_noop_dates_and_category_do_not_reprice(monkeypatch):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        original_total = reservation.total_amount
        original_dates = (reservation.check_in_date, reservation.check_out_date)
        original_version = reservation.version
        audit_count = db.query(AuditLog).filter_by(table_name="reservations", record_id=reservation.id).count()

        def unexpected_pricing(*_args, **_kwargs):
            raise AssertionError("No-op reservation fields must not reprice the booking")

        monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", unexpected_pricing)
        response = client.patch(
            f"/api/bookings/{reservation.id}",
            json={
                "category_id": reservation.category_id,
                "check_in_date": original_dates[0].isoformat(),
                "check_out_date": original_dates[1].isoformat(),
            },
        )

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.total_amount == original_total
        assert (reservation.check_in_date, reservation.check_out_date) == original_dates
        assert reservation.version == original_version
        assert db.query(AuditLog).filter_by(table_name="reservations", record_id=reservation.id).count() == audit_count
    finally:
        _close(db, engine)


def test_legacy_booking_empty_patch_is_a_read_only_noop():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        original_version = reservation.version
        audit_count = db.query(AuditLog).filter_by(table_name="reservations", record_id=reservation.id).count()

        response = client.patch(f"/api/bookings/{reservation.id}", json={})

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.version == original_version
        assert db.query(AuditLog).filter_by(table_name="reservations", record_id=reservation.id).count() == audit_count
    finally:
        _close(db, engine)


def test_legacy_booking_mutations_require_current_client_version():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        original_version = reservation.version

        missing_version = client.patch(
            f"/api/bookings/{reservation.id}", json={"notes": "must not persist"}
        )
        assert missing_version.status_code == 428, missing_version.text
        db.refresh(reservation)
        assert reservation.notes is None
        assert reservation.version == original_version

        stale_version = client.patch(
            f"/api/bookings/{reservation.id}",
            json={"notes": "must not persist", "client_version": original_version - 1},
        )
        assert stale_version.status_code == 409, stale_version.text
        db.refresh(reservation)
        assert reservation.notes is None
        assert reservation.version == original_version
    finally:
        _close(db, engine)


@pytest.mark.parametrize("route", ["/api/bookings", "/api/reservations"])
@pytest.mark.parametrize(
    ("pricing_snapshot", "total", "currency"),
    [
        (None, Decimal("200.00"), "ARS"),
        (
            '{"pricing_source":"manual_total_override","nightly_rate":125.0,'
            '"nights":2,"total_amount":250.0}',
            Decimal("250.00"),
            "USD",
        ),
    ],
)
def test_generic_date_edit_preserves_negotiated_and_unclassified_totals(
    monkeypatch, route, pricing_snapshot, total, currency
):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.total_amount = total
        reservation.subtotal_amount = total
        reservation.net_amount = total
        reservation.currency_code = currency
        reservation.pricing_snapshot = pricing_snapshot
        db.commit()
        new_checkout = reservation.check_out_date + timedelta(days=1)

        def unexpected_pricing(*_args, **_kwargs):
            raise AssertionError("Generic edits must preserve an explicitly negotiated total")

        monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", unexpected_pricing)
        payload = {"check_out_date": new_checkout.isoformat()}
        if route == "/api/bookings":
            response = _patch_legacy_booking(client, reservation, payload)
        else:
            response = client.patch(
                f"{route}/{reservation.id}",
                json={**payload, "client_version": reservation.version},
            )

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.check_out_date == new_checkout
        assert reservation.total_amount == total
        assert reservation.currency_code == currency
        assert reservation.pricing_snapshot == pricing_snapshot
    finally:
        _close(db, engine)


def test_generic_date_edit_preserves_booked_company_base_rate(monkeypatch):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        company = Company(
            hotel_id=1,
            legal_name="Acme Hotels LLC",
            display_name="Acme Hotels",
            base_price=Decimal("225.00"),
            is_active=True,
        )
        db.add(company)
        db.flush()
        reservation.company_id = company.id
        reservation.total_amount = Decimal("350.00")
        reservation.subtotal_amount = Decimal("350.00")
        reservation.net_amount = Decimal("350.00")
        reservation.currency_code = "USD"
        reservation.pricing_snapshot = (
            '{"pricing_source":"company_base_price","company_id":'
            f'{company.id},"nightly_rate":175.0,"nights":2,"total_amount":350.0' + "}"
        )
        db.commit()
        new_checkout = reservation.check_out_date + timedelta(days=1)

        def unexpected_pricing(*_args, **_kwargs):
            raise AssertionError("A generic edit must preserve the booked corporate base rate")

        monkeypatch.setattr(reservation_service, "calculate_reservation_pricing", unexpected_pricing)
        response = client.patch(
            f"/api/reservations/{reservation.id}",
            json={"check_out_date": new_checkout.isoformat(), "client_version": reservation.version},
        )

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.company_id == company.id
        assert reservation.check_out_date == new_checkout
        assert reservation.total_amount == Decimal("350.00")
        assert reservation.currency_code == "USD"
        assert reservation.pricing_snapshot.endswith('"total_amount":350.0}')
    finally:
        _close(db, engine)


def test_legacy_booking_category_change_rejects_occupancy_over_target_capacity():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        source_category = RoomCategory(
            hotel_id=1,
            name="Family source",
            code="FAMSRC",
            base_price_per_night=Decimal("180.00"),
            max_occupancy=4,
        )
        target_category = RoomCategory(
            hotel_id=1,
            name="Small target",
            code="SMALL",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        db.add_all([source_category, target_category])
        db.flush()
        reservation.category_id = source_category.id
        reservation.room_id = None
        reservation.num_adults = 2
        reservation.num_children = 1
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move_capacity", True, actor_user_id=10
        )
        db.commit()

        response = _patch_legacy_booking(
            client, reservation, {"category_id": target_category.id}
        )

        assert response.status_code == 400, response.text
        assert "hasta 2" in response.text
        db.refresh(reservation)
        assert reservation.category_id == source_category.id
        assert reservation.num_adults + reservation.num_children == 3
    finally:
        _close(db, engine)


@pytest.mark.parametrize(("allow_category_move", "expected_status"), [(False, 403), (True, 400)])
def test_category_product_compatibility_is_checked_after_permission(
    allow_category_move, expected_status
):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.room_id = None
        source_category_id = reservation.category_id
        target_category = RoomCategory(
            hotel_id=1,
            name="Commercially incompatible target",
            code="COMM-INCOMPAT",
            base_price_per_night=Decimal("150.00"),
            max_occupancy=2,
        )
        product = SellableProduct(
            hotel_id=1,
            primary_room_category_id=source_category_id,
            code="SOURCE-CATEGORY-ONLY",
            name="Source category only",
            min_occupancy=1,
            max_occupancy=2,
            is_active=True,
        )
        db.add_all([target_category, product])
        db.flush()
        reservation.sellable_product_id = product.id
        set_user_override(
            db,
            1,
            20,
            "receptionist",
            "reservation:move_category",
            allow_category_move,
            actor_user_id=10,
        )
        db.commit()

        response = _patch_legacy_booking(
            client, reservation, {"category_id": target_category.id}
        )

        assert response.status_code == expected_status, response.text
        db.refresh(reservation)
        assert reservation.category_id == source_category_id
    finally:
        _close(db, engine)


def test_legacy_booking_domain_error_during_room_move_returns_400(monkeypatch):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        target_room = Room(
            hotel_id=1,
            category_id=reservation.category_id,
            room_number="102",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        db.flush()
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", True, actor_user_id=10
        )
        db.commit()
        original_room_id = reservation.room_id

        def reject_move(*_args, **_kwargs):
            raise bookings_api.ReservationOperationsError("room category context unavailable")

        monkeypatch.setattr(bookings_api, "enforce_room_move_permission", reject_move)
        response = _patch_legacy_booking(client, reservation, {"room_id": target_room.id})

        assert response.status_code == 400, response.text
        assert "room category context unavailable" in response.text
        db.refresh(reservation)
        assert reservation.room_id == original_room_id
    finally:
        _close(db, engine)


def test_legacy_booking_date_change_checks_destination_room_not_old_room():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        target_room = Room(
            hotel_id=1,
            category_id=reservation.category_id,
            room_number="103",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        db.flush()
        new_check_in = reservation.check_out_date + timedelta(days=2)
        new_check_out = new_check_in + timedelta(days=2)
        blocking_reservation = Reservation(
            hotel_id=1,
            guest_id=reservation.guest_id,
            category_id=reservation.category_id,
            room_id=reservation.room_id,
            confirmation_code="OLD-ROOM-BLOCK",
            check_in_date=new_check_in,
            check_out_date=new_check_out,
            status=ReservationStatusEnum.PENDING,
            total_amount=Decimal("200.00"),
            num_adults=1,
        )
        db.add(blocking_reservation)
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", True, actor_user_id=10
        )
        db.commit()

        response = _patch_legacy_booking(
            client,
            reservation,
            {
                "room_id": target_room.id,
                "check_in_date": new_check_in.isoformat(),
                "check_out_date": new_check_out.isoformat(),
            },
        )

        assert response.status_code == 200, response.text
        db.refresh(reservation)
        assert reservation.room_id == target_room.id
        assert reservation.check_in_date == new_check_in
        assert reservation.check_out_date == new_check_out
    finally:
        _close(db, engine)


@pytest.mark.parametrize("route", ["/api/bookings", "/api/reservations"])
def test_generic_reservation_edit_requires_manager_for_paid_date_change(route):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.status = ReservationStatusEnum.FULLY_PAID
        reservation.amount_paid = reservation.total_amount
        original_dates = (reservation.check_in_date, reservation.check_out_date)
        original_total = reservation.total_amount
        db.commit()

        denied = client.patch(
            f"{route}/{reservation.id}",
            json={
                "check_out_date": (reservation.check_out_date + timedelta(days=1)).isoformat(),
                "client_version": reservation.version,
            },
        )

        assert denied.status_code == 403, denied.text
        db.refresh(reservation)
        assert (reservation.check_in_date, reservation.check_out_date) == original_dates
        assert reservation.total_amount == original_total
    finally:
        _close(db, engine)


@pytest.mark.parametrize("route", ["/api/bookings", "/api/reservations"])
def test_generic_reservation_edit_requires_manager_for_paid_occupancy_change(route):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.status = ReservationStatusEnum.FULLY_PAID
        reservation.amount_paid = reservation.total_amount
        db.commit()

        payload = {"num_adults": 2, "client_version": reservation.version}
        response = (
            _patch_legacy_booking(client, reservation, payload)
            if route == "/api/bookings"
            else client.patch(f"{route}/{reservation.id}", json=payload)
        )

        assert response.status_code == 403, response.text
        db.refresh(reservation)
        assert reservation.num_adults == 1
        assert reservation.total_amount == Decimal("200.00")
    finally:
        _close(db, engine)


def test_legacy_booking_create_and_update_respect_inactive_subscription():
    client, db, engine, auth, reservation, _stock_item = _client()
    try:
        config = db.get(HotelConfiguration, 1)
        config.subscription_active = False
        db.commit()

        create = client.post(
            "/api/bookings/",
            json={
                "guest_id": reservation.guest_id,
                "category_id": reservation.category_id,
                "check_in_date": (date.today() + timedelta(days=10)).isoformat(),
                "check_out_date": (date.today() + timedelta(days=12)).isoformat(),
                "quote_token": "synthetic-quote-token-value",
            },
        )
        update = _patch_legacy_booking(client, reservation, {"notes": "must not persist"})
        set_user_override(
            db, 1, 20, "receptionist", "reservation:cancel", True, actor_user_id=10
        )
        db.commit()
        cancel = client.post(f"/api/bookings/{reservation.id}/cancel")
        auth["user_id"] = 10
        auth["role"] = "owner"
        delete = client.delete(f"/api/bookings/{reservation.id}")

        assert create.status_code == update.status_code == cancel.status_code == delete.status_code == 402
        db.refresh(reservation)
        assert reservation.notes is None
        assert reservation.status == ReservationStatusEnum.PENDING
        assert reservation.deleted_at is None
    finally:
        _close(db, engine)


@pytest.mark.parametrize("protected_change", ["room", "paid_dates", "paid_occupancy"])
def test_manual_ota_duplicate_update_respects_reservation_action_lanes(protected_change):
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        target_room = Room(
            hotel_id=1,
            category_id=reservation.category_id,
            room_number="102",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        reservation.source_provider_code = "booking"
        reservation.external_id = "OTA-RBAC-1"
        if protected_change in {"paid_dates", "paid_occupancy"}:
            reservation.status = ReservationStatusEnum.FULLY_PAID
            reservation.amount_paid = reservation.total_amount
        db.flush()
        set_user_override(
            db, 1, 20, "receptionist", "reservation:create", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:update", True, actor_user_id=10
        )
        set_user_override(
            db, 1, 20, "receptionist", "reservation:move", False, actor_user_id=10
        )
        original_dates = (reservation.check_in_date, reservation.check_out_date)
        original_room_id = reservation.room_id
        db.commit()

        payload = {
            "guest_id": reservation.guest_id,
            "category_id": reservation.category_id,
            "room_id": target_room.id if protected_change == "room" else original_room_id,
            "check_in_date": original_dates[0].isoformat(),
            "check_out_date": (
                original_dates[1] + timedelta(days=1)
                if protected_change == "paid_dates"
                else original_dates[1]
            ).isoformat(),
            "channel": "booking",
            "external_id": "OTA-RBAC-1",
        }
        if protected_change == "paid_occupancy":
            payload["num_adults"] = 2

        response = client.post("/api/reservations/manual-ota", json=payload)

        assert response.status_code == 403, response.text
        db.refresh(reservation)
        assert reservation.room_id == original_room_id
        assert (reservation.check_in_date, reservation.check_out_date) == original_dates
        assert reservation.num_adults == 1
    finally:
        _close(db, engine)


def test_manual_ota_paid_occupancy_guard_refreshes_and_locks_stale_reservation():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        reservation.source_provider_code = "booking"
        reservation.external_id = "OTA-STALE-PAID-1"
        db.commit()

        # Reproduce an identity-map snapshot read before a payment transaction
        # updates the stored paid state. The endpoint must authorize against
        # the refreshed, locked tenant row rather than this stale Python object.
        db.query(Reservation).filter(
            Reservation.hotel_id == 1,
            Reservation.id == reservation.id,
        ).update(
            {
                Reservation.status: ReservationStatusEnum.FULLY_PAID,
                Reservation.amount_paid: reservation.total_amount,
            },
            synchronize_session=False,
        )
        assert reservation.status == ReservationStatusEnum.PENDING
        assert reservation.amount_paid == Decimal("0")

        response = client.post(
            "/api/reservations/manual-ota",
            json={
                "guest_id": reservation.guest_id,
                "category_id": reservation.category_id,
                "room_id": reservation.room_id,
                "check_in_date": reservation.check_in_date.isoformat(),
                "check_out_date": reservation.check_out_date.isoformat(),
                "num_adults": 2,
                "channel": "booking",
                "external_id": "OTA-STALE-PAID-1",
            },
        )

        assert response.status_code == 403, response.text
        db.refresh(reservation)
        assert reservation.status == ReservationStatusEnum.FULLY_PAID
        assert reservation.num_adults == 1
    finally:
        _close(db, engine)


def test_reservation_date_change_extension_and_room_move_respect_inactive_subscription():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        config = db.get(HotelConfiguration, 1)
        config.subscription_active = False
        target_room = Room(
            hotel_id=1,
            category_id=reservation.category_id,
            room_number="102",
            floor=1,
            status=RoomStatusEnum.AVAILABLE,
        )
        db.add(target_room)
        for permission in (
            "reservation:update",
            "reservation:move",
            "reservation:charge",
            "cash:operate",
        ):
            set_user_override(
                db, 1, 20, "receptionist", permission, True, actor_user_id=10
            )
        db.commit()

        date_change = client.post(
            f"/api/reservations/{reservation.id}/date-change",
            json={
                "check_in_date": reservation.check_in_date.isoformat(),
                "check_out_date": (reservation.check_out_date + timedelta(days=1)).isoformat(),
                "client_version": reservation.version,
            },
        )
        extension = client.post(
            f"/api/reservations/{reservation.id}/extend",
            json={
                "new_checkout_date": (reservation.check_out_date + timedelta(days=1)).isoformat(),
                "client_version": reservation.version,
            },
        )
        room_move = client.post(
            f"/api/reservations/{reservation.id}/room-move",
            json={"client_version": reservation.version, "to_room_id": target_room.id, "reason_code": "guest_request"},
        )

        assert date_change.status_code == extension.status_code == room_move.status_code == 402
        db.refresh(reservation)
        assert reservation.room_id != target_room.id
        assert reservation.check_out_date == date.today() + timedelta(days=2)
    finally:
        _close(db, engine)


def test_legacy_booking_cancel_records_actor_and_disables_active_payment_link():
    client, db, engine, _auth, reservation, _stock_item = _client()
    try:
        link = PaymentLink(
            hotel_id=1,
            reservation_id=reservation.id,
            link_code="LEGACY-CANCEL-1",
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
            status="pending",
            execution_mode="provider",
            payable=True,
            external_checkout_url="https://payments.example/checkout/legacy-cancel-1",
        )
        db.add(link)
        db.commit()

        response = client.post(f"/api/bookings/{reservation.id}/cancel")

        assert response.status_code == 200, response.text
        db.refresh(link)
        assert link.status == "cancelled"
        assert not link.payable
        history = (
            db.query(ReservationStatusHistory)
            .filter_by(reservation_id=reservation.id, to_status="cancelled")
            .one()
        )
        assert history.reason_code == "cancelled_by_user"
        assert history.changed_by_user_id == 20
    finally:
        _close(db, engine)


def test_stock_read_movement_and_admin_are_independently_enforced_without_mutation():
    client, db, engine, auth, _reservation, stock_item = _client()
    try:
        auth.update(user_id=30, role="manager")
        assert client.get("/api/stock/items").status_code == 200

        set_user_override(db, 1, 30, "manager", "stock:read", False, actor_user_id=10)
        db.commit()
        denied_read = client.get("/api/stock/items")
        assert denied_read.status_code == 403
        assert "Soap" not in denied_read.text

        set_user_override(db, 1, 30, "manager", "stock:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "stock:admin", False, actor_user_id=10)
        db.commit()
        assert client.get("/api/stock/items").status_code == 200
        denied_delete = client.delete(f"/api/stock/items/{stock_item.id}")
        assert denied_delete.status_code == 403
        assert db.get(StockItem, stock_item.id) is not None

        set_user_override(db, 1, 30, "manager", "stock:movement", False, actor_user_id=10)
        db.commit()
        denied_movement = client.post(
            "/api/stock/movements",
            json={"item_id": stock_item.id, "movement_type": "in", "quantity": "2.00"},
        )
        assert denied_movement.status_code == 403
        current = client.get(f"/api/stock/items/{stock_item.id}/current")
        assert current.status_code == 200
        assert Decimal(str(current.json()["quantity"])) == Decimal("0.00")

        auth.update(user_id=10, role="owner")
        set_role_override(db, 1, "owner", "stock:adjust", False, actor_user_id=10)
        db.commit()
        adjustment = {"item_id": stock_item.id, "movement_type": "adjustment", "quantity": "3.00"}
        assert client.post("/api/stock/movements", json=adjustment).status_code == 403
        set_role_override(db, 1, "owner", "stock:adjust", True, actor_user_id=10)
        db.commit()
        assert client.post("/api/stock/movements", json=adjustment).status_code == 201
    finally:
        _close(db, engine)


def test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(monkeypatch):
    client, db, engine, auth, reservation, _stock_item = _client()
    calls: list[str] = []

    def fake_checkin(db, reservation_id, **_kwargs):
        calls.append("checkin")
        target = db.get(Reservation, reservation_id)
        target.status = ReservationStatusEnum.CHECKED_IN
        db.flush()
        return target

    def fake_checkout(db, reservation_id, *, force=False, **_kwargs):
        calls.append("force_checkout" if force else "checkout")
        target = db.get(Reservation, reservation_id)
        target.status = ReservationStatusEnum.CHECKED_OUT
        db.flush()
        return target

    monkeypatch.setattr(checkin_api, "perform_checkin", fake_checkin)
    monkeypatch.setattr(checkin_api, "perform_checkout", fake_checkout)
    try:
        set_user_override(db, 1, 20, "receptionist", "checkin:perform", False, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/{reservation.id}").status_code == 403
        assert calls == []

        set_user_override(db, 1, 20, "receptionist", "checkin:perform", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/{reservation.id}").status_code == 200
        assert calls == ["checkin"]

        set_user_override(db, 1, 20, "receptionist", "checkout:perform", False, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/checkout/{reservation.id}").status_code == 403
        assert calls == ["checkin"]

        set_user_override(db, 1, 20, "receptionist", "checkout:perform", True, actor_user_id=10)
        db.commit()
        assert client.post(f"/api/checkin/checkout/{reservation.id}").status_code == 200
        assert calls[-1] == "checkout"

        assert client.post(f"/api/checkin/checkout/{reservation.id}?force=true").status_code == 403
        assert calls[-1] == "checkout"
        auth.update(user_id=10, role="owner")
        assert client.post(f"/api/checkin/checkout/{reservation.id}?force=true").status_code == 200
        assert calls[-1] == "force_checkout"
    finally:
        _close(db, engine)


def test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    room = db.query(Room).filter_by(hotel_id=1).one()
    try:
        auth.update(user_id=30, role="manager")
        set_user_override(db, 1, 30, "manager", "room:read", False, actor_user_id=10)
        db.commit()

        denied_read = client.get("/api/rooms/")
        assert denied_read.status_code == 403
        assert room.room_number not in denied_read.text

        set_user_override(db, 1, 30, "manager", "room:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "room:status_update", False, actor_user_id=10)
        db.commit()
        assert client.get("/api/rooms/").status_code == 200

        denied_status = client.patch(
            f"/api/rooms/{room.id}/status",
            json={"status": "maintenance"},
        )
        assert denied_status.status_code == 403
        db.refresh(room)
        assert room.status == RoomStatusEnum.AVAILABLE

        set_user_override(db, 1, 30, "manager", "room:status_update", True, actor_user_id=10)
        db.commit()
        allowed_status = client.patch(
            f"/api/rooms/{room.id}/status",
            json={"status": "maintenance"},
        )
        assert allowed_status.status_code == 200
        db.refresh(room)
        assert room.status == RoomStatusEnum.MAINTENANCE
    finally:
        _close(db, engine)


def test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    try:
        auth.update(user_id=30, role="manager")
        seeded = client.post("/api/laundry/batches", json={"notes": "safe synthetic batch"})
        assert seeded.status_code == 201
        batch_code = seeded.json()["batch_code"]

        set_user_override(db, 1, 30, "manager", "laundry:read", False, actor_user_id=10)
        db.commit()
        denied_read = client.get("/api/laundry/batches")
        assert denied_read.status_code == 403
        assert batch_code not in denied_read.text

        set_user_override(db, 1, 30, "manager", "laundry:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "laundry:movement", False, actor_user_id=10)
        db.commit()
        allowed_read = client.get("/api/laundry/batches")
        assert allowed_read.status_code == 200
        before_count = db.query(LaundryBatch).filter_by(hotel_id=1).count()

        denied_movement = client.post("/api/laundry/batches", json={"notes": "must not persist"})
        assert denied_movement.status_code == 403
        assert db.query(LaundryBatch).filter_by(hotel_id=1).count() == before_count

        set_user_override(db, 1, 30, "manager", "laundry:movement", True, actor_user_id=10)
        db.commit()
        assert client.post("/api/laundry/batches", json={"notes": "allowed"}).status_code == 201
        assert db.query(LaundryBatch).filter_by(hotel_id=1).count() == before_count + 1
    finally:
        _close(db, engine)


def test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation():
    client, db, engine, auth, _reservation, _stock_item = _client()
    category = db.query(RoomCategory).filter_by(hotel_id=1).one()
    target_date = date.today() + timedelta(days=30)
    path = f"/api/rates/category/{category.id}"
    try:
        auth.update(user_id=30, role="manager")
        set_user_override(db, 1, 30, "manager", "rates:read", False, actor_user_id=10)
        db.commit()

        denied_read = client.get(
            path,
            params={"from_date": target_date.isoformat(), "to_date": target_date.isoformat()},
        )
        assert denied_read.status_code == 403
        assert "daily_rate" not in denied_read.text
        denied_calendar = client.get(
            "/api/rate-calendar/daily",
            params={
                "category_id": category.id,
                "date_from": target_date.isoformat(),
                "date_to": target_date.isoformat(),
            },
        )
        assert denied_calendar.status_code == 403

        set_user_override(db, 1, 30, "manager", "rates:read", True, actor_user_id=10)
        set_user_override(db, 1, 30, "manager", "rates:update", False, actor_user_id=10)
        db.commit()
        assert client.get(
            path,
            params={"from_date": target_date.isoformat(), "to_date": target_date.isoformat()},
        ).status_code == 200
        assert client.get(
            "/api/rate-calendar/daily",
            params={
                "category_id": category.id,
                "date_from": target_date.isoformat(),
                "date_to": target_date.isoformat(),
            },
        ).status_code == 200

        denied_update = client.post(
            f"{path}/daily",
            json={"date": target_date.isoformat(), "price": 123.45},
        )
        assert denied_update.status_code == 403
        assert db.query(DailyRate).filter_by(
            hotel_id=1,
            category_id=category.id,
            date=target_date,
        ).one_or_none() is None

        set_user_override(db, 1, 30, "manager", "rates:update", True, actor_user_id=10)
        db.commit()
        assert client.post(
            f"{path}/daily",
            json={"date": target_date.isoformat(), "price": 123.45},
        ).status_code == 200
        assert db.query(DailyRate).filter_by(
            hotel_id=1,
            category_id=category.id,
            date=target_date,
        ).one().price == 123.45
    finally:
        _close(db, engine)
