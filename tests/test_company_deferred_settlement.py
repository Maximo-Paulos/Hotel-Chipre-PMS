"""v72 §3.5 corporate deferred billing flow (R5b ITEM C).

A company reservation with payment_deferred is created with settlement_status
'deferred' and a settlement_due_date = check_out + deferred_days. Registering the
collection transitions it to 'settled'.
"""
from datetime import date, timedelta

import pytest

from app.models.company import Company
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    register_company_settlement,
)


def _deferred_company(db, *, hotel_id: int = 1, deferred_days: int = 30) -> Company:
    company = Company(
        hotel_id=hotel_id,
        legal_name="UOCRA SA",
        display_name="UOCRA",
        payment_deferred=True,
        deferred_days=deferred_days,
    )
    db.add(company)
    db.flush()
    return company


def test_deferred_company_reservation_sets_settlement(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    company = _deferred_company(db, deferred_days=30)
    check_out = date(2026, 4, 5)
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=check_out,
        company_id=company.id,
    )
    reservation = create_reservation(db, data)

    assert reservation.settlement_status == "deferred"
    assert reservation.settlement_due_date == check_out + timedelta(days=30)


def test_register_settlement_marks_settled(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    company = _deferred_company(db, deferred_days=15)
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 5, 1),
        check_out_date=date(2026, 5, 3),
        company_id=company.id,
    )
    reservation = create_reservation(db, data)
    assert reservation.settlement_status == "deferred"

    register_company_settlement(db, reservation, hotel_id=1)
    assert reservation.settlement_status == "settled"

    # Idempotent: a second call does not raise and stays settled.
    register_company_settlement(db, reservation, hotel_id=1)
    assert reservation.settlement_status == "settled"


def test_register_settlement_rejects_non_company(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data)
    with pytest.raises(ReservationError):
        register_company_settlement(db, reservation, hotel_id=1)
