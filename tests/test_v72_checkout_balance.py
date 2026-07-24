"""
Tests for v72 check-out balance reconciliation.
"""
import pytest
from datetime import date
from decimal import Decimal

from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest
from app.services.checkin_service import CheckInError, perform_checkin, perform_checkout
from app.services.payment_service import process_payment
from app.services.reservation_service import create_reservation
from app.services.cash_register_service import open_session


@pytest.fixture(autouse=True)
def opened_cash_register(db, hotel_config):
    """Checkout balance scenarios collect cash through an open caja."""
    open_session(db, hotel_id=hotel_config.id, opened_by_user_id=None, opening_balance=0)


def _create_checked_in_reservation(db, guest, categories, config, check_in_date, check_out_date):
    data = ReservationCreate(
        guest_id=guest.id,
        category_id=categories[0].id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
    )
    reservation = create_reservation(db, data)
    db.flush()
    payment = PaymentRequest(
        reservation_id=reservation.id,
        amount=reservation.total_amount,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
    )
    process_payment(db, payment, hotel_id=config.id)
    db.flush()
    perform_checkin(db, reservation.id, hotel_id=config.id)
    db.flush()
    return reservation


def _add_billing_charge(db, reservation, hotel_id, amount):
    db.add(
        BillingAdjustment(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
            amount=amount,
            currency_code="ARS",
            total_amount=amount,
            notes="Consumo durante la estadia",
        )
    )
    db.flush()


def test_checkout_blocked_when_reservation_has_operational_balance(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    reservation = _create_checked_in_reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        date(2026, 9, 1),
        date(2026, 9, 3),
    )
    _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))

    with pytest.raises(CheckInError, match=r"saldo pendiente de \$25\.00"):
        perform_checkout(db, reservation.id, hotel_id=hotel_config.id)

    assert reservation.status == ReservationStatusEnum.CHECKED_IN


def test_checkout_succeeds_when_operational_balance_is_fully_paid(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    reservation = _create_checked_in_reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        date(2026, 10, 1),
        date(2026, 10, 3),
    )
    _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))
    reservation.amount_paid = Decimal(str(reservation.total_amount or 0)) + Decimal("25.00")
    db.flush()

    result = perform_checkout(db, reservation.id, hotel_id=hotel_config.id)

    assert result.status == ReservationStatusEnum.CHECKED_OUT
    assert result.actual_check_out is not None


def test_checkout_succeeds_with_force_even_when_balance_remains(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    reservation = _create_checked_in_reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        date(2026, 11, 1),
        date(2026, 11, 3),
    )
    _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))

    result = perform_checkout(db, reservation.id, hotel_id=hotel_config.id, force=True)

    assert result.status == ReservationStatusEnum.CHECKED_OUT
    assert result.actual_check_out is not None
