from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.daily_rate import DailyRate
from app.models.hotel_config import HotelConfiguration
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.room import RoomCategory
from app.services.payment_service import calculate_payment_surcharge


def _override_auth(hotel_id: int, role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id, user_id=1, user_email="owner@test.com",
            user_role=role, is_verified=True, permissions=set(),
        )

    return dependency


def _build_client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def _cleanup(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_payment_surcharge_amount_is_decimal_safe_and_supports_discount(db):
    db.add(HotelConfiguration(id=101, subscription_active=True))
    db.add(PaymentSurcharge(hotel_id=101, payment_method="cash", surcharge_type=PaymentSurchargeTypeEnum.PERCENTAGE, amount=Decimal("-5.00")))
    db.flush()

    info = calculate_payment_surcharge(db, hotel_id=101, payment_method="cash", base_amount=Decimal("100.00"))
    assert info["surcharge_amount"] == Decimal("-5.00")
    assert info["final_amount"] == Decimal("95.00")


def test_payment_surcharge_final_amount_never_goes_negative(db):
    db.add(HotelConfiguration(id=102, subscription_active=True))
    db.add(PaymentSurcharge(hotel_id=102, payment_method="cash", surcharge_type=PaymentSurchargeTypeEnum.FIXED, amount=Decimal("-500.00")))
    db.flush()

    info = calculate_payment_surcharge(db, hotel_id=102, payment_method="cash", base_amount=Decimal("100.00"))
    assert info["final_amount"] == Decimal("0.00")


def test_create_payment_surcharge_rejects_percentage_over_100():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=103, subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(103)
        response = client.post(
            "/api/payment-surcharges",
            json={"payment_method": "cash", "surcharge_type": "percentage", "amount": 150},
        )
        assert response.status_code == 422
    finally:
        _cleanup(db, engine)


def test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=104, subscription_active=True))
        category = RoomCategory(hotel_id=104, name="Std", code="STD104", base_price_per_night=100, max_occupancy=2)
        db.add(category)
        db.flush()
        db.add(DailyRate(hotel_id=104, category_id=category.id, date=date(2026, 6, 1), price=100.0, price_cash=90.0))
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(104)
        response = client.post(
            "/api/payment-surcharges",
            json={"payment_method": "cash", "surcharge_type": "fixed", "amount": 10},
        )
        assert response.status_code == 409
    finally:
        _cleanup(db, engine)


def test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=105, subscription_active=True))
        category = RoomCategory(hotel_id=105, name="Std", code="STD105", base_price_per_night=100, max_occupancy=2)
        db.add(category)
        db.flush()
        db.add(DailyRate(hotel_id=105, category_id=category.id, date=date(2026, 6, 1), price=100.0, price_cash=90.0))
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(105)
        response = client.post(
            "/api/payment-surcharges",
            json={"payment_method": "credit_card", "surcharge_type": "percentage", "amount": 8},
        )
        assert response.status_code == 201
        assert Decimal(response.json()["amount"]) == Decimal("8")
    finally:
        _cleanup(db, engine)


def test_reactivate_deactivated_surcharge_via_patch():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=106, subscription_active=True))
        surcharge = PaymentSurcharge(hotel_id=106, payment_method="cash", surcharge_type=PaymentSurchargeTypeEnum.FIXED, amount=Decimal("5.00"), is_active=False)
        db.add(surcharge)
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(106)
        response = client.patch(f"/api/payment-surcharges/{surcharge.id}", json={"is_active": True})
        assert response.status_code == 200
        assert response.json()["is_active"] is True
    finally:
        _cleanup(db, engine)
