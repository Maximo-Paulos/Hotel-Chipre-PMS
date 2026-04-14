"""
Commercial pricing, tax, commission and FX quoting service.

This layer turns the new commercial foundation tables into a consistent quote
object that later OTA sync, rebook flows and billing adjustments can reuse.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.commercial import FxPolicy, RatePlan, RatePlanPrice, TaxPolicy, TaxRule
from app.models.ota_core import OTACommissionRule, OTACurrencyRate, OTAProvider


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
    output_currency = currency_code
    if target_currency and target_currency != currency_code:
        gross_total, fx_rate_snapshot = _convert_amount(
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
            or_(RatePlanPrice.valid_to == None, RatePlanPrice.valid_to >= check_out),
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
) -> tuple[float, float]:
    policy = _select_fx_policy(db, hotel_id=hotel_id, fx_policy_id=fx_policy_id)
    provider_id = None
    if provider_code:
        provider = db.query(OTAProvider).filter(OTAProvider.code == provider_code).first()
        provider_id = provider.id if provider else None

    rate = (
        db.query(OTACurrencyRate)
        .filter(
            OTACurrencyRate.hotel_id == hotel_id,
            OTACurrencyRate.base_currency == from_currency,
            OTACurrencyRate.quote_currency == to_currency,
            or_(OTACurrencyRate.provider_id == provider_id, OTACurrencyRate.provider_id == None),
        )
        .order_by(OTACurrencyRate.captured_at.desc())
        .first()
    )
    if not rate:
        raise PricingPolicyError(f"Missing FX rate from {from_currency} to {to_currency}")

    effective_rate = rate.rate
    if policy and policy.spread_pct:
        effective_rate = effective_rate * (1 + (policy.spread_pct / 100.0))

    return round(amount * effective_rate, 2), round(effective_rate, 6)


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
