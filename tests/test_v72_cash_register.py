"""
Adapted tests for V72 §17 - Caja Basica (Cash Register).

This branch implements caja as:
- CashSession
- CashMovement
- CashCloseReport

The source V72 tests expected older names such as CashEntry and route helpers
such as get_current_session/export_session/daily_totals.  Those absent surfaces
are kept as explicit xfails with BRM reasons.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.cash_register import (
    CashCloseReport,
    CashMovement,
    CashMovementTypeEnum,
    CashSession,
    CashSessionStatusEnum,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user import User
from app.schemas.cash_register import CashMovementCreate, CashSessionClose, CashSessionOpen
from app.services.cash_register_service import add_movement, close_session, open_session
from app.services.permission_service import PERMISSION_CASH_APPROVE_DIFFERENCE


HOTEL_ID = 1
USER_ID = 42

BRM17_MISSING_REASON = (
    "BRM §17 caja básica gap: main branch exposes sessions/movements/close reports only; "
    "this V72 endpoint/automation surface is not implemented"
)


def _make_user(db: Session, user_id: int = USER_ID, role: str = "manager") -> User:
    user = db.get(User, user_id)
    if user is None:
        user = User(
            id=user_id,
            email=f"cash-user-{user_id}@hotel.test",
            password_hash="hashed",
            is_active=True,
            is_verified=True,
            role=role,
        )
        db.add(user)
        db.flush()
    return user


def _make_hotel(db: Session, hotel_id: int = HOTEL_ID) -> HotelConfiguration:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel is None:
        hotel = HotelConfiguration(
            id=hotel_id,
            deposit_percentage=Decimal("30.00"),
            enable_cash=True,
            enable_mercado_pago=True,
            subscription_active=True,
        )
        db.add(hotel)
        db.flush()
    return hotel


def _auth_context(
    hotel_id: int = HOTEL_ID,
    user_id: int = USER_ID,
    *,
    role: str = "manager",
    permissions: set[str] | None = None,
) -> MagicMock:
    ctx = MagicMock()
    ctx.hotel_id = hotel_id
    ctx.user_id = user_id
    ctx.user_role = role
    ctx.permissions = permissions if permissions is not None else set()
    return ctx


def _open_cash_session(
    db: Session,
    *,
    hotel_id: int = HOTEL_ID,
    user_id: int = USER_ID,
    opening_balance: Decimal = Decimal("0.00"),
) -> CashSession:
    _make_hotel(db, hotel_id)
    _make_user(db, user_id)
    return open_session(
        db,
        hotel_id=hotel_id,
        opened_by_user_id=user_id,
        opening_balance=opening_balance,
    )


def _add_cash_movement(
    db: Session,
    session: CashSession,
    *,
    amount: Decimal,
    movement_type: CashMovementTypeEnum = CashMovementTypeEnum.INCOME,
    transaction_id: int | None = None,
    reservation_id: int | None = None,
) -> CashMovement:
    return add_movement(
        db,
        hotel_id=session.hotel_id,
        session_id=session.id,
        recorded_by_user_id=USER_ID,
        movement_type=movement_type,
        amount=amount,
        description="test movement",
        transaction_id=transaction_id,
        reservation_id=reservation_id,
    )


def _make_reservation(db: Session, hotel_id: int = HOTEL_ID) -> Reservation:
    _make_hotel(db, hotel_id)
    guest = Guest(first_name="Cash", last_name="Guest", hotel_id=hotel_id)
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == hotel_id, RoomCategory.code == f"CASH{hotel_id}")
        .first()
    )
    if category is None:
        category = RoomCategory(
            hotel_id=hotel_id,
            name=f"Cash Category {hotel_id}",
            code=f"CASH{hotel_id}",
            base_price_per_night=Decimal("100.00"),
            max_occupancy=2,
        )
        db.add(category)
        db.flush()
    db.add(guest)
    db.flush()
    sequence = db.query(Reservation).filter(Reservation.hotel_id == hotel_id).count() + 1
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"CASH-{hotel_id}-{sequence}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 9, 1),
        check_out_date=date(2026, 9, 4),
        total_amount=Decimal("300.00"),
        amount_paid=Decimal("0.00"),
        deposit_amount=Decimal("90.00"),
        subtotal_amount=Decimal("300.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _make_transaction(
    db: Session,
    reservation: Reservation,
    *,
    amount: Decimal,
    method: PaymentMethodEnum = PaymentMethodEnum.CASH,
    status: TransactionStatusEnum = TransactionStatusEnum.COMPLETED,
    tx_type: TransactionTypeEnum = TransactionTypeEnum.PARTIAL_PAYMENT,
) -> Transaction:
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation.id,
        amount=amount,
        currency="ARS",
        transaction_type=tx_type,
        payment_method=method,
        status=status,
    )
    db.add(tx)
    db.flush()
    return tx


class TestOpenSession:
    def test_open_session_creates_new_session(self, db: Session):
        from app.api.cash_register import open_cash_session

        _make_hotel(db)
        _make_user(db)
        result = open_cash_session(
            CashSessionOpen(opening_balance=Decimal("500.00")),
            db=db,
            context=_auth_context(),
        )

        assert result.status == CashSessionStatusEnum.OPEN
        assert result.opening_balance == Decimal("500.00")
        assert result.hotel_id == HOTEL_ID
        assert result.opened_by_user_id == USER_ID

    def test_open_session_with_zero_balance(self, db: Session):
        from app.api.cash_register import open_cash_session

        _make_hotel(db)
        _make_user(db)
        result = open_cash_session(CashSessionOpen(), db=db, context=_auth_context())

        assert result.opening_balance == Decimal("0.00")
        assert result.status == CashSessionStatusEnum.OPEN

    def test_open_session_fails_if_already_open(self, db: Session):
        from app.api.cash_register import open_cash_session

        _open_cash_session(db)

        with pytest.raises(HTTPException) as exc_info:
            open_cash_session(
                CashSessionOpen(opening_balance=Decimal("100.00")),
                db=db,
                context=_auth_context(),
            )

        assert exc_info.value.status_code == 400

    def test_open_session_different_hotels_are_independent(self, db: Session):
        from app.api.cash_register import open_cash_session

        _make_hotel(db, 1)
        _make_hotel(db, 2)
        _make_user(db)
        _open_cash_session(db, hotel_id=1)

        result = open_cash_session(
            CashSessionOpen(opening_balance=Decimal("25.00")),
            db=db,
            context=_auth_context(hotel_id=2),
        )

        assert result.hotel_id == 2
        assert result.status == CashSessionStatusEnum.OPEN

    def test_list_cash_sessions_returns_hotel_scoped_sessions(self, db: Session):
        from app.api.cash_register import list_cash_sessions

        session_h1 = _open_cash_session(db, hotel_id=1)
        _open_cash_session(db, hotel_id=2)

        result = list_cash_sessions(db=db, context=_auth_context(hotel_id=1))

        assert [session.id for session in result] == [session_h1.id]


class TestCloseSession:
    def test_close_session_with_actual_closing_amount_tracks_difference(self, db: Session):
        session = _open_cash_session(db, opening_balance=Decimal("200.00"))
        _add_cash_movement(db, session, amount=Decimal("300.00"))

        report = close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("480.00"),
        )

        assert report.expected_balance == Decimal("500.00")
        assert report.declared_balance == Decimal("480.00")
        assert report.difference == Decimal("-20.00")
        assert report.difference_approved is False
        assert session.status == CashSessionStatusEnum.PENDING_APPROVAL

    def test_close_session_balanced_marks_session_closed(self, db: Session):
        session = _open_cash_session(db, opening_balance=Decimal("100.00"))

        report = close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("100.00"),
        )

        assert report.difference == Decimal("0.00")
        assert session.status == CashSessionStatusEnum.CLOSED

    def test_close_session_with_approved_difference_closes_session(self, db: Session):
        from app.api.cash_register import close_cash_session

        session = _open_cash_session(db, opening_balance=Decimal("100.00"))
        ctx = _auth_context(permissions={PERMISSION_CASH_APPROVE_DIFFERENCE})

        report = close_cash_session(
            session.id,
            CashSessionClose(counted_balance=Decimal("99.00"), approve_difference=True),
            db=db,
            context=ctx,
        )

        assert report.difference == Decimal("-1.00")
        assert report.difference_approved is True
        assert report.approved_by_user_id == USER_ID
        assert session.status == CashSessionStatusEnum.CLOSED

    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": per-method close breakdown is absent")
    def test_close_session_with_per_method_breakdown(self):
        from app.api.cash_register import BreakdownItem  # noqa: F401

    def test_close_session_no_breakdown_has_no_method_report(self, db: Session):
        session = _open_cash_session(db)
        report = close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("0.00"),
        )

        assert not hasattr(report, "breakdown_by_method")

    def test_close_already_closed_session_raises_400(self, db: Session):
        from app.api.cash_register import close_cash_session

        session = _open_cash_session(db)
        close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("0.00"),
        )

        with pytest.raises(HTTPException) as exc_info:
            close_cash_session(
                session.id,
                CashSessionClose(counted_balance=Decimal("0.00")),
                db=db,
                context=_auth_context(),
            )

        assert exc_info.value.status_code == 400

    def test_close_nonexistent_session_raises_400(self, db: Session):
        from app.api.cash_register import close_cash_session

        _make_hotel(db)
        _make_user(db)

        with pytest.raises(HTTPException) as exc_info:
            close_cash_session(
                99999,
                CashSessionClose(counted_balance=Decimal("0.00")),
                db=db,
                context=_auth_context(),
            )

        assert exc_info.value.status_code == 400


class TestCashMovements:
    def test_create_income_movement_adds_to_session(self, db: Session):
        from app.api.cash_register import add_cash_movement

        session = _open_cash_session(db, opening_balance=Decimal("100.00"))
        result = add_cash_movement(
            session.id,
            CashMovementCreate(
                movement_type=CashMovementTypeEnum.INCOME,
                amount=Decimal("250.00"),
                description="Room payment",
            ),
            db=db,
            context=_auth_context(),
        )

        assert result.movement_type == CashMovementTypeEnum.INCOME
        assert result.amount == Decimal("250.00")
        assert result.session_id == session.id

    def test_create_expense_movement_adds_to_session(self, db: Session):
        from app.api.cash_register import add_cash_movement

        session = _open_cash_session(db, opening_balance=Decimal("500.00"))
        result = add_cash_movement(
            session.id,
            CashMovementCreate(
                movement_type=CashMovementTypeEnum.EXPENSE,
                amount=Decimal("75.00"),
                description="Office supplies purchase",
            ),
            db=db,
            context=_auth_context(),
        )

        assert result.movement_type == CashMovementTypeEnum.EXPENSE
        assert result.amount == Decimal("75.00")
        assert result.description == "Office supplies purchase"

    def test_create_movement_on_closed_session_raises_400(self, db: Session):
        from app.api.cash_register import add_cash_movement

        session = _open_cash_session(db)
        close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("0.00"),
        )

        with pytest.raises(HTTPException) as exc_info:
            add_cash_movement(
                session.id,
                CashMovementCreate(
                    movement_type=CashMovementTypeEnum.INCOME,
                    amount=Decimal("100.00"),
                ),
                db=db,
                context=_auth_context(),
            )

        assert exc_info.value.status_code == 400

    def test_create_movement_zero_amount_rejected_by_schema(self):
        with pytest.raises(ValidationError):
            CashMovementCreate(
                movement_type=CashMovementTypeEnum.INCOME,
                amount=Decimal("0.00"),
            )


class TestListSessionMovements:
    def test_get_session_movements_returns_all_movements(self, db: Session):
        from app.api.cash_register import list_cash_movements

        session = _open_cash_session(db, opening_balance=Decimal("100.00"))
        _add_cash_movement(db, session, amount=Decimal("200.00"), movement_type=CashMovementTypeEnum.INCOME)
        _add_cash_movement(db, session, amount=Decimal("50.00"), movement_type=CashMovementTypeEnum.EXPENSE)

        result = list_cash_movements(session.id, db=db, context=_auth_context())

        assert [movement.amount for movement in result] == [Decimal("200.00"), Decimal("50.00")]
        assert [movement.movement_type for movement in result] == [
            CashMovementTypeEnum.INCOME,
            CashMovementTypeEnum.EXPENSE,
        ]

    def test_get_session_movements_empty_session(self, db: Session):
        from app.api.cash_register import list_cash_movements

        session = _open_cash_session(db)

        result = list_cash_movements(session.id, db=db, context=_auth_context())

        assert result == []

    def test_get_movements_for_wrong_hotel_returns_empty_list(self, db: Session):
        from app.api.cash_register import list_cash_movements

        session = _open_cash_session(db, hotel_id=1)

        result = list_cash_movements(session.id, db=db, context=_auth_context(hotel_id=2))

        assert result == []


class TestSessionSummary:
    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": session summary endpoint is absent")
    def test_get_session_summary_shows_totals_and_difference(self):
        from app.api.cash_register import get_session_summary  # noqa: F401

    def test_close_report_shows_totals_and_difference(self, db: Session):
        session = _open_cash_session(db, opening_balance=Decimal("500.00"))
        _add_cash_movement(db, session, amount=Decimal("300.00"), movement_type=CashMovementTypeEnum.INCOME)
        _add_cash_movement(db, session, amount=Decimal("100.00"), movement_type=CashMovementTypeEnum.EXPENSE)

        report = close_session(
            db,
            hotel_id=HOTEL_ID,
            session_id=session.id,
            closed_by_user_id=USER_ID,
            counted_balance=Decimal("690.00"),
        )

        assert report.expected_balance == Decimal("700.00")
        assert report.declared_balance == Decimal("690.00")
        assert report.difference == Decimal("-10.00")


class TestCurrentSession:
    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": current-session endpoint is absent")
    def test_get_current_session_returns_open_session(self):
        from app.api.cash_register import get_current_session  # noqa: F401

    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": current-session endpoint is absent")
    def test_get_current_session_returns_404_when_none_open(self):
        from app.api.cash_register import get_current_session  # noqa: F401


class TestAutoCashEntry:
    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": payment service does not auto-create cash movements")
    def test_auto_cash_entry_on_payment(self):
        from app.services.payment_service import _auto_register_cash_entry  # noqa: F401

    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": payment service does not auto-create cash movements")
    def test_auto_cash_entry_on_refund(self):
        from app.services.payment_service import _auto_register_cash_entry  # noqa: F401

    def test_manual_cash_movement_can_link_payment_transaction(self, db: Session):
        session = _open_cash_session(db)
        reservation = _make_reservation(db)
        tx = _make_transaction(db, reservation, amount=Decimal("300.00"))

        movement = _add_cash_movement(
            db,
            session,
            amount=Decimal("300.00"),
            transaction_id=tx.id,
            reservation_id=reservation.id,
        )

        assert movement.transaction_id == tx.id
        assert movement.reservation_id == reservation.id
        assert movement.movement_type == CashMovementTypeEnum.INCOME

    def test_manual_cash_movement_rejects_cross_reservation_transaction(self, db: Session):
        session = _open_cash_session(db)
        reservation = _make_reservation(db)
        other_reservation = _make_reservation(db)
        tx = _make_transaction(db, reservation, amount=Decimal("100.00"))

        with pytest.raises(Exception, match="selected reservation"):
            _add_cash_movement(
                db,
                session,
                amount=Decimal("100.00"),
                transaction_id=tx.id,
                reservation_id=other_reservation.id,
            )


class TestExportSession:
    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": export session endpoint is absent")
    def test_export_session_returns_data(self):
        from app.api.cash_register import export_session  # noqa: F401

    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": export session endpoint is absent")
    def test_export_nonexistent_session_raises_404(self):
        from app.api.cash_register import export_session  # noqa: F401


class TestDailyTotals:
    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": daily totals endpoint is absent")
    def test_daily_totals_endpoint(self):
        from app.api.cash_register import daily_totals  # noqa: F401

    @pytest.mark.xfail(reason=BRM17_MISSING_REASON + ": daily totals endpoint is absent")
    def test_daily_totals_no_sessions_returns_empty(self):
        from app.api.cash_register import daily_totals  # noqa: F401

    def test_daily_totals_can_be_derived_from_movements_for_today(self, db: Session):
        session = _open_cash_session(db)
        _add_cash_movement(db, session, amount=Decimal("1000.00"), movement_type=CashMovementTypeEnum.INCOME)
        _add_cash_movement(db, session, amount=Decimal("100.00"), movement_type=CashMovementTypeEnum.EXPENSE)

        income = sum(
            movement.amount
            for movement in db.query(CashMovement).filter(
                CashMovement.session_id == session.id,
                CashMovement.movement_type == CashMovementTypeEnum.INCOME,
            )
        )
        expenses = sum(
            movement.amount
            for movement in db.query(CashMovement).filter(
                CashMovement.session_id == session.id,
                CashMovement.movement_type == CashMovementTypeEnum.EXPENSE,
            )
        )

        assert income - expenses == Decimal("900.00")
        assert db.query(CashCloseReport).count() == 0
