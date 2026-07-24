"""Enable PostgreSQL row-level tenant isolation.

Revision ID: 20260724_tenant_rls_context
Revises: 20260626_repair_reservation_unique_constraint
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260724_tenant_rls_context"
down_revision: Union[str, None] = "20260626_repair_reservation_unique_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Kept explicit so a future schema change cannot silently expand the RLS
# surface without a migration review.  The list was generated from the ORM
# metadata and reviewed against app/models; hotel_api_keys is intentionally
# excluded because the public API must resolve a bearer key before it knows
# which hotel context to set.  Its lookup is by a SHA-256 hash and never
# returns credentials for an unrelated request after authentication.
TENANT_TABLES: tuple[str, ...] = (
    "onboarding_state",
    "ai_assistant_sessions",
    "allocation_policy_profiles",
    "analytics_ai_usage_monthly",
    "analytics_alert_settings",
    "analytics_alert_snoozes",
    "analytics_export_jobs",
    "audit_logs",
    "cash_sessions",
    "companies",
    "fx_policies",
    "fx_rate_snapshots",
    "guests",
    "hotel_audit_events",
    "hotel_entitlement_overrides",
    "hotel_permission_overrides",
    "hotel_subscriptions",
    "integration_connections",
    "laundry_batches",
    "ota_connections",
    "ota_currency_rates",
    "ota_webhook_credentials",
    "payment_link_tests",
    "payment_surcharges",
    "room_categories",
    "room_movement_groups",
    "security_audit_logs",
    "stock_items",
    "stock_locations",
    "subscriptions",
    "tax_policies",
    "ai_assistant_action_runs",
    "ai_assistant_insights",
    "ai_assistant_messages",
    "allocation_policy_versions",
    "cash_close_reports",
    "daily_rates",
    "guest_tags",
    "llm_policy_suggestions",
    "ota_property_mappings",
    "ota_sync_jobs",
    "price_periods",
    "rooms",
    "sellable_products",
    "subscription_events",
    "tax_rules",
    "allocation_runs",
    "laundry_items",
    "ota_room_mappings",
    "ota_sync_events",
    "product_room_compatibility",
    "rate_plans",
    "room_blocks",
    "room_state_events",
    "ota_cancellation_rules",
    "ota_commission_rules",
    "ota_inventory_rules",
    "ota_price_rules",
    "ota_rate_plan_mappings",
    "rate_plan_prices",
    "reservations",
    "solver_metrics",
    "allocation_assignments",
    "allocation_explanations",
    "company_documents",
    "fact_reservation_daily",
    "fact_room_occupancy_daily",
    "hotel_vouchers",
    "manual_override_reasons",
    "ota_reservation_links",
    "ota_reservation_mappings",
    "payment_links",
    "pending_operational_actions",
    "reservation_allocation_locks",
    "reservation_status_history",
    "room_move_events",
    "stock_movements",
    "transactions",
    "waitlist_entries",
    "cash_movements",
    "llm_feedback_events",
    "payments",
    "refund_requests",
    "reservation_adjustments",
    "voucher_redemptions",
    "billing_adjustments",
    "payment_webhook_events",
)


def _policy_name(table_name: str) -> str:
    return f"tenant_isolation_{table_name}"


def _quoted_table(table_name: str) -> str:
    # The table names are the reviewed static tuple above, not user input.
    return f'"{table_name}"'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in TENANT_TABLES:
        table = _quoted_table(table_name)
        policy = _policy_name(table_name)
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON {table}')
        op.execute(
            f'''CREATE POLICY "{policy}" ON {table}
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )

    memberships = _quoted_table("hotel_memberships")
    membership_policy = _policy_name("hotel_memberships")
    op.execute(f"ALTER TABLE {memberships} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {memberships} FORCE ROW LEVEL SECURITY")
    op.execute(f'DROP POLICY IF EXISTS "{membership_policy}" ON {memberships}')
    op.execute(
        f'''CREATE POLICY "{membership_policy}" ON {memberships}
            USING (
                user_id = NULLIF(current_setting('app.user_id', true), '')::integer
                OR hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer
            )
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name in (*TENANT_TABLES, "hotel_memberships"):
        table = _quoted_table(table_name)
        policy = _policy_name(table_name)
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON {table}')
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
