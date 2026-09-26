"""Reads and writes for the public marketing site.

Kept apart from subscription_entitlements on purpose: that module owns what a
hotel is *entitled* to, this one owns what the website *says*. The owner edits
the second from the master-admin console without touching enforcement.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.marketing import MarketingLead, MarketingPricingPlan
from app.services.subscription_entitlements import PLAN_CATALOG, TRIAL_DURATION_DAYS


def _decode_features(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []


def _plan_to_public(plan: MarketingPricingPlan) -> dict[str, Any]:
    return {
        "code": plan.code,
        "name": plan.name,
        "price_amount": plan.price_amount,
        "currency": plan.currency,
        "billing_period": plan.billing_period,
        "headline": plan.headline,
        "description": plan.description,
        "features": _decode_features(plan.features_json),
        "room_limit": plan.room_limit,
        "staff_limit": plan.staff_limit,
        "cta_label": plan.cta_label,
        "cta_kind": plan.cta_kind,
        "highlight": bool(plan.highlight),
    }


def _ordered_plans(db: Session, *, public_only: bool) -> list[MarketingPricingPlan]:
    query = db.query(MarketingPricingPlan)
    if public_only:
        query = query.filter(MarketingPricingPlan.is_public.is_(True))
    return query.order_by(MarketingPricingPlan.sort_order, MarketingPricingPlan.id).all()


def _plan_catalog_fallback() -> list[dict[str, Any]]:
    """The enforced plan caps, with no price.

    Used when nothing is published yet and, deliberately, when the table
    itself cannot be read: the public site must degrade to a correct pricing
    section rather than to a 500, and these limits come from the same catalog
    the application enforces.
    """
    return [
        {
            "code": code,
            "name": data["name"],
            "price_amount": None,
            "currency": None,
            "billing_period": "month",
            "headline": None,
            "description": None,
            "features": [],
            "room_limit": data.get("room_limit"),
            "staff_limit": data.get("staff_limit"),
            "cta_label": None,
            "cta_kind": "early_access",
            "highlight": code == "pro",
        }
        for code, data in PLAN_CATALOG.items()
    ]


def public_pricing(db: Session) -> dict[str, Any]:
    """What the landing page renders. Falls back to the enforced plan caps so a
    database that has not been seeded still shows the real room/staff limits
    rather than an empty pricing section."""
    try:
        plans = _ordered_plans(db, public_only=True)
    except SQLAlchemyError:
        # Most likely the migration has not run on this environment yet.
        # Falling back keeps the pricing section correct instead of failing
        # the whole page on a deploy-ordering problem.
        db.rollback()
        plans = []

    if not plans:
        return {"plans": _plan_catalog_fallback(), "trial_days": TRIAL_DURATION_DAYS}

    return {"plans": [_plan_to_public(plan) for plan in plans], "trial_days": TRIAL_DURATION_DAYS}


def admin_pricing(db: Session) -> list[dict[str, Any]]:
    """Every plan, public or not, as the master-admin form edits them."""
    return [
        {
            **_plan_to_public(plan),
            "is_public": bool(plan.is_public),
            "sort_order": plan.sort_order,
        }
        for plan in _ordered_plans(db, public_only=False)
    ]


def replace_pricing(db: Session, plans: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Upsert by code, then drop any plan the payload no longer mentions."""
    existing = {plan.code: plan for plan in db.query(MarketingPricingPlan).all()}
    seen: set[str] = set()

    for payload in plans:
        code = payload["code"]
        seen.add(code)
        plan = existing.get(code) or MarketingPricingPlan(code=code)
        plan.name = payload["name"]
        plan.is_public = payload.get("is_public", True)
        plan.sort_order = payload.get("sort_order", 0)
        plan.price_amount = payload.get("price_amount")
        plan.currency = payload.get("currency")
        plan.billing_period = payload.get("billing_period", "month")
        plan.headline = payload.get("headline")
        plan.description = payload.get("description")
        plan.features_json = json.dumps(payload.get("features") or [], ensure_ascii=False)
        plan.room_limit = payload.get("room_limit")
        plan.staff_limit = payload.get("staff_limit")
        plan.cta_label = payload.get("cta_label")
        plan.cta_kind = payload.get("cta_kind", "early_access")
        plan.highlight = payload.get("highlight", False)
        if plan.id is None:
            db.add(plan)

    for code, plan in existing.items():
        if code not in seen:
            db.delete(plan)

    db.flush()
    return admin_pricing(db)


def hash_source(value: str) -> str:
    """One-way, so abuse triage can group by origin without keeping an IP."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def record_lead(db: Session, *, email: str, source_key: str, **fields: Any) -> MarketingLead:
    """Create once per email without letting anonymous repeats edit a lead.

    A repeat submission receives the same public response but cannot overwrite
    another person's contact details or restart the retention clock.
    """
    normalized = email.strip().lower()
    lead = db.query(MarketingLead).filter(MarketingLead.email == normalized).one_or_none()
    if lead is not None:
        return lead

    lead = MarketingLead(email=normalized)
    db.add(lead)

    utm = fields.pop("utm", None)
    for key, value in fields.items():
        if value not in (None, "") and hasattr(lead, key):
            setattr(lead, key, value)
    if utm:
        lead.utm_json = json.dumps(utm, ensure_ascii=False)
    lead.ip_hash = hash_source(source_key)

    db.flush()
    return lead
