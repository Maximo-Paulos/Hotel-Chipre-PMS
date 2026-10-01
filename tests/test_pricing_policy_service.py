from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest

from app.models.commercial import FxPolicy, RatePlan, RatePlanPrice, SellableProduct, TaxPolicy, TaxRule
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTACommissionRule, OTACurrencyRate, OTAProvider
from app.models.room import RoomCategory
from app.services import pricing_policy_service
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


def test_quote_rate_plan_converts_currency_with_fx_policy_spread(db, monkeypatch):
    rate_plan, tax_policy, fx_policy = _seed_pricing_foundation(db)

    def conversion_quote(currency, market="oficial"):
        return {
            "moneda": currency,
            "casa": "oficial",
            "compra": 1000.0,
            "venta": 1000.0,
            "fechaActualizacion": datetime.now(timezone.utc).isoformat(),
        }

    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", conversion_quote)

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
    assert quote.fx_quote_details["usd_market"] == "oficial"
    assert quote.fx_quote_details["source_side"] == "venta"
    assert quote.fx_quote_details["target_side"] is None


def test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(db):
    rate_plan, _tax_policy, _ = _seed_pricing_foundation(db)
    rate_plan.min_nights_default = 2
    rate_plan.max_nights_default = 2
    db.flush()

    with pytest.raises(ValueError, match="at least 2 nights"):
        quote_rate_plan_stay(
            db,
            hotel_id=51,
            rate_plan_id=rate_plan.id,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 2),
            occupancy=2,
            channel_code="booking",
        )

    with pytest.raises(ValueError, match="at most 2 nights"):
        quote_rate_plan_stay(
            db,
            hotel_id=51,
            rate_plan_id=rate_plan.id,
            check_in=date(2026, 10, 1),
            check_out=date(2026, 10, 4),
            occupancy=2,
            channel_code="booking",
        )

    db.add(
        RatePlanPrice(
            hotel_id=51,
            rate_plan_id=rate_plan.id,
            sales_channel_code="booking",
            occupancy=2,
            currency_code="ARS",
            base_amount=125.0,
            valid_from=date(2026, 10, 1),
            valid_to=date(2026, 10, 2),
        )
    )
    db.flush()
    quote = quote_rate_plan_stay(
        db,
        hotel_id=51,
        rate_plan_id=rate_plan.id,
        check_in=date(2026, 10, 1),
        check_out=date(2026, 10, 3),
        occupancy=2,
        channel_code="booking",
    )
    assert quote.nights == 2
    assert quote.subtotal_amount == 250.0


_FX_TEST_RATES = {
    "USD": {"compra": 1000.0, "venta": 1100.0},
    "EUR": {"compra": 1200.0, "venta": 1300.0},
    "BRL": {"compra": 200.0, "venta": 220.0},
    "CLP": {"compra": 1.0, "venta": 1.2},
    "UYU": {"compra": 25.0, "venta": 27.0},
}
_SUPPORTED_CURRENCIES = ("ARS", "USD", "EUR", "BRL", "CLP", "UYU")
_DIRECTED_FX_PAIRS = [
    (source, target)
    for source in _SUPPORTED_CURRENCIES
    for target in _SUPPORTED_CURRENCIES
    if source != target
]


@pytest.mark.parametrize("from_currency,to_currency", _DIRECTED_FX_PAIRS)
def test_all_supported_fx_pairs_use_directional_quotes_via_ars(
    db, monkeypatch, from_currency, to_currency
):
    _seed_pricing_foundation(db)
    now = datetime.now(timezone.utc).isoformat()

    def conversion_quote(currency, market="oficial"):
        values = _FX_TEST_RATES[currency]
        return {
            "moneda": currency,
            "casa": market if currency == "USD" else "oficial",
            **values,
            "fechaActualizacion": now,
        }

    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", conversion_quote)
    amount, effective_rate, details = pricing_policy_service._convert_amount(
        db,
        hotel_id=51,
        amount=100.0,
        from_currency=from_currency,
        to_currency=to_currency,
        fx_policy_id=None,
        provider_code=None,
    )

    source_ars = 1.0 if from_currency == "ARS" else _FX_TEST_RATES[from_currency]["venta"]
    target_ars = 1.0 if to_currency == "ARS" else _FX_TEST_RATES[to_currency]["compra"]
    expected_rate = source_ars / target_ars * 1.05
    assert effective_rate == pytest.approx(expected_rate, rel=1e-6)
    assert amount == pytest.approx(round(100.0 * expected_rate, 2))
    assert details["path"] == "via_ars"
    assert details["configured_usd_market"] == "oficial"
    assert details["usd_market"] == ("oficial" if "USD" in {from_currency, to_currency} else None)
    assert details["source_side"] == (None if from_currency == "ARS" else "venta")
    assert details["target_side"] == (None if to_currency == "ARS" else "compra")
    if from_currency == "USD":
        assert details["source_quote"]["usd_market"] == "oficial"
    elif from_currency != "ARS":
        assert details["source_quote"]["direct_currency_market"] == "oficial"
    if to_currency == "USD":
        assert details["target_quote"]["usd_market"] == "oficial"
    elif to_currency != "ARS":
        assert details["target_quote"]["direct_currency_market"] == "oficial"


