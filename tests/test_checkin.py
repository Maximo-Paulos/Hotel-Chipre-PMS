"""
Tests for Check-in Service.
Validates guest data requirements before allowing check-in.
"""
import pytest
from datetime import date
from sqlalchemy import func
from app.models.company import Company
from app.models.company_document import CompanyDocumentTypeEnum, CompanyDocumentStatusEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.stored_object import StoredObject, StoredObjectStatusEnum
from app.models.guest import Guest
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation
from app.services.company_document_service import create_document, set_signature_status
from app.services.payment_service import process_payment
from app.services import checkin_service
from app.services.checkin_service import perform_checkin, perform_checkout, validate_guest_for_checkin, CheckInError
from app.schemas.transaction import PaymentRequest
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.services.cash_register_service import open_session


@pytest.fixture(autouse=True)
def opened_cash_register(db, hotel_config, monkeypatch):
    """Operational tests must prepare the caja before collecting cash."""
    # These fixtures use historical reservation dates. Pin the hotel-local day
    # to the reservation's arrival so the tests exercise payment/data rules,
    # not the separate early/expired-arrival guards.
    def hotel_day_for_test(session, hotel_id):
        latest_arrival = (
            session.query(func.max(Reservation.check_in_date))
            .filter(Reservation.hotel_id == hotel_id)
            .scalar()
        )
        return latest_arrival or date(2027, 1, 1)

    monkeypatch.setattr(checkin_service, "hotel_today", hotel_day_for_test)
    open_session(db, hotel_id=hotel_config.id, opened_by_user_id=None, opening_balance=0)


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
        # birth_place/birth_country/marital_status/occupation (B3.3) are always
        # required regardless of config -- only document/terms are config-gated.
        sample_guest_incomplete.birth_place = "Cordoba"
        sample_guest_incomplete.birth_country = "Argentina"
        sample_guest_incomplete.marital_status = "single"
        sample_guest_incomplete.occupation = "Docente"
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
        process_payment(db, payment, hotel_id=config.id)
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
        with pytest.raises(CheckInError, match="full reservation amount"):
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
        process_payment(db, payment, hotel_id=hotel_config.id)
        db.flush()
        db.refresh(res)
        with pytest.raises(CheckInError, match="missing required guest data"):
            perform_checkin(db, res.id)

    def test_company_checkin_requires_private_voucher_and_signed_document(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        company = Company(
            hotel_id=hotel_config.id,
            legal_name="Check-in Voucher SA",
            display_name="Check-in Voucher",
            payment_deferred=True,
            requires_voucher=True,
            requires_signature=True,
        )
        db.add(company)
        db.flush()
        reservation = create_reservation(
            db,
            ReservationCreate(
                guest_id=sample_guest.id,
                category_id=sample_categories[0].id,
                room_id=sample_rooms[0].id,
                company_id=company.id,
                check_in_date=date(2026, 4, 1),
                check_out_date=date(2026, 4, 3),
            ),
            hotel_id=hotel_config.id,
        )
        db.flush()

        with pytest.raises(CheckInError, match="requires an uploaded reservation voucher"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        stored_object = StoredObject(
            hotel_id=hotel_config.id,
            purpose="company_voucher",
            object_key="company-vouchers/test/checkin.pdf",
            backend="local",
            content_type="application/pdf",
            byte_size=8,
            sha256_hex="0" * 64,
            status=StoredObjectStatusEnum.READY.value,
        )
        db.add(stored_object)
        db.flush()
        voucher = create_document(
            db,
            hotel_id=hotel_config.id,
            user_id=None,
            reservation_id=reservation.id,
            company_id=company.id,
            doc_type=CompanyDocumentTypeEnum.VOUCHER_PDF,
            file_name="voucher.pdf",
            stored_object_id=stored_object.id,
            requires_signature=True,
        )

        with pytest.raises(CheckInError, match="requires a signed reservation document"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        set_signature_status(
            db,
            hotel_id=hotel_config.id,
            user_id=None,
            document_id=voucher.id,
            status=CompanyDocumentStatusEnum.SIGNED,
        )
        checked_in = perform_checkin(db, reservation.id, hotel_id=hotel_config.id)
        assert checked_in.status == ReservationStatusEnum.CHECKED_IN


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
        process_payment(db, payment, hotel_id=hotel_config.id)
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
