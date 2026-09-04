"""Tenant-scoped realtime domain events backed by Redis/Valkey pub/sub.

Postgres remains the source of truth. These events are only invalidation
signals: consumers must refetch the authoritative API representation.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Mapping, TYPE_CHECKING

import redis
from sqlalchemy import func

from app.config import get_settings
from app.infrastructure.redis_backend import get_sync_redis_client, namespaced_key
from app.models.domain_event_outbox import DomainEventOutbox
from app.services.tenant_context import set_tenant_hotel_context


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

EVENT_CHANNEL_TEMPLATE = "hotel:{hotel_id}:events"
REVISION_KEY_TEMPLATE = "hotel:{hotel_id}:revision:{domain}"
EVENT_NAME = "domain_change"
PENDING_EVENTS_KEY = "_hotel_pms_pending_domain_events"

# Exponential backoff base for outbox replay (worker/Celery retries), in
# seconds: attempt 1 waits this long, attempt 2 waits 2x, attempt 3 4x, etc.
OUTBOX_RETRY_BASE_SECONDS = 5
OUTBOX_RETRY_MAX_SECONDS = 15 * 60
OUTBOX_MAX_ATTEMPTS = 8
RECOVERY_MAX_ROWS = 500
POSTGRES_FALLBACK_BATCH_SIZE = 100
# The normal poll leaves most of the ten-second freshness budget for the
# network hop and authoritative refetch after an invalidation arrives.
POSTGRES_FALLBACK_DEFAULT_POLL_SECONDS = 2.0
# Even a direct caller that bypasses Settings must leave room for the client
# refetch and network latency inside the ten-second freshness budget.
POSTGRES_FALLBACK_MAX_POLL_SECONDS = 5.0
SUPPORTED_DOMAINS = frozenset(
    {
        "analytics",
        "cash",
        "guests",
        "notifications",
        "onboarding",
        "payments",
        "reservations",
        "rooms",
        "security",
        "settings",
        "stock",
        "users",
    }
)

# Event payloads are deliberately identifiers and operational metadata only.
# Guest contact data, credentials, tokens, and payment proofs never belong in
# Redis pub/sub messages.
SAFE_PAYLOAD_KEYS = frozenset(
    {
        "action_id",
        "adjustment_id",
        "allocation_id",
        "assignment_id",
        "audit_id",
        "block_id",
        "category_id",
        "close_report_id",
        "company_id",
        "connection_id",
        "document_id",
        "event_id",
        "export_id",
        "family",
        "group_id",
        "guest_id",
        "handoff_id",
        "item_id",
        "linen_item_id",
        "link_id",
        "location_id",
        "mapping_id",
        "movement_id",
        "payment_id",
        "payment_link_id",
        "proof_id",
        "redemption_id",
        "reservation_id",
        "restriction_id",
        "room_id",
        "run_id",
        "session_id",
        "source",
        "status",
        "status_history_id",
        "transaction_id",
        "user_id",
        "vendor_id",
        "voucher_id",
    }
)


class RealtimeEventsUnavailable(RuntimeError):
    """Raised when a required Redis/Valkey realtime backend is unavailable."""


@dataclass(frozen=True)
class DomainEvent:
    hotel_id: int
    domain: str
    event_type: str
    revision: int
    occurred_at: str
    payload: dict[str, Any]
    event_id: str | None = None
    schema_version: int = 1
    cursor: int | None = None

    def __post_init__(self) -> None:
        if not self.event_id:
            object.__setattr__(self, "event_id", str(uuid.uuid4()))

    @property
    def channel(self) -> str:
        return channel_for_hotel(self.hotel_id)

    def as_payload(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "hotel_id": self.hotel_id,
            "domain": self.domain,
            "event_type": self.event_type,
            "revision": self.revision,
            "cursor": self.cursor,
            "occurred_at": self.occurred_at,
            "payload": dict(self.payload),
        }


@dataclass(frozen=True)
class QueuedDomainChange:
    """A safe invalidation signal waiting for the surrounding DB commit."""

    hotel_id: int
    domain: str
    event_type: str
    payload: dict[str, Any]
    transaction_id: int | None = None
    # The durable outbox row inserted in the same (still-open) transaction as
    # the business change. Set by ``queue_domain_change``; the after-commit
    # fast path reads its id to record its own publish attempt.
    outbox: DomainEventOutbox | None = None


# A single ORM transaction can update several read models. Mapping the
# persisted model once here avoids depending on every API route remembering to
# publish all of its downstream domains. Tables not in this allowlist are
# intentionally ignored, especially credentials, sessions, blobs and global
# catalog tables.
MODEL_DOMAIN_DEPENDENCIES: dict[str, tuple[str, ...]] = {
    "reservations": ("reservations", "analytics"),
    "reservation_adjustments": ("reservations", "analytics"),
    "reservation_status_history": ("reservations", "analytics"),
    "billing_adjustments": ("reservations", "payments", "analytics"),
    "room_move_events": ("reservations", "rooms", "analytics"),
    "room_movement_groups": ("reservations", "rooms", "analytics"),
    "pending_operational_actions": ("reservations", "analytics"),
    "waitlist_entries": ("reservations", "analytics"),
    "guest_room_avoidance": ("reservations", "rooms", "analytics"),
    "ota_reservation_mappings": ("reservations", "analytics"),
    "ota_reservation_links": ("reservations", "analytics"),
    "ota_sync_events": ("reservations", "analytics"),
    "allocation_assignments": ("reservations", "rooms", "analytics"),
    "reservation_allocation_locks": ("reservations", "rooms", "analytics"),
    "transactions": ("payments", "cash", "analytics"),
    "payments": ("payments", "analytics"),
    "payment_links": ("payments", "reservations", "analytics"),
    "payment_proofs": ("payments", "reservations", "analytics"),
    "payment_webhook_events": ("payments", "analytics"),
    "refund_requests": ("payments", "cash", "analytics"),
    "hotel_vouchers": ("payments", "analytics"),
    "voucher_redemptions": ("payments", "analytics"),
    "payment_link_tests": ("payments", "analytics"),
    "payment_surcharges": ("payments", "settings", "analytics"),
    "cash_sessions": ("cash", "analytics"),
    "cash_movements": ("cash", "payments", "analytics"),
    "cash_close_reports": ("cash", "analytics"),
    "cash_custody_handoffs": ("cash", "analytics"),
    "guests": ("guests", "reservations", "analytics"),
    "guest_companions": ("guests", "reservations", "analytics"),
    "guest_tags": ("guests", "analytics"),
    # Guest restrictions use a service-level event with a stable event type;
    # the service queues it explicitly so the generic ORM collector does not
    # publish a duplicate signal for the same restriction transition.
    "rooms": ("rooms", "reservations", "analytics"),
    "room_categories": ("rooms", "reservations", "analytics"),
    "room_blocks": ("rooms", "reservations", "analytics"),
    "room_state_events": ("rooms", "analytics"),
    "daily_rates": ("rooms", "analytics"),
    "price_periods": ("rooms", "analytics"),
    "category_pricing_legacy": ("rooms", "analytics"),
    "stock_items": ("stock", "analytics"),
    "stock_locations": ("stock", "analytics"),
    "stock_movements": ("stock", "analytics"),
    "linen_items": ("stock", "analytics"),
    "linen_locations": ("stock", "analytics"),
    "linen_movements": ("stock", "analytics"),
    "laundry_batches": ("stock", "analytics"),
    "laundry_items": ("stock", "analytics"),
    "laundry_vendors": ("stock", "analytics"),
    "laundry_vendor_prices": ("stock", "analytics"),
    "laundry_remitos": ("stock", "analytics"),
    "laundry_remito_lines": ("stock", "analytics"),
    "laundry_vendor_settlements": ("stock", "cash", "analytics"),
    "hotel_configuration": ("settings", "analytics"),
    "companies": ("settings", "analytics"),
    "company_documents": ("settings", "analytics"),
    "promotions": ("settings", "analytics"),
    "integration_connections": ("settings",),
    "integration_events": ("settings", "analytics"),
    "subscriptions": ("settings",),
    "hotel_subscriptions": ("settings",),
    "subscription_entitlements": ("settings",),
    "hotel_entitlement_overrides": ("settings",),
    "hotel_api_keys": ("settings",),
    "onboarding_state": ("onboarding", "settings"),
    "users": ("users", "security"),
    "hotel_memberships": ("users", "security"),
    "staff_invitations": ("users", "security"),
    "user_permission_overrides": ("security", "users"),
    "hotel_permission_overrides": ("security", "settings"),
    "hotel_role_visibility_window": ("security", "settings"),
    "temporary_action_grants": ("security", "users"),
    "notification_preferences": ("notifications", "settings"),
    "notifications": ("notifications",),
    "notification_outbox": ("notifications",),
    "daily_report_schedules": ("notifications", "settings", "analytics"),
    # Allocation and AI read models. Their prompts, explanations and numeric
    # scores are deliberately not copied into the event payload; the event is
    # only a tenant-scoped cache invalidation signal.
    "ai_assistant_action_runs": ("analytics",),
    "ai_assistant_insights": ("analytics",),
    "ai_assistant_messages": ("analytics",),
    "ai_assistant_sessions": ("analytics",),
    "allocation_explanations": ("reservations", "rooms", "analytics"),
    "allocation_policy_profiles": ("settings", "rooms", "reservations", "analytics"),
    "allocation_policy_versions": ("settings", "rooms", "reservations", "analytics"),
    "allocation_runs": ("reservations", "rooms", "analytics"),
    "analytics_ai_usage_monthly": ("analytics",),
    "analytics_alert_settings": ("settings", "analytics"),
    "analytics_alert_snoozes": ("analytics",),
    "analytics_export_jobs": ("analytics",),
    "audit_logs": ("security", "analytics"),
    "fact_reservation_daily": ("analytics",),
    "fact_room_occupancy_daily": ("analytics",),
    "fx_policies": ("settings", "rooms", "reservations", "analytics"),
    "fx_rate_snapshots": ("settings", "analytics"),
    "hotel_audit_events": ("security", "analytics"),
    "llm_feedback_events": ("analytics",),
    "llm_policy_suggestions": ("settings", "analytics"),
    "manual_override_reasons": ("reservations", "analytics"),
    # OTA configuration is safe to invalidate by identifier/status. Secret
    # credential tables remain intentionally absent from this registry.
    "ota_cancellation_rules": ("settings", "reservations", "analytics"),
    "ota_commission_rules": ("settings", "reservations", "analytics"),
    "ota_connections": ("settings",),
    "ota_currency_rates": ("settings", "analytics"),
    "ota_inventory_rules": ("settings", "rooms", "reservations", "analytics"),
    "ota_price_rules": ("settings", "rooms", "reservations", "analytics"),
    "ota_property_mappings": ("settings", "rooms", "reservations", "analytics"),
    "ota_rate_plan_mappings": ("settings", "rooms", "reservations", "analytics"),
    "ota_room_mappings": ("settings", "rooms", "reservations", "analytics"),
    "ota_sync_jobs": ("settings", "reservations", "analytics"),
    "product_room_compatibility": ("settings", "rooms", "reservations", "analytics"),
    "rate_plan_prices": ("settings", "rooms", "reservations", "analytics"),
    "rate_plans": ("settings", "rooms", "reservations", "analytics"),
    "security_audit_logs": ("security",),
    "sellable_products": ("settings", "rooms", "reservations", "analytics"),
    "solver_metrics": ("reservations", "rooms", "analytics"),
    "subscription_adjustments": ("settings",),
    "subscription_events": ("settings",),
    "tax_policies": ("settings", "rooms", "reservations", "analytics"),
    "tax_rules": ("settings", "rooms", "reservations", "analytics"),
}

# Fact tables can receive one row per stay/room day during a single write.
# They still need to wake analytics, but publishing one signal per row would
# create a needless Redis storm. Use a stable family event for those models.
DERIVED_ANALYTICS_MODEL_FAMILIES = {
    "fact_reservation_daily": "reservation_daily",
    "fact_room_occupancy_daily": "room_occupancy_daily",
    "analytics_ai_usage_monthly": "ai_usage_monthly",
}

_MODEL_ID_PAYLOAD_KEYS: dict[str, str] = {
    "reservations": "reservation_id",
    "reservation_adjustments": "adjustment_id",
    "reservation_status_history": "status_history_id",
    "billing_adjustments": "adjustment_id",
    "room_move_events": "movement_id",
    "room_movement_groups": "group_id",
    "pending_operational_actions": "action_id",
    "waitlist_entries": "action_id",
    "guest_room_avoidance": "action_id",
    "transactions": "transaction_id",
    "payments": "payment_id",
    "payment_links": "payment_link_id",
    "payment_proofs": "proof_id",
    "refund_requests": "action_id",
    "hotel_vouchers": "voucher_id",
    "voucher_redemptions": "redemption_id",
    "payment_link_tests": "action_id",
    "payment_surcharges": "action_id",
    "cash_sessions": "session_id",
    "cash_movements": "movement_id",
    "cash_close_reports": "close_report_id",
    "cash_custody_handoffs": "handoff_id",
    "rooms": "room_id",
    "room_categories": "category_id",
    "room_blocks": "block_id",
    "room_state_events": "action_id",
    "stock_items": "item_id",
    "stock_locations": "location_id",
    "stock_movements": "movement_id",
    "linen_items": "item_id",
    "linen_locations": "location_id",
    "linen_movements": "movement_id",
    "laundry_vendors": "vendor_id",
    "laundry_vendor_prices": "action_id",
    "laundry_remitos": "action_id",
    "laundry_remito_lines": "action_id",
    "laundry_vendor_settlements": "action_id",
    "promotions": "action_id",
    "companies": "company_id",
    "company_documents": "document_id",
    "integration_connections": "connection_id",
    "integration_events": "action_id",
    "onboarding_state": "action_id",
    "users": "user_id",
    "hotel_memberships": "action_id",
    "staff_invitations": "action_id",
    "user_permission_overrides": "action_id",
    "hotel_permission_overrides": "action_id",
    "hotel_role_visibility_window": "action_id",
    "temporary_action_grants": "action_id",
    "notification_preferences": "action_id",
    "notifications": "action_id",
    "notification_outbox": "action_id",
    "daily_report_schedules": "action_id",
    "ai_assistant_action_runs": "action_id",
    "ai_assistant_insights": "action_id",
    "ai_assistant_messages": "action_id",
    "ai_assistant_sessions": "session_id",
    "allocation_explanations": "action_id",
    "allocation_policy_profiles": "action_id",
    "allocation_policy_versions": "action_id",
    "allocation_runs": "run_id",
    "analytics_ai_usage_monthly": "action_id",
    "analytics_alert_settings": "action_id",
    "analytics_alert_snoozes": "action_id",
    "analytics_export_jobs": "export_id",
    "audit_logs": "audit_id",
    "fact_reservation_daily": "action_id",
    "fact_room_occupancy_daily": "action_id",
    "fx_policies": "action_id",
    "fx_rate_snapshots": "action_id",
    "hotel_audit_events": "event_id",
    "llm_feedback_events": "event_id",
    "llm_policy_suggestions": "action_id",
    "manual_override_reasons": "action_id",
    "ota_cancellation_rules": "action_id",
    "ota_commission_rules": "action_id",
    "ota_connections": "connection_id",
    "ota_currency_rates": "action_id",
    "ota_inventory_rules": "action_id",
    "ota_price_rules": "action_id",
    "ota_property_mappings": "mapping_id",
    "ota_rate_plan_mappings": "mapping_id",
    "ota_room_mappings": "mapping_id",
    "ota_sync_jobs": "action_id",
    "product_room_compatibility": "action_id",
    "rate_plan_prices": "action_id",
    "rate_plans": "action_id",
    "security_audit_logs": "event_id",
    "sellable_products": "action_id",
    "solver_metrics": "action_id",
    "subscription_adjustments": "adjustment_id",
    "subscription_events": "event_id",
    "tax_policies": "action_id",
    "tax_rules": "action_id",
}


def _scalar_event_value(value: Any) -> str | int | float | bool | None:
    if hasattr(value, "value"):
        value = value.value
    return value if value is None or isinstance(value, (str, int, float, bool)) else None


def _model_hotel_id(model: Any, table_name: str) -> int | None:
    value = getattr(model, "hotel_id", None)
    # HotelConfiguration is keyed by hotel id rather than carrying a separate
    # hotel_id column. It is still safe to scope its event to that id.
    if value is None and table_name == "hotel_configuration":
        value = getattr(model, "id", None)
    if isinstance(value, int) and value > 0:
        return value
    return None


def _model_event_payload(model: Any, table_name: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    id_key = _MODEL_ID_PAYLOAD_KEYS.get(table_name)
    if id_key:
        value = _scalar_event_value(getattr(model, "id", None))
        if isinstance(value, int) and value > 0:
            payload[id_key] = value

    for attribute, payload_key in (
        ("reservation_id", "reservation_id"),
        ("guest_id", "guest_id"),
        ("room_id", "room_id"),
        ("category_id", "category_id"),
        ("item_id", "item_id"),
        ("location_id", "location_id"),
        ("group_id", "group_id"),
        ("session_id", "session_id"),
        ("transaction_id", "transaction_id"),
        ("vendor_id", "vendor_id"),
        ("linen_item_id", "linen_item_id"),
        ("company_id", "company_id"),
        ("movement_group_id", "group_id"),
    ):
        value = _scalar_event_value(getattr(model, attribute, None))
        if isinstance(value, int) and value > 0:
            payload[payload_key] = value

    status = _scalar_event_value(getattr(model, "status", None))
    if isinstance(status, (str, int, float, bool)):
        payload["status"] = status
    return validate_event_input(
        hotel_id=_model_hotel_id(model, table_name) or 1,
        domain="analytics",
        event_type="model.changed",
        payload=payload,
    )


def queue_model_changes(session: Any) -> None:
    """Collect safe domain signals from ORM writes before a transaction ends."""

    collections = (
        ("created", getattr(session, "new", ())),
        ("updated", getattr(session, "dirty", ())),
        ("deleted", getattr(session, "deleted", ())),
    )
    seen: set[tuple[int, str]] = set()
    for action, models in collections:
        for model in models:
            table_name = str(getattr(model, "__tablename__", "") or "")
            domains = MODEL_DOMAIN_DEPENDENCIES.get(table_name)
            hotel_id = _model_hotel_id(model, table_name)
            if not domains or not hotel_id or (id(model), action) in seen:
                continue
            seen.add((id(model), action))
            derived_family = DERIVED_ANALYTICS_MODEL_FAMILIES.get(table_name)
            if derived_family:
                event_type = "analytics.read_model.changed"
                payload = {"family": derived_family}
            else:
                event_type = f"{table_name}.{action}"
                payload = _model_event_payload(model, table_name)
            # A hard-deleted hotel_configuration row is the outbox's own FK
            # target: an outbox insert queued from its delete would only
            # reach the DB in a later flush pass, after that row (and its
            # CASCADE-linked outbox rows) are already gone, violating the FK.
            # There is also no tenant left to durably notify -- skip the
            # durable row but keep the best-effort live publish.
            durable = not (action == "deleted" and table_name == "hotel_configuration")
            for domain in domains:
                queue_domain_change(
                    session,
                    hotel_id=hotel_id,
                    domain=domain,
                    event_type=event_type,
                    payload=payload,
                    durable=durable,
                )


def queue_domain_change(
    session: "Session",
    *,
    hotel_id: int,
    domain: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    durable: bool = True,
) -> None:
    """Queue one tenant-scoped change for publication after commit.

    Services can call this as soon as they know a transaction changed. The
    event is held in ``Session.info`` so a rollback removes it and duplicate
    service/model notifications collapse before publication. This function
    never sends a payload containing amounts, PII, credentials or file bytes.

    A ``DomainEventOutbox`` row is added to ``session`` in the same breath, so
    it is inserted in the very same (still-open) transaction as the business
    change it describes -- if the process dies between this commit and the
    Redis publish, the row survives for a worker to replay. Pass
    ``durable=False`` to skip that row (best-effort live publish only) for the
    rare case where there is no tenant left to durably notify -- see
    ``queue_model_changes``'s hotel_configuration-delete handling.
    """

    normalized_payload = validate_event_input(
        hotel_id=hotel_id,
        domain=domain,
        event_type=event_type,
        payload=payload,
    )
    pending = session.info.setdefault(PENDING_EVENTS_KEY, {})
    dedupe_key = (
        hotel_id,
        domain.strip().lower(),
        event_type.strip(),
        json.dumps(normalized_payload, sort_keys=True, ensure_ascii=True, allow_nan=False),
    )
    if dedupe_key in pending:
        # Same logical event already queued (and its outbox row already
        # added) earlier in this transaction -- collapse duplicates.
        return

    outbox_row = None
    if durable:
        outbox_row = DomainEventOutbox(
            hotel_id=hotel_id,
            event_id=str(uuid.uuid4()),
            domain=domain.strip().lower(),
            event_type=event_type.strip(),
            payload=normalized_payload,
            schema_version=1,
            deduplication_key=f"{hotel_id}:{domain.strip().lower()}:{event_type.strip()}:{uuid.uuid4()}",
            status="pending",
        )
        session.add(outbox_row)
    pending[dedupe_key] = QueuedDomainChange(
        hotel_id=hotel_id,
        domain=domain.strip().lower(),
        event_type=event_type.strip(),
        payload=normalized_payload,
        transaction_id=_session_transaction_id(session),
        outbox=outbox_row,
    )


def publish_queued_domain_changes(session: "Session") -> None:
    """Publish committed signals without allowing Redis to break the request.

    This runs from ``Session`` ``after_commit`` (see ``app.database``), where
    ``session`` itself cannot safely issue new SQL -- so each queued change's
    durable outbox row (already committed as part of the transaction that
    just ended) is instead recorded through a short-lived, separate
    ``Session`` bound to the same engine. Already-loaded attributes on
    ``session``'s own objects (like ``outbox.id``) are still safe to read
    here: SQLAlchemy expires them only after ``after_commit`` listeners run.
    """

    pending = session.info.pop(PENDING_EVENTS_KEY, {})
    if not pending:
        return

    from sqlalchemy.orm import Session as _Session

    bind = session.get_bind()
    outbox_session = _Session(bind=bind) if bind is not None else None
    try:
        for change in pending.values():
            outbox = change.outbox
            outbox_id = outbox.id if outbox is not None else None
            try:
                publish_kwargs = {
                    "hotel_id": change.hotel_id,
                    "domain": change.domain,
                    "event_type": change.event_type,
                    "payload": change.payload,
                }
                if outbox is not None:
                    publish_kwargs.update(
                        event_id=outbox.event_id,
                        cursor=outbox.stream_cursor or outbox.id,
                        schema_version=outbox.schema_version or 1,
                    )
                event = publish_domain_event(**publish_kwargs)
                if event is None:
                    raise RealtimeEventsUnavailable("publish_domain_event returned no event")
                _record_outbox_attempt(
                    outbox_session, outbox_id, revision=event.revision, published=True
                )
            except Exception as exc:  # post-commit work must not turn 200 into 500
                logger.warning(
                    "realtime_events.post_commit_publish_failed",
                    extra={
                        "hotel_id": change.hotel_id,
                        "domain": change.domain,
                        "event_type": change.event_type,
                        "error_type": type(exc).__name__,
                    },
                )
                _record_outbox_attempt(
                    outbox_session, outbox_id, error=type(exc).__name__, published=False
                )
        if outbox_session is not None:
            outbox_session.commit()
    finally:
        if outbox_session is not None:
            outbox_session.close()


def _record_outbox_attempt(
    outbox_session: "Session | None",
    outbox_id: int | None,
    *,
    published: bool,
    revision: int | None = None,
    error: str | None = None,
) -> None:
    """Record one publish attempt on a durable outbox row, if it still exists."""

    if outbox_session is None or outbox_id is None:
        return
    row = outbox_session.get(DomainEventOutbox, outbox_id)
    if row is None:
        return
    row.attempts += 1
    if published:
        row.status = "published"
        row.revision = revision
        row.published_at = datetime.now(timezone.utc)
        row.last_error = None
        row.next_attempt_at = None
    else:
        row.last_error = error
        if row.attempts >= OUTBOX_MAX_ATTEMPTS:
            row.status = "dead_letter"
            row.dead_lettered_at = datetime.now(timezone.utc)
        else:
            row.status = "pending"
            # The after-commit fast path is already the first delivery
            # attempt. Leave its row immediately eligible so the next worker
            # sweep can recover a process/Redis failure without waiting for a
            # second in-memory timer; worker-originated failures apply the
            # exponential delay below.
            row.next_attempt_at = datetime.now(timezone.utc)


def discard_queued_domain_changes(session: "Session", transaction_id: int | None = None) -> None:
    """Drop signals from a rolled-back root or nested transaction."""

    if transaction_id is None:
        session.info.pop(PENDING_EVENTS_KEY, None)
        return
    pending = session.info.get(PENDING_EVENTS_KEY)
    if not isinstance(pending, dict):
        return
    remaining = {
        key: change
        for key, change in pending.items()
        if getattr(change, "transaction_id", None) != transaction_id
    }
    if remaining:
        session.info[PENDING_EVENTS_KEY] = remaining
    else:
        session.info.pop(PENDING_EVENTS_KEY, None)


def _session_transaction_id(session: "Session") -> int | None:
    """Identify the innermost SQLAlchemy transaction for rollback pruning."""

    get_nested_transaction = getattr(session, "get_nested_transaction", None)
    get_transaction = getattr(session, "get_transaction", None)
    nested_transaction = get_nested_transaction() if callable(get_nested_transaction) else None
    root_transaction = get_transaction() if callable(get_transaction) else None
    transaction = nested_transaction or root_transaction
    return id(transaction) if transaction is not None else None


def _settings():
    return get_settings()


def channel_for_hotel(hotel_id: int) -> str:
    _validate_hotel_id(hotel_id)
    return namespaced_key(EVENT_CHANNEL_TEMPLATE.format(hotel_id=hotel_id))


def revision_key_for_hotel(hotel_id: int, domain: str) -> str:
    _validate_hotel_id(hotel_id)
    if domain not in SUPPORTED_DOMAINS:
        raise ValueError("Unsupported domain")
    return namespaced_key(REVISION_KEY_TEMPLATE.format(hotel_id=hotel_id, domain=domain))


def validate_event_input(
    *,
    hotel_id: int,
    domain: str,
    event_type: str,
    payload: Mapping[str, Any] | None,
) -> dict[str, Any]:
    _validate_hotel_id(hotel_id)
    normalized_domain = str(domain or "").strip().lower()
    if normalized_domain not in SUPPORTED_DOMAINS:
        raise ValueError("Unsupported domain")
    normalized_type = str(event_type or "").strip()
    if not normalized_type or len(normalized_type) > 100 or any(char.isspace() for char in normalized_type):
        raise ValueError("Event type must be non-empty and contain no whitespace")

    normalized_payload = dict(payload or {})
    unknown_keys = set(normalized_payload) - SAFE_PAYLOAD_KEYS
    if unknown_keys:
        raise ValueError("Unsupported payload key: " + ", ".join(sorted(unknown_keys)))
    for key, value in normalized_payload.items():
        if isinstance(value, (dict, list, tuple, set)):
            raise ValueError(f"Payload value for {key} must be scalar")
        if value is not None and not isinstance(value, (str, int, float, bool)):
            raise ValueError(f"Payload value for {key} must be JSON scalar")
    json.dumps(normalized_payload, ensure_ascii=True, allow_nan=False)
    return normalized_payload


def _validate_hotel_id(hotel_id: int) -> None:
    if not isinstance(hotel_id, int) or hotel_id <= 0:
        raise ValueError("hotel_id must be a positive integer")


def _get_redis_client() -> redis.Redis | None:
    settings = _settings()
    if not bool(getattr(settings, "REALTIME_EVENTS_ENABLED", True)):
        return None
    try:
        return get_sync_redis_client(capability="realtime")
    except Exception as exc:  # pragma: no cover - defensive config fallback
        logger.warning("realtime_events.redis_unavailable", extra={"error_type": type(exc).__name__})
        return None


def _required() -> bool:
    return bool(_settings().DISTRIBUTED_LOCK_REQUIRED)


def _unavailable(message: str, exc: Exception | None = None):
    if _required():
        raise RealtimeEventsUnavailable(message) from exc
    logger.warning("realtime_events.degraded", extra={"error": message})


def publish_domain_event(
    *,
    hotel_id: int,
    domain: str,
    event_type: str,
    payload: Mapping[str, Any] | None = None,
    client: redis.Redis | None = None,
    revision: int | None = None,
    occurred_at: datetime | str | None = None,
    event_id: str | None = None,
    cursor: int | None = None,
    schema_version: int = 1,
) -> DomainEvent | None:
    """Publish one event. ``revision``/``occurred_at`` let an outbox replay
    reuse the values already stored on a durable row instead of minting a new
    Redis revision or "now" timestamp on every retry; omit both for the
    normal first-attempt path (revision is a fresh Redis INCR, occurred_at is
    now)."""
    normalized_payload = validate_event_input(
        hotel_id=hotel_id,
        domain=domain,
        event_type=event_type,
        payload=payload,
    )
    if not bool(getattr(_settings(), "REALTIME_EVENTS_ENABLED", True)):
        return None
    redis_client = client or _get_redis_client()
    if redis_client is None:
        _unavailable("Redis/Valkey realtime backend is unavailable")
        return None

    try:
        resolved_revision = (
            int(revision) if revision else int(redis_client.incr(revision_key_for_hotel(hotel_id, domain)))
        )
        resolved_occurred_at = (
            occurred_at.isoformat() if isinstance(occurred_at, datetime) else occurred_at
        ) or datetime.now(timezone.utc).isoformat()
        event = DomainEvent(
            hotel_id=hotel_id,
            domain=domain.strip().lower(),
            event_type=event_type.strip(),
            revision=resolved_revision,
            occurred_at=resolved_occurred_at,
            payload=normalized_payload,
            event_id=event_id,
            schema_version=schema_version,
            cursor=cursor,
        )
        redis_client.publish(event.channel, json.dumps(event.as_payload(), ensure_ascii=True, allow_nan=False))
        return event
    except Exception as exc:
        _unavailable("Redis/Valkey realtime publish failed", exc)
        return None


def _outbox_backoff_seconds(attempts: int) -> int:
    """Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt."""
    return min(OUTBOX_RETRY_MAX_SECONDS, OUTBOX_RETRY_BASE_SECONDS * (2 ** max(attempts - 1, 0)))


def publish_pending_domain_events(
    db: "Session",
    *,
    hotel_id: int,
    batch_size: int = 100,
) -> dict[str, Any]:
    """Drain durable outbox rows for one tenant onto Redis/Valkey.

    Used both by the after-commit fast path's own worker retries and by the
    periodic Celery task (``app.tasks.domain_event_tasks.publish_outbox``).
    Scoped to a single hotel per call so one stuck tenant never blocks
    another; on PostgreSQL the selecting query also takes
    ``FOR UPDATE SKIP LOCKED`` so concurrent workers never double-publish the
    same row. Does not commit -- the caller controls the transaction
    boundary (matching this codebase's other outbox worker, ``app.services.
    notification_service.process_pending_outbox``).
    """

    _validate_hotel_id(hotel_id)

    query = (
        db.query(DomainEventOutbox)
        .filter(
            DomainEventOutbox.hotel_id == hotel_id,
            DomainEventOutbox.published_at.is_(None),
            DomainEventOutbox.status != "dead_letter",
            (DomainEventOutbox.next_attempt_at.is_(None) | (DomainEventOutbox.next_attempt_at <= datetime.now(timezone.utc))),
        )
        .order_by(DomainEventOutbox.id.asc())
        .limit(max(batch_size, 1))
    )
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    rows = query.all()

    published = 0
    failed = 0
    retry_after_seconds: int | None = None

    for row in rows:
        try:
            # SQLite drops tzinfo on round-trip (unlike DateTime(timezone=True)
            # under PostgreSQL); the stored instant is always UTC either way.
            row_occurred_at = row.occurred_at
            if row_occurred_at is not None and row_occurred_at.tzinfo is None:
                row_occurred_at = row_occurred_at.replace(tzinfo=timezone.utc)
            event = publish_domain_event(
                hotel_id=row.hotel_id,
                domain=row.domain,
                event_type=row.event_type,
                payload=row.payload,
                revision=row.revision,
                occurred_at=row_occurred_at,
                event_id=row.event_id,
                cursor=row.stream_cursor or row.id,
                schema_version=row.schema_version or 1,
            )
            if event is None:
                raise RealtimeEventsUnavailable("publish_domain_event returned no event")
            row.attempts += 1
            row.status = "published"
            row.revision = event.revision
            row.published_at = datetime.now(timezone.utc)
            row.last_error = None
            row.next_attempt_at = None
            published += 1
        except Exception as exc:
            row.attempts += 1
            row.last_error = f"publish_failed:{type(exc).__name__}"
            if row.attempts >= OUTBOX_MAX_ATTEMPTS:
                row.status = "dead_letter"
                row.dead_lettered_at = datetime.now(timezone.utc)
            else:
                row.status = "pending"
                row.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                    seconds=_outbox_backoff_seconds(row.attempts)
                )
            failed += 1
            backoff = _outbox_backoff_seconds(row.attempts)
            retry_after_seconds = backoff if retry_after_seconds is None else min(retry_after_seconds, backoff)

    return {
        "selected": len(rows),
        "published": published,
        "failed": failed,
        "retry_after_seconds": retry_after_seconds,
    }


def get_domain_event_outbox_metrics(
    db: "Session",
    *,
    hotel_id: int,
    now: datetime | None = None,
    stale_after_seconds: float = 300.0,
) -> dict[str, Any]:
    """Report pending-outbox depth/age for one tenant; warn when stale.

    "Stale" means the oldest still-unpublished row is older than
    ``stale_after_seconds`` -- a signal the fast path and the periodic
    worker are both failing (or not running) for this hotel.
    """

    _validate_hotel_id(hotel_id)
    now = now or datetime.now(timezone.utc)

    pending_rows = (
        db.query(DomainEventOutbox)
        .filter(
            DomainEventOutbox.hotel_id == hotel_id,
            DomainEventOutbox.published_at.is_(None),
        )
        .all()
    )
    pending_count = len(pending_rows)
    oldest_age_seconds = 0.0
    if pending_rows:
        oldest_occurred_at = min(row.occurred_at for row in pending_rows)
        if oldest_occurred_at.tzinfo is None:
            oldest_occurred_at = oldest_occurred_at.replace(tzinfo=timezone.utc)
        oldest_age_seconds = (now - oldest_occurred_at).total_seconds()

    stale = pending_count > 0 and oldest_age_seconds >= stale_after_seconds
    if stale:
        logger.warning(
            "realtime_events.outbox_stale",
            extra={
                "hotel_id": hotel_id,
                "pending_count": pending_count,
                "oldest_age_seconds": oldest_age_seconds,
            },
        )

    return {
        "pending_count": pending_count,
        "oldest_age_seconds": oldest_age_seconds,
        "stale": stale,
    }


def get_domain_event_recovery(
    db: "Session",
    *,
    hotel_id: int,
    after_cursor: int | None = None,
) -> dict[str, Any]:
    """Return changed domains after a tenant-scoped outbox cursor.

    V2 rows use ``stream_cursor``; legacy rows fall back to ``id`` during the
    expand/backfill rollout. Both published and pending rows represent
    committed business changes, so neither is filtered out here. Only a cursor
    and domain are selected; event payloads never cross this contract.

    A missing/zero cursor, a cursor before the retained tenant rows, or more
    than ``RECOVERY_MAX_ROWS`` changes requires a full authoritative refetch.
    """

    _validate_hotel_id(hotel_id)
    if after_cursor is not None and after_cursor < 0:
        raise ValueError("after_cursor must be non-negative")

    cursor_value = func.coalesce(DomainEventOutbox.stream_cursor, DomainEventOutbox.id)
    latest_value = (
        db.query(func.max(cursor_value))
        .filter(DomainEventOutbox.hotel_id == hotel_id)
        .scalar()
    )
    oldest_value = (
        db.query(func.min(cursor_value))
        .filter(DomainEventOutbox.hotel_id == hotel_id)
        .scalar()
    )

    cursor = after_cursor or 0
    recovery_query = db.query(cursor_value.label("cursor"), DomainEventOutbox.domain).filter(
        DomainEventOutbox.hotel_id == hotel_id,
        cursor_value > cursor,
    )
    has_more = (
        recovery_query.order_by(cursor_value.asc())
        .offset(RECOVERY_MAX_ROWS)
        .limit(1)
        .first()
        is not None
    )
    rows = (
        recovery_query
        .order_by(cursor_value.asc())
        .limit(RECOVERY_MAX_ROWS)
        .all()
    )
    domains = sorted({str(domain) for _event_cursor, domain in rows if domain})

    reset_required = after_cursor in (None, 0)
    if (
        after_cursor is not None
        and after_cursor > 0
        and oldest_value is not None
        and after_cursor < int(oldest_value)
    ):
        reset_required = True
    if has_more:
        reset_required = True

    latest_cursor = max(after_cursor or 0, int(latest_value or 0))
    return {
        "latest_cursor": latest_cursor,
        "domains": domains,
        "reset_required": reset_required,
        "has_more": has_more,
    }


def get_realtime_client() -> redis.Redis | None:
    """Return a configured client after a bounded connectivity check."""

    if not bool(getattr(_settings(), "REALTIME_EVENTS_ENABLED", True)):
        return None
    client = _get_redis_client()
    if client is None:
        _unavailable("Redis/Valkey realtime backend is unavailable")
        return None
    try:
        client.ping()
    except Exception as exc:
        _unavailable("Redis/Valkey realtime backend is unavailable", exc)
        return None
    return client


def _outbox_sse_payload(row: DomainEventOutbox, cursor: int) -> dict[str, Any] | None:
    """Build a safe invalidation frame from a committed outbox row.

    The PostgreSQL fallback deliberately carries no business payload. Clients
    refetch the authoritative, tenant-scoped API representation after seeing
    the domain signal, just as they do for Redis messages.
    """

    try:
        domain = str(row.domain or "").strip().lower()
        event_type = str(row.event_type or "").strip()
        validate_event_input(
            hotel_id=int(row.hotel_id),
            domain=domain,
            event_type=event_type,
            payload={},
        )
        occurred_at = row.occurred_at
        if occurred_at is None:
            occurred_at_value = None
        elif isinstance(occurred_at, datetime):
            occurred_at_value = occurred_at.isoformat()
        else:
            occurred_at_value = str(occurred_at)
        return {
            "version": 1,
            "schema_version": int(row.schema_version or 1),
            "event_id": str(row.event_id),
            "hotel_id": int(row.hotel_id),
            "domain": domain,
            "event_type": event_type,
            "revision": int(row.revision or 0),
            "cursor": cursor,
            "occurred_at": occurred_at_value,
            "payload": {},
            "transport": "postgres-outbox",
        }
    except (TypeError, ValueError) as exc:
        # A malformed row must not take down every tenant's stream, and the
        # error log must not echo its payload or provider details.
        logger.warning(
            "realtime_events.invalid_outbox_row",
            extra={"row_id": getattr(row, "id", None), "error_type": type(exc).__name__},
        )
        return None


def iter_postgres_event_stream(
    hotel_id: int,
    *,
    after_cursor: int | None = None,
    poll_seconds: float = POSTGRES_FALLBACK_DEFAULT_POLL_SECONDS,
    authorization_check: Callable[[], bool] | None = None,
    authorization_revalidate_seconds: int = 60,
    session_factory: Callable[[], Any] | None = None,
) -> Iterable[str]:
    """Stream committed outbox invalidations when Redis is unavailable.

    Each poll uses a short-lived PostgreSQL session and closes it before a
    frame is yielded, so a long-lived SSE connection never pins a database
    connection. ``None`` means start after the current latest cursor; this is
    important for a first connection because the recovery endpoint has already
    refetched the current state. An explicit cursor replays rows after it.
    """

    _validate_hotel_id(hotel_id)
    if after_cursor is not None and after_cursor < 0:
        raise ValueError("after_cursor must be non-negative")
    if session_factory is None:
        from app.database import get_session_factory

        session_factory = get_session_factory()

    poll_delay = max(1.0, min(float(poll_seconds), POSTGRES_FALLBACK_MAX_POLL_SECONDS))
    cursor_value = func.coalesce(DomainEventOutbox.stream_cursor, DomainEventOutbox.id)
    cursor = int(after_cursor or 0)
    if after_cursor is None:
        initial_db = session_factory()
        try:
            set_tenant_hotel_context(initial_db, hotel_id)
            latest = (
                initial_db.query(func.max(cursor_value))
                .filter(DomainEventOutbox.hotel_id == hotel_id)
                .scalar()
            )
            cursor = int(latest or 0)
        finally:
            initial_db.close()

    last_authorization_check = time.monotonic()
    yield format_sse(
        {
            "schema_version": 2,
            "hotel_id": hotel_id,
            "status": "ready",
            "transport": "postgres-outbox",
            "cursor": cursor,
        },
        event_name="ready",
    )

    while True:
        now = time.monotonic()
        if (
            authorization_check
            and now - last_authorization_check >= max(1, authorization_revalidate_seconds)
        ):
            last_authorization_check = now
            try:
                authorized = authorization_check()
            except Exception as exc:  # pragma: no cover - fail closed on provider errors
                logger.warning(
                    "realtime_events.authorization_check_failed",
                    extra={"error_type": type(exc).__name__},
                )
                authorized = False
            if not authorized:
                yield format_sse(
                    {
                        "schema_version": 2,
                        "hotel_id": hotel_id,
                        "event_type": "authorization_lost",
                        "status": "reauthenticate",
                        "transport": "postgres-outbox",
                    },
                    event_name="control",
                )
                return

        rows: list[DomainEventOutbox] = []
        try:
            poll_db = session_factory()
            try:
                set_tenant_hotel_context(poll_db, hotel_id)
                rows = (
                    poll_db.query(DomainEventOutbox)
                    .filter(
                        DomainEventOutbox.hotel_id == hotel_id,
                        cursor_value > cursor,
                    )
                    .order_by(cursor_value.asc())
                    .limit(POSTGRES_FALLBACK_BATCH_SIZE)
                    .all()
                )
            finally:
                poll_db.close()
        except Exception as exc:  # pragma: no cover - provider/runtime failure
            logger.warning(
                "realtime_events.postgres_fallback_poll_failed",
                extra={"hotel_id": hotel_id, "error_type": type(exc).__name__},
            )

        if rows:
            for row in rows:
                row_cursor = int(row.stream_cursor or row.id)
                cursor = max(cursor, row_cursor)
                payload = _outbox_sse_payload(row, row_cursor)
                if payload is not None:
                    yield format_sse(payload)
            continue

        yield ": heartbeat\n\n"
        time.sleep(poll_delay)


def format_sse(payload: Mapping[str, Any], *, event_name: str = EVENT_NAME) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=True, allow_nan=False)
    if len(encoded.encode("utf-8")) > 4 * 1024:
        raise ValueError("SSE event exceeds 4 KiB")
    cursor = payload.get("cursor")
    event_id = payload.get("event_id")
    identifier = cursor if cursor is not None else event_id
    id_line = f"id: {identifier}\n" if identifier is not None else ""
    return f"{id_line}event: {event_name}\ndata: {encoded}\n\n"


def iter_event_stream(
    hotel_id: int,
    client: redis.Redis,
    *,
    heartbeat_seconds: int = 15,
    authorization_check: Callable[[], bool] | None = None,
    authorization_revalidate_seconds: int = 60,
) -> Iterable[str]:
    """Yield a tenant-scoped stream and close when membership is revoked."""

    pubsub = client.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(channel_for_hotel(hotel_id))
    last_authorization_check = time.monotonic()
    try:
        yield format_sse({"schema_version": 2, "hotel_id": hotel_id, "status": "ready"}, event_name="ready")
        while True:
            message = pubsub.get_message(timeout=heartbeat_seconds)
            if authorization_check and time.monotonic() - last_authorization_check >= max(1, authorization_revalidate_seconds):
                last_authorization_check = time.monotonic()
                try:
                    authorized = authorization_check()
                except Exception as exc:  # pragma: no cover - fail closed on DB/provider errors
                    logger.warning("realtime_events.authorization_check_failed", extra={"error_type": type(exc).__name__})
                    authorized = False
                if not authorized:
                    yield format_sse(
                        {
                            "schema_version": 2,
                            "hotel_id": hotel_id,
                            "event_type": "authorization_lost",
                            "status": "reauthenticate",
                        },
                        event_name="control",
                    )
                    return
            if message and message.get("type") == "message":
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                try:
                    payload = json.loads(raw_data)
                except (TypeError, json.JSONDecodeError):
                    logger.warning("realtime_events.invalid_message", extra={"hotel_id": hotel_id})
                    continue
                if isinstance(payload, dict) and payload.get("hotel_id") == hotel_id:
                    yield format_sse(payload)
            else:
                yield ": heartbeat\n\n"
    finally:
        try:
            pubsub.close()
        except Exception:  # pragma: no cover - best effort cleanup
            logger.debug("realtime_events.pubsub_close_failed", exc_info=True)
