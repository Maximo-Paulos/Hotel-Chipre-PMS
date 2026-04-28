from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.models.analytics import FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum
from app.models.company import Company
from app.models.reservation import (
    ReservationChannelCodeEnum,
    ReservationGuestSegmentEnum,
    ReservationGuestSegmentSourceEnum,
    ReservationNoShowPolicyAppliedEnum,
    ReservationOutcomeEnum,
    ReservationStatusEnum,
)
from app.schemas.analytics import (
    AnalyticsComparisonStateRead,
    AnalyticsComparisonWindowRead,
    AnalyticsMetricCardRead,
    AnalyticsResponseEnvelopeRead,
    AnalyticsStarterSummaryDataRead,
    AnalyticsStarterSummaryRead,
)
from app.services.analytics_contracts import (
    MonetaryTotals,
    backfill_channel_code,
    build_analytics_window,
    build_comparison_state,
    build_reservation_nightly_facts,
    build_room_occupancy_nightly_fact,
    calculate_physical_room_nights,
    calculate_pickup_30d_count_from_rows,
    infer_guest_segment_from_company,
    normalize_channel_code,
    reservation_status_to_outcome,
    resolve_guest_segment,
    split_amount_evenly,
)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ReservationStatusEnum.PENDING, ReservationOutcomeEnum.PENDING),
        (ReservationStatusEnum.DEPOSIT_PAID, ReservationOutcomeEnum.PENDING),
        (ReservationStatusEnum.FULLY_PAID, ReservationOutcomeEnum.PENDING),
        (ReservationStatusEnum.CHECKED_IN, ReservationOutcomeEnum.CHECKED_IN),
        (ReservationStatusEnum.CHECKED_OUT, ReservationOutcomeEnum.COMPLETED),
        (ReservationStatusEnum.CANCELLED, ReservationOutcomeEnum.CANCELLED),
        (ReservationStatusEnum.NO_SHOW, ReservationOutcomeEnum.NO_SHOW),
    ],
)
def test_status_to_outcome(status, expected):
    assert reservation_status_to_outcome(status) == expected


def test_guest_segment_inference(db, hotel_config):
    company = Company(
        hotel_id=hotel_config.id,
        legal_name="Acme SRL",
        display_name="Acme",
        tax_id="30-12345678-9",
        country_code="AR",
    )
    db.add(company)
    db.flush()

    reservation = SimpleNamespace(
        guest_segment=None,
        guest_segment_source=None,
        company_id=company.id,
    )

    segment, source = resolve_guest_segment(reservation, company)
    assert segment == ReservationGuestSegmentEnum.BUSINESS
    assert source == ReservationGuestSegmentSourceEnum.INFERRED_FROM_COMPANY
    assert infer_guest_segment_from_company(company) == ReservationGuestSegmentEnum.BUSINESS

    manual = SimpleNamespace(
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.MANUAL,
        company_id=company.id,
    )
    segment, source = resolve_guest_segment(manual, company)
    assert segment == ReservationGuestSegmentEnum.LEISURE
    assert source == ReservationGuestSegmentSourceEnum.MANUAL


@pytest.mark.parametrize(
    ("value", "source", "provider", "expected"),
    [
        ("Booking.com", None, None, ReservationChannelCodeEnum.BOOKING),
        (None, "direct", None, ReservationChannelCodeEnum.OTHER_DIRECT),
        (None, None, "whatsapp", ReservationChannelCodeEnum.WHATSAPP),
        ("walkin", None, None, ReservationChannelCodeEnum.WALK_IN),
    ],
)
def test_channel_normalization(value, source, provider, expected):
    assert normalize_channel_code(value, source=source, source_provider_code=provider) == expected


def test_channel_backfill_from_reservation():
    reservation = SimpleNamespace(
        channel_code=None,
        source="booking",
        source_provider_code=None,
    )
    assert backfill_channel_code(reservation) == ReservationChannelCodeEnum.BOOKING


