from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.cash_register import CashCloseReport, CashMovementTypeEnum, CashSessionStatusEnum
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import NotificationChannelEnum, NotificationOutbox
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.security_audit_log import SecurityAuditLog
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.models.user import User
from app.schemas.transaction import PaymentRequest
from app.services.cash_register_service import (
    CashRegisterError,
    add_movement,
    approve_close_difference,
    close_session,
    confirm_cash_custody,
    enqueue_pending_difference_notification,
    open_session,
)
from app.services.payment_service import process_payment


def _hotel(db, hotel_id: int) -> HotelConfiguration:
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True)
    db.add(hotel)
    db.flush()
    return hotel


def _user(db, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            email=f"cash-user-{user_id}@test.com",
            password_hash="test-hash",
            is_active=True,
            is_verified=True,
        )
        db.add(user)
        db.flush()
    return user


def _reservation(db, hotel_id: int, code: str) -> Reservation:
    if db.get(HotelConfiguration, hotel_id) is None:
        _hotel(db, hotel_id)
    guest = Guest(first_name="Cash", last_name="Guest", hotel_id=hotel_id)
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Cash Room {hotel_id}",
        code=f"CASH{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=code,
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 2),
        total_amount=Decimal("100.00"),
        deposit_amount=Decimal("30.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _transaction(
    db,
    *,
    hotel_id: int,
    reservation_id: int,
    amount: Decimal,
    status: TransactionStatusEnum = TransactionStatusEnum.COMPLETED,
    method: PaymentMethodEnum = PaymentMethodEnum.CASH,
) -> Transaction:
    tx = Transaction(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency="ARS",
        transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        payment_method=method,
        status=status,
    )
    db.add(tx)
    db.flush()
    return tx


def test_only_one_open_cash_session_per_hotel_and_currency_is_allowed(db):
    _hotel(db, 1)
    _hotel(db, 2)
    _user(db, 10)
    _user(db, 11)
    _user(db, 12)

    session_a = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    assert session_a.status == CashSessionStatusEnum.OPEN

    with pytest.raises(CashRegisterError):
        open_session(db, hotel_id=1, opened_by_user_id=11, opening_balance=Decimal("50.00"))

    session_usd = open_session(
        db,
        hotel_id=1,
        opened_by_user_id=11,
        opening_balance=Decimal("10.00"),
        currency_code="USD",
    )
    assert session_usd.currency_code == "USD"

    session_b = open_session(db, hotel_id=2, opened_by_user_id=12, opening_balance=Decimal("50.00"))
    assert session_b.hotel_id == 2


def test_cash_movement_requires_open_session(db):
    _hotel(db, 1)
    _user(db, 10)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("0.00"))
    close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("0.00"),
    )

    with pytest.raises(CashRegisterError):
        add_movement(
            db,
            hotel_id=1,
            session_id=session.id,
            recorded_by_user_id=10,
            movement_type=CashMovementTypeEnum.INCOME,
            amount=Decimal("10.00"),
        )


def test_close_report_expected_balance_from_confirmed_cash(db):
    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-1")
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    completed_cash = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=60,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            currency="ARS",
        ),
        hotel_id=1,
        apply_surcharge=False,
    )
    pending_cash = _transaction(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("40.00"),
        status=TransactionStatusEnum.PENDING,
    )
    completed_card = _transaction(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        amount=Decimal("30.00"),
        method=PaymentMethodEnum.CREDIT_CARD,
    )

    assert completed_cash.status == TransactionStatusEnum.COMPLETED
    assert pending_cash.status == TransactionStatusEnum.PENDING
    assert completed_card.status == TransactionStatusEnum.COMPLETED
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.EXPENSE,
        amount=Decimal("15.00"),
    )

    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("145.00"),
    )

    assert report.expected_balance == Decimal("145.00")
    assert report.difference == Decimal("0.00")
    assert session.status == CashSessionStatusEnum.CLOSED


def test_close_with_difference_requires_approval(db):
    _hotel(db, 1)
    _user(db, 10)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("25.00"),
    )

    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("120.00"),
    )

    assert report.expected_balance == Decimal("125.00")
    assert report.difference == Decimal("-5.00")
    assert report.difference_approved is False
    assert session.status == CashSessionStatusEnum.PENDING_APPROVAL


