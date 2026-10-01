"""Build the canonical quote shared by reservation-facing surfaces."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.services.pricing_service import build_pricing_revision
from app.services.quote_token_service import issue_quote_token
from app.services.reservation_service import (
    _apply_corporate_pricing,
    _resolve_reservation_company,
    calculate_reservation_pricing,
    normalize_pricing_payment_method,
)


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
    guest_id: int | None = None,
    company_id: int | None = None,
) -> dict[str, Any]:
    """Build a quote response and its short-lived creation token.

    For a company configured with deferred payment, `company_billing_deferred`
    is true, `billing_mode` is `external_company_invoice`, `amounts_disclosed`
    is false, all monetary
    response fields are null, and price breakdown/promotion details are empty.
    The encrypted token still carries the server-verified amounts needed by
    reservation creation without making them readable to the client.
    """
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
        guest_id=guest_id,
        company_id=company_id,
    )
    company = None
    if company_id is not None:
        company = _resolve_reservation_company(db, hotel_id=hotel_id, company_id=company_id)
        pricing = _apply_corporate_pricing(
            db,
            hotel_id=hotel_id,
            pricing=pricing,
            company=company,
            explicit_total=None,
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
        company_id=company_id,
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
    promotions_applied = snapshot.get("promotions_applied")
    if not isinstance(promotions_applied, list):
        promotions_applied = []

    deferred_company_invoice = bool(company and company.payment_deferred)

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
        "company_id": company_id,
        "pricing_revision": revision,
        "total_amount": pricing.total_amount,
        "deposit_amount": pricing.deposit_amount,
        "currency_code": pricing.currency_code,
    }
    token = issue_quote_token(
        token_payload,
        ttl_seconds=900,
        encrypt_payload=deferred_company_invoice,
    )
    quote = {
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
        "promotions_applied": promotions_applied,
        "quote_token": token,
        "expires_at": datetime.fromtimestamp(expires_at, timezone.utc),
        "company_billing_deferred": deferred_company_invoice,
        "amounts_disclosed": not deferred_company_invoice,
    }
    if deferred_company_invoice:
        # The lodging invoice is handled outside this PMS. Keep the signed
        # pricing details encrypted inside the token because reservation
        # creation still validates the current quote, but disclose no monetary
        # fields, per-night prices, or promotion amounts in the API response.
        for amount_field in (
            "nightly_rate",
            "subtotal_amount",
            "tax_amount",
            "fee_amount",
            "commission_amount",
            "net_amount",
            "total_amount",
            "deposit_amount",
        ):
            quote[amount_field] = None
        quote["breakdown"] = []
        quote["promotions_applied"] = []
        quote["billing_mode"] = "external_company_invoice"
    else:
        quote["billing_mode"] = "pms"
    return quote
