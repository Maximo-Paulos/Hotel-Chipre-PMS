from __future__ import annotations

from tests.smoke.helpers import register_owner, seed_operational_reservation
from app.models.reservation import ReservationStatusEnum


def test_reservation_checkin_checkout_smoke(client, engine):
    headers, hotel_id = register_owner(client, "reservation-ops-owner@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.FULLY_PAID,
        total_amount=150.0,
        amount_paid=150.0,
    )

    validate = client.get(f"/api/checkin/validate/{seeded['guest_id']}", headers=headers)
    assert validate.status_code == 200, validate.text
    assert validate.json()["valid"] is True

    checkin = client.post(f"/api/checkin/{seeded['reservation_id']}", headers=headers)
    assert checkin.status_code == 200, checkin.text
    assert checkin.json()["status"] == "checked_in"

    checkout = client.post(f"/api/checkin/checkout/{seeded['reservation_id']}", headers=headers)
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["status"] == "checked_out"
