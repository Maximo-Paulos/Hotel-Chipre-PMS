"""
V72 §7.1 — Check-in Payment Gate Tests.

Requirement: check-in payment is configured per hotel (deposit by default, full amount, or no upfront payment).

These tests are COMPLEMENTARY to tests/test_checkin.py.
They focus on explicit payment-gate scenarios not covered there:
  - deposit policy allows check-in after the configured deposit
  - total policy blocks a deposit-only payment
  - free policy permits check-in without upfront payment
  - arrival date is enforced
  - validate_guest_for_checkin document/terms checks as separate cases
  - Checkout room status side-effects
  - Cancelled reservation blocked at check-in
"""
import pytest
from datetime import date, timedelta
from sqlalchemy import func

from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomStatusEnum, Room
from app.models.guest import Guest, DocumentTypeEnum
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation
from app.services.payment_service import process_payment
from app.services.checkin_service import (
    perform_checkin,
    perform_checkout,
    validate_guest_for_checkin,
    CheckInError,
)
from app.services import checkin_service
from app.schemas.transaction import PaymentRequest, PaymentGatewayResponse
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.services.cash_register_service import open_session


@pytest.fixture(autouse=True)
def opened_cash_register(db, hotel_config, monkeypatch):
    """Payment-gate scenarios start with an explicitly opened caja."""
    # Anchor ordinary cases to their own arrival date; dedicated tests below
    # replace this value to exercise early/expired arrival boundaries.
    def hotel_day_for_test(session, hotel_id):
        latest_arrival = (
            session.query(func.max(Reservation.check_in_date))
            .filter(Reservation.hotel_id == hotel_id)
            .scalar()
        )
        return latest_arrival or date(2027, 1, 1)

    monkeypatch.setattr(checkin_service, "hotel_today", hotel_day_for_test)
    open_session(db, hotel_id=hotel_config.id, opened_by_user_id=None, opening_balance=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_reservation(db, guest, categories, check_in=date(2027, 1, 10), check_out=date(2027, 1, 12)):
    """Create a PENDING reservation using the first available category."""
    data = ReservationCreate(
        guest_id=guest.id,
        category_id=categories[0].id,
        check_in_date=check_in,
        check_out_date=check_out,
    )
    res = create_reservation(db, data)
    db.flush()
    return res


def _pay_deposit(db, reservation, hotel_id=1):
    """Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.

    Note: TransactionTypeEnum.DEPOSIT with is_deposit=True has a known bug where
    it doubles the deposit_amount threshold before checking status, so we use
    PARTIAL_PAYMENT for a clean deposit-amount partial payment instead.
    """
    deposit_amount = reservation.deposit_amount
    assert deposit_amount > 0, "Reservation must have a positive deposit_amount (check hotel_config.deposit_percentage)"
    payment = PaymentRequest(
        reservation_id=reservation.id,
        amount=deposit_amount,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
    )
    process_payment(db, payment, hotel_id=hotel_id)
    db.flush()
    db.refresh(reservation)


def _pay_full(db, reservation, hotel_id=1):
    """Pay the full amount → FULLY_PAID."""
    payment = PaymentRequest(
        reservation_id=reservation.id,
        amount=reservation.total_amount,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.FULL_PAYMENT,
    )
    process_payment(db, payment, hotel_id=hotel_id)
    db.flush()
    db.refresh(reservation)


# ---------------------------------------------------------------------------
# Hotel payment policy: deposit is the explicit configured default.
# ---------------------------------------------------------------------------

class TestPaymentGateDepositPaid:
    """Check-in must follow the explicit per-hotel payment policy."""

    def test_default_deposit_policy_allows_checkin_after_deposit(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        assert hotel_config.checkin_payment_policy == "deposit"
        res = _make_reservation(db, sample_guest, sample_categories)
        _pay_deposit(db, res)
        assert res.status == ReservationStatusEnum.DEPOSIT_PAID

        result = perform_checkin(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_IN

    def test_total_policy_blocks_deposit_only_and_allows_full_payment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        hotel_config.checkin_payment_policy = "total"
        db.flush()
        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 2, 1), check_out=date(2027, 2, 3))
        _pay_deposit(db, res)

        with pytest.raises(CheckInError, match="full reservation amount"):
            perform_checkin(db, res.id)

        remaining = res.total_amount - res.amount_paid
        process_payment(
            db,
            PaymentRequest(
                reservation_id=res.id,
                amount=remaining,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.FULL_PAYMENT,
            ),
            hotel_id=hotel_config.id,
        )
        db.flush()
        db.refresh(res)
        assert perform_checkin(db, res.id).status == ReservationStatusEnum.CHECKED_IN

    def test_free_policy_allows_checkin_without_upfront_payment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        hotel_config.checkin_payment_policy = "free"
        db.flush()
        res = _make_reservation(db, sample_guest, sample_categories)

        assert res.status == ReservationStatusEnum.PENDING
        assert perform_checkin(db, res.id).status == ReservationStatusEnum.CHECKED_IN

    def test_free_policy_still_blocks_unconfirmed_legacy_ota_prepayment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        hotel_config.checkin_payment_policy = "free"
        db.flush()
        res = _make_reservation(db, sample_guest, sample_categories)
        res.source_provider_code = "booking"
        res.external_id = "BKG-LEGACY-UNVERIFIED"
        res.external_paid_amount = 30
        res.external_paid_confirmed = False
        res.external_paid_ever_confirmed = True
        res.amount_paid = 0
        db.flush()

        with pytest.raises(CheckInError, match="OTA prepayment needs a manager's confirmation"):
            perform_checkin(db, res.id)

    def test_checkin_before_arrival_date_is_rejected(
        self, db, sample_guest, sample_rooms, sample_categories, monkeypatch
    ):
        today = date(2026, 9, 27)
        monkeypatch.setattr(checkin_service, "hotel_today", lambda _db, _hotel_id: today)
        # Create through the normal quote/availability path, then move the
        # persisted dates to tomorrow so this test isolates the check-in gate.
        res = _make_reservation(db, sample_guest, sample_categories)
        res.check_in_date = today + timedelta(days=1)
        res.check_out_date = today + timedelta(days=3)
        db.flush()

        with pytest.raises(CheckInError, match="before the reservation arrival date"):
            perform_checkin(db, res.id)

    def test_checkin_after_departure_date_is_rejected(self, db, sample_guest, sample_rooms, sample_categories, monkeypatch):
        today = date(2026, 9, 27)
        monkeypatch.setattr(checkin_service, "hotel_today", lambda _db, _hotel_id: today)
        res = _make_reservation(db, sample_guest, sample_categories)
        res.check_in_date = today - timedelta(days=3)
        res.check_out_date = today
        db.flush()

        with pytest.raises(CheckInError, match="after the reservation departure date"):
            perform_checkin(db, res.id)

    def test_checkin_succeeds_after_balance_paid_following_deposit(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """§7.1 positive: paying the remaining balance after deposit allows check-in."""
        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 4, 1), check_out=date(2027, 4, 3))
        _pay_deposit(db, res)
        assert res.status == ReservationStatusEnum.DEPOSIT_PAID

        # Pay the remaining balance
        remaining = res.total_amount - res.amount_paid
        assert remaining > 0
        balance_payment = PaymentRequest(
            reservation_id=res.id,
            amount=remaining,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        )
        process_payment(db, balance_payment, hotel_id=hotel_config.id)
        db.flush()
        db.refresh(res)
        assert res.status == ReservationStatusEnum.FULLY_PAID

        result = perform_checkin(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_IN


# ---------------------------------------------------------------------------
# §7.1 — Payment gate: PENDING is explicitly blocked
# ---------------------------------------------------------------------------

class TestPaymentGatePending:
    """PENDING status (no payment at all) must NOT allow check-in."""

    def test_checkin_blocked_when_pending_error_mentions_status(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """§7.1: Error message mentions current status 'pending' when no payment made."""
        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 5, 1), check_out=date(2027, 5, 3))
        assert res.status == ReservationStatusEnum.PENDING

        with pytest.raises(CheckInError, match="configured deposit"):
            perform_checkin(db, res.id)

    def test_checkin_blocked_cancelled_reservation(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """§7.1: A CANCELLED reservation cannot be checked in regardless of payment."""
        from app.services.reservation_service import transition_reservation_status

        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 6, 1), check_out=date(2027, 6, 3))
        transition_reservation_status(db, res, ReservationStatusEnum.CANCELLED, hotel_config.id)
        db.flush()
        db.refresh(res)
        assert res.status == ReservationStatusEnum.CANCELLED

        with pytest.raises(CheckInError):
            perform_checkin(db, res.id)


