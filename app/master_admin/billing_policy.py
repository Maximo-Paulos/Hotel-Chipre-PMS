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
    "exempt_hotel_ids": [],
    "exempt_user_ids": [],
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


def _parse_user_ids(value: str | None) -> list[int]:
    return _parse_hotel_ids(value)


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
        "exempt_hotel_ids": _parse_hotel_ids(policy.exempt_hotel_ids_json),
        "exempt_user_ids": _parse_user_ids(getattr(policy, "exempt_user_ids_json", "[]")),
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
            notes=DEFAULT_POLICY["notes"],
        )
        policy.exempt_hotel_ids_json = json.dumps([], ensure_ascii=True)
        policy.exempt_user_ids_json = json.dumps([], ensure_ascii=True)
        db.add(policy)
    policy.enabled = bool(payload.get("enabled", policy.enabled))
    policy.allow_active = bool(payload.get("allow_active", policy.allow_active))
    policy.allow_trialing = bool(payload.get("allow_trialing", policy.allow_trialing))
    hotel_ids = []
    for raw in payload.get("exempt_hotel_ids", []):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            hotel_ids.append(parsed)
    policy.exempt_hotel_ids_json = json.dumps(sorted(set(hotel_ids)), ensure_ascii=True)
    user_ids = []
    for raw in payload.get("exempt_user_ids", []):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            user_ids.append(parsed)
    policy.exempt_user_ids_json = json.dumps(sorted(set(user_ids)), ensure_ascii=True)
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
    exempt_hotel_ids = set(policy.get("exempt_hotel_ids") or [])
    exempt_user_ids = set(policy.get("exempt_user_ids") or [])
    exempt = hotel_id in exempt_hotel_ids
    user_id = snapshot.get("user_id")
    user_exempt = isinstance(user_id, int) and user_id in exempt_user_ids
    exempt = exempt or user_exempt

    if not policy["enabled"]:
        return BillingDecision(True, "policy_disabled", status, plan, hotel_id, exempt, policy)
    if exempt:
        return BillingDecision(True, "exempt", status, plan, hotel_id, exempt, policy)
    if status == "active" and policy["allow_active"]:
        return BillingDecision(True, "subscription_active", status, plan, hotel_id, exempt, policy)
    if status == "trialing" and policy["allow_trialing"]:
        return BillingDecision(True, "trial_allowed", status, plan, hotel_id, exempt, policy)
    if status == "comped" and snapshot.get("is_comped"):
        return BillingDecision(True, "subscription_active", status, plan, hotel_id, exempt, policy)
    return BillingDecision(False, "billing_policy_block", status, plan, hotel_id, exempt, policy)
