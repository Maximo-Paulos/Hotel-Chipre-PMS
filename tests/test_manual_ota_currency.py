from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.schemas.ota_manual import ManualOTAReservationCreate
from app.services.financial_ledger import (
    operational_balance_due,
    paid_amount_with_legacy_fallback,
    reconciled_paid_amounts_by_reservation,
)
from app.services.financial_report_service import build_financial_report
from app.services.timezones import hotel_today
from app.services.ota_manual_service import create_or_update_manual_ota_reservation
from app.services.timezones import hotel_today


def _seed_hotel(db):
    db.add(HotelConfiguration(id=1, hotel_name="OTA currency test", subscription_active=True))
    db.flush()
    category = RoomCategory(
        hotel_id=1,
        name="Standard",
        code="STD-OTA-CURRENCY",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(
        hotel_id=1,
        room_number="701",
        floor=7,
        category_id=category.id,
        status=RoomStatusEnum.AVAILABLE,
        is_active=True,
    )
    guest = Guest(
        hotel_id=1,
        first_name="OTA",
        last_name="Guest",
        document_type=DocumentTypeEnum.DNI,
        document_number="OTA-CURRENCY-TEST",
        email="ota-currency@example.test",
        terms_accepted=True,
    )
    db.add_all([room, guest])
    db.flush()
    return category, room, guest


def _manual_payload(*, guest_id: int, category_id: int, room_id: int, external_id: str, paid_currency: str):
    return ManualOTAReservationCreate(
        guest_id=guest_id,
        category_id=category_id,
        room_id=room_id,
        check_in_date=date(2026, 11, 1),
        check_out_date=date(2026, 11, 2),
        num_adults=2,
        num_children=0,
        channel="expedia",
        external_id=external_id,
        target_currency="ARS",
        total_amount=Decimal("100000.00"),
        amount_paid=Decimal("40.00"),
        external_paid_currency=paid_currency,
        external_paid_reference=f"{external_id}-PREPAID",
    )


def test_foreign_currency_ota_prepayment_is_reported_without_reducing_local_balance(db):
    category, room, guest = _seed_hotel(db)
    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            external_id="EXP-USD-40",
            paid_currency=" usd ",
        ),
        actor_user_id=7,
    )
    db.flush()

    assert reservation.currency_code == "ARS"
    assert reservation.external_paid_amount == Decimal("40.00")
    assert reservation.external_paid_currency == "USD"
    assert reservation.external_paid_confirmed is True
    assert reservation.fx_rate_snapshot is None
    assert reservation.amount_paid == Decimal("0.00")
    assert paid_amount_with_legacy_fallback(db, 1, reservation) == Decimal("0.00")
    assert operational_balance_due(db, hotel_id=1, reservation=reservation) == Decimal("100000.00")
    assert reconciled_paid_amounts_by_reservation(db, 1, [reservation.id])[reservation.id] == Decimal("0.00")
    from app.api.reservations import _to_read

    read_payload = _to_read(reservation).model_dump()
    assert read_payload["external_paid_currency"] == "USD"
    assert read_payload["external_paid_balance_credit_applied"] is False

    report_date = hotel_today(db, 1)
    report = build_financial_report(
        db,
        hotel_id=1,
        start_date=report_date,
        end_date=report_date,
    )
    assert report["collected"]["by_currency"] == []
    assert report["external_ota_collected"]["by_currency"] == [
        {"currency_code": "USD", "amount": Decimal("40.00")}
    ]
    assert report["external_ota_collected"]["by_channel"] == [
        {"channel_code": "expedia_manual", "currency_code": "USD", "amount": Decimal("40.00")}
    ]


def test_same_currency_ota_prepayment_keeps_existing_balance_credit_behavior(db):
    category, room, guest = _seed_hotel(db)
    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=_manual_payload(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            external_id="EXP-ARS-40",
            paid_currency="ars",
        ),
        actor_user_id=7,
    )
    db.flush()

    assert reservation.external_paid_currency == "ARS"
    assert paid_amount_with_legacy_fallback(db, 1, reservation) == Decimal("40.00")
    assert operational_balance_due(db, hotel_id=1, reservation=reservation) == Decimal("99960.00")


def test_legacy_api_omission_defaults_external_payment_to_reservation_currency(db):
    category, room, guest = _seed_hotel(db)
    payload = _manual_payload(
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        external_id="EXP-LEGACY-CLIENT",
        paid_currency="USD",
    )
    payload.external_paid_currency = None
    payload.target_currency = "USD"

    reservation = create_or_update_manual_ota_reservation(
        db,
        hotel_id=1,
        data=payload,
        actor_user_id=7,
    )
    db.flush()

    assert reservation.currency_code == "USD"
    assert reservation.external_paid_currency == "USD"
    assert paid_amount_with_legacy_fallback(db, 1, reservation) == Decimal("40.00")
