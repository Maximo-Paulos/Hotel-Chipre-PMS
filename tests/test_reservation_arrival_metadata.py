"""Regression coverage for reservation arrival metadata and internal comments."""

from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.booking import BookingUpdate
from app.schemas.ota_manual import ManualOTAReservationCreate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.services.ota.contracts import NormalizedOTAReservation
from app.services.ota_service import OTAIntegrationService
from app.services.reservation_service import create_reservation, update_reservation_fields


def test_arrival_time_and_comment_are_normalized_and_validated():
    payload = ReservationCreate(
        guest_id=1,
        category_id=1,
        check_in_date=date(2027, 1, 10),
        check_out_date=date(2027, 1, 11),
        arrival_time_hint=" 09:05 ",
        reservation_comment="  Cuna y habitación silenciosa  ",
    )

    assert payload.arrival_time_hint == "09:05"
    assert payload.reservation_comment == "Cuna y habitación silenciosa"
    assert ReservationUpdate(arrival_time_hint="   ").arrival_time_hint is None
    assert ReservationUpdate(reservation_comment="   ").reservation_comment is None

    with pytest.raises(ValidationError):
        ReservationUpdate(arrival_time_hint="24:00")
    with pytest.raises(ValidationError):
        ReservationUpdate(arrival_time_hint="9:05")
    with pytest.raises(ValidationError):
        ReservationCreate(
            guest_id=1,
            category_id=1,
            check_in_date=date(2027, 1, 10),
            check_out_date=date(2027, 1, 11),
            reservation_comment="x" * 1001,
        )


def test_legacy_booking_and_manual_ota_contracts_share_normalization():
    booking = BookingUpdate(arrival_time_hint=" 07:40 ", reservation_comment="  Cuna  ")
    manual_ota = ManualOTAReservationCreate(
        guest_id=1,
        category_id=1,
        check_in_date=date(2027, 1, 10),
        check_out_date=date(2027, 1, 11),
        channel="booking",
        external_id="OTA-1",
        arrival_time_hint=" 21:15 ",
        reservation_comment="  Llegada tarde  ",
    )

    assert booking.arrival_time_hint == "07:40"
    assert booking.reservation_comment == "Cuna"
    assert manual_ota.arrival_time_hint == "21:15"
    assert manual_ota.reservation_comment == "Llegada tarde"


def test_create_and_update_metadata_preserve_legacy_notes(db, sample_categories, sample_rooms, sample_guest):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2027, 2, 1),
            check_out_date=date(2027, 2, 3),
            total_amount=200,
            notes="legacy notes stay intact",
            arrival_time_hint="18:30",
            reservation_comment="Late arrival",
        ),
        hotel_id=1,
    )
    db.flush()

    assert reservation.arrival_time_hint == "18:30"
    assert reservation.reservation_comment == "Late arrival"
    assert reservation.notes == "legacy notes stay intact"

    version = reservation.version
    update_reservation_fields(
        db,
        reservation,
        ReservationUpdate(
            arrival_time_hint=" 20:00 ",
            reservation_comment="   ",
            client_version=version,
        ),
        hotel_id=1,
    )

    assert reservation.arrival_time_hint == "20:00"
    assert reservation.reservation_comment is None
    assert reservation.notes == "legacy notes stay intact"
    assert reservation.version == version + 1


def test_ota_snapshot_updates_arrival_without_overwriting_internal_comment(db):
    from app.models.reservation import Reservation

    reservation = Reservation(arrival_time_hint="08:00", reservation_comment="Keep this internal")
    normalized = NormalizedOTAReservation(
        provider_code="booking",
        external_reservation_id="OTA-1",
        external_confirmation_code="CONF-OTA-1",
        guest_full_name="Guest OTA",
        guest_email=None,
        check_in_date=date(2027, 3, 1),
        check_out_date=date(2027, 3, 2),
        sellable_product_code=None,
        rate_plan_code=None,
        num_adults=1,
        num_children=0,
        currency_code="ARS",
        gross_total=100,
        tax_total=0,
        fee_total=0,
        commission_total=0,
        arrival_time_hint="19:30",
    )

    OTAIntegrationService._apply_financial_snapshot(db, 1, reservation, normalized)

    assert reservation.arrival_time_hint == "19:30"
    assert reservation.reservation_comment == "Keep this internal"
