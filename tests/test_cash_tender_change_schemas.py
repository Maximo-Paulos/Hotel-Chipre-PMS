from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.reservation_group_payment import (
    ReservationGroupPaymentAllocationRequest,
    ReservationGroupPaymentCreate,
)
from app.schemas.transaction import PaymentRequest


def test_cash_payment_request_accepts_physical_tender_separate_from_charge():
    payment = PaymentRequest(
        reservation_id=1,
        amount=46000,
        cash_received_amount=Decimal("50000.00"),
        cash_tip_amount=Decimal("200.00"),
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
    )

    assert payment.amount == 46000
    assert payment.cash_received_amount == Decimal("50000.00")
    assert payment.cash_tip_amount == Decimal("200.00")


@pytest.mark.parametrize(
    "payment_method,transaction_type",
    [
        (PaymentMethodEnum.BANK_TRANSFER, TransactionTypeEnum.PARTIAL_PAYMENT),
        (PaymentMethodEnum.CASH, TransactionTypeEnum.REFUND),
    ],
)
def test_individual_payment_rejects_cash_tender_for_non_cash_or_refund(payment_method, transaction_type):
    with pytest.raises(ValidationError):
        PaymentRequest(
            reservation_id=1,
            amount=46000,
            cash_received_amount=Decimal("50000.00"),
            payment_method=payment_method,
            transaction_type=transaction_type,
        )


def test_group_payment_keeps_allocation_total_separate_from_physical_cash_tender():
    payment = ReservationGroupPaymentCreate(
        received_amount=Decimal("46000.00"),
        cash_received_amount=Decimal("50000.00"),
        cash_tip_amount=Decimal("200.00"),
        currency="ARS",
        payment_method=PaymentMethodEnum.CASH,
        allocations=[
            ReservationGroupPaymentAllocationRequest(reservation_id=1, received_amount=Decimal("30000.00")),
            ReservationGroupPaymentAllocationRequest(reservation_id=2, received_amount=Decimal("16000.00")),
        ],
    )

    assert payment.received_amount == Decimal("46000.00")
    assert payment.cash_received_amount == Decimal("50000.00")
    assert payment.cash_tip_amount == Decimal("200.00")


def test_group_payment_rejects_physical_cash_tender_for_non_cash_method():
    with pytest.raises(ValidationError):
        ReservationGroupPaymentCreate(
            received_amount=Decimal("46000.00"),
            cash_received_amount=Decimal("50000.00"),
            currency="ARS",
            payment_method=PaymentMethodEnum.BANK_TRANSFER,
            allocations=[
                ReservationGroupPaymentAllocationRequest(
                    reservation_id=1,
                    received_amount=Decimal("46000.00"),
                ),
            ],
        )


@pytest.mark.parametrize(
    "payment_method,transaction_type,received",
    [
        (PaymentMethodEnum.CASH, TransactionTypeEnum.PARTIAL_PAYMENT, None),
        (PaymentMethodEnum.BANK_TRANSFER, TransactionTypeEnum.PARTIAL_PAYMENT, Decimal("50000.00")),
        (PaymentMethodEnum.CASH, TransactionTypeEnum.REFUND, Decimal("50000.00")),
    ],
)
def test_individual_payment_requires_cash_tender_for_explicit_tip(payment_method, transaction_type, received):
    with pytest.raises(ValidationError):
        PaymentRequest(
            reservation_id=1,
            amount=46000,
            cash_received_amount=received,
            cash_tip_amount=Decimal("200.00"),
            payment_method=payment_method,
            transaction_type=transaction_type,
        )


def test_group_payment_requires_cash_tender_for_explicit_tip():
    with pytest.raises(ValidationError):
        ReservationGroupPaymentCreate(
            received_amount=Decimal("46000.00"),
            currency="ARS",
            payment_method=PaymentMethodEnum.CASH,
            cash_tip_amount=Decimal("200.00"),
            allocations=[
                ReservationGroupPaymentAllocationRequest(
                    reservation_id=1,
                    received_amount=Decimal("46000.00"),
                ),
            ],
        )
