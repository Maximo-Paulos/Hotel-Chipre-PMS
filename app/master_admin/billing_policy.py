from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .models import MasterBillingPolicy


DEFAULT_POLICY_KEY = "default"
DEFAULT_POLICY = {
    "enabled": True,
    "allow_active": True,
    "allow_trialing": True,
    "allow_demo": True,
    "allow_comped": True,
    "allow_past_due_grace": False,
    "exempt_hotel_ids": [],
    "notes": None,
}


@dataclass
class BillingDecision:
    can_write: bool
    reason: str
    status: str
    plan: str
    hotel_id: int
    exempt: bool
    policy: dict[str, Any]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_policy_row(db: Session) -> MasterBillingPolicy | None:
    return db.query(MasterBillingPolicy).filter(MasterBillingPolicy.policy_key == DEFAULT_POLICY_KEY).first()


def _parse_hotel_ids(value: str | None) -> list[int]:
    if not value:
        return []
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return []
    result: list[int] = []
    for item in raw if isinstance(raw, list) else []:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            result.append(parsed)
    return sorted(set(result))


def get_policy_payload(db: Session) -> dict[str, Any]:
    policy = _get_policy_row(db)
    if not policy:
        return {
            "policy_key": DEFAULT_POLICY_KEY,
            **DEFAULT_POLICY,
            "updated_at": None,
            "updated_by_user_id": None,
        }
    return {
        "policy_key": policy.policy_key,
        "enabled": policy.enabled,
        "allow_active": policy.allow_active,
        "allow_trialing": policy.allow_trialing,
        "allow_demo": policy.allow_demo,
        "allow_comped": policy.allow_comped,
        "allow_past_due_grace": policy.allow_past_due_grace,
        "exempt_hotel_ids": _parse_hotel_ids(policy.exempt_hotel_ids_json),
        "notes": policy.notes,
        "updated_at": policy.updated_at,
        "updated_by_user_id": policy.updated_by_user_id,
    }


def update_policy(db: Session, payload: dict[str, Any], actor_user_id: int | None = None) -> dict[str, Any]:
    policy = _get_policy_row(db)
    if not policy:
        policy = MasterBillingPolicy(
            policy_key=DEFAULT_POLICY_KEY,
            enabled=DEFAULT_POLICY["enabled"],
            allow_active=DEFAULT_POLICY["allow_active"],
            allow_trialing=DEFAULT_POLICY["allow_trialing"],
            allow_demo=DEFAULT_POLICY["allow_demo"],
            allow_comped=DEFAULT_POLICY["allow_comped"],
            allow_past_due_grace=DEFAULT_POLICY["allow_past_due_grace"],
            notes=DEFAULT_POLICY["notes"],
        )
        policy.exempt_hotel_ids_json = json.dumps([], ensure_ascii=True)
        db.add(policy)
    policy.enabled = bool(payload.get("enabled", policy.enabled))
    policy.allow_active = bool(payload.get("allow_active", policy.allow_active))
    policy.allow_trialing = bool(payload.get("allow_trialing", policy.allow_trialing))
    policy.allow_demo = bool(payload.get("allow_demo", policy.allow_demo))
    policy.allow_comped = bool(payload.get("allow_comped", policy.allow_comped))
    policy.allow_past_due_grace = bool(payload.get("allow_past_due_grace", policy.allow_past_due_grace))
    hotel_ids = []
    for raw in payload.get("exempt_hotel_ids", []):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            hotel_ids.append(parsed)
    policy.exempt_hotel_ids_json = json.dumps(sorted(set(hotel_ids)), ensure_ascii=True)
    policy.notes = payload.get("notes")
    policy.updated_by_user_id = actor_user_id
    policy.updated_at = _utcnow()
    db.flush()
    return get_policy_payload(db)


def evaluate_hotel_write_access(db: Session, hotel_id: int, snapshot: dict[str, Any] | None = None) -> BillingDecision:
    from app.services.subscription_entitlements import get_subscription_snapshot

    policy = get_policy_payload(db)
    snapshot = snapshot or get_subscription_snapshot(db, hotel_id)
    status = str(snapshot.get("status") or "suspended")
    plan = str(snapshot.get("plan") or "starter")
    can_write = bool(snapshot.get("can_write", False))
    exempt_hotel_ids = set(policy.get("exempt_hotel_ids") or [])
    exempt = hotel_id in exempt_hotel_ids

    if not policy["enabled"]:
        return BillingDecision(True, "policy_disabled", status, plan, hotel_id, exempt, policy)
    if exempt:
        return BillingDecision(True, "hotel_exempt", status, plan, hotel_id, exempt, policy)
    if status == "active" and policy["allow_active"]:
        return BillingDecision(True, "subscription_active", status, plan, hotel_id, exempt, policy)
    if status == "trialing" and policy["allow_trialing"]:
        return BillingDecision(True, "trial_allowed", status, plan, hotel_id, exempt, policy)
    if status == "demo" and policy["allow_demo"]:
        return BillingDecision(True, "demo_allowed", status, plan, hotel_id, exempt, policy)
    if status == "comped" and policy["allow_comped"]:
        return BillingDecision(True, "comped_allowed", status, plan, hotel_id, exempt, policy)
    if status == "past_due" and policy["allow_past_due_grace"] and snapshot.get("grace_until"):
        return BillingDecision(True, "grace_allowed", status, plan, hotel_id, exempt, policy)
    return BillingDecision(False, "billing_policy_block", status, plan, hotel_id, exempt, policy)
