"""Build the canonical quote shared by reservation-facing surfaces."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.pricing_service import build_pricing_revision
from app.services.quote_token_service import issue_quote_token
from app.services.reservation_service import calculate_reservation_pricing, normalize_pricing_payment_method


def build_reservation_quote(
    db: Session,
    *,
    hotel_id: int,
    category_id: int,
    check_in_date: date,
    check_out_date: date,
    sellable_product_id: int | None = None,
    rate_plan_id: int | None = None,
    tax_policy_id: int | None = None,
    pricing_channel_code: str | None = None,
    pricing_payment_method: str | None = None,
    guest_scope: str = "all",
    target_currency: str | None = None,
    occupancy: int | None = None,
) -> dict[str, Any]:
    normalized_payment_method = normalize_pricing_payment_method(pricing_payment_method)
    pricing = calculate_reservation_pricing(
        db,
        category_id=category_id,
        check_in=check_in_date,
        check_out=check_out_date,
        hotel_id=hotel_id,
        sellable_product_id=sellable_product_id,
        rate_plan_id=rate_plan_id,
        tax_policy_id=tax_policy_id,
        pricing_channel_code=pricing_channel_code,
        pricing_payment_method=normalized_payment_method,
        guest_scope=guest_scope,
        target_currency=target_currency,
        occupancy=occupancy,
    )
    revision = build_pricing_revision(
        db,
        hotel_id=hotel_id,
        category_id=category_id,
        check_in=check_in_date,
        check_out=check_out_date,
        sellable_product_id=sellable_product_id,
        rate_plan_id=rate_plan_id,
        tax_policy_id=tax_policy_id,
        pricing_channel_code=pricing_channel_code,
        pricing_payment_method=normalized_payment_method,
        guest_scope=guest_scope,
        target_currency=target_currency,
        occupancy=occupancy,
    )

    snapshot: dict[str, Any] = {}
    if pricing.pricing_snapshot:
        try:
            loaded = json.loads(pricing.pricing_snapshot)
            if isinstance(loaded, dict):
                snapshot = loaded
        except json.JSONDecodeError:
            snapshot = {}
    breakdown = snapshot.get("breakdown")
    if not isinstance(breakdown, list):
        breakdown = [
            {
                "date": (check_in_date + timedelta(days=offset)).isoformat(),
                "price": pricing.nightly_rate,
            }
            for offset in range(pricing.nights)
        ]

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at.timestamp() + 900
    token_payload = {
        "hotel_id": hotel_id,
        "category_id": category_id,
        "check_in_date": check_in_date.isoformat(),
        "check_out_date": check_out_date.isoformat(),
        "sellable_product_id": sellable_product_id,
        "rate_plan_id": rate_plan_id,
        "tax_policy_id": tax_policy_id,
        "pricing_channel_code": pricing_channel_code,
        "pricing_payment_method": normalized_payment_method,
        "guest_scope": guest_scope,
        "target_currency": target_currency,
        "occupancy": occupancy,
        "pricing_revision": revision,
        "total_amount": pricing.total_amount,
        "deposit_amount": pricing.deposit_amount,
        "currency_code": pricing.currency_code,
    }
    token = issue_quote_token(token_payload, ttl_seconds=900)
    return {
        "status": "ok",
        "category_id": category_id,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "nights": pricing.nights,
        "nightly_rate": pricing.nightly_rate,
        "subtotal_amount": pricing.subtotal_amount,
        "tax_amount": pricing.tax_amount,
        "fee_amount": pricing.fee_amount,
        "commission_amount": pricing.commission_amount,
        "net_amount": pricing.net_amount,
        "total_amount": pricing.total_amount,
        "deposit_amount": pricing.deposit_amount,
        "currency_code": pricing.currency_code,
        "pricing_payment_method": normalized_payment_method,
        "pricing_revision": revision,
        "breakdown": breakdown,
        "quote_token": token,
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc),
    }
