"""audit_log table and transaction.hotel_id FK

Adds the tenant-scoped audit_logs table and fixes the missing FK constraint on
transactions.hotel_id (was a bare integer without referential integrity).

Revision ID: 20260612_audit_log_and_transaction_fk
Revises: 20260424_analytics_r1_base
Create Date: 2026-06-12 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg


revision: str = "20260612_audit_log_and_transaction_fk"
down_revision: Union[str, Sequence[str], None] = "20260424_analytics_r1_base"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _audit_action_enum(dialect_name: str) -> sa.Enum:
    values = ("create", "update", "delete", "status_change")
    if dialect_name == "postgresql":
        return pg.ENUM(*values, name="audit_action_enum", create_type=True)
    return sa.Enum(*values, name="audit_action_enum", create_constraint=True)


def upgrade() -> None:
    dialect_name = op.get_context().dialect.name

    # 1. Create audit_action_enum type (PostgreSQL only)
    if dialect_name == "postgresql":
        _audit_action_enum(dialect_name).create(op.get_bind(), checkfirst=True)

    # 2. Create audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "hotel_id",
            sa.Integer(),
            sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("table_name", sa.String(100), nullable=False),
        sa.Column("record_id", sa.Integer(), nullable=False),
        sa.Column(
            "action",
            _audit_action_enum(dialect_name),
            nullable=False,
        ),
        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payload_before", sa.Text(), nullable=True),
        sa.Column("payload_after", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "ix_audit_logs_hotel_created",
        "audit_logs",
        ["hotel_id", "created_at"],
    )
    op.create_index(
        "ix_audit_logs_hotel_table_record",
        "audit_logs",
        ["hotel_id", "table_name", "record_id"],
    )

    # 3. Add FK constraint to transactions.hotel_id
    # In SQLite (dev/test), adding a FK constraint isn't supported via ALTER TABLE;
    # the column already exists so we skip the FK-only alter on SQLite.
    if dialect_name == "postgresql":
        op.create_foreign_key(
            "fk_transactions_hotel_id",
            "transactions",
            "hotel_configuration",
            ["hotel_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    dialect_name = op.get_context().dialect.name

    if dialect_name == "postgresql":
        op.drop_constraint("fk_transactions_hotel_id", "transactions", type_="foreignkey")

    op.drop_index("ix_audit_logs_hotel_table_record", table_name="audit_logs")
    op.drop_index("ix_audit_logs_hotel_created", table_name="audit_logs")
    op.drop_table("audit_logs")

    if dialect_name == "postgresql":
        sa.Enum(name="audit_action_enum").drop(op.get_bind(), checkfirst=True)
