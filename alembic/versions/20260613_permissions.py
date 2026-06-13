"""permission matrix, role boundaries, and security audit log

Revision ID: 20260613_permissions
Revises: 20260613_payment_idempotency
Create Date: 2026-06-13

Configurable permission matrix (permissions catalog, role defaults, per-hotel
overrides) plus security_audit_logs for free-form security events (permission
overrides/denials). NOTE: this does NOT create `audit_logs` — that table is the
enum-typed row-mutation ledger already created by 20260612_audit_log_and_transaction_fk.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_permissions"
down_revision: Union[str, Sequence[str], None] = "20260613_payment_idempotency"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "permissions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )

    op.create_table(
        "role_permission_defaults",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(
            ["permission_code"], ["permissions.code"],
            name="fk_role_permission_defaults_permission_code_permissions",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("role", "permission_code", name="uq_role_permission_defaults_role_permission"),
    )

    op.create_table(
        "hotel_permission_overrides",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_hotel_permission_overrides_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_code"], ["permissions.code"],
            name="fk_hotel_permission_overrides_permission_code_permissions",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.id"],
            name="fk_hotel_permission_overrides_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "hotel_id", "role", "permission_code",
            name="uq_hotel_permission_overrides_hotel_role_permission",
        ),
    )
    op.create_index(
        "ix_hotel_permission_overrides_hotel_id", "hotel_permission_overrides", ["hotel_id"], unique=False
    )

    op.create_table(
        "security_audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_security_audit_logs_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_security_audit_logs_hotel_created", "security_audit_logs", ["hotel_id", "created_at"])
    op.create_index("ix_security_audit_logs_hotel_action", "security_audit_logs", ["hotel_id", "action"])


def downgrade() -> None:
    op.drop_index("ix_security_audit_logs_hotel_action", table_name="security_audit_logs")
    op.drop_index("ix_security_audit_logs_hotel_created", table_name="security_audit_logs")
    op.drop_table("security_audit_logs")

    op.drop_index("ix_hotel_permission_overrides_hotel_id", table_name="hotel_permission_overrides")
    op.drop_table("hotel_permission_overrides")
    op.drop_table("role_permission_defaults")
    op.drop_table("permissions")
