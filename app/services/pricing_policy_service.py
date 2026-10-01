"""
Commercial pricing, tax, commission and FX quoting service.

This layer turns the new commercial foundation tables into a consistent quote
object that later OTA sync, rebook flows and billing adjustments can reuse.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.commercial import FxPolicy, RatePlan, RatePlanPrice, TaxPolicy, TaxRule
from app.models.fx_rate_snapshot import FxRateSnapshot
from app.models.hotel_config import HotelConfiguration
from app.models.ota_core import OTACommissionRule, OTAProvider
from app.services.fx_service import (
    SUPPORTED_CONVERSION_CURRENCIES,
    get_conversion_quote_sync,
    parse_provider_updated_at,
    quote_is_fresh,
)


class PricingPolicyError(ValueError):
    """Raised when pricing policies cannot produce a reliable quote."""


@dataclass(slots=True)
class StayPricingQuote:
    hotel_id: int
    rate_plan_id: int
    nights: int
    base_currency: str
    output_currency: str
    nightly_amount: float
    subtotal_amount: float
    tax_amount: float
    fee_amount: float
    gross_total: float
    commission_amount: float
    net_amount: float
    fx_rate_snapshot: float | None
    fx_quote_details: dict | None
    tax_breakdown: list[dict]


def quote_rate_plan_stay(
    db: Session,
    *,
    hotel_id: int,
    rate_plan_id: int,
    check_in: date,
    check_out: date,
    occupancy: int | None = None,
    channel_code: str | None = None,
    provider_code: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    tax_policy_id: int | None = None,
    fx_policy_id: int | None = None,
) -> StayPricingQuote:
    if check_out <= check_in:
        raise PricingPolicyError("Checkout must be after check-in")

    rate_plan = (
        db.query(RatePlan)
        .filter(RatePlan.id == rate_plan_id, RatePlan.hotel_id == hotel_id, RatePlan.is_active == True)
        .first()
    )
    if not rate_plan:
        raise PricingPolicyError("Rate plan not found for hotel")

    nights = (check_out - check_in).days
    if nights < rate_plan.min_nights_default:
        raise PricingPolicyError(
            f"Rate plan requires at least {rate_plan.min_nights_default} nights"
        )
    if rate_plan.max_nights_default is not None and nights > rate_plan.max_nights_default:
        raise PricingPolicyError(
            f"Rate plan allows at most {rate_plan.max_nights_default} nights"
        )
    if occupancy is not None:
        product = rate_plan.sellable_product
        if product and not product.min_occupancy <= occupancy <= product.max_occupancy:
            raise PricingPolicyError(
                f"Sellable product accepts between {product.min_occupancy} and {product.max_occupancy} guests"
            )
    price = _select_rate_plan_price(
        db,
        hotel_id=hotel_id,
        rate_plan_id=rate_plan_id,
        occupancy=occupancy,
        channel_code=channel_code,
        check_in=check_in,
        check_out=check_out,
    )
    currency_code = price.currency_code or rate_plan.currency_code
    nightly_amount = round(price.base_amount, 2)
    quoted_base_total = round(nightly_amount * nights, 2)

    tax_policy = _select_tax_policy(db, hotel_id=hotel_id, tax_policy_id=tax_policy_id)
    tax_amount, fee_amount, tax_breakdown = _apply_tax_policy(
        quoted_amount=quoted_base_total,
        nights=nights,
        tax_policy=tax_policy,
        guest_scope=guest_scope,
        channel_code=channel_code,
    )

    if price.tax_inclusive:
        gross_total = quoted_base_total
        subtotal_amount = round(max(gross_total - tax_amount - fee_amount, 0.0), 2)
    else:
        subtotal_amount = quoted_base_total
        gross_total = round(subtotal_amount + tax_amount + fee_amount, 2)

    commission_amount = _resolve_commission_amount(
        db,
        hotel_id=hotel_id,
        rate_plan_id=rate_plan_id,
        provider_code=provider_code,
        gross_total=gross_total,
    )
    net_amount = round(gross_total - commission_amount, 2)

    fx_rate_snapshot = None
    fx_quote_details = None
    output_currency = currency_code
    if target_currency and target_currency != currency_code:
        gross_total, fx_rate_snapshot, fx_quote_details = _convert_amount(
            db,
            hotel_id=hotel_id,
            amount=gross_total,
            from_currency=currency_code,
            to_currency=target_currency,
            fx_policy_id=fx_policy_id,
            provider_code=provider_code,
        )
        subtotal_amount = round(subtotal_amount * fx_rate_snapshot, 2)
        tax_amount = round(tax_amount * fx_rate_snapshot, 2)
        fee_amount = round(fee_amount * fx_rate_snapshot, 2)
        commission_amount = round(commission_amount * fx_rate_snapshot, 2)
        net_amount = round(gross_total - commission_amount, 2)
        output_currency = target_currency

    return StayPricingQuote(
        hotel_id=hotel_id,
        rate_plan_id=rate_plan_id,
        nights=nights,
        base_currency=currency_code,
        output_currency=output_currency,
        nightly_amount=nightly_amount,
        subtotal_amount=subtotal_amount,
        tax_amount=tax_amount,
        fee_amount=fee_amount,
        gross_total=gross_total,
        commission_amount=commission_amount,
        net_amount=net_amount,
        fx_rate_snapshot=fx_rate_snapshot,
        fx_quote_details=fx_quote_details,
        tax_breakdown=tax_breakdown,
    )


def _select_rate_plan_price(
    db: Session,
    *,
    hotel_id: int,
    rate_plan_id: int,
    occupancy: int | None,
    channel_code: str | None,
    check_in: date,
    check_out: date,
) -> RatePlanPrice:
    prices = (
        db.query(RatePlanPrice)
        .filter(
            RatePlanPrice.hotel_id == hotel_id,
            RatePlanPrice.rate_plan_id == rate_plan_id,
            RatePlanPrice.is_active == True,
            or_(RatePlanPrice.valid_from == None, RatePlanPrice.valid_from <= check_in),
            or_(RatePlanPrice.valid_to == None, RatePlanPrice.valid_to >= check_out - timedelta(days=1)),
        )
        .all()
    )
    if not prices:
        raise PricingPolicyError("No active prices found for rate plan")

    def _score(price: RatePlanPrice) -> tuple[int, int, int]:
        channel_score = 2 if price.sales_channel_code == channel_code else (1 if price.sales_channel_code is None else 0)
        occupancy_score = 2 if occupancy is not None and price.occupancy == occupancy else (1 if price.occupancy is None else 0)
        date_score = 1 if price.valid_from or price.valid_to else 0
        return (channel_score, occupancy_score, date_score)

    selected = max(prices, key=_score)
    if _score(selected)[0] == 0:
        raise PricingPolicyError("No matching price found for the selected sales channel")
    if occupancy is not None and _score(selected)[1] == 0:
        raise PricingPolicyError("No matching price found for the selected occupancy")
    return selected


def _select_tax_policy(db: Session, *, hotel_id: int, tax_policy_id: int | None) -> TaxPolicy | None:
    query = db.query(TaxPolicy).filter(TaxPolicy.hotel_id == hotel_id, TaxPolicy.is_active == True)
    if tax_policy_id is not None:
        policy = query.filter(TaxPolicy.id == tax_policy_id).first()
        if not policy:
            raise PricingPolicyError("Tax policy not found for hotel")
        return policy
    return query.order_by(TaxPolicy.id.asc()).first()


def _apply_tax_policy(
    *,
    quoted_amount: float,
    nights: int,
    tax_policy: TaxPolicy | None,
    guest_scope: str,
    channel_code: str | None,
) -> tuple[float, float, list[dict]]:
    if not tax_policy:
        return 0.0, 0.0, []

    effective_guest_scope = guest_scope.lower()
    if effective_guest_scope == "foreign" and tax_policy.foreign_guest_tax_exempt:
        return 0.0, 0.0, []

    total_tax = 0.0
    total_fee = 0.0
    breakdown: list[dict] = []

    applicable_rules = [
        rule
        for rule in tax_policy.rules
        if rule.is_active
        and (rule.channel_code in (None, "", channel_code))
        and (rule.guest_scope in ("all", effective_guest_scope))
    ]

    if not applicable_rules and tax_policy.apply_vat_by_default and tax_policy.vat_rate:
        vat_amount = round(quoted_amount * (tax_policy.vat_rate / 100.0), 2)
        return vat_amount, 0.0, [{"tax_code": "VAT_DEFAULT", "kind": "tax", "amount": vat_amount}]

    for rule in sorted(applicable_rules, key=lambda current: (current.priority, current.id)):
        amount = _calculate_rule_amount(rule=rule, quoted_amount=quoted_amount, nights=nights)
        entry = {"tax_code": rule.tax_code, "amount": amount}
        if str(rule.tax_code).lower().startswith("fee"):
            total_fee += amount
            entry["kind"] = "fee"
        else:
            total_tax += amount
            entry["kind"] = "tax"
        breakdown.append(entry)

    return round(total_tax, 2), round(total_fee, 2), breakdown


def _calculate_rule_amount(*, rule: TaxRule, quoted_amount: float, nights: int) -> float:
    applies_when = _load_json_dict(rule.applies_when_json)
    per_night = bool(applies_when.get("per_night")) if applies_when else False

    if rule.tax_type == "percentage":
        base = quoted_amount
        return round(base * (rule.amount / 100.0), 2)

    multiplier = nights if per_night else 1
    return round(rule.amount * multiplier, 2)


def _resolve_commission_amount(
    db: Session,
    *,
    hotel_id: int,
    rate_plan_id: int,
    provider_code: str | None,
    gross_total: float,
) -> float:
    if not provider_code:
        return 0.0

    provider = db.query(OTAProvider).filter(OTAProvider.code == provider_code).first()
    if not provider:
        return 0.0

    rules = (
        db.query(OTACommissionRule)
        .filter(
            OTACommissionRule.hotel_id == hotel_id,
            OTACommissionRule.provider_id == provider.id,
            OTACommissionRule.is_active == True,
            or_(OTACommissionRule.rate_plan_id == rate_plan_id, OTACommissionRule.rate_plan_id == None),
        )
        .all()
    )
    if not rules:
        return 0.0

    selected = max(rules, key=lambda rule: 1 if rule.rate_plan_id == rate_plan_id else 0)
    commission_amount = 0.0
    if selected.commission_pct:
        commission_amount += gross_total * (selected.commission_pct / 100.0)
    if selected.commission_fixed:
        commission_amount += selected.commission_fixed
    return round(commission_amount, 2)


def _convert_amount(
    db: Session,
    *,
    hotel_id: int,
    amount: float,
    from_currency: str,
    to_currency: str,
    fx_policy_id: int | None,
    provider_code: str | None,
) -> tuple[float, float, dict | None]:
    policy = _select_fx_policy(db, hotel_id=hotel_id, fx_policy_id=fx_policy_id)
    from_code = str(from_currency or "").strip().upper()
    to_code = str(to_currency or "").strip().upper()
    if from_code == to_code:
        return round(amount, 2), 1.0, None

    if from_code not in SUPPORTED_CONVERSION_CURRENCIES or to_code not in SUPPORTED_CONVERSION_CURRENCIES:
        raise PricingPolicyError(f"Conversión no soportada de {from_code} a {to_code}")

    if from_code in SUPPORTED_CONVERSION_CURRENCIES and to_code in SUPPORTED_CONVERSION_CURRENCIES:
        config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
        configured_market = str(getattr(config, "fx_conversion_rate_type", "oficial") or "oficial").lower()
        if configured_market not in {"oficial", "blue"}:
            raise PricingPolicyError("La cotización USD configurada no es válida")

        selected_market = configured_market

        source_quote = _resolve_conversion_quote(
            db,
            hotel_id=hotel_id,
            currency=from_code,
            market=selected_market,
        ) if from_code != "ARS" else None
        target_quote = _resolve_conversion_quote(
            db,
            hotel_id=hotel_id,
            currency=to_code,
            market=selected_market,
        ) if to_code != "ARS" else None

        source_ars_per_unit = float(source_quote["venta"]) if source_quote else 1.0
        target_ars_per_unit = float(target_quote["compra"]) if target_quote else 1.0
        if source_ars_per_unit <= 0 or target_ars_per_unit <= 0:
            raise PricingPolicyError("La cotización FX debe ser positiva")
        raw_rate = source_ars_per_unit / target_ars_per_unit

        if source_quote is not None:
            _record_conversion_snapshot(
                db,
                hotel_id=hotel_id,
                currency=from_code,
                market=selected_market,
                quote=source_quote,
                side="venta",
            )
        if target_quote is not None:
            _record_conversion_snapshot(
                db,
                hotel_id=hotel_id,
                currency=to_code,
                market=selected_market,
                quote=target_quote,
                side="compra",
            )

        spread_pct = float(policy.spread_pct or 0.0) if policy else 0.0
        if not math.isfinite(spread_pct) or spread_pct < 0:
            raise PricingPolicyError(
                "El spread FX debe ser cero o mayor para conservar una cotización favorable al hotel."
            )
        # The hotel's global market always governs USD quotes. FxPolicy still
        # supplies spread; preferred_source/preferred_side are legacy fields
        # and intentionally do not override market or directional side.
        effective_rate = raw_rate * (1 + (spread_pct / 100.0))
        if not math.isfinite(effective_rate) or effective_rate <= 0:
            raise PricingPolicyError("La tasa FX resultante no es válida")
        details = {
            "provider": "dolarapi.com",
            "configured_usd_market": selected_market,
            "usd_market": selected_market if "USD" in {from_code, to_code} else None,
            "path": "via_ars",
            "from_currency": from_code,
            "to_currency": to_code,
            "source_side": "venta" if from_code != "ARS" else None,
            "target_side": "compra" if to_code != "ARS" else None,
            "source_ars_per_unit": source_ars_per_unit,
            "target_ars_per_unit": target_ars_per_unit,
            "spread_pct": spread_pct,
            "applied_rate": round(effective_rate, 8),
            "source_updated_at": source_quote.get("_provider_updated_at") if source_quote else None,
            "target_updated_at": target_quote.get("_provider_updated_at") if target_quote else None,
            "source_quote": _quote_provenance(source_quote, from_code, "venta") if source_quote else None,
            "target_quote": _quote_provenance(target_quote, to_code, "compra") if target_quote else None,
        }
        return round(amount * effective_rate, 2), round(effective_rate, 6), details


def _resolve_conversion_quote(
    db: Session,
    *,
    hotel_id: int,
    currency: str,
    market: str,
) -> dict:
    selected_type = market if currency == "USD" else f"{currency.lower()}_oficial"
    quote = get_conversion_quote_sync(currency, market)
    expected_market = market if currency == "USD" else "oficial"
    if (
        not quote_is_fresh(quote)
        or not isinstance(quote, dict)
        or str(quote.get("casa") or "").strip().lower() != expected_market
    ):
        quote = None

    if quote is None:
        snapshot = (
            db.query(FxRateSnapshot)
            .filter(
                FxRateSnapshot.hotel_id == hotel_id,
                FxRateSnapshot.rate_type == selected_type,
                FxRateSnapshot.moneda == currency,
            )
            .order_by(FxRateSnapshot.provider_updated_at.desc(), FxRateSnapshot.fetched_at.desc())
            .first()
        )
        if snapshot is not None:
            candidate_time = snapshot.provider_updated_at or snapshot.fetched_at
            candidate = {
                "compra": snapshot.compra,
                "venta": snapshot.venta,
                "fechaActualizacion": candidate_time.isoformat() if candidate_time else None,
                "casa": snapshot.provider_market or expected_market,
            }
            if quote_is_fresh(candidate) and candidate["casa"] == expected_market:
                quote = candidate

    if quote is None:
        raise PricingPolicyError(
            f"No hay una cotización fresca de {selected_type} para {currency}; no se usará otro mercado."
        )

    provider_updated_at = parse_provider_updated_at(quote.get("fechaActualizacion") or quote.get("fecha"))
    quote = dict(quote)
    quote["_provider_updated_at"] = provider_updated_at.isoformat() if provider_updated_at else None
    quote["_rate_type"] = selected_type
    return quote


def _record_conversion_snapshot(
    db: Session,
    *,
    hotel_id: int,
    currency: str,
    market: str,
    quote: dict,
    side: str,
) -> None:
    provider_updated_at = parse_provider_updated_at(
        quote.get("fechaActualizacion") or quote.get("fecha")
    )
    rate_type = market if currency == "USD" else f"{currency.lower()}_oficial"
    db.add(
        FxRateSnapshot(
            hotel_id=hotel_id,
            rate_type=rate_type,
            provider_market=str(quote.get("casa") or (market if currency == "USD" else "oficial")),
            moneda=currency,
            compra=float(quote["compra"]),
            venta=float(quote["venta"]),
            fetched_at=datetime.now(timezone.utc),
            provider_updated_at=provider_updated_at,
            selected_side=side,
            base_currency="ARS",
            quote_currency=currency,
            applied_rate=float(quote[side]),
            source="dolarapi.com",
        )
    )


def _quote_provenance(quote: dict, currency: str, side: str) -> dict:
    provider_market = quote.get("casa")
    return {
        "currency": currency,
        "rate_type": quote.get("_rate_type"),
        "market": provider_market,
        "usd_market": provider_market if currency == "USD" else None,
        "direct_currency_market": provider_market if currency != "USD" else None,
        "side": side,
        "ars_per_unit": float(quote[side]),
        "provider_updated_at": quote.get("_provider_updated_at"),
    }


def _select_fx_policy(db: Session, *, hotel_id: int, fx_policy_id: int | None) -> FxPolicy | None:
    query = db.query(FxPolicy).filter(FxPolicy.hotel_id == hotel_id, FxPolicy.is_active == True)
    if fx_policy_id is not None:
        policy = query.filter(FxPolicy.id == fx_policy_id).first()
        if not policy:
            raise PricingPolicyError("FX policy not found for hotel")
        return policy
    return query.order_by(FxPolicy.id.asc()).first()


def _load_json_dict(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
