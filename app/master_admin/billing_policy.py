from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import MetaData, Table, select
from sqlalchemy.orm import Session

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


def _policy_table(db: Session) -> Table | None:
    bind = db.get_bind()
    if bind is None:
        return None
    try:
        return Table("master_billing_policies", MetaData(), autoload_with=bind)
    except Exception:
        return None


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
    table = _policy_table(db)
    if table is None:
        return {
            "policy_key": DEFAULT_POLICY_KEY,
            **DEFAULT_POLICY,
            "updated_at": None,
            "updated_by_user_id": None,
        }
    row = db.execute(select(table).where(table.c.policy_key == DEFAULT_POLICY_KEY).limit(1)).mappings().first()
    if not row:
        return {
            "policy_key": DEFAULT_POLICY_KEY,
            **DEFAULT_POLICY,
            "updated_at": None,
            "updated_by_user_id": None,
        }
    policy = dict(row)
    return {
        "policy_key": str(policy.get("policy_key") or DEFAULT_POLICY_KEY),
        "enabled": bool(policy.get("enabled", DEFAULT_POLICY["enabled"])),
        "allow_active": bool(policy.get("allow_active", DEFAULT_POLICY["allow_active"])),
        "allow_trialing": bool(policy.get("allow_trialing", DEFAULT_POLICY["allow_trialing"])),
        "exempt_hotel_ids": _parse_hotel_ids(policy.get("exempt_hotel_ids_json")),
        "exempt_user_ids": _parse_user_ids(policy.get("exempt_user_ids_json")),
        "notes": policy.get("notes"),
        "updated_at": policy.get("updated_at"),
        "updated_by_user_id": policy.get("updated_by_user_id"),
    }


def update_policy(db: Session, payload: dict[str, Any], actor_user_id: int | None = None) -> dict[str, Any]:
    table = _policy_table(db)
    if table is None:
        return {
            "policy_key": DEFAULT_POLICY_KEY,
            **DEFAULT_POLICY,
            "updated_at": None,
            "updated_by_user_id": actor_user_id,
        }

    existing = db.execute(select(table).where(table.c.policy_key == DEFAULT_POLICY_KEY).limit(1)).mappings().first()
    current = dict(existing) if existing else {}

    enabled = bool(payload.get("enabled", current.get("enabled", DEFAULT_POLICY["enabled"])))
    allow_active = bool(payload.get("allow_active", current.get("allow_active", DEFAULT_POLICY["allow_active"])))
    allow_trialing = bool(payload.get("allow_trialing", current.get("allow_trialing", DEFAULT_POLICY["allow_trialing"])))
    hotel_ids = []
    for raw in payload.get("exempt_hotel_ids", []):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            hotel_ids.append(parsed)
    exempt_hotel_ids_json = json.dumps(sorted(set(hotel_ids)), ensure_ascii=True)
    user_ids = []
    for raw in payload.get("exempt_user_ids", []):
        try:
            parsed = int(raw)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            user_ids.append(parsed)
    exempt_user_ids_json = json.dumps(sorted(set(user_ids)), ensure_ascii=True)
    notes = payload.get("notes")
    now = _utcnow()

    values: dict[str, Any] = {
        "policy_key": DEFAULT_POLICY_KEY,
        "enabled": enabled,
        "allow_active": allow_active,
        "allow_trialing": allow_trialing,
        "notes": notes,
        "updated_by_user_id": actor_user_id,
        "updated_at": now,
    }
    insert_values = dict(values)
    insert_values["created_at"] = current.get("created_at") or now
    if "allow_demo" in table.c:
        values["allow_demo"] = bool(current.get("allow_demo", DEFAULT_POLICY.get("allow_active", True)))
        insert_values["allow_demo"] = values["allow_demo"]
    if "allow_comped" in table.c:
        values["allow_comped"] = bool(current.get("allow_comped", DEFAULT_POLICY.get("allow_active", True)))
        insert_values["allow_comped"] = values["allow_comped"]
    if "allow_past_due_grace" in table.c:
        values["allow_past_due_grace"] = bool(current.get("allow_past_due_grace", False))
        insert_values["allow_past_due_grace"] = values["allow_past_due_grace"]
    if "exempt_hotel_ids_json" in table.c:
        values["exempt_hotel_ids_json"] = exempt_hotel_ids_json
        insert_values["exempt_hotel_ids_json"] = exempt_hotel_ids_json
    if "exempt_user_ids_json" in table.c:
        values["exempt_user_ids_json"] = exempt_user_ids_json
        insert_values["exempt_user_ids_json"] = exempt_user_ids_json

    if existing:
        db.execute(
            table.update().where(table.c.policy_key == DEFAULT_POLICY_KEY).values(**values)
        )
    else:
        db.execute(table.insert().values(**insert_values))
    db.flush()
    return {
        "policy_key": DEFAULT_POLICY_KEY,
        "enabled": enabled,
        "allow_active": allow_active,
        "allow_trialing": allow_trialing,
        "exempt_hotel_ids": sorted(set(hotel_ids)),
        "exempt_user_ids": sorted(set(user_ids)),
        "notes": notes,
        "updated_at": now,
        "updated_by_user_id": actor_user_id,
    }


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
