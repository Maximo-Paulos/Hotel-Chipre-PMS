"""Explainable, recommendation-only category tariff adjustments."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.daily_rate import PricePeriod
from app.models.hotel_config import HotelConfiguration
from app.models.published_rate_history import PublishedRateHistory
from app.models.rate_change_draft import RateChangeDraft
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.services.business_clock_service import hotel_today
from app.services.pricing_service import resolve_rate_calendar
from app.services.published_rate_history_service import get_fresh_ars_per_usd_snapshot
from app.services.rate_change_draft_service import (
    MAX_DRAFT_DATES,
    create_rate_change_draft,
)

PICKUP_WINDOW = timedelta(days=7)
HISTORY_LOOKBACK_DAYS = 365 * 5
MIN_COMPARABLE_RATE_DATES = 3
MAX_RECOMMENDATION_RANGE_DAYS = MAX_DRAFT_DATES


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return amount if amount.is_finite() else None


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


def _season_period_for_date(
    periods: list[PricePeriod], target_date: date
) -> PricePeriod | None:
    matches = [
        period
        for period in periods
        if period.start_date <= target_date <= period.end_date
    ]
    if not matches:
        return None
    return max(matches, key=lambda period: (period.priority, period.id))


def _high_demand_event_for_date(
    periods: list[PricePeriod], target_date: date
) -> PricePeriod | None:
    matches = [
        period
        for period in periods
        if period.is_high_demand_event
        and period.start_date <= target_date <= period.end_date
    ]
    if not matches:
        return None
    return max(matches, key=lambda period: (period.priority, period.id))


def _consecutive_date_runs(dates: list[date]) -> list[tuple[date, date]]:
    ordered = sorted(set(dates))
    if not ordered:
        return []
    runs: list[tuple[date, date]] = []
    start = previous = ordered[0]
    for current in ordered[1:]:
        if current == previous + timedelta(days=1):
            previous = current
            continue
        runs.append((start, previous))
        start = previous = current
    runs.append((start, previous))
    return runs


def _latest_comparable_rates(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    as_of_date: date,
) -> dict[str, dict[date, Decimal]]:
    earliest = as_of_date - timedelta(days=HISTORY_LOOKBACK_DAYS)
    rows = (
        db.query(PublishedRateHistory)
        .filter(
            PublishedRateHistory.hotel_id == hotel_id,
            PublishedRateHistory.category_id == category_id,
            PublishedRateHistory.rate_date >= earliest,
            PublishedRateHistory.rate_date < as_of_date,
            PublishedRateHistory.comparable_season_key.is_not(None),
            PublishedRateHistory.usd_amount.is_not(None),
        )
        .order_by(PublishedRateHistory.captured_at.desc(), PublishedRateHistory.id.desc())
        .all()
    )
    result: dict[str, dict[date, Decimal]] = defaultdict(dict)
    for row in rows:
        key = str(row.comparable_season_key or "").strip().casefold()
        if not key or row.rate_date in result[key]:
            continue
        amount = _decimal(row.usd_amount)
        if amount is not None and amount > 0:
            result[key][row.rate_date] = amount
    return result


def _historical_pickups_by_date(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    comparable_dates: list[date],
    min_lead_days: int,
    max_lead_days: int,
) -> dict[date, list[Reservation]]:
    """Load historical bookings once, scoped to comparable nights and lead windows."""
    by_date: dict[date, list[Reservation]] = defaultdict(list)
    runs = _consecutive_date_runs(comparable_dates)
    if not runs:
        return by_date

    windows = []
    for start, end in runs:
        # A booking can belong to any seven-day pickup window in the requested
        # lead-time range. The outer interval lets Python apply exact windows.
        created_from = start - timedelta(days=max_lead_days) - PICKUP_WINDOW
        created_to = end - timedelta(days=min_lead_days)
        windows.append(
            and_(
                Reservation.check_in_date <= end,
                Reservation.check_out_date > start,
                Reservation.created_at >= _naive_utc(datetime.combine(created_from, time.min, UTC)),
                Reservation.created_at < _naive_utc(
                    datetime.combine(created_to + timedelta(days=1), time.min, UTC)
                ),
            )
        )
    rows = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.category_id == category_id,
            Reservation.deleted_at.is_(None),
            or_(*windows),
        )
        .all()
    )
    date_set = set(comparable_dates)
    for reservation in rows:
        current = max(reservation.check_in_date, min(date_set))
        final = min(reservation.check_out_date - timedelta(days=1), max(date_set))
        while current <= final:
            if current in date_set:
                by_date[current].append(reservation)
            current += timedelta(days=1)
    return by_date


def _historical_pickup_average(
    reservations_by_date: dict[date, list[Reservation]],
    *,
    comparable_dates: list[date],
    lead_days: int,
    now: datetime,
) -> Decimal | None:
    pickup_counts: list[int] = []
    current_time = now.timetz().replace(tzinfo=UTC)
    for stay_date in comparable_dates:
        cutoff_date = stay_date - timedelta(days=lead_days)
        cutoff = datetime.combine(cutoff_date, current_time, UTC)
        window_start = cutoff - PICKUP_WINDOW
        count = 0
        for reservation in reservations_by_date.get(stay_date, []):
            created_at = _utc(reservation.created_at)
            if created_at is None or not window_start <= created_at < cutoff:
                continue
            cancelled_at = _utc(reservation.cancelled_at)
            if reservation.status == ReservationStatusEnum.CANCELLED and (
                cancelled_at is None or cancelled_at <= cutoff
            ):
                continue
            no_show_at = _utc(reservation.no_show_confirmed_at)
            if reservation.status == ReservationStatusEnum.NO_SHOW and (
                no_show_at is None or no_show_at <= cutoff
            ):
                continue
            count += 1
        pickup_counts.append(count)
    if len(pickup_counts) < MIN_COMPARABLE_RATE_DATES:
        return None
    average = Decimal(sum(pickup_counts)) / Decimal(len(pickup_counts))
    return average if average > 0 else None


def _current_occupancy_and_pickup(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    start_date: date,
    end_date: date,
    room_count: int,
    now: datetime,
) -> tuple[dict[date, int], dict[date, int]]:
    occupied: Counter[date] = Counter()
    recent_pickup: Counter[date] = Counter()
    rows = (
        db.query(Reservation)
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.category_id == category_id,
            Reservation.deleted_at.is_(None),
            Reservation.check_in_date <= end_date,
            Reservation.check_out_date > start_date,
            Reservation.status.notin_([
                ReservationStatusEnum.CANCELLED,
                ReservationStatusEnum.NO_SHOW,
            ]),
        )
        .all()
    )
    pickup_start = now - PICKUP_WINDOW
    for reservation in rows:
        first = max(start_date, reservation.check_in_date)
        last = min(end_date, reservation.check_out_date - timedelta(days=1))
        if first > last:
            continue
        created_at = _utc(reservation.created_at)
        is_recent = created_at is not None and pickup_start <= created_at <= now
        current = first
        while current <= last:
            occupied[current] += 1
            if is_recent:
                recent_pickup[current] += 1
            current += timedelta(days=1)
    return dict(occupied), dict(recent_pickup)


def _current_rate_in_usd(
    *,
    amount: Decimal,
    currency: str,
    ars_per_usd: Decimal | None,
) -> Decimal | None:
    if currency == "USD":
        return amount
    if currency == "ARS" and ars_per_usd is not None and ars_per_usd > 0:
        return amount / ars_per_usd
    return None


def _recommend_rate_direction(
    *,
    occupancy_pct: Decimal,
    pickup_change_pct: Decimal | None,
    high_occupancy_pct: Decimal,
    low_occupancy_pct: Decimal,
    pickup_threshold_pct: Decimal,
    high_demand_event: bool,
) -> tuple[int, str] | None:
    """Return an explainable direction only for an event or matching signals."""
    if high_demand_event:
        return 1, "hotel_marked_high_demand_event"
    if pickup_change_pct is None:
        return None
    if occupancy_pct >= high_occupancy_pct and pickup_change_pct >= pickup_threshold_pct:
        return 1, "high_occupancy_and_pickup"
    if occupancy_pct <= low_occupancy_pct and pickup_change_pct <= -pickup_threshold_pct:
        return -1, "low_occupancy_and_pickup"
    return None


def _effective_rate_adjustment_pct(
    *,
    current_usd: Decimal,
    comparable_average_usd: Decimal,
    max_step_pct: Decimal,
    direction: int,
) -> Decimal:
    """Modulate the signed step by how far the USD rate is in the move direction.

    A rate already above its comparable mean gets a smaller increase; a rate
    already below that mean gets a smaller decrease. The inverse ratio provides
    a smooth modulation without introducing a separate minimum-price floor.
    """
    if current_usd <= 0 or comparable_average_usd <= 0 or direction not in {-1, 1}:
        raise ValueError("La recomendación requiere importes positivos y una dirección válida.")
    step_pct = min(max_step_pct, Decimal(5))
    if step_pct <= 0:
        raise ValueError("El paso de tarifa debe ser positivo.")
    comparator_factor = (
        comparable_average_usd / current_usd
        if direction > 0
        else current_usd / comparable_average_usd
    )
    return step_pct * min(Decimal(1), comparator_factor) * Decimal(direction)


def _suggest_rate_amount(
    *,
    current_amount: Decimal,
    comparable_average_usd: Decimal,
    currency: str,
    ars_per_usd: Decimal | None,
    max_step_pct: Decimal,
    direction: int,
) -> Decimal:
    """Apply the modulated percentage to today's tariff and round to a unit."""
    if current_amount <= 0 or comparable_average_usd <= 0:
        raise ValueError("La recomendación requiere importes positivos y una dirección válida.")
    current_usd = _current_rate_in_usd(
        amount=current_amount, currency=currency, ars_per_usd=ars_per_usd
    )
    if current_usd is None or current_usd <= 0:
        raise ValueError("No se puede convertir la tarifa vigente a USD.")
    adjustment_pct = _effective_rate_adjustment_pct(
        current_usd=current_usd,
        comparable_average_usd=comparable_average_usd,
        max_step_pct=max_step_pct,
        direction=direction,
    )
    amount_delta = current_amount * (abs(adjustment_pct) / Decimal(100))
    return (current_amount + amount_delta * Decimal(direction)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )


