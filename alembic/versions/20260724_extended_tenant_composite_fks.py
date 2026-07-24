"""Complete tenant-leading foreign keys outside the core booking domain.

The core migration hardens the most frequently written booking, payment,
cash, stock, and analytics relationships.  This follow-up covers the rest of
the hotel-scoped graph, including OTA, allocation, AI-assistant, laundry,
voucher, and operational-history records.

These constraints are deliberately added at the PostgreSQL boundary while
the ORM keeps its existing scalar relationships.  That avoids introducing
ambiguous SQLAlchemy join paths in legacy relationships while the database
still rejects a child row whose ``hotel_id`` differs from its parent.  SQLite
remains a local metadata-driven test dialect, so this migration is a no-op
there.

For legacy nullable scalar FKs whose old action was ``SET NULL``, the
composite constraint intentionally uses PostgreSQL's default ``NO ACTION``:
``hotel_id`` is required and cannot be nulled together with the child ID.
Application code must remove or re-home the dependent record explicitly.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_extended_tenant_composite_fks"
down_revision: Union[str, None] = "20260724_core_tenant_composite_fks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UNIQUE_TARGETS = (
    ("ai_assistant_sessions", "uq_ai_assistant_sessions_hotel_id_id"),
    ("allocation_policy_profiles", "uq_allocation_policy_profiles_hotel_id_id"),
    ("allocation_policy_versions", "uq_allocation_policy_versions_hotel_id_id"),
    ("allocation_runs", "uq_allocation_runs_hotel_id_id"),
    ("hotel_vouchers", "uq_hotel_vouchers_hotel_id_id"),
    ("laundry_batches", "uq_laundry_batches_hotel_id_id"),
    ("manual_override_reasons", "uq_manual_override_reasons_hotel_id_id"),
    ("ota_connections", "uq_ota_connections_hotel_id_id"),
    ("ota_reservation_links", "uq_ota_reservation_links_hotel_id_id"),
    ("ota_sync_jobs", "uq_ota_sync_jobs_hotel_id_id"),
    ("reservation_adjustments", "uq_reservation_adjustments_hotel_id_id"),
    ("room_movement_groups", "uq_room_movement_groups_hotel_id_id"),
    ("subscriptions", "uq_subscriptions_hotel_id_id"),
)


# ondelete is only retained where it is safe for a required tenant key.
# Nullable legacy SET NULL relationships intentionally use None; see module
# docstring for why a composite SET NULL would violate tenant integrity.
COMPOSITE_FKS = (
    ("ai_assistant_action_runs", "fk_ai_action_runs_hotel_session", ("hotel_id", "session_id"), "ai_assistant_sessions", ("hotel_id", "id"), "CASCADE"),
    ("ai_assistant_insights", "fk_ai_insights_hotel_session", ("hotel_id", "session_id"), "ai_assistant_sessions", ("hotel_id", "id"), "CASCADE"),
    ("ai_assistant_messages", "fk_ai_messages_hotel_session", ("hotel_id", "session_id"), "ai_assistant_sessions", ("hotel_id", "id"), "CASCADE"),
    ("allocation_policy_versions", "fk_alloc_policy_versions_hotel_profile", ("hotel_id", "profile_id"), "allocation_policy_profiles", ("hotel_id", "id"), "CASCADE"),
    ("daily_rates", "fk_daily_rates_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), "CASCADE"),
    ("llm_policy_suggestions", "fk_llm_policy_suggestions_hotel_profile", ("hotel_id", "profile_id"), "allocation_policy_profiles", ("hotel_id", "id"), None),
    ("ota_property_mappings", "fk_ota_property_mappings_hotel_connection", ("hotel_id", "connection_id"), "ota_connections", ("hotel_id", "id"), "CASCADE"),
    ("ota_sync_jobs", "fk_ota_sync_jobs_hotel_connection", ("hotel_id", "connection_id"), "ota_connections", ("hotel_id", "id"), None),
    ("price_periods", "fk_price_periods_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), "CASCADE"),
    ("subscription_events", "fk_subscription_events_hotel_subscription", ("hotel_id", "subscription_id"), "subscriptions", ("hotel_id", "id"), "CASCADE"),
    ("allocation_runs", "fk_allocation_runs_hotel_policy_version", ("hotel_id", "policy_version_id"), "allocation_policy_versions", ("hotel_id", "id"), None),
    ("laundry_items", "fk_laundry_items_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("laundry_items", "fk_laundry_items_hotel_batch", ("hotel_id", "batch_id"), "laundry_batches", ("hotel_id", "id"), "CASCADE"),
    ("ota_room_mappings", "fk_ota_room_mappings_hotel_product", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id"), "CASCADE"),
    ("ota_room_mappings", "fk_ota_room_mappings_hotel_category", ("hotel_id", "room_category_id"), "room_categories", ("hotel_id", "id"), "CASCADE"),
    ("ota_room_mappings", "fk_ota_room_mappings_hotel_connection", ("hotel_id", "connection_id"), "ota_connections", ("hotel_id", "id"), "CASCADE"),
    ("ota_sync_events", "fk_ota_sync_events_hotel_job", ("hotel_id", "job_id"), "ota_sync_jobs", ("hotel_id", "id"), "CASCADE"),
    ("room_blocks", "fk_room_blocks_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), "CASCADE"),
    ("room_state_events", "fk_room_state_events_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("ota_cancellation_rules", "fk_ota_cancellation_rules_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), "CASCADE"),
    ("ota_commission_rules", "fk_ota_commission_rules_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), None),
    ("ota_inventory_rules", "fk_ota_inventory_rules_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), "CASCADE"),
    ("ota_price_rules", "fk_ota_price_rules_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), "CASCADE"),
    ("ota_rate_plan_mappings", "fk_ota_rate_plan_mappings_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), "CASCADE"),
    ("ota_rate_plan_mappings", "fk_ota_rate_plan_mappings_hotel_connection", ("hotel_id", "connection_id"), "ota_connections", ("hotel_id", "id"), "CASCADE"),
    ("solver_metrics", "fk_solver_metrics_hotel_allocation_run", ("hotel_id", "allocation_run_id"), "allocation_runs", ("hotel_id", "id"), "CASCADE"),
    ("allocation_assignments", "fk_allocation_assignments_hotel_run", ("hotel_id", "allocation_run_id"), "allocation_runs", ("hotel_id", "id"), "CASCADE"),
    ("allocation_assignments", "fk_allocation_assignments_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("allocation_assignments", "fk_allocation_assignments_hotel_product", ("hotel_id", "sellable_product_id"), "sellable_products", ("hotel_id", "id"), None),
    ("allocation_assignments", "fk_allocation_assignments_hotel_room", ("hotel_id", "room_id"), "rooms", ("hotel_id", "id"), None),
    ("allocation_explanations", "fk_allocation_explanations_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("allocation_explanations", "fk_allocation_explanations_hotel_run", ("hotel_id", "allocation_run_id"), "allocation_runs", ("hotel_id", "id"), "CASCADE"),
    ("company_documents", "fk_company_documents_hotel_company", ("hotel_id", "company_id"), "companies", ("hotel_id", "id"), None),
    ("company_documents", "fk_company_documents_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("hotel_vouchers", "fk_hotel_vouchers_hotel_source_reservation", ("hotel_id", "source_reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("hotel_vouchers", "fk_hotel_vouchers_hotel_guest", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id"), None),
    ("manual_override_reasons", "fk_manual_override_reasons_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("ota_reservation_links", "fk_ota_reservation_links_hotel_rate_plan", ("hotel_id", "rate_plan_id"), "rate_plans", ("hotel_id", "id"), None),
    ("ota_reservation_links", "fk_ota_reservation_links_hotel_connection", ("hotel_id", "connection_id"), "ota_connections", ("hotel_id", "id"), None),
    ("ota_reservation_links", "fk_ota_reservation_links_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("ota_reservation_mappings", "fk_ota_reservation_mappings_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("pending_operational_actions", "fk_pending_actions_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("reservation_allocation_locks", "fk_reservation_locks_hotel_room", ("hotel_id", "locked_room_id"), "rooms", ("hotel_id", "id"), None),
    ("reservation_allocation_locks", "fk_reservation_locks_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("reservation_status_history", "fk_reservation_status_history_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("room_move_events", "fk_room_move_events_hotel_movement_group", ("hotel_id", "movement_group_id"), "room_movement_groups", ("hotel_id", "id"), None),
    ("room_move_events", "fk_room_move_events_hotel_to_room", ("hotel_id", "to_room_id"), "rooms", ("hotel_id", "id"), None),
    ("room_move_events", "fk_room_move_events_hotel_from_room", ("hotel_id", "from_room_id"), "rooms", ("hotel_id", "id"), None),
    ("room_move_events", "fk_room_move_events_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("waitlist_entries", "fk_waitlist_entries_hotel_category", ("hotel_id", "category_id"), "room_categories", ("hotel_id", "id"), "CASCADE"),
    ("waitlist_entries", "fk_waitlist_entries_hotel_guest", ("hotel_id", "guest_id"), "guests", ("hotel_id", "id"), "CASCADE"),
    ("waitlist_entries", "fk_waitlist_entries_hotel_promoted_reservation", ("hotel_id", "promoted_reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("llm_feedback_events", "fk_llm_feedback_events_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("llm_feedback_events", "fk_llm_feedback_events_hotel_override_reason", ("hotel_id", "manual_override_reason_id"), "manual_override_reasons", ("hotel_id", "id"), None),
    ("llm_feedback_events", "fk_llm_feedback_events_hotel_allocation_run", ("hotel_id", "allocation_run_id"), "allocation_runs", ("hotel_id", "id"), None),
    ("refund_requests", "fk_refund_requests_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("refund_requests", "fk_refund_requests_hotel_voucher", ("hotel_id", "voucher_id"), "hotel_vouchers", ("hotel_id", "id"), None),
    ("refund_requests", "fk_refund_requests_hotel_transaction", ("hotel_id", "original_transaction_id"), "transactions", ("hotel_id", "id"), None),
    ("reservation_adjustments", "fk_reservation_adjustments_hotel_resulting_reservation", ("hotel_id", "resulting_reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("reservation_adjustments", "fk_reservation_adjustments_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
    ("reservation_adjustments", "fk_reservation_adjustments_hotel_ota_link", ("hotel_id", "ota_reservation_link_id"), "ota_reservation_links", ("hotel_id", "id"), None),
    ("voucher_redemptions", "fk_voucher_redemptions_hotel_voucher", ("hotel_id", "voucher_id"), "hotel_vouchers", ("hotel_id", "id"), "CASCADE"),
    ("voucher_redemptions", "fk_voucher_redemptions_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), None),
    ("billing_adjustments", "fk_billing_adjustments_hotel_reservation_adjustment", ("hotel_id", "reservation_adjustment_id"), "reservation_adjustments", ("hotel_id", "id"), None),
    ("billing_adjustments", "fk_billing_adjustments_hotel_reservation", ("hotel_id", "reservation_id"), "reservations", ("hotel_id", "id"), "CASCADE"),
)


def _has_unique(inspector, table_name: str, columns: tuple[str, ...]) -> bool:
    wanted = list(columns)
    return any(item.get("column_names") == wanted for item in inspector.get_unique_constraints(table_name)) or any(
        item.get("unique") and item.get("column_names") == wanted
        for item in inspector.get_indexes(table_name)
    )


def _has_fk(inspector, table_name: str, columns: tuple[str, ...], referred_table: str, referred_columns: tuple[str, ...]) -> bool:
    return any(
        item.get("constrained_columns") == list(columns)
        and item.get("referred_table") == referred_table
        and item.get("referred_columns") == list(referred_columns)
        for item in inspector.get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table_name, constraint_name in UNIQUE_TARGETS:
        if not _has_unique(inspector, table_name, ("hotel_id", "id")):
            op.create_unique_constraint(constraint_name, table_name, ["hotel_id", "id"])

    for table_name, constraint_name, columns, referred_table, referred_columns, ondelete in COMPOSITE_FKS:
        if _has_fk(inspector, table_name, columns, referred_table, referred_columns):
            continue
        kwargs = {"ondelete": ondelete} if ondelete else {}
        op.create_foreign_key(
            constraint_name,
            table_name,
            referred_table,
            list(columns),
            list(referred_columns),
            **kwargs,
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    inspector = sa.inspect(bind)
    for table_name, constraint_name, columns, referred_table, referred_columns, _ in reversed(COMPOSITE_FKS):
        for item in inspector.get_foreign_keys(table_name):
            if (
                item.get("name") == constraint_name
                and item.get("constrained_columns") == list(columns)
                and item.get("referred_table") == referred_table
                and item.get("referred_columns") == list(referred_columns)
            ):
                op.drop_constraint(constraint_name, table_name, type_="foreignkey")
                break

    inspector = sa.inspect(bind)
    for table_name, constraint_name in reversed(UNIQUE_TARGETS):
        if any(item.get("name") == constraint_name for item in inspector.get_unique_constraints(table_name)):
            op.drop_constraint(constraint_name, table_name, type_="unique")
