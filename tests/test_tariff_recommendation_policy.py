from decimal import Decimal

import pytest

from app.services.tariff_recommendation_service import (
    _effective_rate_adjustment_pct,
    _recommend_rate_direction,
    _suggest_rate_amount,
)


def _direction(occupancy_pct: int, pickup_change_pct: int | None, *, event: bool = False):
    return _recommend_rate_direction(
        occupancy_pct=Decimal(occupancy_pct),
        pickup_change_pct=Decimal(pickup_change_pct) if pickup_change_pct is not None else None,
        high_occupancy_pct=Decimal(80),
        low_occupancy_pct=Decimal(40),
        pickup_threshold_pct=Decimal(20),
        high_demand_event=event,
    )


def test_direction_requires_matching_occupancy_and_pickup_signals():
    assert _direction(85, 25) == (1, "high_occupancy_and_pickup")
    assert _direction(35, -25) == (-1, "low_occupancy_and_pickup")
    assert _direction(85, 19) is None
    assert _direction(50, 25) is None
    assert _direction(50, None) is None


def test_marked_high_demand_event_always_points_up():
    assert _direction(20, -70, event=True) == (1, "hotel_marked_high_demand_event")


@pytest.mark.parametrize(
    ("current", "average", "currency", "fx", "direction", "expected"),
    [
        # A move farther away from the comparator is reduced in proportion.
        ("200", "100", "USD", None, 1, "205"),
        ("80", "100", "USD", None, -1, "77"),
        ("10000", "100", "ARS", "1000", -1, "9950"),
        # A move toward the comparator keeps the configured step, based on today's tariff.
        ("100", "10", "USD", None, 1, "101"),
        ("103", "100", "USD", None, 1, "108"),
        ("103", "100", "USD", None, -1, "98"),
    ],
)
def test_suggested_amount_uses_current_rate_percentage_and_rounds_to_integer(
    current, average, currency, fx, direction, expected
):
    actual = _suggest_rate_amount(
        current_amount=Decimal(current),
        comparable_average_usd=Decimal(average),
        currency=currency,
        ars_per_usd=Decimal(fx) if fx is not None else None,
        max_step_pct=Decimal(8),
        direction=direction,
    )
    assert actual == Decimal(expected)


@pytest.mark.parametrize(
    ("current_usd", "average_usd", "direction", "expected_pct"),
    [
        ("200", "100", 1, "2.5"),
        ("80", "100", -1, "-4.0"),
        ("100", "200", 1, "5"),
        ("200", "100", -1, "-5"),
    ],
)
def test_comparable_rate_distance_modulates_step_by_direction(
    current_usd, average_usd, direction, expected_pct
):
    assert _effective_rate_adjustment_pct(
        current_usd=Decimal(current_usd),
        comparable_average_usd=Decimal(average_usd),
        max_step_pct=Decimal(8),
        direction=direction,
    ) == Decimal(expected_pct)


def test_suggested_amount_rejects_invalid_direction():
    with pytest.raises(ValueError):
        _suggest_rate_amount(
            current_amount=Decimal(100),
            comparable_average_usd=Decimal(100),
            currency="USD",
            ars_per_usd=None,
            max_step_pct=Decimal(5),
            direction=0,
        )