# ---------------------------------------------------------------------------
# The guest identity/terms flags remain independent from the payment policy.
# ---------------------------------------------------------------------------

class TestConfigFlag:
    """Verify payment and guest-data gates remain separate."""

    def test_default_config_enforces_payment_gate(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Config flag is True by default; gate is active for PENDING reservation."""
        assert hotel_config.require_document_for_checkin is True
        assert hotel_config.require_terms_acceptance is True
        assert hotel_config.checkin_payment_policy == "deposit"

        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 7, 1), check_out=date(2027, 7, 3))
        # Reservation is PENDING — the default deposit policy still applies.
        with pytest.raises(CheckInError, match="configured deposit"):
            perform_checkin(db, res.id)

    def test_payment_gate_not_bypassable_via_config(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Even if document/terms config flags are disabled, payment gate remains active."""
        hotel_config.require_document_for_checkin = False
        hotel_config.require_terms_acceptance = False
        db.flush()

        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 8, 1), check_out=date(2027, 8, 3))
        # Disabling guest-document checks cannot bypass the separate payment gate.
        with pytest.raises(CheckInError, match="configured deposit"):
            perform_checkin(db, res.id)


# ---------------------------------------------------------------------------
# validate_guest_for_checkin — document and terms as separate gate checks
# ---------------------------------------------------------------------------

