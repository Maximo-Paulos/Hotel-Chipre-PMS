"""
V72 §13 — Daily Rate Management tests.

Tests cover:
  - get_price_for_date: DailyRate lookup, PricePeriod fallback, CategoryPricing fallback
  - apply_price_period: creates rows, always upserts, count returned
  - DailyRate uniqueness constraint
  - PricePeriod → correct number of DailyRate rows generated
  - Overlapping periods: second apply overwrites dates already covered
  - per-payment-method column resolution on get_price_for_date
"""
from __future__ import annotations

import pytest
from datetime import date
from sqlalchemy.exc import IntegrityError

from app.models.daily_rate import DailyRate, PricePeriod
from app.models.pricing import CategoryPricing
from app.services.pricing_service import apply_price_period, get_price_for_date


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_period(
    db,
    hotel_id: int,
    category_id: int,
    start: date,
    end: date,
    price: float,
    name: str = "Test Period",
    priority: int = 0,
) -> PricePeriod:
    period = PricePeriod(
        hotel_id=hotel_id,
        category_id=category_id,
        name=name,
        start_date=start,
        end_date=end,
        price_per_night=price,
        priority=priority,
        is_active=True,
    )
    db.add(period)
    db.flush()
    return period


# ---------------------------------------------------------------------------
# TestGetPriceForDate
# ---------------------------------------------------------------------------

class TestGetPriceForDate:
    def test_returns_daily_rate_when_exists(self, db, sample_categories):
        """Tier-1: explicit DailyRate row wins over everything else."""
        category = sample_categories[0]
        rate = DailyRate(
            hotel_id=1,
            category_id=category.id,
            date=date(2026, 9, 1),
            price=150.0,
        )
        db.add(rate)
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 9, 1)
        )
        assert price == 150.0

    def test_daily_rate_beats_price_period(self, db, sample_categories):
        """DailyRate explicit row takes priority over an active PricePeriod."""
        category = sample_categories[0]
        # PricePeriod covers the target date
        _make_period(
            db, 1, category.id,
            start=date(2026, 9, 1), end=date(2026, 9, 30),
            price=200.0,
        )
        # Explicit DailyRate for one date inside that period
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 9, 15), price=99.0,
        ))
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 9, 15)
        )
        assert price == 99.0

    def test_falls_back_to_price_period_when_no_daily_rate(self, db, sample_categories):
        """Tier-2: active PricePeriod used when no DailyRate exists."""
        category = sample_categories[1]
        _make_period(
            db, 1, category.id,
            start=date(2026, 10, 1), end=date(2026, 10, 31),
            price=175.0,
        )

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 10, 15)
        )
        assert price == 175.0

    def test_inactive_price_period_is_skipped(self, db, sample_categories):
        """An inactive PricePeriod must not be used as fallback."""
        category = sample_categories[0]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 11, 1), end=date(2026, 11, 30),
            price=300.0,
        )
        period.is_active = False
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 11, 10)
        )
        # No active period → should fall to CategoryPricing or 0
        assert price == 0.0

    def test_falls_back_to_category_pricing_when_no_period(self, db, sample_categories):
        """Tier-3: CategoryPricing used when neither DailyRate nor PricePeriod exists."""
        category = sample_categories[2]
        db.add(CategoryPricing(
            category_id=category.id,
            price_cash=250.0,
        ))
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 12, 25)
        )
        assert price == 250.0

    def test_returns_zero_when_no_pricing_at_all(self, db, sample_categories):
        """Returns 0.0 when there is absolutely no pricing information."""
        category = sample_categories[0]
        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2027, 1, 1)
        )
        assert price == 0.0

    def test_payment_method_returns_override_column(self, db, sample_categories):
        """per-method column (price_cash) wins over base price when specified."""
        category = sample_categories[0]
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 9, 5),
            price=100.0,
            price_cash=85.0,
        ))
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id,
            target_date=date(2026, 9, 5),
            payment_method="cash",
        )
        assert price == 85.0

    def test_payment_method_falls_back_to_base_price_when_no_override(
        self, db, sample_categories
    ):
        """When requested payment method column is NULL, base DailyRate price is used."""
        category = sample_categories[0]
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 9, 6),
            price=120.0,
            price_cash=None,
        ))
        db.flush()

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id,
            target_date=date(2026, 9, 6),
            payment_method="cash",
        )
        assert price == 120.0

    def test_highest_priority_period_wins(self, db, sample_categories):
        """When two PricePeriods overlap, the one with higher priority is returned."""
        category = sample_categories[1]
        _make_period(
            db, 1, category.id,
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            price=100.0, priority=0, name="Base",
        )
        _make_period(
            db, 1, category.id,
            start=date(2026, 8, 1), end=date(2026, 8, 31),
            price=180.0, priority=10, name="High-priority promo",
        )

        price = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 8, 15)
        )
        assert price == 180.0

    def test_price_period_out_of_range_not_used(self, db, sample_categories):
        """PricePeriod is NOT used for dates outside its range."""
        category = sample_categories[0]
        _make_period(
            db, 1, category.id,
            start=date(2026, 9, 1), end=date(2026, 9, 30),
            price=200.0,
        )

        price_before = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 8, 31)
        )
        price_after = get_price_for_date(
            db, hotel_id=1, category_id=category.id, target_date=date(2026, 10, 1)
        )
        assert price_before == 0.0
        assert price_after == 0.0