def test_close_with_positive_difference_also_requires_approval(db):
    """A cash surplus (counted > expected) is exactly as much a discrepancy as
    a shortage and must follow the same pending-approval gate -- there is no
    reason to special-case 'found more cash than expected' as harmless."""
    _hotel(db, 1)
    _user(db, 10)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("25.00"),
    )

    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("140.00"),
    )

    assert report.expected_balance == Decimal("125.00")
    assert report.difference == Decimal("15.00")
    assert report.difference_approved is False
    assert session.status == CashSessionStatusEnum.PENDING_APPROVAL

    approve_close_difference(db, hotel_id=1, report_id=report.id, approved_by_user_id=10)
    assert report.difference_approved is True
    assert session.status == CashSessionStatusEnum.CLOSED


def test_successor_cash_session_starts_at_zero_when_no_carry_over_is_requested(db):
    _hotel(db, 1)
    _user(db, 10)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("95.00"),
    )

    assert session.status == CashSessionStatusEnum.PENDING_APPROVAL
    assert report.successor_session.status == CashSessionStatusEnum.OPEN
    assert report.successor_session.opening_balance == Decimal("0.00")

    approve_close_difference(db, hotel_id=1, report_id=report.id, approved_by_user_id=10)
    assert session.status == CashSessionStatusEnum.CLOSED


def test_cash_difference_approval_is_idempotent_and_keeps_first_approver_audited(db):
    _hotel(db, 1)
    _user(db, 10)
    _user(db, 20)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("99.00"),
    )

    approve_close_difference(db, hotel_id=1, report_id=report.id, approved_by_user_id=10)
    approve_close_difference(db, hotel_id=1, report_id=report.id, approved_by_user_id=20)

    assert report.difference_approved is True
    assert report.approved_by_user_id == 10
    audit_rows = (
        db.query(SecurityAuditLog)
        .filter_by(hotel_id=1, action="cash.close_difference.approved", resource_id=str(report.id))
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].user_id == 10


def test_pending_difference_notification_targets_only_owner_roles_in_app(db):
    _hotel(db, 1)
    for user_id, role in ((10, "owner"), (11, "co_owner"), (12, "manager")):
        _user(db, user_id)
        db.add(HotelMembership(hotel_id=1, user_id=user_id, role=role, status="active"))
    db.flush()
    session = open_session(db, hotel_id=1, opened_by_user_id=12, opening_balance=Decimal("100.00"))
    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=12,
        counted_balance=Decimal("99.00"),
    )

    enqueue_pending_difference_notification(db, report)

    rows = db.query(NotificationOutbox).filter_by(hotel_id=1).all()
    assert {row.recipient_user_id for row in rows} == {10, 11}
    assert {row.channel for row in rows} == {NotificationChannelEnum.IN_APP}
    assert all(row.dedupe_key == f"cash-close-difference-pending:{report.id}" for row in rows)


def test_cross_hotel_isolation(db):
    _hotel(db, 1)
    _hotel(db, 2)
    _user(db, 10)
    _user(db, 20)
    session_a = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    session_b = open_session(db, hotel_id=2, opened_by_user_id=20, opening_balance=Decimal("200.00"))

    with pytest.raises(CashRegisterError):
        add_movement(
            db,
            hotel_id=1,
            session_id=session_b.id,
            recorded_by_user_id=10,
            movement_type=CashMovementTypeEnum.INCOME,
            amount=Decimal("1.00"),
        )

    close_session(db, hotel_id=1, session_id=session_a.id, closed_by_user_id=10, counted_balance=Decimal("100.00"))

    assert db.query(CashCloseReport).filter(CashCloseReport.hotel_id == 1).count() == 1
    assert db.query(CashCloseReport).filter(CashCloseReport.hotel_id == 2).count() == 0


def test_cash_payment_posts_income_movement_to_open_session(db):
    """A cash payment on a reservation must land in the open caja as an INCOME
    movement linked to the transaction, so the arqueo reconciles."""
    from app.schemas.transaction import PaymentRequest
    from app.services.cash_register_service import list_movements
    from app.services.payment_service import process_payment

    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-PAY-1")
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("0.00"))

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=30.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    db.flush()

    movements = list_movements(db, hotel_id=1, session_id=session.id)
    assert len(movements) == 1
    movement = movements[0]
    assert movement.movement_type == CashMovementTypeEnum.INCOME
    assert movement.amount == Decimal("30.00")
    assert movement.transaction_id == tx.id
    assert movement.reservation_id == reservation.id


