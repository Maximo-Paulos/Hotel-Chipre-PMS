from datetime import date
from decimal import Decimal

import pytest

from app.models.cash_register import CashCloseReport, CashMovementTypeEnum, CashSessionStatusEnum
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.models.user import User
from app.services.cash_register_service import (
    CashRegisterError,
    add_movement,
    close_session,
    open_session,
)


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


def test_only_one_open_cash_session_per_hotel_is_allowed(db):
    _hotel(db, 1)
    _hotel(db, 2)
    _user(db, 10)
    _user(db, 11)
    _user(db, 12)

    session_a = open_session(db, hotel_id=1, opened_by_user_id=10, opening_balance=Decimal("100.00"))
    assert session_a.status == CashSessionStatusEnum.OPEN

    with pytest.raises(CashRegisterError):
        open_session(db, hotel_id=1, opened_by_user_id=11, opening_balance=Decimal("50.00"))

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
    completed_cash = _transaction(db, hotel_id=1, reservation_id=reservation.id, amount=Decimal("60.00"))
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

    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("60.00"),
        transaction_id=completed_cash.id,
        reservation_id=reservation.id,
    )
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("40.00"),
        transaction_id=pending_cash.id,
        reservation_id=reservation.id,
    )
    add_movement(
        db,
        hotel_id=1,
        session_id=session.id,
        recorded_by_user_id=10,
        movement_type=CashMovementTypeEnum.INCOME,
        amount=Decimal("30.00"),
        transaction_id=completed_card.id,
        reservation_id=reservation.id,
    )
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


def test_cash_payment_without_open_session_opens_zero_balance_session(db):
    """A cash payment must be visible in caja even when the shift was not
    opened manually first."""
    from app.schemas.transaction import PaymentRequest
    from app.services.payment_service import process_payment
    from app.models.cash_register import CashMovement, CashSession, CashSessionStatusEnum

    _hotel(db, 1)
    _user(db, 10)
    reservation = _reservation(db, 1, "CASH-PAY-2")

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

    assert tx.status == TransactionStatusEnum.COMPLETED
    session = db.query(CashSession).filter(CashSession.hotel_id == 1).one()
    assert session.status == CashSessionStatusEnum.OPEN
    assert session.opening_balance == Decimal("0.00")
    movement = db.query(CashMovement).filter(CashMovement.hotel_id == 1).one()
    assert movement.transaction_id == tx.id
    assert movement.amount == Decimal("30.00")


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
