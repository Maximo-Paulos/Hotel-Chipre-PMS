from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.analytics import FactReservationRowKindEnum
from app.models.reservation import (
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)
from app.services.analytics_service import (
    _category_fact_read,
    _company_fact_read,
    _company_reservation_read,
    _operations_reservation_read,
)


def test_analytics_reservation_serializers_derive_completed_from_status():
    reservation = SimpleNamespace(
        id=43,
        confirmation_code="RES-QA",
        status=ReservationStatusEnum.CHECKED_OUT,
        outcome=ReservationOutcomeEnum.PENDING,
        check_in_date=date(2026, 11, 4),
        check_out_date=date(2026, 11, 7),
        room_id=1,
        category_id=5,
        company_id=8,
    )

    assert _operations_reservation_read(reservation)["outcome"] == "completed"
    assert _company_reservation_read(reservation)["outcome"] == "completed"


def test_analytics_fact_serializers_derive_completed_from_status():
    fact = SimpleNamespace(
        stay_date=date(2026, 11, 4),
        reservation_id=43,
        room_id=1,
        category_id=5,
        status=ReservationStatusEnum.CHECKED_OUT,
        outcome=ReservationOutcomeEnum.PENDING,
        channel_code=ReservationChannelCodeEnum.OTHER_DIRECT,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        row_kind=FactReservationRowKindEnum.OCCUPIED,
        revenue_net_ars=Decimal("0"),
        revenue_net_usd=Decimal("0"),
        margin_operating_ars=Decimal("0"),
        margin_operating_usd=Decimal("0"),
        source_currency="ARS",
        fx_rate_snapshot=None,
    )

    assert _company_fact_read(fact)["outcome"] == "completed"
    assert _category_fact_read(fact)["outcome"] == "completed"