def test_cash_payment_without_open_session_is_rejected(db):
    """A cash payment cannot be approved outside an explicitly opened caja.

    process_payment translates the cash-register guard's CashRegisterError into
    its own PaymentError so every caller (the direct payment API route, the
    MercadoPago webhook, reservation extension, transfer-proof approval) gets
    the same clean 4xx contract instead of an unhandled 500 -- see the P1 fix
    in payment_service.process_payment.
    """
    from app.schemas.transaction import PaymentRequest
    from app.services.payment_service import PaymentError, process_payment

    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-PAY-2")

    with pytest.raises(PaymentError, match="open cash session"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=30.0,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.DEPOSIT,
            ),
            hotel_id=1,
            actor_user_id=10,
        )


def test_non_cash_payments_never_increase_physical_cash_in_the_open_session(db):
    """MercadoPago and bank-transfer payments settle the reservation balance
    but must NEVER post a movement into the caja or move expected_balance --
    only physical CASH does. Exercised through the real process_payment path
    (not just the record_cash_payment_movement early-return unit), because a
    non-cash payment increasing the physical cash count would be a critical
    reconciliation bug (Fase 6 caja checklist item 11)."""
    from app.schemas.transaction import PaymentRequest
    from app.services.cash_register_service import get_session_summary, list_movements
    from app.services.payment_service import process_payment

    def _extra_reservation(code: str) -> Reservation:
        # _reservation() reuses a fixed "Cash Room 1"/"CASH1" category per
        # hotel_id, so a second call in the same hotel hits its unique
        # (hotel_id, name) constraint. This test needs several independent
        # reservations in the SAME hotel/cash session, so give each its own
        # category instead of reusing the shared helper.
        guest = Guest(first_name="Cash", last_name="Guest", hotel_id=1)
        category = RoomCategory(
            hotel_id=1,
            name=f"Cash Room 1 {code}",
            code=code,
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        reservation = Reservation(
            hotel_id=1,
            confirmation_code=code,
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=date(2026, 8, 1),
            check_out_date=date(2026, 8, 2),
            total_amount=Decimal("100.00"),
            deposit_amount=Decimal("30.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
        )
        db.add(reservation)
        db.flush()
        return reservation

    hotel = _hotel(db, 1)
    hotel.enable_bank_transfer = True
    hotel.enable_mercado_pago = True
    _user(db, 10)
    mp_reservation = _reservation(db, 1, "CASH-NONCASH-MP")
    transfer_reservation = _extra_reservation("CASH-NONCASH-XFER")
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))

    process_payment(
        db,
        PaymentRequest(
            reservation_id=mp_reservation.id,
            amount=30.0,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    process_payment(
        db,
        PaymentRequest(
            reservation_id=transfer_reservation.id,
            amount=45.0,
            payment_method=PaymentMethodEnum.BANK_TRANSFER,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    db.flush()

    assert list_movements(db, hotel_id=1, session_id=session.id) == []
    summary = get_session_summary(db, hotel_id=1, session_id=session.id)
    assert summary["expected_balance"] == Decimal("100.00")
    assert summary["income_total"] == Decimal("0.00")
    assert summary["movements_count"] == 0

    # Now a real cash payment on a third reservation is the only thing that
    # may move the caja.
    cash_reservation = _extra_reservation("CASH-NONCASH-CASH")
    process_payment(
        db,
        PaymentRequest(
            reservation_id=cash_reservation.id,
            amount=30.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    db.flush()

    summary_after_cash = get_session_summary(db, hotel_id=1, session_id=session.id)
    assert summary_after_cash["expected_balance"] == Decimal("130.00")
    assert len(list_movements(db, hotel_id=1, session_id=session.id)) == 1


def test_close_counts_full_cash_then_records_successor_float_as_a_separate_action(db):
    _hotel(db, 1)
    _user(db, 10)
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100000.00"))

    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("100000.00"),
    )

    assert report.successor_session_id is not None
    assert report.successor_session.status == CashSessionStatusEnum.OPEN
    assert report.declared_balance == Decimal("100000.00")
    assert report.successor_session.opening_balance == Decimal("0.00")
    assert report.custody_handoff.delivered_amount == Decimal("100000.00")
    assert report.custody_handoff.delivered_by_user_id == 10

    confirmed = confirm_cash_custody(
        db,
        hotel_id=1,
        report_id=report.id,
        received_by_user_id=10,
        successor_float_amount=Decimal("10000.00"),
    )

    assert confirmed.successor_session.opening_balance == Decimal("10000.00")
    assert confirmed.successor_opening_balance == Decimal("10000.00")
    assert confirmed.successor_float_declared_amount == Decimal("10000.00")
    assert confirmed.successor_float_declared_by_user_id == 10
    assert confirmed.successor_float_declared_at is not None
    assert confirmed.custody_handoff.delivered_amount == Decimal("100000.00")
    assert report.custody_handoff.received_by_user_id == 10
    assert report.custody_handoff.received_at is not None
    audit_actions = {
        row.action
        for row in db.query(SecurityAuditLog).filter_by(hotel_id=1, resource_id=str(report.id)).all()
    }
    assert "cash.custody.received" in audit_actions
    assert "cash.successor_float.declared" in audit_actions
    confirm_cash_custody(
        db,
        hotel_id=1,
        report_id=report.id,
        received_by_user_id=10,
        successor_float_amount=Decimal("10000.00"),
    )
    assert db.query(SecurityAuditLog).filter_by(
        hotel_id=1,
        action="cash.successor_float.declared",
        resource_id=str(report.id),
    ).count() == 1
    with pytest.raises(CashRegisterError, match="different successor float"):
        confirm_cash_custody(
            db,
            hotel_id=1,
            report_id=report.id,
            received_by_user_id=10,
            successor_float_amount=Decimal("9000.00"),
        )


def test_cash_custody_cannot_rewrite_float_after_successor_is_closed(db):
    _hotel(db, 1)
    _user(db, 10)
    original = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    report = close_session(
        db,
        hotel_id=1,
        session_id=original.id,
        closed_by_user_id=10,
        counted_balance=Decimal("100.00"),
    )
    successor = report.successor_session

    close_session(
        db,
        hotel_id=1,
        session_id=successor.id,
        closed_by_user_id=10,
        counted_balance=Decimal("0.00"),
    )
    successor_close_report = db.query(CashCloseReport).filter_by(session_id=successor.id).one()

    with pytest.raises(CashRegisterError, match="[Ss]uccessor cash session is not open"):
        confirm_cash_custody(
            db,
            hotel_id=1,
            report_id=report.id,
            received_by_user_id=10,
            successor_float_amount=Decimal("25.00"),
        )

    db.refresh(successor)
    db.refresh(report.custody_handoff)
    assert successor.opening_balance == Decimal("0.00")
    assert successor_close_report.expected_balance == Decimal("0.00")
    assert report.successor_float_declared_amount is None
    assert report.custody_handoff.status.value == "pending"


def test_session_summary_expected_balance_matches_arqueo(db):
    """The live summary's expected_balance must equal the arqueo's expected
    balance (single source of truth): opening + confirmed cash movements."""
    from app.schemas.transaction import PaymentRequest
    from app.services.cash_register_service import get_session_summary
    from app.services.payment_service import process_payment

    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-SUM-1")
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))

    # Cash payment (auto-posts INCOME) + a manual expense.
    process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=30.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.DEPOSIT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.EXPENSE,
        amount=Decimal("10.00"),
    )
    db.flush()

    summary = get_session_summary(db, hotel_id=1, session_id=session.id)
    # opening 100 + income 30 - expense 10 = 120
    assert summary["expected_balance"] == Decimal("120.00")
    assert summary["income_total"] == Decimal("30.00")
    assert summary["expense_total"] == Decimal("10.00")

    report = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("120.00"),
    )
    # Live summary must match the arqueo's computed expected balance exactly.
    assert summary["expected_balance"] == report.expected_balance
    assert report.difference == Decimal("0.00")


def test_cash_payment_with_surcharge_posts_gross_amount_to_caja(db):
    """A cash payment carrying a payment surcharge must post the GROSS amount
    (base + recargo) to the caja, since that is the cash physically received."""
    from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
    from app.schemas.transaction import PaymentRequest
    from app.services.cash_register_service import list_movements
    from app.services.payment_service import process_payment

    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-SUR-1")  # total 100
    db.add(
        PaymentSurcharge(
            hotel_id=1,
            payment_method="cash",
            surcharge_type=PaymentSurchargeTypeEnum.PERCENTAGE,
            amount=5.0,  # 5%
            is_active=True,
        )
    )
    db.flush()
    session = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("0.00"))

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.FULL_PAYMENT,
        ),
        hotel_id=1,
        actor_user_id=10,
    )
    db.flush()

    assert tx.amount == Decimal("100.00")
    assert tx.gross_amount == Decimal("105.00")
    assert tx.fee_amount == Decimal("5.00")

    movements = list_movements(db, hotel_id=1, session_id=session.id)
    assert len(movements) == 1
    # Caja holds the gross cash received (100 + 5% surcharge).
    assert movements[0].amount == Decimal("105.00")
    assert "recargo" in (movements[0].description or "")


