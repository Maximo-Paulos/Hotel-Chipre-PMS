from __future__ import annotations

import pytest

from app.config import get_settings
from app.models.guest import Guest
from app.models.ota import OTAReservationMapping, OTASyncStatusEnum
from app.models.ota_core import OTAReservationLifecycleEnum, OTAReservationLink
from app.models.payment import PaymentLink
from app.models.reservation import Reservation, ReservationStatusEnum
from app.services.ota_service import OTAIntegrationService
from app.services.reservation_service import transition_reservation_status


@pytest.fixture(autouse=True)
def _enable_mocked_inbound_events(monkeypatch):
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _booking_payload(**overrides):
    payload = {
        "reservation_id": "BKG-LIFECYCLE-001",
        "guest_name": "Jane Doe",
        "guest_email": "jane@example.com",
        "guest_phone": "+5491112345678",
        "checkin": "2026-09-01",
        "checkout": "2026-09-03",
        "room_type": "STD_DBL",
        "num_adults": 2,
        "num_children": 0,
        "total_price": 320.0,
        "currency": "ARS",
        "property_id": "booking-h1",
    }
    payload.update(overrides)
    return payload


def _seed_booking_secret(db, hotel_id: int = 1) -> str:
    secret = f"booking-secret-h{hotel_id}"
    OTAIntegrationService.upsert_webhook_credential(
        db,
        hotel_id=hotel_id,
        provider="booking",
        webhook_secret=secret,
        external_property_id=f"booking-h{hotel_id}",
    )
    return secret


def test_booking_modify_updates_existing_reservation_and_guest(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    initial = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation_id = initial.reservation_id
    db.flush()

    updated_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(
            event="reservation.modified",
            guest_name="Jane Roe",
            guest_email="jane.roe@example.com",
            guest_phone="+5491198765432",
            checkout="2026-09-04",
            total_price=470.0,
        ),
    )
    db.flush()

    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).one()
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert updated_mapping.id == initial.id
    assert reservation.id == reservation_id
    assert str(reservation.check_out_date) == "2026-09-04"
    assert reservation.total_amount == 470.0
    assert reservation.guest.first_name == "Jane"
    assert reservation.guest.last_name == "Roe"
    assert reservation.guest.email == "jane.roe@example.com"
    assert reservation.guest.phone == "+5491198765432"
    assert updated_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert link.provider_state == OTAReservationLifecycleEnum.MODIFIED


def test_booking_cancel_cancels_existing_pre_checkin_reservation(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    db.flush()
    payment_link = PaymentLink(
        hotel_id=hotel_config.id,
        reservation_id=mapping.reservation_id,
        link_code="ota-cancel-open-link",
        requested_amount=100,
        recipient_email="ota-guest@example.test",
        provider="mercado_pago",
        status="pending",
        execution_mode="provider",
        payable=True,
        external_checkout_url="https://mp.test/ota-cancel-open-link",
    )
    db.add(payment_link)
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )
    db.flush()

    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert cancelled_mapping.id == mapping.id
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.allocation_status == "cancelled"
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert link.provider_state == OTAReservationLifecycleEnum.CANCELLED
    assert payment_link.status == "cancelled"
    assert payment_link.payable is False


def test_booking_cancel_with_confirmed_external_payment_requires_settlement_review(
    db, sample_rooms, sample_categories, hotel_config
):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    reservation.external_paid_amount = 90
    reservation.external_paid_confirmed = True
    reservation.external_paid_ever_confirmed = True
    reservation.amount_paid = 90
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )

    db.refresh(reservation)
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.SYNCED
    assert reservation.status == ReservationStatusEnum.CANCELLED
    assert reservation.requires_manual_review is True
    assert reservation.settlement_status == "review_cancellation"


def test_booking_cancel_after_checkin_requires_manual_resolution(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    mapping = OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    reservation = db.query(Reservation).filter(Reservation.id == mapping.reservation_id).one()
    transition_reservation_status(db, reservation, ReservationStatusEnum.FULLY_PAID, hotel_id=hotel_config.id)
    transition_reservation_status(db, reservation, ReservationStatusEnum.CHECKED_IN, hotel_id=hotel_config.id)
    db.flush()

    cancelled_mapping = OTAIntegrationService.process_booking_webhook(
        db,
        hotel_config.id,
        secret,
        _booking_payload(event="reservation.cancelled"),
    )
    db.flush()

    db.refresh(reservation)
    link = db.query(OTAReservationLink).filter_by(
        hotel_id=hotel_config.id,
        external_reservation_id="BKG-LIFECYCLE-001",
    ).one()

    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert reservation.requires_manual_review is True
    assert reservation.allocation_status == "manual_review"
    assert reservation.settlement_status == "manual_resolution_required"
    assert cancelled_mapping.sync_status == OTASyncStatusEnum.CONFLICT
    assert link.provider_state == OTAReservationLifecycleEnum.MANUAL_RESOLUTION_REQUIRED


def test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest(db, sample_rooms, sample_categories, hotel_config):
    secret = _seed_booking_secret(db, hotel_config.id)
    OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    OTAIntegrationService.process_booking_webhook(db, hotel_config.id, secret, _booking_payload())
    db.flush()

    assert db.query(OTAReservationMapping).filter_by(
        hotel_id=hotel_config.id,
        ota_name="booking",
        ota_reservation_id="BKG-LIFECYCLE-001",
    ).count() == 1
    assert db.query(Reservation).filter_by(
        hotel_id=hotel_config.id,
        external_id="BKG-LIFECYCLE-001",
    ).count() == 1
    assert db.query(Guest).filter_by(
        hotel_id=hotel_config.id,
        email="jane@example.com",
    ).count() == 1
