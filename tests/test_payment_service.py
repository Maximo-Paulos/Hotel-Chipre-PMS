"""
Tests for Payment Service — Financial Engine.
Tests the complete payment lifecycle including:
- Deposit payments (30%)
- Full payments
- Balance payments at check-in
- State transitions triggered by payments
- Edge cases (overpayment, disabled methods)
"""
import pytest
from datetime import date

from app.models.hotel_config import HotelConfiguration
from app.models.pricing import CategoryPricing
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import Transaction, PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentRequest, PaymentGatewayResponse
from app.services.reservation_service import create_reservation
from app.services.payment_service import (
    process_payment,
    get_reservation_financial_summary,
    PaymentError,
)

DEFAULT_HOTEL_ID = 1
ALT_HOTEL_ID = 2


@pytest.fixture(autouse=True)
def ensure_category_pricing_table(db_engine):
    """Create CategoryPricing table for tests (not included in Base metadata)."""
    CategoryPricing.__table__.create(bind=db_engine, checkfirst=True)
    yield


def _assign_hotel(reservation: Reservation, hotel_id: int, db):
    """Assign hotel scope to reservation (hotel_id column provided by A1)."""
    setattr(reservation, "hotel_id", hotel_id)
    db.flush()


class TestDepositPayment:
    """Tests for deposit (señas) payment flow."""

    def test_deposit_payment_transitions_status(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """
        Scenario: $1000 reservation. Pay 30% deposit ($300).
        Expected: Status → deposit_paid, balance = $700.
        """
        # Create reservation for $1000 (10 nights × $100)
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 11),  # 10 nights
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)

        assert res.total_amount == 1000.0  # 10 × $100
        assert res.deposit_amount == 300.0  # 30% of $1000
        assert res.status == ReservationStatusEnum.PENDING

        # Pay deposit
        payment = PaymentRequest(
            reservation_id=res.id,
            amount=300.0,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        )

        # Simulate gateway success
        gateway_resp = PaymentGatewayResponse(
            success=True,
            external_payment_id="mp_pref_12345",
            external_status="approved",
            gateway_response='{"id": "mp_pref_12345", "status": "approved"}',
        )

        tx = process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID, gateway_response=gateway_resp)
        db.flush()

        # Verify transaction
        assert tx.status == TransactionStatusEnum.COMPLETED
        assert tx.amount == 300.0
        assert tx.payment_method == PaymentMethodEnum.MERCADO_PAGO
        assert tx.external_payment_id == "mp_pref_12345"

        # Verify reservation state
        db.refresh(res)
        assert res.status == ReservationStatusEnum.DEPOSIT_PAID
        assert res.amount_paid == 300.0
        assert res.balance_due == 700.0

    def test_deposit_below_threshold_stays_pending(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """
        Paying LESS than the deposit threshold should keep status as PENDING.
        """
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 5, 1),
            check_out_date=date(2026, 5, 11),
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)

        # Pay only $100 (deposit is $300)
        payment = PaymentRequest(
            reservation_id=res.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        )
        process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID)
        db.flush()

        db.refresh(res)
        assert res.status == ReservationStatusEnum.PENDING  # Still pending
        assert res.amount_paid == 100.0
        assert res.balance_due == 900.0


class TestFullPayment:
    """Tests for full payment flow."""

    def test_full_payment_in_one_shot(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """
        Pay the full amount at once → status should go directly to fully_paid.
        """
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 6, 1),
            check_out_date=date(2026, 6, 6),  # 5 nights → $500
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()

        assert res.total_amount == 500.0

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=500.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID)
        db.flush()

        db.refresh(res)
        assert res.status == ReservationStatusEnum.FULLY_PAID
        assert res.amount_paid == 500.0
        assert res.balance_due == 0.0


