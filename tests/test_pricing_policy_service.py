from __future__ import annotations

import json
from datetime import date

from app.models.commercial import FxPolicy, RatePlan, RatePlanPrice, SellableProduct, TaxPolicy, TaxRule
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTACommissionRule, OTACurrencyRate, OTAProvider
from app.models.room import RoomCategory
from app.services.pricing_policy_service import quote_rate_plan_stay


def _seed_pricing_foundation(db):
    hotel = HotelConfiguration(id=51, hotel_name="Hotel Pricing", subscription_active=True)
    category = RoomCategory(
        hotel_id=51,
        name="Doble compartida",
        code="DBL_SHR",
        base_price_per_night=100.0,
        max_occupancy=2,
        description="Habitacion doble con bano compartido",
    )
    db.add_all([hotel, category])
    db.flush()

    product = SellableProduct(
        hotel_id=51,
        primary_room_category_id=category.id,
        code="DBL_SHR",
        name="Doble bano compartido",
        min_occupancy=1,
        max_occupancy=2,
        bathroom_type="shared",
    )
    db.add(product)
    db.flush()

    rate_plan = RatePlan(
        hotel_id=51,
        sellable_product_id=product.id,
        code="FLEX",
        name="Flexible",
        currency_code="ARS",
        default_commission_pct=15.0,
    )
    db.add(rate_plan)
    db.flush()

    db.add_all(
        [
            RatePlanPrice(
                hotel_id=51,
                rate_plan_id=rate_plan.id,
                sales_channel_code="booking",
                occupancy=2,
                currency_code="ARS",
                base_amount=100.0,
                tax_inclusive=False,
            ),
            RatePlanPrice(
                hotel_id=51,
                rate_plan_id=rate_plan.id,
                sales_channel_code="expedia",
                occupancy=2,
                currency_code="USD",
                base_amount=100.0,
                tax_inclusive=False,
            ),
        ]
    )

    tax_policy = TaxPolicy(
        hotel_id=51,
        code="DEFAULT",
        name="Default tax policy",
        taxes_included=False,
        apply_vat_by_default=False,
        vat_rate=21.0,
        foreign_guest_tax_exempt=True,
    )
    db.add(tax_policy)
    db.flush()

    db.add_all(
        [
            TaxRule(
                hotel_id=51,
                tax_policy_id=tax_policy.id,
                channel_code="booking",
                guest_scope="local",
                tax_code="VAT",
                tax_name="IVA",
                tax_type="percentage",
                amount=21.0,
                priority=10,
            ),
            TaxRule(
                hotel_id=51,
                tax_policy_id=tax_policy.id,
                channel_code="booking",
                guest_scope="local",
                tax_code="FEE_BOOKING",
                tax_name="Fee operativo",
                tax_type="fixed",
                amount=5.0,
                priority=20,
                applies_when_json=json.dumps({"per_night": True}),
            ),
        ]
    )

    booking_provider = OTAProvider(code="booking", name="Booking.com", auth_type="api_key", security_model="shared_secret")
    expedia_provider = OTAProvider(code="expedia", name="Expedia", auth_type="api_key", security_model="shared_secret")
    db.add_all([booking_provider, expedia_provider])
    db.flush()

    db.add_all(
        [
            OTACommissionRule(
                hotel_id=51,
                provider_id=booking_provider.id,
                rate_plan_id=rate_plan.id,
                commission_pct=15.0,
                payout_model="agency",
            ),
            OTACommissionRule(
                hotel_id=51,
                provider_id=expedia_provider.id,
                rate_plan_id=rate_plan.id,
                commission_pct=18.0,
                payout_model="agency",
            ),
        ]
    )

    fx_policy = FxPolicy(
        hotel_id=51,
        code="OFFICIAL_SELL",
        name="Official sell",
        base_currency="ARS",
        preferred_source="official",
        preferred_side="sell",
        spread_pct=5.0,
    )
    db.add(fx_policy)
    db.flush()

    db.add(
        OTACurrencyRate(
            hotel_id=51,
            provider_id=expedia_provider.id,
            base_currency="USD",
            quote_currency="ARS",
            rate=1000.0,
            source="manual",
        )
    )
    db.flush()
    return rate_plan, tax_policy, fx_policy


def test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(db):
    rate_plan, tax_policy, _ = _seed_pricing_foundation(db)

    quote = quote_rate_plan_stay(
        db,
        hotel_id=51,
        rate_plan_id=rate_plan.id,
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 3),
        occupancy=2,
        channel_code="booking",
        provider_code="booking",
        guest_scope="local",
        tax_policy_id=tax_policy.id,
    )

    assert quote.nights == 2
    assert quote.base_currency == "ARS"
    assert quote.output_currency == "ARS"
    assert quote.subtotal_amount == 200.0
    assert quote.tax_amount == 42.0
    assert quote.fee_amount == 10.0
    assert quote.gross_total == 252.0
    assert quote.commission_amount == 37.8
    assert quote.net_amount == 214.2


def test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(db):
    rate_plan, tax_policy, _ = _seed_pricing_foundation(db)

    quote = quote_rate_plan_stay(
        db,
        hotel_id=51,
        rate_plan_id=rate_plan.id,
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 3),
        occupancy=2,
        channel_code="booking",
        provider_code="booking",
        guest_scope="foreign",
        tax_policy_id=tax_policy.id,
    )

    assert quote.tax_amount == 0.0
    assert quote.fee_amount == 0.0
    assert quote.gross_total == 200.0
    assert quote.commission_amount == 30.0
    assert quote.net_amount == 170.0


def test_quote_rate_plan_converts_currency_with_fx_policy_spread(db):
    rate_plan, tax_policy, fx_policy = _seed_pricing_foundation(db)

    quote = quote_rate_plan_stay(
        db,
        hotel_id=51,
        rate_plan_id=rate_plan.id,
        check_in=date(2026, 11, 1),
        check_out=date(2026, 11, 2),
        occupancy=2,
        channel_code="expedia",
        provider_code="expedia",
        guest_scope="foreign",
        tax_policy_id=tax_policy.id,
        target_currency="ARS",
        fx_policy_id=fx_policy.id,
    )

    assert quote.base_currency == "USD"
    assert quote.output_currency == "ARS"
    assert quote.fx_rate_snapshot == 1050.0
    assert quote.gross_total == 105000.0
    assert quote.commission_amount == 18900.0
    assert quote.net_amount == 86100.0