# ---------------------------------------------------------------------------
# TestApplyPricePeriod
# ---------------------------------------------------------------------------

class TestApplyPricePeriod:
    def test_creates_daily_rate_rows_for_each_date(self, db, sample_categories):
        """apply_price_period materialises one DailyRate per day in the period."""
        category = sample_categories[0]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 9, 1), end=date(2026, 9, 7),  # 7 nights
            price=160.0,
        )

        count = apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period.id)

        assert count == 7
        rows = (
            db.query(DailyRate)
            .filter(DailyRate.hotel_id == 1, DailyRate.category_id == category.id)
            .all()
        )
        assert len(rows) == 7
        assert all(r.price == 160.0 for r in rows)

    def test_apply_overwrites_existing_rates(self, db, sample_categories):
        """apply_price_period updates an existing DailyRate (always upsert)."""
        category = sample_categories[0]
        # Pre-existing rate for one of the dates
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 10, 3), price=999.0,
        ))
        db.flush()

        period = _make_period(
            db, 1, category.id,
            start=date(2026, 10, 1), end=date(2026, 10, 5),  # 5 days
            price=120.0,
        )
        count = apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period.id)

        assert count == 5
        row = (
            db.query(DailyRate)
            .filter(
                DailyRate.hotel_id == 1,
                DailyRate.category_id == category.id,
                DailyRate.date == date(2026, 10, 3),
            )
            .one()
        )
        assert row.price == 120.0  # overwritten

    def test_returns_correct_count_for_single_day_period(self, db, sample_categories):
        """A period where start_date == end_date creates exactly 1 row."""
        category = sample_categories[1]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 12, 31), end=date(2026, 12, 31),
            price=500.0, name="New Year's Eve",
        )

        count = apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period.id)
        assert count == 1

    def test_raises_on_missing_period(self, db, sample_categories):
        """apply_price_period raises ValueError for an unknown period_id."""
        category = sample_categories[0]
        with pytest.raises(ValueError, match="not found"):
            apply_price_period(db, hotel_id=1, category_id=category.id, period_id=99999)

    def test_period_prices_appear_in_get_price_for_date(self, db, sample_categories):
        """After apply_price_period, get_price_for_date returns the materialised price."""
        category = sample_categories[0]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 7, 1), end=date(2026, 7, 3),
            price=95.0,
        )
        apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period.id)

        # DailyRate now exists, so it should be returned at tier-1
        assert get_price_for_date(db, 1, category.id, date(2026, 7, 1)) == 95.0
        assert get_price_for_date(db, 1, category.id, date(2026, 7, 3)) == 95.0


# ---------------------------------------------------------------------------
# TestPricePeriodOverlap
# ---------------------------------------------------------------------------

class TestPricePeriodOverlap:
    def test_applying_two_overlapping_periods_overwrites_overlap(self, db, sample_categories):
        """Applying a second period to overlapping dates updates those dates."""
        category = sample_categories[0]
        period_a = _make_period(
            db, 1, category.id,
            start=date(2026, 8, 1), end=date(2026, 8, 10),
            price=100.0, name="Period A",
        )
        period_b = _make_period(
            db, 1, category.id,
            start=date(2026, 8, 6), end=date(2026, 8, 15),
            price=200.0, name="Period B",
        )

        apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period_a.id)
        apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period_b.id)

        # Dates 1–5: should still be 100 (only period A touched them)
        for day in range(1, 6):
            price = get_price_for_date(db, 1, category.id, date(2026, 8, day))
            assert price == 100.0, f"Aug {day}: expected 100, got {price}"

        # Dates 6–10: overwritten by period B → 200
        for day in range(6, 11):
            price = get_price_for_date(db, 1, category.id, date(2026, 8, day))
            assert price == 200.0, f"Aug {day}: expected 200, got {price}"

        # Dates 11–15: only period B → 200
        for day in range(11, 16):
            price = get_price_for_date(db, 1, category.id, date(2026, 8, day))
            assert price == 200.0, f"Aug {day}: expected 200, got {price}"

    def test_total_unique_rows_after_overlapping_apply(self, db, sample_categories):
        """No duplicate rows after two overlapping period applies (upsert semantics)."""
        category = sample_categories[1]
        period_a = _make_period(
            db, 1, category.id,
            start=date(2026, 11, 1), end=date(2026, 11, 10),
            price=80.0,
        )
        period_b = _make_period(
            db, 1, category.id,
            start=date(2026, 11, 8), end=date(2026, 11, 15),
            price=90.0,
        )
        apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period_a.id)
        apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period_b.id)

        rows = (
            db.query(DailyRate)
            .filter(DailyRate.hotel_id == 1, DailyRate.category_id == category.id)
            .all()
        )
        # 10 days (period A) + 8 new days (period B days 11-15, not duplicated)
        # = 15 unique rows: Nov 1..15
        assert len(rows) == 15