class TestBalancePaymentAtCheckin:
    """
    Critical test: Simulates web booking with deposit, then balance payment at check-in.
    This is the exact flow described in the requirements.
    """

    def test_web_booking_deposit_then_cash_at_checkin(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """
        Requirement test:
        1. Web booking of $1000
        2. Pay $300 deposit via MercadoPago → deposit_paid
        3. Pay remaining $700 in cash at check-in → fully_paid
        4. Verify financial summary shows both transactions correctly
        """
        # Step 1: Create $1000 reservation
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 4, 1),
            check_out_date=date(2026, 4, 11),  # 10 nights × $100
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()

        assert res.total_amount == 1000.0
        assert res.status == ReservationStatusEnum.PENDING

        # Step 2: Pay $300 deposit via MercadoPago
        deposit_payment = PaymentRequest(
            reservation_id=res.id,
            amount=300.0,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        )
        gateway_resp = PaymentGatewayResponse(
            success=True,
            external_payment_id="mp_dep_001",
            external_status="approved",
        )
        tx1 = process_payment(db, deposit_payment, hotel_id=DEFAULT_HOTEL_ID, gateway_response=gateway_resp)
        db.flush()

        db.refresh(res)
        assert res.status == ReservationStatusEnum.DEPOSIT_PAID
        assert res.amount_paid == 300.0
        assert res.balance_due == 700.0

        # Step 3: Pay remaining $700 in CASH at check-in
        balance_payment = PaymentRequest(
            reservation_id=res.id,
            amount=700.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
        )
        tx2 = process_payment(db, balance_payment, hotel_id=DEFAULT_HOTEL_ID)
        db.flush()

        db.refresh(res)
        assert res.status == ReservationStatusEnum.FULLY_PAID
        assert res.amount_paid == 1000.0
        assert res.balance_due == 0.0

        # Step 4: Verify financial summary
        summary = get_reservation_financial_summary(db, DEFAULT_HOTEL_ID, res.id)
        assert summary["total_amount"] == 1000.0
        assert summary["amount_paid"] == 1000.0
        assert summary["balance_due"] == 0.0
        assert summary["completed_payments"] == 1000.0
        assert len(summary["transactions"]) == 2

        # Verify transaction details
        tx_methods = [t["method"] for t in summary["transactions"]]
        assert "mercado_pago" in tx_methods
        assert "cash" in tx_methods


class TestHotelIsolation:
    """Multi-hotel safety: scope payments and methods by hotel_id."""

    def test_payment_rejected_for_other_hotel(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 9, 1),
            check_out_date=date(2026, 9, 3),
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        with pytest.raises(PaymentError, match="does not belong to hotel"):
            process_payment(db, payment, hotel_id=2)

    def test_payment_methods_are_scoped_by_hotel(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        hotel_config.enable_bank_transfer = False
        config_h2 = HotelConfiguration(id=2, enable_bank_transfer=True, deposit_percentage=30.0)
        db.add(config_h2)
        db.flush()

        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 10, 1),
            check_out_date=date(2026, 10, 4),
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()
        _assign_hotel(res, ALT_HOTEL_ID, db)

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=res.total_amount,
            payment_method=PaymentMethodEnum.BANK_TRANSFER,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )

        tx = process_payment(db, payment, hotel_id=2)
        assert tx.payment_method == PaymentMethodEnum.BANK_TRANSFER


class TestPaymentEdgeCases:
    """Edge case tests for the payment engine."""

    def test_overpayment_rejected(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Cannot pay more than the outstanding balance."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),  # $200
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=500.0,  # More than $200!
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        with pytest.raises(PaymentError, match="exceeds balance due"):
            process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID)

    def test_payment_on_cancelled_reservation(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Cannot pay for a cancelled reservation."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 7, 5),
            check_out_date=date(2026, 7, 7),
        )
        res = create_reservation(db, data, hotel_id=1)
        res.status = ReservationStatusEnum.CANCELLED
        db.flush()
        _assign_hotel(res, DEFAULT_HOTEL_ID, db)

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        )
        with pytest.raises(PaymentError, match="Cannot process payment"):
            process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID)

    def test_disabled_payment_method_rejected(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Cannot use a disabled payment method."""
        hotel_config.enable_bank_transfer = False  # Explicitly disabled
        db.flush()

        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 3),
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.BANK_TRANSFER,  # Disabled!
            transaction_type=TransactionTypeEnum.DEPOSIT,
        )
        with pytest.raises(PaymentError, match="currently disabled"):
            process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID)

    def test_failed_gateway_payment(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        """Failed gateway payment should not update reservation financials."""
        data = ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            check_in_date=date(2026, 8, 5),
            check_out_date=date(2026, 8, 8),
        )
        res = create_reservation(db, data, hotel_id=1)
        db.flush()

        payment = PaymentRequest(
            reservation_id=res.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.PAYPAL,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        )
        failed_resp = PaymentGatewayResponse(
            success=False,
            error_message="PayPal declined",
        )
        tx = process_payment(db, payment, hotel_id=DEFAULT_HOTEL_ID, gateway_response=failed_resp)
        db.flush()

        assert tx.status == TransactionStatusEnum.FAILED
        db.refresh(res)
        assert res.amount_paid == 0.0  # No change
        assert res.status == ReservationStatusEnum.PENDING  # No transition