def generate_category_rate_recommendations(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    date_from: date,
    date_to: date,
    user_id: int | None = None,
    trigger: str = "manual",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create one reviewable rate draft when signals and data are sufficient."""
    if date_to < date_from:
        raise ValueError("La fecha final debe ser igual o posterior a la inicial.")
    if (date_to - date_from).days + 1 > MAX_RECOMMENDATION_RANGE_DAYS:
        raise ValueError("El rango de recomendación no puede superar 366 fechas.")
    config = (
        db.query(HotelConfiguration)
        .filter(HotelConfiguration.id == hotel_id)
        .one_or_none()
    )
    if config is None:
        raise ValueError("No se encontró la configuración del hotel.")
    if not config.tariff_recommendations_enabled:
        return {"created": False, "reason": "engine_disabled", "draft": None, "suggestions": []}
    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.hotel_id == hotel_id, RoomCategory.id == category_id)
        .one_or_none()
    )
    if category is None:
        raise ValueError("La categoría no existe en este hotel.")
    open_draft = (
        db.query(RateChangeDraft.id)
        .filter(
            RateChangeDraft.hotel_id == hotel_id,
            RateChangeDraft.category_id == category_id,
            RateChangeDraft.status == "draft",
        )
        .first()
    )
    if open_draft is not None:
        return {"created": False, "reason": "open_rate_draft", "draft": None, "suggestions": []}

    now = _utc(now or datetime.now(UTC))
    assert now is not None
    business_date = hotel_today(db, hotel_id)
    if date_from <= business_date:
        date_from = business_date + timedelta(days=1)
    if date_from > date_to:
        return {"created": False, "reason": "no_future_dates", "draft": None, "suggestions": []}

    room_count = (
        db.query(Room.id)
        .filter(
            Room.hotel_id == hotel_id,
            Room.category_id == category_id,
            Room.is_active.is_(True),
            Room.deleted_at.is_(None),
            Room.status.notin_([RoomStatusEnum.MAINTENANCE, RoomStatusEnum.BLOCKED]),
        )
        .count()
    )
    if room_count <= 0:
        return {"created": False, "reason": "no_sellable_rooms", "draft": None, "suggestions": []}

    currency = str(config.default_currency or "ARS").strip().upper()
    ars_per_usd: Decimal | None = None
    fx_snapshot_id = None
    fx_snapshot = None
    if currency == "ARS":
        fx_snapshot = get_fresh_ars_per_usd_snapshot(
            db, hotel_id=hotel_id, config=config, now=now
        )
        if fx_snapshot is not None:
            ars_per_usd = _decimal(fx_snapshot.applied_rate)
            fx_snapshot_id = fx_snapshot.id
    if currency not in {"ARS", "USD"} or (currency == "ARS" and ars_per_usd is None):
        return {"created": False, "reason": "fresh_usd_conversion_unavailable", "draft": None, "suggestions": []}

    periods = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
            PricePeriod.is_active.is_(True),
            PricePeriod.start_date <= date_to,
            PricePeriod.end_date >= date_from,
        )
        .order_by(PricePeriod.priority.desc(), PricePeriod.id.desc())
        .all()
    )
    rate_rows = resolve_rate_calendar(
        db, hotel_id, category_id, date_from, date_to, category=category
    )
    rates_by_date = {row["date"]: row for row in rate_rows}
    historical_rates = _latest_comparable_rates(
        db, hotel_id=hotel_id, category_id=category_id, as_of_date=business_date
    )
    comparable_dates_by_key = {
        key: sorted(rows.keys()) for key, rows in historical_rates.items()
    }
    historical_dates = sorted(
        {historical_date for dates in comparable_dates_by_key.values() for historical_date in dates}
    )
    lead_days_for_range = max(1, (date_to - business_date).days)
    historic_reservations_by_date = _historical_pickups_by_date(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        comparable_dates=historical_dates,
        min_lead_days=1,
        max_lead_days=lead_days_for_range,
    )
    occupied_by_date, recent_pickup_by_date = _current_occupancy_and_pickup(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        start_date=date_from,
        end_date=date_to,
        room_count=room_count,
        now=now,
    )

    high_occupancy_pct = Decimal(str(config.tariff_high_occupancy_pct))
    low_occupancy_pct = Decimal(str(config.tariff_low_occupancy_pct))
    pickup_threshold_pct = Decimal(str(config.tariff_pickup_change_pct))
    max_step_pct = min(Decimal(str(config.tariff_max_step_pct)), Decimal(5))
    suggestions: list[dict[str, Any]] = []
    skipped: Counter[str] = Counter()
    changes: list[dict[str, Any]] = []

    target = date_from
    while target <= date_to:
        period = _season_period_for_date(periods, target)
        high_demand_event = _high_demand_event_for_date(periods, target)
        if period is None:
            skipped["no_active_price_period"] += 1
            target += timedelta(days=1)
            continue
        season_key = str(period.comparable_season_key or "").strip().casefold()
        if not season_key:
            skipped["season_not_marked_comparable"] += 1
            target += timedelta(days=1)
            continue
        history_for_key = historical_rates.get(season_key, {})
        if len(history_for_key) < MIN_COMPARABLE_RATE_DATES:
            skipped["insufficient_published_history"] += 1
            target += timedelta(days=1)
            continue
        historical_dates_for_key = comparable_dates_by_key.get(season_key, [])
        current_rate = _decimal((rates_by_date.get(target) or {}).get("price"))
        current_usd = (
            _current_rate_in_usd(amount=current_rate, currency=currency, ars_per_usd=ars_per_usd)
            if current_rate is not None and current_rate > 0
            else None
        )
        if current_rate is None or current_rate <= 0 or current_usd is None or current_usd <= 0:
            skipped["current_rate_unavailable"] += 1
            target += timedelta(days=1)
            continue

        comparable_usd = sum(history_for_key.values(), Decimal(0)) / Decimal(len(history_for_key))
        if comparable_usd <= 0:
            skipped["comparable_usd_average_unavailable"] += 1
            target += timedelta(days=1)
            continue
        lead_days = (target - business_date).days
        historical_pickup_avg = _historical_pickup_average(
            historic_reservations_by_date,
            comparable_dates=historical_dates_for_key,
            lead_days=lead_days,
            now=now,
        )
        if historical_pickup_avg is None:
            pickup_change_pct = None
        else:
            current_pickup = Decimal(recent_pickup_by_date.get(target, 0))
            pickup_change_pct = ((current_pickup - historical_pickup_avg) / historical_pickup_avg) * Decimal(100)

        occupied = min(occupied_by_date.get(target, 0), room_count)
        occupancy_pct = (Decimal(occupied) / Decimal(room_count)) * Decimal(100)
        if occupied >= room_count:
            skipped["no_remaining_inventory"] += 1
            target += timedelta(days=1)
            continue

        direction_result = _recommend_rate_direction(
            occupancy_pct=occupancy_pct,
            pickup_change_pct=pickup_change_pct,
            high_occupancy_pct=high_occupancy_pct,
            low_occupancy_pct=low_occupancy_pct,
            pickup_threshold_pct=pickup_threshold_pct,
            high_demand_event=high_demand_event is not None,
        )
        if direction_result is None:
            skip_reason = "pickup_history_unavailable" if pickup_change_pct is None and high_demand_event is None else "signals_do_not_agree"
            skipped[skip_reason] += 1
            target += timedelta(days=1)
            continue
        direction, signal = direction_result

        # Demand selects direction; the comparable USD average modulates the
        # signed step. The resulting percentage is applied to today's rate.
        try:
            suggested_amount = _suggest_rate_amount(
                current_amount=current_rate,
                comparable_average_usd=comparable_usd,
                currency=currency,
                ars_per_usd=ars_per_usd,
                max_step_pct=max_step_pct,
                direction=direction,
            )
        except ValueError:
            skipped["current_rate_unavailable"] += 1
            target += timedelta(days=1)
            continue
        if suggested_amount == current_rate:
            skipped["rounds_to_current_rate"] += 1
            target += timedelta(days=1)
            continue
        suggested_usd = _current_rate_in_usd(
            amount=suggested_amount, currency=currency, ars_per_usd=ars_per_usd
        )
        adjustment_pct = _effective_rate_adjustment_pct(
            current_usd=current_usd,
            comparable_average_usd=comparable_usd,
            max_step_pct=max_step_pct,
            direction=direction,
        )
        current_vs_comparable_pct = (
            (current_usd - comparable_usd) / comparable_usd
        ) * Decimal(100)
        suggestions.append(
            {
                "date": target.isoformat(),
                "direction": "up" if direction > 0 else "down",
                "signal": signal,
                "season_key": season_key,
                "event_name": high_demand_event.name if high_demand_event is not None else None,
                "currency_code": currency,
                "current_amount": float(current_rate),
                "suggested_amount": float(suggested_amount),
                "current_usd": round(float(current_usd), 4),
                "suggested_usd": round(float(suggested_usd or 0), 4),
                "comparable_average_usd": round(float(comparable_usd), 4),
                "current_vs_comparable_pct": round(float(current_vs_comparable_pct), 2),
                "occupancy_pct": round(float(occupancy_pct), 2),
                "pickup_change_pct": round(float(pickup_change_pct), 2) if pickup_change_pct is not None else None,
                "adjustment_pct": float(adjustment_pct),
                "max_step_pct": float(max_step_pct),
            }
        )
        changes.append({"date": target, "values": {"price": float(suggested_amount)}})
        target += timedelta(days=1)

    if not changes:
        return {
            "created": False,
            "reason": "no_eligible_signal",
            "draft": None,
            "suggestions": [],
            "skipped": dict(skipped),
        }

    metadata = {
        "recommendation": {
            "engine": "experimental_tariff_v1",
            "trigger": trigger,
            "generated_at": now.isoformat(),
            "currency_code": currency,
            "fx_snapshot_id": fx_snapshot_id,
            "fx_market": getattr(config, "fx_ars_to_usd_rate_type", None) if currency == "ARS" else None,
            "fx_side": getattr(config, "fx_ars_to_usd_rate_side", None) if currency == "ARS" else None,
            "fx_ars_per_usd": float(ars_per_usd) if ars_per_usd is not None else None,
            "fx_quote_as_of": (
                (_utc(fx_snapshot.provider_updated_at) or _utc(fx_snapshot.fetched_at)).isoformat()
                if fx_snapshot is not None else None
            ),
            "thresholds": {
                "high_occupancy_pct": float(high_occupancy_pct),
                "low_occupancy_pct": float(low_occupancy_pct),
                "pickup_change_pct": float(pickup_threshold_pct),
                "max_step_pct": float(max_step_pct),
            },
            "method": "El promedio USD comparable modula el tamaño del ajuste: se parte del paso máximo configurado (hasta 5%) y se reduce en proporción cuando la tarifa vigente ya supera el promedio antes de una suba, o ya está por debajo antes de una baja. La dirección surge de un evento marcado o de señales concordantes de ocupación y pickup. El porcentaje resultante se aplica a la tarifa vigente y se redondea a una unidad entera.",
            "sources": ["published_rate_history", "reservations", "price_periods"],
            "not_used": ["availability_searches_not_persisted"],
            "suggestions": suggestions,
            "skipped": dict(skipped),
        }
    }
    draft = create_rate_change_draft(
        db,
        hotel_id=hotel_id,
        user_id=user_id,
        category_id=category_id,
        changes=changes,
        impact_metadata=metadata,
    )
    return {"created": True, "reason": None, "draft": draft, "suggestions": suggestions, "skipped": dict(skipped)}


def generate_daily_rate_recommendations(
    db: Session,
    *,
    hotel_id: int,
    lookahead_days: int = 90,
    now: datetime | None = None,
) -> dict[str, int]:
    """Run the bounded daily review without publishing or confirming rates."""
    config = (
        db.query(HotelConfiguration)
        .filter(
            HotelConfiguration.id == hotel_id,
            HotelConfiguration.tariff_recommendations_enabled.is_(True),
        )
        .one_or_none()
    )
    if config is None:
        return {"categories": 0, "drafts_created": 0, "dates_suggested": 0}
    start_date = hotel_today(db, hotel_id) + timedelta(days=1)
    end_date = start_date + timedelta(days=max(1, min(int(lookahead_days), 365))) - timedelta(days=1)
    category_ids = [
        row[0]
        for row in db.query(RoomCategory.id)
        .filter(RoomCategory.hotel_id == hotel_id)
        .order_by(RoomCategory.id.asc())
        .all()
    ]
    created = dates_suggested = 0
    for category_id in category_ids:
        result = generate_category_rate_recommendations(
            db,
            hotel_id=hotel_id,
            category_id=category_id,
            date_from=start_date,
            date_to=end_date,
            trigger="daily_review",
            now=now,
        )
        if result["created"]:
            created += 1
            dates_suggested += len(result["suggestions"])
    return {"categories": len(category_ids), "drafts_created": created, "dates_suggested": dates_suggested}