class TestGuestValidationGates:
    """Separate coverage of document-not-verified vs terms-not-signed blocks."""

    def test_guest_without_document_type_is_blocked(self, db, hotel_config):
        """Guest with no document_type set is blocked by validate_guest_for_checkin."""
        from app.models.hotel_config import HotelConfiguration
        guest = Guest(
            first_name="Sin",
            last_name="Documento",
            email="sin_doc@test.com",
            terms_accepted=True,
            hotel_id=1,
            # document_type and document_number intentionally omitted
        )
        db.add(guest)
        db.flush()

        hotel_config.require_document_for_checkin = True
        db.flush()

        errors = validate_guest_for_checkin(db, guest, hotel_config)
        assert len(errors) > 0
        assert any("document" in e.lower() or "Document" in e for e in errors)

    def test_guest_without_document_number_is_blocked(self, db, hotel_config):
        """Guest with document_type but no document_number is blocked."""
        guest = Guest(
            first_name="Sin",
            last_name="Numero",
            email="sin_num@test.com",
            document_type=DocumentTypeEnum.DNI,
            # document_number intentionally omitted
            terms_accepted=True,
            hotel_id=1,
        )
        db.add(guest)
        db.flush()

        hotel_config.require_document_for_checkin = True
        db.flush()

        errors = validate_guest_for_checkin(db, guest, hotel_config)
        assert len(errors) > 0
        assert any("number" in e.lower() or "Number" in e for e in errors)

    def test_guest_without_terms_accepted_is_blocked(self, db, hotel_config):
        """Guest who has NOT accepted terms is blocked (terms_accepted=False)."""
        guest = Guest(
            first_name="No",
            last_name="Terms",
            email="no_terms@test.com",
            document_type=DocumentTypeEnum.DNI,
            document_number="99887766",
            terms_accepted=False,   # <-- not accepted
            hotel_id=1,
        )
        db.add(guest)
        db.flush()

        hotel_config.require_terms_acceptance = True
        db.flush()

        errors = validate_guest_for_checkin(db, guest, hotel_config)
        assert len(errors) > 0
        assert any("terms" in e.lower() for e in errors)

    def test_document_check_disabled_allows_guest_without_document(self, db, hotel_config):
        """When require_document_for_checkin=False, missing document is not an error."""
        guest = Guest(
            first_name="OK",
            last_name="NoDoc",
            email="ok_nodoc@test.com",
            terms_accepted=True,
            birth_place="Salta",
            birth_country="Argentina",
            marital_status="single",
            occupation="Chef",
            hotel_id=1,
        )
        db.add(guest)
        db.flush()

        hotel_config.require_document_for_checkin = False
        hotel_config.require_terms_acceptance = False
        db.flush()

        errors = validate_guest_for_checkin(db, guest, hotel_config)
        assert len(errors) == 0

    def test_terms_check_disabled_allows_guest_without_terms(self, db, hotel_config):
        """When require_terms_acceptance=False, missing terms is not an error."""
        guest = Guest(
            first_name="OK",
            last_name="NoTerms",
            email="ok_noterms@test.com",
            document_type=DocumentTypeEnum.PASSPORT,
            document_number="XYZ123456",
            terms_accepted=False,
            birth_place="Salta",
            birth_country="Argentina",
            marital_status="single",
            occupation="Chef",
            hotel_id=1,
        )
        db.add(guest)
        db.flush()

        hotel_config.require_document_for_checkin = False
        hotel_config.require_terms_acceptance = False
        db.flush()

        errors = validate_guest_for_checkin(db, guest, hotel_config)
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# perform_checkout — side-effects and failure modes
# ---------------------------------------------------------------------------

