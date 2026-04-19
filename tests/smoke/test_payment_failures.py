from __future__ import annotations

from sqlalchemy.orm import sessionmaker

from app.models.hotel_config import HotelConfiguration
from app.models.reservation import ReservationStatusEnum
from tests.smoke.helpers import register_owner, seed_operational_reservation


def test_payment_overpay_is_blocked_smoke(client, engine):
    headers, hotel_id = register_owner(client, "payment-failure-owner@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.PENDING,
        total_amount=100.0,
        amount_paid=0.0,
    )

    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": seeded["reservation_id"],
            "amount": 150.0,
            "payment_method": "cash",
            "transaction_type": "full_payment",
            "currency": "ARS",
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "exceeds balance due" in response.json()["detail"]


def test_payment_disabled_method_is_blocked_smoke(client, engine):
    headers, hotel_id = register_owner(client, "payment-disabled-owner@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.PENDING,
        total_amount=100.0,
        amount_paid=0.0,
    )

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as db:
        config = db.get(HotelConfiguration, hotel_id)
        config.enable_paypal = False
        db.commit()

    response = client.post(
        "/api/payments/",
        json={
            "reservation_id": seeded["reservation_id"],
            "amount": 25.0,
            "payment_method": "paypal",
            "transaction_type": "partial_payment",
            "currency": "ARS",
        },
        headers=headers,
    )
    assert response.status_code == 400, response.text
    assert "currently disabled" in response.json()["detail"]
