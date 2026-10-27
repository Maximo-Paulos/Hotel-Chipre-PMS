"""Capture approved category rates with the currency and comparable season used."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.models.daily_rate import PricePeriod
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.hotel_config import HotelConfiguration
from app.models.published_rate_history import PublishedRateHistory
from app.models.rate_change_draft import RateChangeDraft

_MAX_FX_AGE = timedelta(hours=24)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _published_base_rates(draft: RateChangeDraft) -> list[tuple[date, Decimal, str]]:
    rows: list[tuple[date, Decimal, str]] = []
    if draft.draft_type == "daily_rates":
        for item in draft.changes or []:
            values = item.get("values") or {}
            if "price" not in values:
                continue
            amount = _decimal(values.get("price"))
            try:
                rate_date = date.fromisoformat(item["date"])
            except (KeyError, TypeError, ValueError):
                continue
            if amount is not None:
                rows.append((rate_date, amount, "daily_rates"))
        return rows

    if draft.draft_type != "price_period":
        return rows
    for item in (draft.period_operation or {}).get("effective_changes", []):
        before = _decimal((item.get("before") or {}).get("price"))
        after = _decimal((item.get("after") or {}).get("price"))
        if after is None or before == after:
            continue
        try:
            rate_date = date.fromisoformat(item["date"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append((rate_date, after, "price_period"))
    return rows


def _comparable_season_key(
    db: Session, *, hotel_id: int, category_id: int, rate_date: date
) -> str | None:
    period = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
            PricePeriod.is_active.is_(True),
            PricePeriod.start_date <= rate_date,
            PricePeriod.end_date >= rate_date,
        )
        .order_by(PricePeriod.priority.desc(), PricePeriod.id.desc())
        .first()
    )
    key = str(period.comparable_season_key or "").strip().casefold() if period else ""
    return key or None


def get_fresh_ars_per_usd_snapshot(
    db: Session,
    *,
    hotel_id: int,
    config: HotelConfiguration,
    now: datetime,
) -> FxRateSnapshot | None:
    market = str(getattr(config, "fx_ars_to_usd_rate_type", "oficial") or "oficial").strip().lower()
    side = str(getattr(config, "fx_ars_to_usd_rate_side", "venta") or "venta").strip().lower()
    if market not in {"oficial", "blue"} or side not in {"compra", "venta"}:
        return None
    snapshots = (
        db.query(FxRateSnapshot)
        .filter(
            FxRateSnapshot.hotel_id == hotel_id,
            FxRateSnapshot.rate_type == market,
            FxRateSnapshot.moneda == "USD",
            FxRateSnapshot.selected_side == side,
            FxRateSnapshot.applied_rate.is_not(None),
            FxRateSnapshot.applied_rate > 0,
        )
        .order_by(FxRateSnapshot.provider_updated_at.desc(), FxRateSnapshot.fetched_at.desc())
        .all()
    )
    for snapshot in snapshots:
        quote_time = _utc(snapshot.provider_updated_at) or _utc(snapshot.fetched_at)
        selected_rate = _decimal(getattr(snapshot, side, None))
        applied_rate = _decimal(snapshot.applied_rate)
        if selected_rate is None or applied_rate != selected_rate:
            continue
        if quote_time is not None and now - _MAX_FX_AGE <= quote_time <= now + timedelta(minutes=5):
            return snapshot
    return None


def record_published_rate_history(
    db: Session,
    draft: RateChangeDraft,
    *,
    now: datetime | None = None,
) -> int:
    """Write a history row for each approved base-rate change in the draft.

    This is called inside the transaction that confirms the rate draft. It
    never fetches a quote from an external provider; ARS values without a
    fresh, already-recorded hotel FX snapshot retain a null USD equivalent.
    """
    if draft.status != "confirmed" or draft.confirmed_at is None:
        return 0
    candidates = _published_base_rates(draft)
    if not candidates:
        return 0

    config = (
        db.query(HotelConfiguration)
        .filter(HotelConfiguration.id == draft.hotel_id)
        .one_or_none()
    )
    if config is None:
        return 0
    currency = str(config.default_currency or "ARS").strip().upper()
    if len(currency) != 3:
        return 0
    captured_at = _utc(now or draft.confirmed_at or datetime.now(UTC))
    assert captured_at is not None

    existing_dates = {
        row[0]
        for row in db.query(PublishedRateHistory.rate_date)
        .filter(
            PublishedRateHistory.hotel_id == draft.hotel_id,
            PublishedRateHistory.source_draft_id == draft.id,
        )
        .all()
    }
    fx_snapshot = (
        get_fresh_ars_per_usd_snapshot(
            db, hotel_id=draft.hotel_id, config=config, now=captured_at
        )
        if currency == "ARS"
        else None
    )
    fx_rate = _decimal(fx_snapshot.applied_rate) if fx_snapshot is not None else None
    added = 0
    for rate_date, amount, rate_source in candidates:
        if rate_date in existing_dates:
            continue
        comparable_key = _comparable_season_key(
            db,
            hotel_id=draft.hotel_id,
            category_id=draft.category_id,
            rate_date=rate_date,
        )
        usd_amount: Decimal | None = None
        if currency == "USD":
            usd_amount = amount.quantize(Decimal("0.0001"))
        elif currency == "ARS" and fx_rate is not None:
            usd_amount = (amount / fx_rate).quantize(Decimal("0.0001"))
        db.add(
            PublishedRateHistory(
                hotel_id=draft.hotel_id,
                category_id=draft.category_id,
                source_draft_id=draft.id,
                rate_date=rate_date,
                comparable_season_key=comparable_key,
                published_amount=amount.quantize(Decimal("0.01")),
                currency_code=currency,
                usd_amount=usd_amount,
                fx_snapshot_id=fx_snapshot.id if fx_snapshot is not None else None,
                fx_market=fx_snapshot.rate_type if fx_snapshot is not None else None,
                fx_side=fx_snapshot.selected_side if fx_snapshot is not None else None,
                ars_per_usd=fx_rate,
                rate_source=rate_source,
                captured_at=captured_at,
            )
        )
        added += 1
    if added:
        db.flush()
    return added
