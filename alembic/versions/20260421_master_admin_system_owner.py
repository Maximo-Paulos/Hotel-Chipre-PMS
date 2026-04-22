"""master admin system owner mail and stripe settings

Revision ID: 20260421_master_admin_system_owner
Revises: 20260421_master_admin_panel
Create Date: 2026-04-21 01:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260421_master_admin_system_owner"
down_revision = "20260421_master_admin_panel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "master_billing_policies",
        sa.Column("exempt_user_ids_json", sa.Text(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "master_system_email_connections",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("connection_key", sa.String(length=50), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("auth_payload", sa.JSON(), nullable=True),
        sa.Column("connected_account_email", sa.String(length=255), nullable=True),
        sa.Column("connected_account_name", sa.String(length=255), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_master_system_email_connections_connection_key",
        "master_system_email_connections",
        ["connection_key"],
        unique=True,
    )

    op.create_table(
        "master_stripe_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("config_key", sa.String(length=50), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("auth_payload", sa.JSON(), nullable=True),
        sa.Column("account_id", sa.String(length=120), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("webhook_secret_configured", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_master_stripe_settings_config_key", "master_stripe_settings", ["config_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_master_stripe_settings_config_key", table_name="master_stripe_settings")
    op.drop_table("master_stripe_settings")
    op.drop_index("ix_master_system_email_connections_connection_key", table_name="master_system_email_connections")
    op.drop_table("master_system_email_connections")
    op.drop_column("master_billing_policies", "exempt_user_ids_json")