# ---------------------------------------------------------------------------
# TestDailyRateModelConstraints
# ---------------------------------------------------------------------------

class TestDailyRateModelConstraints:
    def test_unique_constraint_same_hotel_category_date(self, db, sample_categories):
        """Two DailyRates for the same hotel+category+date raise IntegrityError."""
        category = sample_categories[0]
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 9, 20), price=100.0,
        ))
        db.flush()

        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 9, 20), price=200.0,
        ))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_same_date_different_categories_is_allowed(self, db, sample_categories):
        """Same date but different categories should NOT conflict."""
        cat_a, cat_b = sample_categories[0], sample_categories[1]
        db.add(DailyRate(hotel_id=1, category_id=cat_a.id, date=date(2026, 9, 21), price=100.0))
        db.add(DailyRate(hotel_id=1, category_id=cat_b.id, date=date(2026, 9, 21), price=120.0))
        db.flush()  # should not raise

        rows = (
            db.query(DailyRate)
            .filter(DailyRate.date == date(2026, 9, 21), DailyRate.hotel_id == 1)
            .all()
        )
        assert len(rows) == 2

    def test_same_date_different_hotels_is_allowed(self, db, sample_categories, sample_categories_hotel2):
        """Same category code but different hotels: no constraint violation."""
        cat1 = sample_categories[0]
        cat2 = sample_categories_hotel2[0]
        db.add(DailyRate(hotel_id=1, category_id=cat1.id, date=date(2026, 9, 22), price=100.0))
        db.add(DailyRate(hotel_id=2, category_id=cat2.id, date=date(2026, 9, 22), price=80.0))
        db.flush()

    def test_price_is_stored_and_retrieved_correctly(self, db, sample_categories):
        """DailyRate stores and retrieves price as float without data loss."""
        category = sample_categories[2]
        db.add(DailyRate(
            hotel_id=1, category_id=category.id,
            date=date(2026, 6, 15), price=333.33,
        ))
        db.flush()

        row = (
            db.query(DailyRate)
            .filter(DailyRate.date == date(2026, 6, 15), DailyRate.category_id == category.id)
            .one()
        )
        assert abs(row.price - 333.33) < 0.01


# ---------------------------------------------------------------------------
# TestPricePeriodModel
# ---------------------------------------------------------------------------

class TestPricePeriodModel:
    def test_create_price_period(self, db, sample_categories):
        """PricePeriod can be created and queried."""
        category = sample_categories[0]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 12, 1), end=date(2026, 12, 31),
            price=450.0, name="Temporada Alta Dic 2026",
        )
        assert period.id is not None
        assert period.price_per_night == 450.0
        assert period.is_active is True

    def test_price_period_generates_correct_row_count(self, db, sample_categories):
        """A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates."""
        category = sample_categories[1]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 12, 1), end=date(2026, 12, 30),
            price=220.0,
        )

        count = apply_price_period(db, hotel_id=1, category_id=category.id, period_id=period.id)
        assert count == 30

    def test_inactive_period_not_materialised_automatically(self, db, sample_categories):
        """Creating an inactive PricePeriod does not create DailyRate rows
        (rows only appear via explicit apply_price_period call)."""
        category = sample_categories[0]
        period = _make_period(
            db, 1, category.id,
            start=date(2026, 5, 1), end=date(2026, 5, 31),
            price=180.0,
        )
        period.is_active = False
        db.flush()

        rows = (
            db.query(DailyRate)
            .filter(DailyRate.hotel_id == 1, DailyRate.category_id == category.id)
            .count()
        )
        # No apply was called — no rows
        assert rows == 0
