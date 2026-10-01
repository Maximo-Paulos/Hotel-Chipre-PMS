from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models.cash_register import CashSessionStatusEnum
from app.schemas.cash_register import CashSessionRead


def _cash_session(opened_at: datetime) -> CashSessionRead:
    return CashSessionRead(
        id=1,
        hotel_id=1,
        status=CashSessionStatusEnum.OPEN,
        opening_balance=Decimal("50000.00"),
        currency_code="ARS",
        opened_at=opened_at,
    )


def test_cash_session_serialization_marks_legacy_naive_timestamp_as_utc():
    session = _cash_session(datetime(2026, 9, 28, 21, 55, 19))

    assert session.model_dump(mode="json")["opened_at"] == "2026-09-28T21:55:19Z"


def test_cash_session_serialization_normalizes_aware_offset_to_utc():
    session = _cash_session(
        datetime(2026, 9, 28, 18, 55, 19, tzinfo=timezone(timedelta(hours=-3)))
    )

    assert session.model_dump(mode="json")["opened_at"] == "2026-09-28T21:55:19Z"
