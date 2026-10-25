"""
V72 §7.1 — Check-in Payment Gate Tests.

Requirement: direct check-in requires full payment; deferred company accounts are handled separately.

These tests are COMPLEMENTARY to tests/test_checkin.py.
They focus on explicit payment-gate scenarios not covered there:
  - full-payment default blocks check-in after only the configured deposit
  - total policy blocks a deposit-only payment
  - legacy free/deposit policy values never bypass full-payment check-in
  - arrival date is enforced
  - validate_guest_for_checkin document/terms checks as separate cases
  - Checkout room status side-effects
  - Cancelled reservation blocked at check-in
"""
from datetime import date, datetime, time, timedelta, timezone

import pytest
from sqlalchemy import func

from app.models.company import Company
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomHousekeepingStatusEnum, RoomStatusEnum
from app.models.room_block import RoomBlock
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.reservation import ReservationCreate
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services import checkin_service
from app.services.company_reservation_terms import build_company_terms_snapshot
from app.services.cash_register_service import open_session
from app.services.checkin_service import (
    CheckInError,
    perform_checkin,
    perform_checkout,
    perform_partial_checkin,
    validate_guest_for_checkin,
)
from app.services.payment_service import process_payment
from app.services.reservation_service import create_reservation


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


class TestCheckinRoomReadiness:
    """Final check-in requires an assigned, available, ready room."""

    def test_checkin_rejects_room_block_overlapping_stay(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        check_in = date(2027, 1, 10)
        check_out = date(2027, 1, 12)
        reservation = _make_reservation(
            db, sample_guest, sample_categories, check_in=check_in, check_out=check_out
        )
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        db.add(
            RoomBlock(
                hotel_id=hotel_config.id,
                room_id=reservation.room_id,
                starts_at=date(2027, 1, 11),
                ends_at=date(2027, 1, 13),
            )
        )
        db.flush()

        with pytest.raises(CheckInError, match="bloqueo activo para las fechas de la estadía"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert reservation.status == ReservationStatusEnum.FULLY_PAID
        assert reservation.actual_check_in is None

    @pytest.mark.parametrize(
        "block_window",
        [None, (date(2027, 1, 8), date(2027, 1, 10)), (date(2027, 1, 12), date(2027, 1, 14))],
        ids=["no-block", "block-ends-on-checkin", "block-starts-on-checkout"],
    )
    def test_checkin_allows_ready_room_without_overlapping_block(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config, block_window
    ):
        check_in = date(2027, 1, 10)
        check_out = date(2027, 1, 12)
        reservation = _make_reservation(
            db, sample_guest, sample_categories, check_in=check_in, check_out=check_out
        )
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        if block_window is not None:
            db.add(
                RoomBlock(
                    hotel_id=hotel_config.id,
                    room_id=reservation.room_id,
                    starts_at=block_window[0],
                    ends_at=block_window[1],
                )
            )
            db.flush()

        checked_in = perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert checked_in.status == ReservationStatusEnum.CHECKED_IN

    def test_checkin_requires_an_assigned_room(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        reservation.room_id = None
        reservation.allocation_status = "unassigned"
        db.flush()

        with pytest.raises(CheckInError, match="habitación activa del hotel"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

    def test_company_terms_snapshot_missing_blocks_checkin_by_default(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        company = Company(
            hotel_id=hotel_config.id,
            legal_name="Legacy Terms SA",
            display_name="Legacy Terms",
            tax_id="legacy-terms-test",
            contact_name="Manager",
            contact_email="legacy-terms@example.test",
            contact_phone="+541100000000",
            payment_deferred=False,
            requires_voucher=False,
            requires_signature=False,
        )
        db.add(company)
        db.flush()
        reservation.company_id = company.id
        reservation.company_terms_snapshot = None
        reservation.company_terms_reviewed_config = None
        db.flush()
        _pay_full(db, reservation, hotel_id=hotel_config.id)

        with pytest.raises(CheckInError, match="Gerencia debe revisar esta reserva"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert reservation.actual_check_in is None
        assert reservation.status == ReservationStatusEnum.FULLY_PAID

    def test_first_company_checkin_locks_hotel_gate_and_company_profile(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        company = Company(
            hotel_id=hotel_config.id,
            legal_name="Locked Terms SA",
            display_name="Locked Terms",
            tax_id="locked-terms-test",
            contact_name="Manager",
            contact_email="locked-terms@example.test",
            contact_phone="+541100000000",
            payment_deferred=False,
            requires_voucher=False,
            requires_signature=False,
        )
        db.add(company)
        db.flush()
        reservation.company_id = company.id
        reservation.company_terms_snapshot = build_company_terms_snapshot(company, reservation)
        reservation.company_terms_reviewed_config = reservation.company_terms_snapshot["terms"]
        _pay_full(db, reservation, hotel_id=hotel_config.id)

        real_lock_query = checkin_service.lock_query
        locked_models = []

        def track_lock(query, model):
            locked_models.append(model)
            return real_lock_query(query, model)

        monkeypatch.setattr(checkin_service, "lock_query", track_lock)
        checked_in = perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert checked_in.status == ReservationStatusEnum.CHECKED_IN
        assert Reservation in locked_models
        assert HotelConfiguration in locked_models
        assert Company in locked_models

    def test_hotel_can_configure_legacy_company_terms_review_to_not_block_checkin(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        company = Company(
            hotel_id=hotel_config.id,
            legal_name="Legacy Terms Optional SA",
            display_name="Legacy Terms Optional",
            tax_id="legacy-terms-optional-test",
            contact_name="Manager",
            contact_email="legacy-terms-optional@example.test",
            contact_phone="+541100000000",
            payment_deferred=False,
            requires_voucher=False,
            requires_signature=False,
        )
        db.add(company)
        db.flush()
        reservation.company_id = company.id
        reservation.company_terms_snapshot = None
        reservation.company_terms_reviewed_config = None
        hotel_config.block_checkin_on_company_terms_change = False
        db.flush()
        _pay_full(db, reservation, hotel_id=hotel_config.id)

        result = perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert result.status == ReservationStatusEnum.CHECKED_IN
        assert reservation.status == ReservationStatusEnum.CHECKED_IN
        assert reservation.actual_check_in is not None

    def test_partial_checkin_still_allows_unassigned_reservation(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        reservation.room_id = None
        reservation.allocation_status = "unassigned"
        db.flush()

        pre_checkin = perform_partial_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert pre_checkin.status == ReservationStatusEnum.PRE_CHECK_IN
        assert pre_checkin.pre_check_in_at is not None
        with pytest.raises(CheckInError, match="habitación activa del hotel"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)
        assert reservation.status == ReservationStatusEnum.PRE_CHECK_IN

    def test_checkin_rejects_room_assigned_from_another_hotel(
        self,
        db,
        sample_guest,
        sample_rooms,
        sample_rooms_hotel2,
        sample_categories,
        hotel_config,
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        original_room_id = reservation.room_id
        reservation.room_id = sample_rooms_hotel2[0].id

        # This invalid cross-tenant assignment exists only in memory; the
        # composite reservation-room foreign key prevents it from being stored.
        with db.no_autoflush:
            with pytest.raises(CheckInError, match="habitación activa del hotel"):
                perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        reservation.room_id = original_room_id

    @pytest.mark.parametrize(
        "room_status",
        [
            RoomStatusEnum.OCCUPIED,
            RoomStatusEnum.MAINTENANCE,
            RoomStatusEnum.BLOCKED,
            RoomStatusEnum.CLEANING,
        ],
    )
    def test_checkin_rejects_room_that_is_not_available(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config, room_status
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_config.id).one()
        room.status = room_status
        db.flush()

        with pytest.raises(CheckInError, match="debe estar disponible"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert reservation.status == ReservationStatusEnum.FULLY_PAID
        assert reservation.actual_check_in is None

    @pytest.mark.parametrize(
        "housekeeping_status",
        [RoomHousekeepingStatusEnum.DIRTY, RoomHousekeepingStatusEnum.IN_PROGRESS],
    )
    def test_checkin_rejects_room_that_is_not_clean_or_inspected(
        self,
        db,
        sample_guest,
        sample_rooms,
        sample_categories,
        hotel_config,
        housekeeping_status,
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_config.id).one()
        room.housekeeping_status = housekeeping_status
        db.flush()

        with pytest.raises(CheckInError, match="limpia o inspeccionada"):
            perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert reservation.status == ReservationStatusEnum.FULLY_PAID
        assert reservation.actual_check_in is None

    @pytest.mark.parametrize(
        "housekeeping_status",
        [RoomHousekeepingStatusEnum.CLEAN, RoomHousekeepingStatusEnum.INSPECTED],
    )
    def test_checkin_accepts_ready_room_and_marks_it_occupied(
        self,
        db,
        sample_guest,
        sample_rooms,
        sample_categories,
        hotel_config,
        housekeeping_status,
    ):
        reservation = _make_reservation(db, sample_guest, sample_categories)
        _pay_full(db, reservation, hotel_id=hotel_config.id)
        room = db.query(Room).filter(Room.id == reservation.room_id, Room.hotel_id == hotel_config.id).one()
        room.housekeeping_status = housekeeping_status
        db.flush()

        checked_in = perform_checkin(db, reservation.id, hotel_id=hotel_config.id)

        assert checked_in.status == ReservationStatusEnum.CHECKED_IN
        assert room.status == RoomStatusEnum.OCCUPIED


# ---------------------------------------------------------------------------
# Hotel payment policy: direct check-in always requires full payment.
# ---------------------------------------------------------------------------

class TestPaymentGateDepositPaid:
    """A legacy per-hotel setting cannot bypass the full-payment rule."""

    def test_default_full_payment_policy_blocks_checkin_until_full_payment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        assert hotel_config.checkin_payment_policy == "total"
        res = _make_reservation(db, sample_guest, sample_categories)
        _pay_deposit(db, res)
        assert res.status == ReservationStatusEnum.DEPOSIT_PAID

        with pytest.raises(CheckInError, match="importe total de la reserva"):
            perform_checkin(db, res.id)

        remaining = res.total_amount - res.amount_paid
        process_payment(
            db,
            PaymentRequest(
                reservation_id=res.id,
                amount=remaining,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
                currency="ARS",
            ),
            hotel_id=res.hotel_id,
        )
        result = perform_checkin(db, res.id)
        assert result.status == ReservationStatusEnum.CHECKED_IN

    def test_total_policy_blocks_deposit_only_and_allows_full_payment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        hotel_config.checkin_payment_policy = "total"
        db.flush()
        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 2, 1), check_out=date(2027, 2, 3))
        _pay_deposit(db, res)

        with pytest.raises(CheckInError, match="importe total de la reserva"):
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

    def test_legacy_free_policy_still_blocks_checkin_without_full_payment(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        hotel_config.checkin_payment_policy = "free"
        db.flush()
        res = _make_reservation(db, sample_guest, sample_categories)

        assert res.status == ReservationStatusEnum.PENDING
        with pytest.raises(CheckInError, match="importe total de la reserva"):
            perform_checkin(db, res.id)

    def test_unconfirmed_legacy_ota_prepayment_still_blocks_checkin(
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

        with pytest.raises(CheckInError, match="un gerente debe confirmar el pago anticipado"):
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

        with pytest.raises(CheckInError, match="antes de la fecha de llegada"):
            perform_checkin(db, res.id)

    def test_checkin_after_departure_date_is_rejected(self, db, sample_guest, sample_rooms, sample_categories, monkeypatch):
        today = date(2026, 9, 27)
        monkeypatch.setattr(checkin_service, "hotel_today", lambda _db, _hotel_id: today)
        res = _make_reservation(db, sample_guest, sample_categories)
        res.check_in_date = today - timedelta(days=3)
        res.check_out_date = today
        db.flush()

        with pytest.raises(CheckInError, match="después de la fecha de salida"):
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
    """The default full-payment policy blocks check-in without payment."""

    def test_checkin_blocked_when_pending_error_mentions_full_amount(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """The error explains the full amount required by the default policy."""
        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 5, 1), check_out=date(2027, 5, 3))
        assert res.status == ReservationStatusEnum.PENDING

        with pytest.raises(CheckInError, match="importe total de la reserva"):
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

    def test_default_config_enforces_full_payment_gate(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config
    ):
        """Guest data and the default full-payment gate remain independent."""
        assert hotel_config.require_document_for_checkin is True
        assert hotel_config.require_terms_acceptance is True
        assert hotel_config.checkin_payment_policy == "total"

        res = _make_reservation(db, sample_guest, sample_categories, check_in=date(2027, 7, 1), check_out=date(2027, 7, 3))
        # Reservation is PENDING — default policy requires the full amount.
        with pytest.raises(CheckInError, match="importe total de la reserva"):
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
        with pytest.raises(CheckInError, match="importe total de la reserva"):
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
        assert any("número de documento" in e.lower() for e in errors)

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
        assert any("términos y condiciones" in e.lower() for e in errors)

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

    def test_checkout_records_reserved_and_actually_used_nights_in_hotel_timezone(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
    ):
        res = self._full_checkin(
            db,
            sample_guest,
            sample_rooms,
            sample_categories,
            hotel_config,
            check_in=date(2027, 9, 1),
            check_out=date(2027, 9, 5),
        )
        res.actual_check_in = datetime(2027, 9, 1, 16, tzinfo=timezone.utc)

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                value = cls(2027, 9, 2, 23, tzinfo=timezone.utc)
                return value.astimezone(tz) if tz else value

        monkeypatch.setattr(
            checkin_service,
            "hotel_business_now",
            lambda _db, _hotel_id: FixedDateTime.now(timezone.utc),
        )
        result = perform_checkout(db, res.id)

        assert result.reserved_nights == 4
        assert result.used_nights == 1
        api_result = __import__("app.api.reservations", fromlist=["_to_read"])._to_read(result, db=db)
        assert api_result.reserved_nights == 4
        assert api_result.used_nights == 1

    def test_checkin_and_checkout_use_simulated_business_dates_for_operational_timestamps(
        self, db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
    ):
        reservation = _make_reservation(
            db,
            sample_guest,
            sample_categories,
            check_in=date(2041, 7, 8),
            check_out=date(2041, 7, 15),
        )
        _pay_full(db, reservation, hotel_id=hotel_config.id)

        business_date = {"value": date(2041, 7, 8)}

        def simulated_now(_db, _hotel_id):
            return datetime.combine(
                business_date["value"],
                time(18, 0),
                tzinfo=timezone.utc,
            )

        monkeypatch.setattr(checkin_service, "hotel_business_now", simulated_now)
        pre_checked_in = perform_partial_checkin(db, reservation.id)
        assert pre_checked_in.pre_check_in_at.date() == date(2041, 7, 8)

        checked_in = perform_checkin(db, reservation.id)
        assert checked_in.actual_check_in.date() == date(2041, 7, 8)

        business_date["value"] = date(2041, 7, 13)
        checked_out = perform_checkout(db, reservation.id)

        assert checked_out.actual_check_out.date() == date(2041, 7, 13)
        assert checked_out.used_nights == 5

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