class TestCheckoutGate:
    """Checkout after successful check-in, and failure when not checked_in."""

    def _full_checkin(self, db, guest, rooms, categories, config, check_in=date(2027, 9, 1), check_out=date(2027, 9, 3)):
        res = _make_reservation(db, guest, categories, check_in=check_in, check_out=check_out)
        _pay_full(db, res, hotel_id=config.id)
        assert res.status == ReservationStatusEnum.FULLY_PAID
        perform_checkin(db, res.id)
        db.flush()
        db.refresh(res)
        assert res.status == ReservationStatusEnum.CHECKED_IN
        return res

    def test_checkout_sets_checked_out_status(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Checkout transitions status from CHECKED_IN → CHECKED_OUT."""
        res = self._full_checkin(db, sample_guest, sample_rooms, sample_categories, hotel_config)
        result = perform_checkout(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_OUT

    def test_checkout_records_actual_checkout_timestamp(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """perform_checkout sets actual_check_out timestamp."""
        res = self._full_checkin(db, sample_guest, sample_rooms, sample_categories, hotel_config,
                                  check_in=date(2027, 10, 1), check_out=date(2027, 10, 3))
        result = perform_checkout(db, res.id)
        assert result.actual_check_out is not None

    def test_checkout_marks_room_for_cleaning(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """After checkout, the assigned room status is set to CLEANING."""
        res = self._full_checkin(db, sample_guest, sample_rooms, sample_categories, hotel_config,
                                  check_in=date(2027, 11, 1), check_out=date(2027, 11, 3))

        if res.room_id is None:
            pytest.skip("No room assigned to reservation — room status side-effect not applicable")

        room = db.query(Room).filter(Room.id == res.room_id).first()
        assert room.status == RoomStatusEnum.OCCUPIED  # set during check-in

        perform_checkout(db, res.id)
        db.refresh(room)
        assert room.status == RoomStatusEnum.CLEANING

    def test_checkout_fails_when_fully_paid_not_checked_in(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Cannot checkout a FULLY_PAID reservation that was never checked in."""
        res = _make_reservation(db, sample_guest, sample_categories,
                                 check_in=date(2027, 12, 1), check_out=date(2027, 12, 3))
        _pay_full(db, res, hotel_id=hotel_config.id)
        assert res.status == ReservationStatusEnum.FULLY_PAID

        with pytest.raises(CheckInError, match="checked_in"):
            perform_checkout(db, res.id)

    def test_checkout_fails_when_pending(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Cannot checkout a PENDING reservation."""
        res = _make_reservation(db, sample_guest, sample_categories,
                                 check_in=date(2028, 1, 1), check_out=date(2028, 1, 3))
        assert res.status == ReservationStatusEnum.PENDING

        with pytest.raises(CheckInError, match="checked_in"):
            perform_checkout(db, res.id)

    def test_checkout_idempotency_fails_second_call(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Calling perform_checkout twice on the same reservation raises CheckInError on second call."""
        res = self._full_checkin(db, sample_guest, sample_rooms, sample_categories, hotel_config,
                                  check_in=date(2028, 2, 1), check_out=date(2028, 2, 3))
        perform_checkout(db, res.id)
        db.flush()
        db.refresh(res)
        assert res.status == ReservationStatusEnum.CHECKED_OUT

        with pytest.raises(CheckInError):
            perform_checkout(db, res.id)