def test_twenty_seven_prior_receipts_do_not_inflate_the_open_cash_session(db):
    from app.models.cash_register import CashMovement
    from app.services.cash_daily_summary_service import get_daily_summary
    from app.services.payment_service import PaymentError
    from app.services.cash_register_service import get_session_summary
    from app.services.timezones import hotel_today

    _hotel(db, 1)
    _user(db, 10)
    session = open_session(
        db,
        hotel_id=1,
        opened_by_user_id=10,
        opening_balance=Decimal("50000.00"),
    )
    collected_on = hotel_today(db, 1) - timedelta(days=1)
    amounts = [Decimal("50000.00")] * 26 + [Decimal("410000.00")]
    category = RoomCategory(
        hotel_id=1,
        name="Prior receipt room",
        code="PRIOR-RECEIPTS",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add(category)
    db.flush()

    for index, amount in enumerate(amounts):
        guest = Guest(first_name="Prior", last_name=f"Receipt {index:02d}", hotel_id=1)
        db.add(guest)
        db.flush()
        reservation = Reservation(
            hotel_id=1,
            confirmation_code=f"PRIOR-RECEIPT-{index:02d}",
            guest_id=guest.id,
            category_id=category.id,
            check_in_date=collected_on,
            check_out_date=collected_on + timedelta(days=1),
            total_amount=Decimal("1000000.00"),
            deposit_amount=Decimal("300000.00"),
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
        )
        db.add(reservation)
        db.flush()
        request = PaymentRequest(
            reservation_id=reservation.id,
            amount=float(amount),
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
            collected_before=True,
            collected_on=collected_on,
            prior_receipt_note=f"Seña del cuaderno {index + 1}",
        )
        key = f"prior-receipt-{index:02d}"
        transaction = process_payment(
            db,
            request,
            hotel_id=1,
            actor_user_id=10,
            idempotency_key=key,
        )
        if index == 0:
            retry = process_payment(
                db,
                request,
                hotel_id=1,
                actor_user_id=10,
                idempotency_key=key,
            )
            assert retry.id == transaction.id
            mismatched_retry = request.model_copy(update={"prior_receipt_note": "Motivo distinto"})
            with pytest.raises(PaymentError, match="different payment request"):
                process_payment(
                    db,
                    mismatched_retry,
                    hotel_id=1,
                    actor_user_id=10,
                    idempotency_key=key,
                )
        db.flush()

    assert db.query(Transaction).filter(Transaction.hotel_id == 1).count() == 27
    assert db.query(CashMovement).filter(CashMovement.hotel_id == 1).count() == 0

    summary = get_daily_summary(db, hotel_id=1, report_date=hotel_today(db, 1), currency_code="ARS")
    assert summary["gross_collected"] == Decimal("0.00")
    assert summary["entries"] == []
    assert summary["physical_cash"]["expected_balance"] == Decimal("50000.00")
    assert len(summary["prior_receipts"]) == 27
    assert summary["prior_receipt_totals"] == [
        {"currency_code": "ARS", "amount": Decimal("1710000.00"), "transaction_count": 27}
    ]

    live = get_session_summary(db, hotel_id=1, session_id=session.id)
    assert live["expected_balance"] == Decimal("50000.00")
    closed = close_session(
        db,
        hotel_id=1,
        session_id=session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("50000.00"),
    )
    assert closed.expected_balance == Decimal("50000.00")
    assert closed.difference == Decimal("0.00")


def test_daily_cash_summary_batches_close_reports_across_sessions(db):
    from sqlalchemy import event

    from app.services.cash_daily_summary_service import get_daily_summary
    from app.services.timezones import hotel_today

    _hotel(db, 1)
    _user(db, 10)
    first = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("25.00"))
    first_close = close_session(
        db,
        hotel_id=1,
        session_id=first.id,
        closed_by_user_id=10,
        counted_balance=Decimal("25.00"),
    )
    second_close = close_session(
        db,
        hotel_id=1,
        session_id=first_close.successor_session_id,
        closed_by_user_id=10,
        counted_balance=Decimal("0.00"),
    )

    close_report_selects: list[str] = []

    def capture_close_report_select(_conn, _cursor, statement, _parameters, _context, _many):
        if "cash_close_reports" in statement.lower():
            close_report_selects.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", capture_close_report_select)
    try:
        summary = get_daily_summary(
            db,
            hotel_id=1,
            report_date=hotel_today(db, 1),
            currency_code="ARS",
        )
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture_close_report_select)

    assert len(summary["sessions"]) == 3
    assert len(close_report_selects) == 1


