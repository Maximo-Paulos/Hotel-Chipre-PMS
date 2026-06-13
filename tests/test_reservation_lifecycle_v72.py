from datetime import date
from decimal import Decimal

import pytest

from app.models.reservation import ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate
from app.services.reservation_operations_service import (
    ReservationOperationsError,
    change_reservation_dates,
    extend_reservation_stay,
)
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    mark_reservation_no_show,
)


def _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms, *, code_dates=None):
    check_in, check_out = code_dates or (date(2026, 7, 1), date(2026, 7, 3))
    return create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=check_in,
            check_out_date=check_out,
        ),
        hotel_id=1,
    )


def _completed_transaction(db, reservation, amount="50.00"):
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=Decimal(amount),
        currency=reservation.currency_code or "ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.COMPLETED,
    )
    db.add(tx)
    db.flush()
    return tx


def test_no_show_can_be_marked_without_auto_charge(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    assert db.query(Transaction).count() == 0

    mark_reservation_no_show(
        db,
        reservation,
        hotel_id=1,
        client_version=reservation.version,
        notes="Guest did not arrive",
    )

    assert reservation.status == ReservationStatusEnum.NO_SHOW
    assert reservation.no_show_policy_applied.value == "none"
    assert db.query(Transaction).count() == 0


def test_date_change_without_payments_cancels_and_recreates(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)

    result = change_reservation_dates(
        db,
        reservation=reservation,
        hotel_id=1,
        check_in_date=date(2026, 7, 5),
        check_out_date=date(2026, 7, 7),
        client_version=reservation.version,
        manager_authorized=False,
        reason="Guest requested different dates",
    )

    assert result.recreated is True
    assert result.original_reservation.id == reservation.id
    assert result.original_reservation.status == ReservationStatusEnum.CANCELLED
    assert result.reservation.id != reservation.id
    assert result.reservation.check_in_date == date(2026, 7, 5)
    assert result.reservation.check_out_date == date(2026, 7, 7)


def test_date_change_with_payments_requires_manager_and_preserves_history(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    tx = _completed_transaction(db, reservation)

    with pytest.raises(ReservationOperationsError, match="requiere gerente"):
        change_reservation_dates(
            db,
            reservation=reservation,
            hotel_id=1,
            check_in_date=date(2026, 7, 5),
            check_out_date=date(2026, 7, 7),
            client_version=reservation.version,
            manager_authorized=False,
        )

    result = change_reservation_dates(
        db,
        reservation=reservation,
        hotel_id=1,
        check_in_date=date(2026, 7, 5),
        check_out_date=date(2026, 7, 7),
        client_version=reservation.version,
        manager_authorized=True,
        pricing_mode="keep_current_total",
    )

    assert result.recreated is False
    assert result.reservation.id == reservation.id
    assert reservation.check_in_date == date(2026, 7, 5)
    assert db.get(Transaction, tx.id).reservation_id == reservation.id
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1


def test_extension_requires_payment_or_link_action(db, hotel_config, sample_guest, sample_categories, sample_rooms):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)
    reservation.status = ReservationStatusEnum.FULLY_PAID
    reservation.amount_paid = reservation.total_amount
    db.flush()

    with pytest.raises(ReservationOperationsError, match="requiere generar link"):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=1,
            new_checkout_date=date(2026, 7, 4),
            client_version=reservation.version,
            pricing_mode="current_rate",
            payment_action="payment_link",
        )

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=1,
        new_checkout_date=date(2026, 7, 4),
        client_version=reservation.version,
        pricing_mode="current_rate",
        payment_action="payment_link",
        payment_link=PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
        ),
        notes="Guest extends one night",
    )

    assert reservation.check_out_date == date(2026, 7, 4)
    assert result.extension_amount == Decimal("100.00")
    assert result.payment_link is not None
    assert result.payment_link.reservation_id == reservation.id


def test_reservation_lifecycle_optimistic_lock_conflict(
    db,
    hotel_config,
    sample_guest,
    sample_categories,
    sample_rooms,
):
    reservation = _create_sample_reservation(db, sample_guest, sample_categories, sample_rooms)

    with pytest.raises(ReservationError, match="modified concurrently"):
        mark_reservation_no_show(
            db,
            reservation,
            hotel_id=1,
            client_version=reservation.version + 1,
        )
