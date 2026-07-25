from __future__ import annotations

from tests.smoke.helpers import register_owner, seed_operational_reservation
from app.models.reservation import ReservationStatusEnum
from app.dependencies.auth import AuthContext, get_auth_context
import app.main as main_module


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


def test_housekeeping_cannot_checkout_reservation(client, engine):
    """POST /api/checkin/checkout only enforced authentication (get_auth_context),
    not PERMISSION_CHECKIN_PERFORM like its sibling POST /api/checkin/{id} does.
    housekeeping has checkin:perform=False in the role matrix (V72 SS17) but could
    still call this endpoint directly and close out any guest's stay.
    """
    headers, hotel_id = register_owner(client, "reservation-ops-owner-hk@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.FULLY_PAID,
        total_amount=150.0,
        amount_paid=150.0,
    )

    checkin = client.post(f"/api/checkin/{seeded['reservation_id']}", headers=headers)
    assert checkin.status_code == 200, checkin.text

    def housekeeping_context():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=999,
            user_email="housekeeping-smoke@example.com",
            user_role="housekeeping",
            is_verified=True,
        )

    main_module.app.dependency_overrides[get_auth_context] = housekeeping_context
    try:
        checkout = client.post(f"/api/checkin/checkout/{seeded['reservation_id']}")
    finally:
        del main_module.app.dependency_overrides[get_auth_context]

    assert checkout.status_code == 403, checkout.text