def test_daily_cash_summary_uses_declared_successor_float_without_recounting_full_handoff(db):
    from app.services.cash_daily_summary_service import get_daily_summary, _db_utc_bounds
    from app.services.timezones import hotel_today

    hotel = _hotel(db, 1)
    _user(db, 10)
    report_date = hotel_today(db, 1)
    day_start, _day_end = _db_utc_bounds(report_date, hotel.hotel_timezone or "UTC")

    prior_session = open_session(
        db,
        hotel_id=1,
        opened_by_user_id=10,
        opening_balance=Decimal("0.00"),
    )
    report = close_session(
        db,
        hotel_id=1,
        session_id=prior_session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("100000.00"),
    )
    confirm_cash_custody(
        db,
        hotel_id=1,
        report_id=report.id,
        received_by_user_id=10,
        successor_float_amount=Decimal("10000.00"),
    )

    # Model a close and custody confirmation before the selected local day.
    prior_session.opened_at = day_start - timedelta(days=1)
    prior_session.closed_at = day_start - timedelta(seconds=1)
    report.closed_at = prior_session.closed_at
    report.custody_handoff.delivered_at = prior_session.closed_at
    report.custody_handoff.received_at = prior_session.closed_at
    report.successor_session.opened_at = day_start
    db.flush()

    summary = get_daily_summary(
        db,
        hotel_id=1,
        report_date=report_date,
        currency_code="ARS",
    )

    assert summary["physical_cash"]["opening_balance"] == Decimal("10000.00")
    assert summary["physical_cash"]["expected_balance"] == Decimal("10000.00")


