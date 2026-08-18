"""
Canonical stay pricing pipeline (v72 mobile-first pricing/promotions task).

Applies pricing in this exact order for every quote:

  1. Nightly base rate      -- app.services.pricing_service.resolve_rate_calendar
  2. Manual override        -- caller-supplied ``manual_override_total``; when
                                present, steps 3-6 are skipped entirely (an
                                operator-typed price is authoritative, same
                                convention already used by
                                reservation_service._apply_manual_total_override)
  3. Promotions (per night) -- app.services.promotion_service
  4. Taxes/fees              -- app.services.pricing_policy_service._apply_tax_policy
  5. Currency conversion + FX snapshot -- app.services.pricing_policy_service._convert_amount
  6. Payment-method adjustment -- app.services.payment_service.calculate_payment_surcharge
                                   (Decimal-safe, clamped at 0)
  7. Rounding                -- Decimal quantize to 0.01, ROUND_HALF_UP (the
                                 existing MONEY_QUANTUM convention used across
                                 this codebase, e.g. app/services/analytics_contracts.py)

The payment-method adjustment (step 6) is informational on the returned
breakdown (``payment_adjustment`` / ``final_total_with_payment_adjustment``)
and is NOT folded into ``booking_total``: this codebase already applies
PaymentSurcharge at the moment money is actually collected (see
app.services.payment_service.process_payment), because a single reservation
can be paid across several transactions with different methods. Baking a
projected payment-method adjustment into the booked total would double-count
against that existing, deliberate architecture.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy.orm import Session

from app.models.hotel_config import HotelConfiguration
from app.services.pricing_service import resolve_rate_calendar
from app.services.promotion_service import PromotionMatchContext, apply_promotions_to_night, find_applicable_promotions

MONEY_QUANTUM = Decimal("0.01")


class CanonicalPricingError(ValueError):
    """Raised when the canonical pricing pipeline cannot produce a quote."""


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _hotel_default_currency(db: Session, *, hotel_id: int) -> str:
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    currency_code = getattr(config, "default_currency", None)
    return str(currency_code or "ARS").strip().upper()[:3] or "ARS"


@dataclass(slots=True)
class CanonicalPricingResult:
    hotel_id: int
    category_id: int
    check_in: date
    check_out: date
    nights: int
    base_currency: str
    output_currency: str
    per_night: list[dict]
    promotions_applied: list[dict]
    subtotal_amount: Decimal
    tax_amount: Decimal
    fee_amount: Decimal
    fx_rate_snapshot: Optional[Decimal]
    booking_total: Decimal  # base - promotions + tax/fee, FX-converted, rounded -- what should be persisted
    payment_adjustment: Optional[dict]
    final_total_with_payment_adjustment: Decimal
    pricing_source: str = "canonical_daily_rate"

    def to_snapshot_dict(self) -> dict:
        """JSON-serialisable breakdown, frozen into a reservation's
        pricing_snapshot at booking time so later promotion edits/
        deactivations can never change an already-booked total."""
        return {
            "pricing_source": self.pricing_source,
            "hotel_id": self.hotel_id,
            "category_id": self.category_id,
            "check_in": self.check_in.isoformat(),
            "check_out": self.check_out.isoformat(),
            "nights": self.nights,
            "base_currency": self.base_currency,
            "output_currency": self.output_currency,
            "per_night": self.per_night,
            "promotions_applied": self.promotions_applied,
            "subtotal_amount": str(self.subtotal_amount),
            "tax_amount": str(self.tax_amount),
            "fee_amount": str(self.fee_amount),
            "fx_rate_snapshot": str(self.fx_rate_snapshot) if self.fx_rate_snapshot is not None else None,
            "booking_total": str(self.booking_total),
            "payment_adjustment": self.payment_adjustment,
            "final_total_with_payment_adjustment": str(self.final_total_with_payment_adjustment),
        }


def compute_canonical_stay_pricing(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    check_in: date,
    check_out: date,
    booking_date: Optional[date] = None,
    room_id: Optional[int] = None,
    sales_channel_code: Optional[str] = None,
    guest_id: Optional[int] = None,
    company_id: Optional[int] = None,
    payment_method: Optional[str] = None,
    target_currency: Optional[str] = None,
    tax_policy_id: Optional[int] = None,
    guest_scope: str = "all",
    manual_override_total: Optional[Decimal] = None,
) -> CanonicalPricingResult:
    if check_out <= check_in:
        raise CanonicalPricingError("check_out must be after check_in")

    nights = (check_out - check_in).days
    base_currency = _hotel_default_currency(db, hotel_id=hotel_id)
    booking_date = booking_date or date.today()

    if manual_override_total is not None:
        total = _quantize(Decimal(manual_override_total))
        per_night_amount = _quantize(total / nights) if nights else Decimal("0.00")
        per_night = [
            {
                "date": (check_in + timedelta(days=offset)).isoformat(),
                "base_amount": str(per_night_amount),
                "promotions_applied": [],
                "post_promotion_amount": str(per_night_amount),
            }
            for offset in range(nights)
        ]
        return CanonicalPricingResult(
            hotel_id=hotel_id,
            category_id=category_id,
            check_in=check_in,
            check_out=check_out,
            nights=nights,
            base_currency=base_currency,
            output_currency=target_currency or base_currency,
            per_night=per_night,
            promotions_applied=[],
            subtotal_amount=total,
            tax_amount=Decimal("0.00"),
            fee_amount=Decimal("0.00"),
            fx_rate_snapshot=None,
            booking_total=total,
            payment_adjustment=None,
            final_total_with_payment_adjustment=total,
            pricing_source="manual_override",
        )

    calendar = resolve_rate_calendar(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        from_date=check_in,
        to_date=check_in + timedelta(days=nights - 1),
        payment_method=payment_method,
    )

    per_night: list[dict] = []
    all_promotions_applied: list[dict] = []
    subtotal = Decimal("0.00")
    for offset, row in enumerate(calendar):
        base_amount = _quantize(Decimal(str(row["price"])))
        ctx = PromotionMatchContext(
            hotel_id=hotel_id,
            night_date=row["date"],
            night_index=offset + 1,
            nights_total=nights,
            booking_date=booking_date,
            category_id=category_id,
            room_id=room_id,
            sales_channel_code=sales_channel_code,
            guest_id=guest_id,
            company_id=company_id,
            payment_currency=target_currency or base_currency,
            payment_method=payment_method,
        )
        matched = find_applicable_promotions(db, ctx)
        post_promo_amount, applied = apply_promotions_to_night(base_amount, matched)
        subtotal += post_promo_amount
        all_promotions_applied.extend(applied)
        per_night.append(
            {
                "date": row["date"].isoformat(),
                "base_amount": str(base_amount),
                "promotions_applied": applied,
                "post_promotion_amount": str(post_promo_amount),
            }
        )
    subtotal = _quantize(subtotal)

    # Step 4: taxes/fees -- reuse the existing tax-policy engine.
    from app.services.pricing_policy_service import _apply_tax_policy, _select_tax_policy  # local import: same layer, avoids a hard module-load-order dependency

    tax_policy = _select_tax_policy(db, hotel_id=hotel_id, tax_policy_id=tax_policy_id)
    tax_amount_f, fee_amount_f, _tax_breakdown = _apply_tax_policy(
        quoted_amount=float(subtotal),
        nights=nights,
        tax_policy=tax_policy,
        guest_scope=guest_scope,
        channel_code=sales_channel_code,
    )
    tax_amount = _quantize(Decimal(str(tax_amount_f)))
    fee_amount = _quantize(Decimal(str(fee_amount_f)))
    gross_total = _quantize(subtotal + tax_amount + fee_amount)

    # Step 5: currency conversion with an FX-rate snapshot.
    output_currency = base_currency
    fx_rate_snapshot: Optional[Decimal] = None
    booking_total = gross_total
    if target_currency and target_currency.upper() != base_currency:
        from app.services.pricing_policy_service import PricingPolicyError, _convert_amount

        try:
            converted, rate = _convert_amount(
                db,
                hotel_id=hotel_id,
                amount=float(gross_total),
                from_currency=base_currency,
                to_currency=target_currency.upper(),
                fx_policy_id=None,
                provider_code=None,
            )
        except PricingPolicyError as exc:
            raise CanonicalPricingError(str(exc)) from exc
        booking_total = _quantize(Decimal(str(converted)))
        fx_rate_snapshot = Decimal(str(rate))
        output_currency = target_currency.upper()

    # Step 6: payment-method adjustment -- informational, never persisted into booking_total.
    payment_adjustment = None
    final_total = booking_total
    if payment_method:
        from app.services.payment_service import calculate_payment_surcharge

        info = calculate_payment_surcharge(
            db, hotel_id=hotel_id, payment_method=payment_method, base_amount=booking_total,
        )
        payment_adjustment = {
            "payment_method": payment_method,
            "surcharge_type": info["surcharge_type"],
            "surcharge_value": str(info["surcharge_value"]) if info["surcharge_value"] is not None else None,
            "surcharge_amount": str(info["surcharge_amount"]),
        }
        final_total = _quantize(info["final_amount"])

    return CanonicalPricingResult(
        hotel_id=hotel_id,
        category_id=category_id,
        check_in=check_in,
        check_out=check_out,
        nights=nights,
        base_currency=base_currency,
        output_currency=output_currency,
        per_night=per_night,
        promotions_applied=all_promotions_applied,
        subtotal_amount=subtotal,
        tax_amount=tax_amount,
        fee_amount=fee_amount,
        fx_rate_snapshot=fx_rate_snapshot,
        booking_total=booking_total,
        payment_adjustment=payment_adjustment,
        final_total_with_payment_adjustment=final_total,
    )
