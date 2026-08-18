from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.models.commercial import TaxPolicy, TaxRule
from app.models.daily_rate import DailyRate
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTACurrencyRate, OTAProvider
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.room import RoomCategory
from app.schemas.promotion import PromotionConditions, PromotionCreate
from app.services.promotion_pricing_service import CanonicalPricingError, compute_canonical_stay_pricing
from app.services.promotion_service import create_promotion


def _seed_hotel(db, hotel_id: int, *, currency: str = "ARS") -> RoomCategory:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True, default_currency=currency))
    category = RoomCategory(
        hotel_id=hotel_id, name="Standard", code=f"STD{hotel_id}",
        base_price_per_night=Decimal("100.00"), max_occupancy=2,
    )
    db.add(category)
    db.flush()
    return category


def _seed_daily_rates(db, hotel_id: int, category_id: int, start: date, nights: int, price: float) -> None:
    from datetime import timedelta

    for offset in range(nights):
        db.add(DailyRate(hotel_id=hotel_id, category_id=category_id, date=start + timedelta(days=offset), price=price))
    db.flush()


def test_canonical_pricing_base_only_no_promotions(db):
    category = _seed_hotel(db, 81)
    _seed_daily_rates(db, 81, category.id, date(2026, 5, 1), 2, 100.0)

    result = compute_canonical_stay_pricing(
        db, hotel_id=81, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 3),
    )
    assert result.nights == 2
    assert result.subtotal_amount == Decimal("200.00")
    assert result.booking_total == Decimal("200.00")
    assert result.promotions_applied == []
    assert result.tax_amount == Decimal("0.00")


def test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(db):
    category = _seed_hotel(db, 82)
    _seed_daily_rates(db, 82, category.id, date(2026, 5, 1), 2, 100.0)
    create_promotion(
        db, hotel_id=82,
        payload=PromotionCreate(
            code="FREE_NIGHT", name="Free night", benefit_type="fixed", benefit_value=Decimal("500"),
            conditions=PromotionConditions(category_id=category.id),
        ),
        created_by_user_id=None,
    )

    result = compute_canonical_stay_pricing(
        db, hotel_id=82, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 3),
    )
    # Both nights clamped to 0 by the oversized fixed discount.
    assert result.subtotal_amount == Decimal("0.00")
    assert result.booking_total == Decimal("0.00")
    assert len(result.promotions_applied) == 2


def test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(db):
    category = _seed_hotel(db, 83)
    _seed_daily_rates(db, 83, category.id, date(2026, 5, 1), 3, 100.0)
    create_promotion(
        db, hotel_id=83,
        payload=PromotionCreate(
            code="3RD_NIGHT_OFF", name="3rd night 50% off", benefit_type="percentage", benefit_value=Decimal("50"),
            scope="from_night_n", from_night_number=3,
        ),
        created_by_user_id=None,
    )

    result = compute_canonical_stay_pricing(
        db, hotel_id=83, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 4),
    )
    # Nights 1-2 untouched (100 each), night 3 halved (50) -> 250 total.
    assert result.subtotal_amount == Decimal("250.00")
    assert len(result.promotions_applied) == 1


def test_canonical_pricing_applies_tax_policy(db):
    category = _seed_hotel(db, 84)
    _seed_daily_rates(db, 84, category.id, date(2026, 5, 1), 2, 100.0)
    tax_policy = TaxPolicy(hotel_id=84, code="DEFAULT", name="Default", apply_vat_by_default=True, vat_rate=21.0)
    db.add(tax_policy)
    db.flush()

    result = compute_canonical_stay_pricing(
        db, hotel_id=84, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 3),
        tax_policy_id=tax_policy.id,
    )
    assert result.subtotal_amount == Decimal("200.00")
    assert result.tax_amount == Decimal("42.00")
    assert result.booking_total == Decimal("242.00")


def test_canonical_pricing_converts_currency_with_fx_snapshot(db):
    category = _seed_hotel(db, 85, currency="USD")
    _seed_daily_rates(db, 85, category.id, date(2026, 5, 1), 1, 100.0)
    db.add(OTACurrencyRate(hotel_id=85, base_currency="USD", quote_currency="ARS", rate=1000.0, source="manual"))
    db.flush()

    result = compute_canonical_stay_pricing(
        db, hotel_id=85, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 2),
        target_currency="ARS",
    )
    assert result.output_currency == "ARS"
    assert result.fx_rate_snapshot == Decimal("1000")
    assert result.booking_total == Decimal("100000.00")


def test_canonical_pricing_missing_fx_rate_raises(db):
    category = _seed_hotel(db, 86, currency="USD")
    _seed_daily_rates(db, 86, category.id, date(2026, 5, 1), 1, 100.0)

    with pytest.raises(CanonicalPricingError):
        compute_canonical_stay_pricing(
            db, hotel_id=86, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 2),
            target_currency="ARS",
        )


def test_canonical_pricing_payment_adjustment_is_informational_only(db):
    category = _seed_hotel(db, 87)
    _seed_daily_rates(db, 87, category.id, date(2026, 5, 1), 1, 100.0)
    db.add(PaymentSurcharge(hotel_id=87, payment_method="credit_card", surcharge_type=PaymentSurchargeTypeEnum.PERCENTAGE, amount=Decimal("10")))
    db.flush()

    result = compute_canonical_stay_pricing(
        db, hotel_id=87, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 2),
        payment_method="credit_card",
    )
    # booking_total (what would be persisted) is untouched by the surcharge --
    # it's collected at payment time, not baked into the quoted/booked total.
    assert result.booking_total == Decimal("100.00")
    assert result.payment_adjustment["surcharge_amount"] == "10.00"
    assert result.final_total_with_payment_adjustment == Decimal("110.00")


def test_canonical_pricing_manual_override_skips_promotions_entirely(db):
    category = _seed_hotel(db, 88)
    _seed_daily_rates(db, 88, category.id, date(2026, 5, 1), 2, 100.0)
    create_promotion(
        db, hotel_id=88,
        payload=PromotionCreate(
            code="WOULD_APPLY", name="Would apply", benefit_type="fixed", benefit_value=Decimal("50"),
        ),
        created_by_user_id=None,
    )

    result = compute_canonical_stay_pricing(
        db, hotel_id=88, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 3),
        manual_override_total=Decimal("999.00"),
    )
    assert result.pricing_source == "manual_override"
    assert result.booking_total == Decimal("999.00")
    assert result.promotions_applied == []


def test_canonical_pricing_rounds_to_two_decimals(db):
    category = _seed_hotel(db, 89)
    _seed_daily_rates(db, 89, category.id, date(2026, 5, 1), 3, 33.335)
    create_promotion(
        db, hotel_id=89,
        payload=PromotionCreate(
            code="ODD_PCT", name="Odd percent", benefit_type="percentage", benefit_value=Decimal("10"),
        ),
        created_by_user_id=None,
    )
    result = compute_canonical_stay_pricing(
        db, hotel_id=89, category_id=category.id, check_in=date(2026, 5, 1), check_out=date(2026, 5, 4),
    )
    # Every stored amount must be quantized to cents.
    assert result.subtotal_amount == result.subtotal_amount.quantize(Decimal("0.01"))
    for night in result.per_night:
        assert Decimal(night["post_promotion_amount"]) == Decimal(night["post_promotion_amount"]).quantize(Decimal("0.01"))