def test_daily_cash_summary_subtracts_same_day_handoff_and_reconciles_close_difference(db):
    from app.services.cash_daily_summary_service import get_daily_summary
    from app.services.timezones import hotel_today

    hotel = _hotel(db, 1)
    _user(db, 10)
    report_date = hotel_today(db, 1)
    prior_session = open_session(
        db,
        hotel_id=1,
        opened_by_user_id=10,
        opening_balance=Decimal("0.00"),
    )
    add_movement(
        db,
        hotel_id=1,
        session_id=prior_session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("100000.00"),
        description="Cobros del turno",
    )
    report = close_session(
        db,
        hotel_id=1,
        session_id=prior_session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("105000.00"),
    )
    confirm_cash_custody(
        db,
        hotel_id=1,
        report_id=report.id,
        received_by_user_id=10,
        successor_float_amount=Decimal("10000.00"),
    )

    summary = get_daily_summary(db, hotel_id=1, report_date=report_date, currency_code="ARS")

    assert summary["physical_cash"]["opening_balance"] == Decimal("10000.00")
    assert summary["physical_cash"]["income_total"] == Decimal("100000.00")
    assert summary["physical_cash"]["custody_delivered_total"] == Decimal("105000.00")
    assert summary["physical_cash"]["custody_difference_total"] == Decimal("5000.00")
    assert summary["physical_cash"]["expected_balance"] == Decimal("10000.00")
