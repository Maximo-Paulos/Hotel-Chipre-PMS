"""
Tests for v72 check-out balance reconciliation.
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func

from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment, BillingAdjustmentTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest
from app.services import checkin_service
from app.services.cash_register_service import open_session
from app.services.checkin_service import CheckInError, perform_checkin, perform_checkout
from app.services.financial_ledger import paid_amount_with_legacy_fallback
from app.services.payment_service import process_payment
from app.services.reservation_service import create_reservation


@pytest.fixture(autouse=True)
def opened_cash_register(db, hotel_config, monkeypatch):
    """Checkout balance scenarios collect cash through an open caja."""
    def hotel_day_for_test(session, hotel_id):
        return (
            session.query(func.max(Reservation.check_in_date))
            .filter(Reservation.hotel_id == hotel_id)
            .scalar()
        ) or date(2027, 1, 1)

    monkeypatch.setattr(checkin_service, "hotel_today", hotel_day_for_test)
    open_session(db, hotel_id=hotel_config.id, opened_by_user_id=None, opening_balance=0)


def _create_checked_in_reservation(
    db, guest, categories, config, check_in_date, check_out_date, *, company_id=None
):
    data = ReservationCreate(
        guest_id=guest.id,
        category_id=categories[0].id,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        company_id=company_id,
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
    adjustment = BillingAdjustment(
        hotel_id=hotel_id,
        reservation_id=reservation.id,
        adjustment_type=BillingAdjustmentTypeEnum.CHARGE,
        amount=amount,
        currency_code="ARS",
        total_amount=amount,
        notes="Consumo durante la estadia",
    )
    db.add(adjustment)
    db.flush()
    return adjustment


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
    process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=25.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
        ),
        hotel_id=hotel_config.id,
    )
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


def test_checkout_allows_deferred_company_balance_without_changing_financial_records(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Empresa con cuenta diferida SA",
        display_name="Empresa con cuenta diferida",
        payment_deferred=True,
    )
    db.add(company)
    db.flush()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=date(2026, 12, 1),
            check_out_date=date(2026, 12, 3),
            company_id=company.id,
        ),
    )
    db.flush()
    perform_checkin(db, reservation.id, hotel_id=hotel_config.id)
    db.flush()
    adjustment = _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))

    paid_before = paid_amount_with_legacy_fallback(db, hotel_config.id, reservation)
    total_before = Decimal(str(reservation.total_amount or 0))
    balance_before = total_before + Decimal(str(adjustment.total_amount)) - paid_before
    payment_count_before = db.query(Transaction).filter(
        Transaction.hotel_id == hotel_config.id,
        Transaction.reservation_id == reservation.id,
    ).count()

    result = perform_checkout(db, reservation.id, hotel_id=hotel_config.id)
    db.flush()
    db.refresh(reservation)
    db.refresh(adjustment)

    paid_after = paid_amount_with_legacy_fallback(db, hotel_config.id, reservation)
    balance_after = (
        Decimal(str(reservation.total_amount or 0))
        + Decimal(str(adjustment.total_amount))
        - paid_after
    )
    payment_count_after = db.query(Transaction).filter(
        Transaction.hotel_id == hotel_config.id,
        Transaction.reservation_id == reservation.id,
    ).count()

    assert result.status == ReservationStatusEnum.CHECKED_OUT
    assert reservation.total_amount == total_before
    assert paid_after == paid_before == Decimal("0.00")
    assert balance_after == balance_before == Decimal("25.00")
    assert adjustment.total_amount == Decimal("25.00")
    assert payment_count_after == payment_count_before == 0


def test_checkout_still_blocks_company_without_deferred_payment_when_balance_remains(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Empresa con pago al checkout SA",
        display_name="Empresa con pago al checkout",
        payment_deferred=False,
    )
    db.add(company)
    db.flush()
    reservation = _create_checked_in_reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        date(2027, 1, 1),
        date(2027, 1, 3),
        company_id=company.id,
    )
    adjustment = _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))

    with pytest.raises(CheckInError, match=r"saldo pendiente de \$25\.00"):
        perform_checkout(db, reservation.id, hotel_id=hotel_config.id)

    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert adjustment.total_amount == Decimal("25.00")


def test_checkout_does_not_use_another_hotels_deferred_company(
    db,
    sample_guest,
    sample_rooms,
    sample_categories,
    hotel_config,
):
    other_hotel = HotelConfiguration(
        id=hotel_config.id + 1,
        hotel_name="Otro hotel",
        subscription_active=True,
    )
    db.add(other_hotel)
    db.flush()
    foreign_company = Company(
        hotel_id=other_hotel.id,
        legal_name="Empresa diferida ajena SA",
        display_name="Empresa diferida ajena",
        payment_deferred=True,
    )
    db.add(foreign_company)
    db.flush()
    reservation = _create_checked_in_reservation(
        db,
        sample_guest,
        sample_categories,
        hotel_config,
        date(2027, 2, 1),
        date(2027, 2, 3),
    )
    adjustment = _add_billing_charge(db, reservation, hotel_config.id, Decimal("25.00"))
    # Model a legacy cross-tenant reference without flushing it through the
    # composite hotel/company foreign key constraint.
    reservation.company_id = foreign_company.id

    with pytest.raises(CheckInError, match=r"saldo pendiente de \$25\.00"):
        perform_checkout(db, reservation.id, hotel_id=hotel_config.id)

    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert adjustment.total_amount == Decimal("25.00")
