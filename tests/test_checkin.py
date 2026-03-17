"""
Tests for Check-in Service.
Validates guest data requirements before allowing check-in.
"""
import pytest
from datetime import date
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.guest import Guest
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation
from app.services.payment_service import process_payment
from app.services.checkin_service import perform_checkin, perform_checkout, validate_guest_for_checkin, CheckInError
from app.schemas.transaction import PaymentRequest
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum


class TestGuestValidation:
    def test_valid_guest_passes(self, db, sample_guest, hotel_config):
        errors = validate_guest_for_checkin(db, sample_guest, hotel_config)
        assert len(errors) == 0

    def test_missing_document_fails(self, db, sample_guest_incomplete, hotel_config):
        errors = validate_guest_for_checkin(db, sample_guest_incomplete, hotel_config)
        assert any("Document type" in e for e in errors)
        assert any("Document number" in e for e in errors)

    def test_missing_terms_fails(self, db, sample_guest_incomplete, hotel_config):
        errors = validate_guest_for_checkin(db, sample_guest_incomplete, hotel_config)
        assert any("terms" in e.lower() for e in errors)

    def test_validation_respects_config(self, db, sample_guest_incomplete, hotel_config):
        hotel_config.require_document_for_checkin = False
        hotel_config.require_terms_acceptance = False
        db.flush()
        errors = validate_guest_for_checkin(db, sample_guest_incomplete, hotel_config)
        assert len(errors) == 0


class TestCheckIn:
    def _create_fully_paid_reservation(self, db, guest, rooms, categories, config):
        data = ReservationCreate(
            guest_id=guest.id, category_id=categories[0].id,
            check_in_date=date(2026,4,1), check_out_date=date(2026,4,3),
        )
        res = create_reservation(db, data)
        db.flush()
        payment = PaymentRequest(
            reservation_id=res.id, amount=res.total_amount,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        process_payment(db, payment)
        db.flush()
        return res

    def test_checkin_success(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        res = self._create_fully_paid_reservation(db, sample_guest, sample_rooms, sample_categories, hotel_config)
        db.refresh(res)
        assert res.status == ReservationStatusEnum.FULLY_PAID
        result = perform_checkin(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_IN
        assert result.actual_check_in is not None

    def test_checkin_blocked_without_payment(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id, category_id=sample_categories[0].id,
            check_in_date=date(2026,5,1), check_out_date=date(2026,5,3),
        )
        res = create_reservation(db, data)
        db.flush()
        with pytest.raises(CheckInError, match="fully_paid"):
            perform_checkin(db, res.id)

    def test_checkin_blocked_missing_documents(self, db, sample_guest_incomplete, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest_incomplete.id, category_id=sample_categories[0].id,
            check_in_date=date(2026,6,1), check_out_date=date(2026,6,3),
        )
        res = create_reservation(db, data)
        db.flush()
        payment = PaymentRequest(
            reservation_id=res.id, amount=res.total_amount,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        process_payment(db, payment)
        db.flush()
        db.refresh(res)
        with pytest.raises(CheckInError, match="missing required guest data"):
            perform_checkin(db, res.id)


class TestCheckOut:
    def test_checkout_success(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id, category_id=sample_categories[0].id,
            check_in_date=date(2026,7,1), check_out_date=date(2026,7,3),
        )
        res = create_reservation(db, data)
        db.flush()
        payment = PaymentRequest(
            reservation_id=res.id, amount=res.total_amount,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        process_payment(db, payment)
        db.flush()
        perform_checkin(db, res.id)
        db.flush()
        result = perform_checkout(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_OUT
        assert result.actual_check_out is not None

    def test_checkout_not_checked_in(self, db, sample_guest, sample_rooms, sample_categories, hotel_config):
        data = ReservationCreate(
            guest_id=sample_guest.id, category_id=sample_categories[0].id,
            check_in_date=date(2026,8,1), check_out_date=date(2026,8,3),
        )
        res = create_reservation(db, data)
        db.flush()
        with pytest.raises(CheckInError, match="checked_in"):
            perform_checkout(db, res.id)
