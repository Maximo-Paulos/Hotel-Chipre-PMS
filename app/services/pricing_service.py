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

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.daily_rate import DailyRate, PricePeriod
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

    return 0.0


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
        return {"total": 0.0, "nights": 0, "breakdown": []}

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