def test_even_split_and_no_show_allocation():
    parts = split_amount_evenly(Decimal("10.00"), 3)
    assert parts == [Decimal("3.34"), Decimal("3.33"), Decimal("3.33")]

    reservation = SimpleNamespace(
        id=10,
        hotel_id=1,
        room_id=7,
        category_id=2,
        company_id=None,
        source="direct",
        source_provider_code=None,
        status=ReservationStatusEnum.FULLY_PAID,
        outcome=ReservationOutcomeEnum.PENDING,
        guest_segment=ReservationGuestSegmentEnum.LEISURE,
        guest_segment_source=ReservationGuestSegmentSourceEnum.SYSTEM_DEFAULT,
    )
    facts = build_reservation_nightly_facts(
        reservation=reservation,
        stay_dates=[date(2026, 4, 1), date(2026, 4, 2)],
        totals=MonetaryTotals(
            revenue_gross_ars=Decimal("10.00"),
            revenue_gross_usd=Decimal("2.00"),
            revenue_net_ars=Decimal("8.00"),
            revenue_net_usd=Decimal("1.60"),
            tax_ars=Decimal("1.00"),
            tax_usd=Decimal("0.20"),
            fee_ars=Decimal("0.50"),
            fee_usd=Decimal("0.10"),
            commission_ars=Decimal("0.25"),
            commission_usd=Decimal("0.05"),
            variable_cost_ars=Decimal("0.75"),
            variable_cost_usd=Decimal("0.15"),
            margin_operating_ars=Decimal("7.00"),
            margin_operating_usd=Decimal("1.40"),
            source_currency="ARS",
            fx_rate_snapshot=Decimal("1.000000"),
        ),
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.FULL_CHARGE,
    )
    assert len(facts) == 2
    assert all(f.row_kind == FactReservationRowKindEnum.NO_SHOW_CHARGEABLE for f in facts)
    assert all(f.occupied_night is False for f in facts)
    assert all(f.chargeable_night is True for f in facts)
    assert sum(f.revenue_gross_ars for f in facts) == Decimal("10.00")
    assert sum(f.margin_operating_ars for f in facts) == Decimal("7.00")

    waived = build_reservation_nightly_facts(
        reservation=reservation,
        stay_dates=[date(2026, 4, 1)],
        totals=MonetaryTotals(
            revenue_gross_ars=Decimal("10.00"),
            revenue_gross_usd=Decimal("2.00"),
            revenue_net_ars=Decimal("8.00"),
            revenue_net_usd=Decimal("1.60"),
            tax_ars=Decimal("1.00"),
            tax_usd=Decimal("0.20"),
            fee_ars=Decimal("0.50"),
            fee_usd=Decimal("0.10"),
            commission_ars=Decimal("0.25"),
            commission_usd=Decimal("0.05"),
            variable_cost_ars=Decimal("0.75"),
            variable_cost_usd=Decimal("0.15"),
            margin_operating_ars=Decimal("7.00"),
            margin_operating_usd=Decimal("1.40"),
            source_currency="ARS",
            fx_rate_snapshot=Decimal("1.000000"),
        ),
        no_show_policy_applied=ReservationNoShowPolicyAppliedEnum.WAIVED,
    )
    assert waived[0].row_kind == FactReservationRowKindEnum.NO_SHOW_WAIVED
    assert waived[0].chargeable_night is False
    assert waived[0].revenue_gross_ars == Decimal("0.00")
    assert waived[0].margin_operating_ars == Decimal("0.00")


def test_room_occupancy_fact_and_metrics():
    occupancy_fact = build_room_occupancy_nightly_fact(
        hotel_id=1,
        room_id=33,
        stay_date=date(2026, 4, 1),
        category_id=2,
        status_at_night=FactRoomOccupancyStatusAtNightEnum.OCCUPIED,
        is_sellable_night=True,
        is_occupied=True,
        reservation_id=9,
        revenue_net_ars=Decimal("5.50"),
        revenue_net_usd=Decimal("1.10"),
        margin_operating_ars=Decimal("4.40"),
        margin_operating_usd=Decimal("0.88"),
    )
    assert occupancy_fact.status_at_night == FactRoomOccupancyStatusAtNightEnum.OCCUPIED
    assert occupancy_fact.revenue_net_ars == Decimal("5.50")
    assert calculate_physical_room_nights(active_room_count=5, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3)) == 15


def test_pickup_30d_count_from_rows():
    rows = [
        SimpleNamespace(
            created_at=datetime(2026, 4, 1, 15, 0, tzinfo=timezone.utc),
            check_in_date=date(2026, 4, 30),
            outcome=ReservationOutcomeEnum.PENDING,
        ),
        SimpleNamespace(
            created_at=datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc),
            check_in_date=date(2026, 5, 31),
            outcome=ReservationOutcomeEnum.PENDING,
        ),
        SimpleNamespace(
            created_at=datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc),
            check_in_date=date(2026, 4, 30),
            outcome=ReservationOutcomeEnum.CANCELLED,
        ),
    ]
    assert calculate_pickup_30d_count_from_rows(
        rows,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        hotel_timezone="America/Argentina/Buenos_Aires",
    ) == 1


def test_comparison_contracts_and_schemas():
    state = build_comparison_state(
        date(2026, 4, 1),
        date(2026, 4, 30),
        compare_previous=True,
        compare_yoy=True,
    )
    assert state.previous.requested is True
    assert state.previous.date_from == date(2026, 3, 2)
    assert state.previous.date_to == date(2026, 3, 31)
    assert state.yoy.date_from == date(2025, 4, 1)
    assert state.yoy.date_to == date(2025, 4, 30)

    envelope = build_analytics_window(
        date(2026, 4, 1),
        date(2026, 4, 30),
        compare_previous=True,
        compare_yoy=False,
    )
    assert envelope["date_from"] == date(2026, 4, 1)
    assert envelope["comparison"].previous.requested is True
    assert envelope["comparison"].yoy.requested is False

    comparison_window = AnalyticsComparisonWindowRead(
        requested=True,
        available=True,
        date_from=date(2026, 3, 2),
        date_to=date(2026, 3, 31),
    )
    comparison_state = AnalyticsComparisonStateRead(previous=comparison_window, yoy=comparison_window)
    metric = AnalyticsMetricCardRead(card_code="starter_revenue_month", label="Revenue del mes", value_ars="455000.00")
    starter = AnalyticsStarterSummaryRead(
        hotel_id=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        data=AnalyticsStarterSummaryDataRead(cards=[metric]),
        generated_at=datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
    )
    response = AnalyticsResponseEnvelopeRead(
        hotel_id=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 30),
        currency_display="ARS",
        comparison=comparison_state,
        data={"cards": [metric.model_dump()]},
        generated_at=datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
    )
    assert starter.data.cards[0].value_ars == "455000.00"
    assert response.comparison.previous.available is True
