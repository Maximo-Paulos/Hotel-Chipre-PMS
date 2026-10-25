"""Pure cancellation-policy evaluation from the immutable booking snapshot."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

CancellationDecision = Literal[
    "cancel_without_penalty",
    "manager_approval_required",
    "manager_review_required",
    "hotel_configuration_required",
]

_CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class CancellationEvaluation:
    decision: CancellationDecision
    penalty_amount: Decimal | None
    currency_code: str | None
    cutoff_at: datetime | None
    reason: str


def evaluate_cancellation_policy(
    *,
    check_in_date: date,
    total_amount: Decimal | int | float | str | None,
    reservation_currency: str | None,
    policy_snapshot: dict[str, Any] | None,
    check_in_time: str | None,
    hotel_timezone: str | None,
    requested_at: datetime | None = None,
) -> CancellationEvaluation:
    """Calculate a proposed cancellation penalty without applying it.

    Missing historical terms and invalid hotel schedule configuration fail
    closed into review states. This function never reads today's rate-plan or
    hotel cancellation settings and never mutates reservation/payment data.
    """
    if not isinstance(policy_snapshot, dict):
        return CancellationEvaluation(
            decision="manager_review_required",
            penalty_amount=None,
            currency_code=None,
            cutoff_at=None,
            reason="missing_booking_policy_snapshot",
        )

    parsed_time = _parse_hotel_time(check_in_time)
    timezone_name = (hotel_timezone or "").strip()
    if parsed_time is None or not timezone_name:
        return CancellationEvaluation(
            decision="hotel_configuration_required",
            penalty_amount=None,
            currency_code=None,
            cutoff_at=None,
            reason="check_in_schedule_not_configured",
        )
    try:
        hotel_zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        return CancellationEvaluation(
            decision="hotel_configuration_required",
            penalty_amount=None,
            currency_code=None,
            cutoff_at=None,
            reason="hotel_timezone_invalid",
        )

    raw_free_hours = policy_snapshot.get("free_cancellation_hours")
    if isinstance(raw_free_hours, bool):
        return _review("invalid_free_cancellation_window")
    try:
        free_hours = int(raw_free_hours)
    except (TypeError, ValueError):
        return _review("invalid_free_cancellation_window")
    if free_hours < 0 or str(free_hours) != str(raw_free_hours).strip():
        return _review("invalid_free_cancellation_window")

    local_check_in = datetime.combine(check_in_date, parsed_time, tzinfo=hotel_zone)
    # Compute elapsed hours on the timeline. Subtracting before converting to
    # UTC would use wall-clock arithmetic across a daylight-saving transition.
    cutoff_at = local_check_in.astimezone(timezone.utc) - timedelta(hours=free_hours)
    instant = requested_at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)
    cutoff_utc = cutoff_at

    non_refundable = (
        policy_snapshot.get("is_refundable") is False
        or str(policy_snapshot.get("cancellation_model") or "").strip().lower() == "non_refundable"
    )
    if instant <= cutoff_utc and not non_refundable:
        return CancellationEvaluation(
            decision="cancel_without_penalty",
            penalty_amount=Decimal("0.00"),
            currency_code=_currency(reservation_currency),
            cutoff_at=cutoff_utc,
            reason="within_free_cancellation_window",
        )

    amount = _decimal_amount(total_amount)
    if amount is None:
        return _review("reservation_total_invalid", cutoff_at=cutoff_utc)

    penalty_type = str(policy_snapshot.get("penalty_type") or "").strip().lower()
    raw_value = policy_snapshot.get("penalty_value")
    if non_refundable and (not penalty_type or raw_value in (None, "")):
        penalty = amount
        currency = _currency(reservation_currency)
    else:
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError):
            return _review("cancellation_penalty_not_configured", cutoff_at=cutoff_utc)
        if not value.is_finite() or value < 0:
            return _review("cancellation_penalty_invalid", cutoff_at=cutoff_utc)
        if penalty_type == "percentage":
            if value > 100:
                return _review("cancellation_penalty_invalid", cutoff_at=cutoff_utc)
            penalty = (amount * value / Decimal("100")).quantize(_CENT, rounding=ROUND_HALF_UP)
            currency = _currency(reservation_currency)
        elif penalty_type == "fixed":
            penalty = value.quantize(_CENT, rounding=ROUND_HALF_UP)
            currency = _currency(policy_snapshot.get("currency") or reservation_currency)
        else:
            return _review("cancellation_penalty_not_configured", cutoff_at=cutoff_utc)

    if currency is None:
        return _review("cancellation_penalty_currency_invalid", cutoff_at=cutoff_utc)
    if penalty == 0:
        return CancellationEvaluation(
            decision="cancel_without_penalty",
            penalty_amount=Decimal("0.00"),
            currency_code=currency,
            cutoff_at=cutoff_utc,
            reason="policy_penalty_is_zero",
        )
    return CancellationEvaluation(
        decision="manager_approval_required",
        penalty_amount=penalty,
        currency_code=currency,
        cutoff_at=cutoff_utc,
        reason="penalty_requires_manager_approval",
    )


def _parse_hotel_time(value: str | None) -> time | None:
    if not isinstance(value, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value.strip()) is None:
        return None
    try:
        return time.fromisoformat(value.strip())
    except ValueError:
        return None


def _decimal_amount(value: Decimal | int | float | str | None) -> Decimal | None:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    return amount.quantize(_CENT, rounding=ROUND_HALF_UP)


def _currency(value: Any) -> str | None:
    currency = str(value or "").strip().upper()
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha():
        return None
    return currency


def _review(reason: str, *, cutoff_at: datetime | None = None) -> CancellationEvaluation:
    return CancellationEvaluation(
        decision="manager_review_required",
        penalty_amount=None,
        currency_code=None,
        cutoff_at=cutoff_at,
        reason=reason,
    )
