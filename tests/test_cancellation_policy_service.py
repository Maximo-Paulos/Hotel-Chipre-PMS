from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.cancellation_policy_service import evaluate_cancellation_policy


def _evaluate(
    *,
    policy_snapshot: dict | None,
    requested_at: datetime,
    check_in_date: date = date(2026, 11, 12),
    check_in_time: str | None = "15:00",
    hotel_timezone: str | None = "America/Argentina/Buenos_Aires",
    total_amount: str = "100000.00",
    reservation_currency: str = "ARS",
):
    return evaluate_cancellation_policy(
        check_in_date=check_in_date,
        total_amount=total_amount,
        reservation_currency=reservation_currency,
        policy_snapshot=policy_snapshot,
        check_in_time=check_in_time,
        hotel_timezone=hotel_timezone,
        requested_at=requested_at,
    )


def test_cancellation_inside_saved_free_window_has_no_penalty():
    result = _evaluate(
        policy_snapshot={"free_cancellation_hours": 48, "is_refundable": True},
        requested_at=datetime(2026, 11, 10, 17, 59, tzinfo=timezone.utc),
    )

    assert result.decision == "cancel_without_penalty"
    assert result.penalty_amount == Decimal("0.00")
    assert result.cutoff_at == datetime(2026, 11, 10, 18, 0, tzinfo=timezone.utc)


def test_cancellation_after_cutoff_requires_approval_for_saved_percentage():
    result = _evaluate(
        policy_snapshot={
            "free_cancellation_hours": 48,
            "is_refundable": True,
            "penalty_type": "percentage",
            "penalty_value": "50",
        },
        requested_at=datetime(2026, 11, 10, 18, 1, tzinfo=timezone.utc),
    )

    assert result.decision == "manager_approval_required"
    assert result.penalty_amount == Decimal("50000.00")
    assert result.currency_code == "ARS"


def test_non_refundable_saved_plan_uses_full_total_without_creating_a_charge():
    result = _evaluate(
        policy_snapshot={
            "cancellation_model": "non_refundable",
            "is_refundable": False,
            "free_cancellation_hours": 48,
        },
        requested_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )

    assert result.decision == "manager_approval_required"
    assert result.penalty_amount == Decimal("100000.00")
    assert result.reason == "penalty_requires_manager_approval"


def test_fixed_penalty_uses_saved_currency():
    result = _evaluate(
        policy_snapshot={
            "free_cancellation_hours": 48,
            "is_refundable": True,
            "penalty_type": "fixed",
            "penalty_value": "250.50",
            "currency": "usd",
        },
        requested_at=datetime(2026, 11, 10, 18, 1, tzinfo=timezone.utc),
    )

    assert result.decision == "manager_approval_required"
    assert result.penalty_amount == Decimal("250.50")
    assert result.currency_code == "USD"


def test_missing_snapshot_requires_manager_review_without_using_current_policy():
    result = _evaluate(
        policy_snapshot=None,
        requested_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )

    assert result.decision == "manager_review_required"
    assert result.penalty_amount is None
    assert result.reason == "missing_booking_policy_snapshot"


def test_missing_checkin_time_requires_hotel_configuration():
    result = _evaluate(
        policy_snapshot={"free_cancellation_hours": 48, "penalty_type": "percentage", "penalty_value": 50},
        requested_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        check_in_time=None,
    )

    assert result.decision == "hotel_configuration_required"
    assert result.penalty_amount is None


def test_invalid_policy_values_fail_closed_to_manager_review():
    result = _evaluate(
        policy_snapshot={"free_cancellation_hours": "48.5", "penalty_type": "percentage", "penalty_value": 150},
        requested_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
    )

    assert result.decision == "manager_review_required"
    assert result.penalty_amount is None


def test_cutoff_subtracts_elapsed_hours_across_daylight_saving_transition():
    result = _evaluate(
        policy_snapshot={
            "free_cancellation_hours": 48,
            "is_refundable": True,
            "penalty_type": "percentage",
            "penalty_value": 50,
        },
        requested_at=datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc),
        check_in_date=date(2026, 11, 1),
        check_in_time="15:00",
        hotel_timezone="America/New_York",
    )

    assert result.cutoff_at == datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)
    assert result.decision == "cancel_without_penalty"
