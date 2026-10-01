from decimal import Decimal

import pytest

from app.models.cash_register import CashSessionStatusEnum, CashCustodyStatusEnum
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.services.cash_register_service import (
    CashRegisterError,
    close_session,
    confirm_cash_custody,
    open_session,
)


def test_successor_float_cannot_exceed_cash_delivered_by_previous_shift(db):
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.add(
        User(
            id=10,
            email="cash-float-limit@test.com",
            password_hash="test-hash",
            is_active=True,
            is_verified=True,
        )
    )
    db.flush()

    previous_session = open_session(
        db,
        hotel_id=1,
        opened_by_user_id=10,
        opening_balance=Decimal("100000.00"),
    )
    report = close_session(
        db,
        hotel_id=1,
        session_id=previous_session.id,
        closed_by_user_id=10,
        counted_balance=Decimal("100000.00"),
    )

    with pytest.raises(CashRegisterError, match="cannot exceed the cash delivered"):
        confirm_cash_custody(
            db,
            hotel_id=1,
            report_id=report.id,
            received_by_user_id=10,
            successor_float_amount=Decimal("100000.01"),
        )

    db.refresh(report.successor_session)
    db.refresh(report.custody_handoff)
    assert report.successor_session.status == CashSessionStatusEnum.OPEN
    assert report.successor_session.opening_balance == Decimal("0.00")
    assert report.successor_float_declared_amount is None
    assert report.custody_handoff.status == CashCustodyStatusEnum.PENDING
