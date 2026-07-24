"""Tests for operator-created reservation consumption charges."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.reservation import ReservationStatusEnum
from app.schemas.reservation import ReservationCreate
from app.services.payment_service import get_reservation_financial_summary
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    add_reservation_charge,
)
from app.services.reservation_service import create_reservation


def _reservation(db, guest, category, room):
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
        ),
    )
    db.flush()
    return reservation


def test_add_reservation_charge_updates_operational_financial_summary(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
    hotel_config,
):
    reservation = _reservation(db, sample_guest, sample_categories[0], sample_rooms[0])

    charge = add_reservation_charge(
        db,
        reservation=reservation,
        hotel_id=hotel_config.id,
        amount=Decimal("1250.50"),
        currency_code="ars",
        description="Desayuno y minibar",
        actor_user_id=None,
    )
    db.flush()

    assert charge.adjustment_type.value == "charge"
    assert charge.amount == Decimal("1250.50")
    assert charge.total_amount == Decimal("1250.50")
    assert charge.currency_code == "ARS"
    assert charge.notes == "Desayuno y minibar"
    assert charge.created_by_user_id is None

    summary = get_reservation_financial_summary(db, hotel_config.id, reservation.id)
    assert summary["billing_adjustment_total"] == Decimal("1250.50")
    assert summary["operational_total_amount"] == Decimal(str(reservation.total_amount)) + Decimal("1250.50")
    assert summary["operational_balance_due"] == summary["operational_total_amount"]
    assert summary["billing_adjustments"][0]["notes"] == "Desayuno y minibar"


def test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(
    db,
    sample_guest,
    sample_categories,
    sample_rooms,
    hotel_config,
):
    reservation = _reservation(db, sample_guest, sample_categories[0], sample_rooms[0])

    with pytest.raises(ReservationOperationsError, match="no pertenece"):
        add_reservation_charge(
            db,
            reservation=reservation,
            hotel_id=hotel_config.id + 1,
            amount=Decimal("10"),
            currency_code="ARS",
            description="No debe cruzar hoteles",
            actor_user_id=None,
        )

    reservation.status = ReservationStatusEnum.CHECKED_OUT
    with pytest.raises(ReservationOperationsError, match="estadia activa"):
        add_reservation_charge(
            db,
            reservation=reservation,
            hotel_id=hotel_config.id,
            amount=Decimal("10"),
            currency_code="ARS",
            description="No debe cargarse despues del checkout",
            actor_user_id=None,
        )