def test_global_blue_market_dominates_fx_policy_source_and_side(db, monkeypatch):
    _seed_pricing_foundation(db)
    config = db.get(HotelConfiguration, 51)
    config.fx_conversion_rate_type = "blue"
    policy = db.query(FxPolicy).filter(FxPolicy.hotel_id == 51).first()
    policy.preferred_source = "official"  # Legacy policy source cannot override hotel settings.
    policy.preferred_side = "buy"  # Legacy side does not override the directional rule.
    now = datetime.now(timezone.utc).isoformat()
    seen_markets = []

    def conversion_quote(currency, market="oficial"):
        seen_markets.append(market)
        if currency == "USD" and market == "blue":
            values = {"compra": 1200.0, "venta": 1250.0}
        else:
            values = _FX_TEST_RATES[currency]
        return {
            "moneda": currency,
            "casa": market if currency == "USD" else "oficial",
            **values,
            "fechaActualizacion": now,
        }

    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", conversion_quote)
    _, global_blue_rate, global_details = pricing_policy_service._convert_amount(
        db,
        hotel_id=51,
        amount=1,
        from_currency="USD",
        to_currency="ARS",
        fx_policy_id=None,
        provider_code=None,
    )
    assert global_blue_rate == pytest.approx(1250.0 * 1.05)
    assert global_details["configured_usd_market"] == "blue"
    assert global_details["usd_market"] == "blue"

    _, policy_blue_rate, policy_details = pricing_policy_service._convert_amount(
        db,
        hotel_id=51,
        amount=1,
        from_currency="USD",
        to_currency="ARS",
        fx_policy_id=policy.id,
        provider_code=None,
    )
    assert policy_blue_rate == pytest.approx(1250.0 * 1.05)
    assert policy_details["usd_market"] == "blue"
    assert seen_markets == ["blue", "blue"]

    _, cross_rate, cross_details = pricing_policy_service._convert_amount(
        db,
        hotel_id=51,
        amount=1,
        from_currency="USD",
        to_currency="EUR",
        fx_policy_id=None,
        provider_code=None,
    )
    assert cross_rate == pytest.approx(1250.0 / 1200.0 * 1.05)
    assert cross_details["source_quote"]["market"] == "blue"
    assert cross_details["source_quote"]["usd_market"] == "blue"
    assert cross_details["source_quote"]["rate_type"] == "blue"
    assert cross_details["target_quote"]["market"] == "oficial"
    assert cross_details["target_quote"]["direct_currency_market"] == "oficial"
    assert cross_details["target_quote"]["rate_type"] == "eur_oficial"

    _, _, direct_only_details = pricing_policy_service._convert_amount(
        db,
        hotel_id=51,
        amount=1,
        from_currency="EUR",
        to_currency="BRL",
        fx_policy_id=None,
        provider_code=None,
    )
    assert direct_only_details["configured_usd_market"] == "blue"
    assert direct_only_details["usd_market"] is None
    assert direct_only_details["source_quote"]["direct_currency_market"] == "oficial"
    assert direct_only_details["target_quote"]["direct_currency_market"] == "oficial"


def test_missing_selected_blue_market_does_not_fall_back_to_official_snapshot(db, monkeypatch):
    _seed_pricing_foundation(db)
    config = db.get(HotelConfiguration, 51)
    config.fx_conversion_rate_type = "blue"
    fresh_time = datetime.now(timezone.utc)
    db.add(
        FxRateSnapshot(
            hotel_id=51,
            rate_type="oficial",
            moneda="USD",
            compra=1000,
            venta=1100,
            provider_updated_at=fresh_time,
        )
    )
    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", lambda *_: None)

    with pytest.raises(ValueError, match="blue.*USD.*no se usará otro mercado"):
        pricing_policy_service._convert_amount(
            db,
            hotel_id=51,
            amount=1,
            from_currency="USD",
            to_currency="ARS",
            fx_policy_id=None,
            provider_code=None,
        )


def test_negative_fx_spread_is_rejected_instead_of_reducing_hotel_quote(db, monkeypatch):
    _seed_pricing_foundation(db)
    policy = db.query(FxPolicy).filter(FxPolicy.hotel_id == 51).first()
    policy.spread_pct = -0.01
    monkeypatch.setattr(
        pricing_policy_service,
        "get_conversion_quote_sync",
        lambda currency, market="oficial": {
            "moneda": currency,
            "casa": market if currency == "USD" else "oficial",
            "compra": 1000.0,
            "venta": 1100.0,
            "fechaActualizacion": datetime.now(timezone.utc).isoformat(),
        },
    )

    with pytest.raises(ValueError, match="spread FX debe ser cero o mayor"):
        pricing_policy_service._convert_amount(
            db,
            hotel_id=51,
            amount=100,
            from_currency="ARS",
            to_currency="USD",
            fx_policy_id=policy.id,
            provider_code=None,
        )
