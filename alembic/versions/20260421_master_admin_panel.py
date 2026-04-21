"""master admin panel

Revision ID: 20260421_master_admin_panel
Revises: 9c0d2f3e1a44
Create Date: 2026-04-21 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_master_admin_panel"
down_revision = "9c0d2f3e1a44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "master_admin_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_token_hash", sa.String(length=128), nullable=False, unique=True),
        sa.Column("csrf_token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_admin_sessions_session_token_hash", "master_admin_sessions", ["session_token_hash"], unique=True)

    op.create_table(
        "master_admin_audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=True),
        sa.Column("target_id", sa.String(length=80), nullable=True),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("request_path", sa.String(length=255), nullable=True),
        sa.Column("request_method", sa.String(length=16), nullable=True),
        sa.Column("request_id", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_admin_audit_events_actor_user_id", "master_admin_audit_events", ["actor_user_id"], unique=False)
    op.create_index("ix_master_admin_audit_events_action", "master_admin_audit_events", ["action"], unique=False)

    op.create_table(
        "master_admin_auth_lockouts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("login_identifier", sa.String(length=200), nullable=False, unique=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_reason", sa.String(length=120), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_admin_lockouts_login_identifier", "master_admin_auth_lockouts", ["login_identifier"], unique=False)

    op.create_table(
        "master_billing_policies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("policy_key", sa.String(length=50), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("allow_active", sa.Boolean(), nullable=False),
        sa.Column("allow_trialing", sa.Boolean(), nullable=False),
        sa.Column("allow_demo", sa.Boolean(), nullable=False),
        sa.Column("allow_comped", sa.Boolean(), nullable=False),
        sa.Column("allow_past_due_grace", sa.Boolean(), nullable=False),
        sa.Column("exempt_hotel_ids_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_billing_policies_policy_key", "master_billing_policies", ["policy_key"], unique=False)

    op.create_table(
        "master_stripe_webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("event_id", sa.String(length=120), nullable=False, unique=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("signature_header", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_stripe_webhook_events_event_type", "master_stripe_webhook_events", ["event_type"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_master_stripe_webhook_events_event_type", table_name="master_stripe_webhook_events")
    op.drop_table("master_stripe_webhook_events")
    op.drop_index("ix_master_billing_policies_policy_key", table_name="master_billing_policies")
    op.drop_table("master_billing_policies")
    op.drop_index("ix_master_admin_lockouts_login_identifier", table_name="master_admin_auth_lockouts")
    op.drop_table("master_admin_auth_lockouts")
    op.drop_index("ix_master_admin_audit_events_action", table_name="master_admin_audit_events")
    op.drop_index("ix_master_admin_audit_events_actor_user_id", table_name="master_admin_audit_events")
    op.drop_table("master_admin_audit_events")
    op.drop_index("ix_master_admin_sessions_session_token_hash", table_name="master_admin_sessions")
    op.drop_table("master_admin_sessions")

