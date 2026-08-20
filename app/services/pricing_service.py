"""
V72 §8.5 — Pricing service.

Priority for a given (hotel, category, date):
  1. DailyRate explicit row            — highest specificity
  2. PricePeriod (highest priority)    — season / bulk definition
  3. CategoryPricing.price_*           — flat fallback per payment method

For per-method prices on a DailyRate row:
  explicit override column > DailyRate.price > period / category fallback
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.daily_rate import DailyRate, PricePeriod
from app.models.hotel_config import HotelConfiguration
from app.models.commercial import RatePlan, RatePlanPrice, TaxPolicy, TaxRule
from app.models.pricing import CategoryPricing
from app.models.room import RoomCategory

# Payment method column names on DailyRate / CategoryPricing
_METHOD_COLS: dict[str, str] = {
    "cash": "price_cash",
    "transfer": "price_transfer",
    "mercadopago": "price_mercadopago",
    "paypal": "price_paypal",
    "credit_card": "price_credit_card",
}


def get_price_for_date(
    db: Session,
    hotel_id: int,
    category_id: int,
    target_date: date,
    payment_method: Optional[str] = None,
) -> float:
    """Return the price for a single night.

    Priority: DailyRate explicit > PricePeriod (highest priority first)
              > CategoryPricing base price.

    If *payment_method* is supplied the per-method column is checked first on
    the winning DailyRate row; if it is NULL the row's base ``price`` is used.
    PricePeriod and CategoryPricing always use their single price / method
    column (no per-method override on PricePeriod by design).
    """
    # 1. Explicit DailyRate
    daily: Optional[DailyRate] = (
        db.query(DailyRate)
        .filter(
            DailyRate.hotel_id == hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date == target_date,
        )
        .first()
    )
    if daily is not None:
        if payment_method:
            col = _METHOD_COLS.get(payment_method)
            if col:
                override = getattr(daily, col, None)
                if override is not None:
                    return float(override)
        return float(daily.price)

    # 2. Best active PricePeriod covering this date
    period: Optional[PricePeriod] = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
            PricePeriod.is_active == True,
            PricePeriod.start_date <= target_date,
            PricePeriod.end_date >= target_date,
        )
        .order_by(PricePeriod.priority.desc(), PricePeriod.id.desc())
        .first()
    )
    if period is not None:
        return float(period.price_per_night)

    # 3. CategoryPricing flat fallback
    cat_pricing: Optional[CategoryPricing] = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if cat_pricing is not None:
        if payment_method:
            col = _METHOD_COLS.get(payment_method)
            if col:
                override = getattr(cat_pricing, col, None)
                if override is not None:
                    return float(override)
        # CategoryPricing has no single base_price; use cash as best guess
        for col in ("price_cash", "price_transfer", "price_mercadopago",
                    "price_paypal", "price_credit_card"):
            val = getattr(cat_pricing, col, None)
            if val is not None:
                return float(val)

    # 4. RoomCategory.base_price_per_night — final fallback so the resolver is the
    #    single source of truth shared by the rate calendar, reservation pricing and
    #    the rooms inventory view (never silently returns 0 when a base price exists).
    category: Optional[RoomCategory] = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if category is not None and category.base_price_per_night is not None:
        return float(category.base_price_per_night)

    return 0.0


def resolve_rate_calendar(
    db: Session,
    hotel_id: int,
    category_id: int,
    from_date: date,
    to_date: date,
    payment_method: Optional[str] = None,
) -> list[dict]:
    """Resolve the effective rate for every date in ``[from_date, to_date]`` using
    a fixed number of queries (no per-date round-trips).

    Returns one dict per date with the resolved base ``price``, the per-method
    override columns (when the winning row carries them) and the ``source`` that
    won: ``daily_rate`` | ``price_period`` | ``category_pricing`` | ``category_base``
    | ``none``. ``daily_rate_id`` is set only when an explicit DailyRate row exists.

    If ``payment_method`` is supplied, ``price`` is the effective price for that
    method and follows exactly the same override/fallback contract as
    :func:`get_price_for_date`. The per-method columns remain in the response so
    the calendar can render all configured prices at once.
    """
    # Load everything once.
    daily_rows: dict[date, DailyRate] = {
        r.date: r
        for r in db.query(DailyRate).filter(
            DailyRate.hotel_id == hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date >= from_date,
            DailyRate.date <= to_date,
        )
    }
    periods: list[PricePeriod] = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
            PricePeriod.is_active == True,
            PricePeriod.start_date <= to_date,
            PricePeriod.end_date >= from_date,
        )
        .order_by(PricePeriod.priority.desc(), PricePeriod.id.desc())
        .all()
    )
    cat_pricing: Optional[CategoryPricing] = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    category: Optional[RoomCategory] = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    base_price = (
        float(category.base_price_per_night)
        if category is not None and category.base_price_per_night is not None
        else None
    )

    cat_pricing_value: Optional[float] = None
    if cat_pricing is not None:
        method_column = _METHOD_COLS.get(payment_method) if payment_method else None
        columns = ((method_column,) if method_column else ()) + (
            "price_cash", "price_transfer", "price_mercadopago", "price_paypal", "price_credit_card"
        )
        for col in columns:
            val = getattr(cat_pricing, col, None)
            if val is not None:
                cat_pricing_value = float(val)
                break

    def _period_for(target: date) -> Optional[PricePeriod]:
        # periods is ordered by priority desc, id desc → first cover wins
        for p in periods:
            if p.start_date <= target <= p.end_date:
                return p
        return None

    result: list[dict] = []
    current = from_date
    while current <= to_date:
        row = daily_rows.get(current)
        if row is not None:
            price = float(row.price)
            if payment_method:
                column = _METHOD_COLS.get(payment_method)
                override = getattr(row, column, None) if column else None
                if override is not None:
                    price = float(override)
            result.append({
                "date": current,
                "price": price,
                "price_cash": row.price_cash,
                "price_transfer": row.price_transfer,
                "price_mercadopago": row.price_mercadopago,
                "price_paypal": row.price_paypal,
                "price_credit_card": row.price_credit_card,
                "source": "daily_rate",
                "daily_rate_id": row.id,
            })
            current += timedelta(days=1)
            continue

        period = _period_for(current)
        if period is not None:
            price = float(period.price_per_night)
            source = "price_period"
        elif cat_pricing_value is not None:
            price = cat_pricing_value
            source = "category_pricing"
        elif base_price is not None:
            price = base_price
            source = "category_base"
        else:
            price = 0.0
            source = "none"

        result.append({
            "date": current,
            "price": round(price, 2),
            "price_cash": None,
            "price_transfer": None,
            "price_mercadopago": None,
            "price_paypal": None,
            "price_credit_card": None,
            "source": source,
            "daily_rate_id": None,
        })
        current += timedelta(days=1)

    return result


def get_prices_for_range(
    db: Session,
    hotel_id: int,
    category_id: int,
    check_in: date,
    check_out: date,
    payment_method: Optional[str] = None,
) -> dict:
    """Return pricing breakdown for a stay.

    *check_in* inclusive, *check_out* exclusive (standard hotel convention —
    check_out night is NOT charged).

    Returns::

        {
            "total": float,
            "nights": int,
            "breakdown": [{"date": date, "price": float}, ...],
        }
    """
    if check_out <= check_in:
        raise ValueError("check_out must be after check_in")

    breakdown = []
    current = check_in
    while current < check_out:
        price = get_price_for_date(
            db, hotel_id, category_id, current, payment_method
        )
        breakdown.append({"date": current, "price": price})
        current += timedelta(days=1)

    total = round(sum(row["price"] for row in breakdown), 2)
    return {
        "total": total,
        "nights": len(breakdown),
        "breakdown": breakdown,
    }


def apply_price_period(
    db: Session,
    hotel_id: int,
    category_id: int,
    period_id: int,
) -> int:
    """Materialise a PricePeriod into explicit DailyRate rows (upsert by date).

    Returns the number of rows created or updated.
    """
    from datetime import datetime, timezone  # local import avoids circularity risk

    period = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.id == period_id,
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
        )
        .first()
    )
    if period is None:
        raise ValueError(f"PricePeriod {period_id} not found for hotel={hotel_id} category={category_id}")

    count = 0
    current = period.start_date
    while current <= period.end_date:
        existing = (
            db.query(DailyRate)
            .filter(
                DailyRate.hotel_id == hotel_id,
                DailyRate.category_id == category_id,
                DailyRate.date == current,
            )
            .first()
        )
        if existing is None:
            db.add(
                DailyRate(
                    hotel_id=hotel_id,
                    category_id=category_id,
                    date=current,
                    price=period.price_per_night,
                )
            )
        else:
            existing.price = period.price_per_night
            existing.updated_at = datetime.now(timezone.utc)
        count += 1
        current += timedelta(days=1)

    db.flush()
    return count


def build_pricing_revision(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    check_in: date,
    check_out: date,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int | None = None,
) -> str:
    """Return a deterministic revision for every input that affects a quote.

    This is deliberately derived from PostgreSQL-owned pricing rows instead of
    a frontend timestamp.  A quote can therefore be rejected after a rate,
    tax policy, deposit policy, or relevant product rule changes.
    """

    category = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if category is None:
        raise ValueError("Category not found for hotel")
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()

    def _stamp(value):
        if value is None:
            return None
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    source: dict[str, object] = {
        "inputs": {
            "hotel_id": hotel_id,
            "category_id": category_id,
            "check_in": check_in.isoformat(),
            "check_out": check_out.isoformat(),
            "sellable_product_id": sellable_product_id,
            "rate_plan_id": rate_plan_id,
            "tax_policy_id": tax_policy_id,
            "pricing_channel_code": pricing_channel_code,
            "pricing_payment_method": pricing_payment_method,
            "guest_scope": guest_scope,
            "target_currency": target_currency,
            "occupancy": occupancy,
        },
        "hotel_policy": {
            "updated_at": _stamp(getattr(config, "updated_at", None)),
            "deposit_percentage": getattr(config, "deposit_percentage", None),
            "default_currency": getattr(config, "default_currency", None),
        },
        "category": {
            "id": category.id,
            "base_price_per_night": category.base_price_per_night,
            "max_occupancy": category.max_occupancy,
            "name": category.name,
            "code": category.code,
        },
    }

    daily_rows = (
        db.query(DailyRate)
        .filter(
            DailyRate.hotel_id == hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date >= check_in,
            DailyRate.date < check_out,
        )
        .order_by(DailyRate.date.asc(), DailyRate.id.asc())
        .all()
    )
    source["daily_rates"] = [
        {
            "id": row.id,
            "date": _stamp(row.date),
            "price": row.price,
            "price_cash": row.price_cash,
            "price_transfer": row.price_transfer,
            "price_mercadopago": row.price_mercadopago,
            "price_paypal": row.price_paypal,
            "price_credit_card": row.price_credit_card,
            "updated_at": _stamp(row.updated_at),
        }
        for row in daily_rows
    ]

    periods = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.hotel_id == hotel_id,
            PricePeriod.category_id == category_id,
            PricePeriod.deleted_at.is_(None),
            PricePeriod.is_active.is_(True),
            PricePeriod.start_date < check_out,
            PricePeriod.end_date >= check_in,
        )
        .order_by(PricePeriod.priority.desc(), PricePeriod.id.desc())
        .all()
    )
    source["price_periods"] = [
        {
            "id": row.id,
            "name": row.name,
            "start_date": _stamp(row.start_date),
            "end_date": _stamp(row.end_date),
            "price_per_night": row.price_per_night,
            "priority": row.priority,
            "is_active": row.is_active,
            "updated_at": _stamp(row.created_at),
        }
        for row in periods
    ]

    category_pricing = (
        db.query(CategoryPricing)
        .join(RoomCategory, RoomCategory.id == CategoryPricing.category_id)
        .filter(CategoryPricing.category_id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    source["category_pricing"] = {
        column.name: getattr(category_pricing, column.name)
        for column in CategoryPricing.__table__.columns
    } if category_pricing is not None else None

    if rate_plan_id is not None:
        rate_plan = (
            db.query(RatePlan)
            .filter(RatePlan.id == rate_plan_id, RatePlan.hotel_id == hotel_id)
            .first()
        )
        source["rate_plan"] = {
            column.name: getattr(rate_plan, column.name)
            for column in RatePlan.__table__.columns
        } if rate_plan is not None else None
        rate_plan_prices = (
            db.query(RatePlanPrice)
            .filter(
                RatePlanPrice.hotel_id == hotel_id,
                RatePlanPrice.rate_plan_id == rate_plan_id,
                RatePlanPrice.is_active.is_(True),
                or_(RatePlanPrice.valid_from.is_(None), RatePlanPrice.valid_from < check_out),
                or_(RatePlanPrice.valid_to.is_(None), RatePlanPrice.valid_to >= check_in),
            )
            .order_by(RatePlanPrice.id.asc())
            .all()
        )
        source["rate_plan_prices"] = [
            {column.name: getattr(row, column.name) for column in RatePlanPrice.__table__.columns}
            for row in rate_plan_prices
        ]

    if tax_policy_id is not None:
        tax_policy = (
            db.query(TaxPolicy)
            .filter(TaxPolicy.id == tax_policy_id, TaxPolicy.hotel_id == hotel_id)
            .first()
        )
        source["tax_policy"] = {
            column.name: getattr(tax_policy, column.name)
            for column in TaxPolicy.__table__.columns
        } if tax_policy is not None else None
        tax_rules = (
            db.query(TaxRule)
            .filter(TaxRule.hotel_id == hotel_id, TaxRule.tax_policy_id == tax_policy_id)
            .order_by(TaxRule.id.asc())
            .all()
        )
        source["tax_rules"] = [
            {column.name: getattr(row, column.name) for column in TaxRule.__table__.columns}
            for row in tax_rules
        ]

    serialized = json.dumps(source, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:32]
