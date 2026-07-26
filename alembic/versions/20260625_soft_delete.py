"""soft delete audited domain records.

Revision ID: 20260625_soft_delete
Revises: 20260624_fx_rate_snapshots
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_soft_delete"
down_revision: Union[str, Sequence[str], None] = "20260624_fx_rate_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = (
    "reservations",
    "rooms",
    "company_documents",
    "price_periods",
    "stock_items",
    "stock_locations",
)


def upgrade() -> None:
    # Guarded because some production environments already have these
    # columns out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    for table_name in TABLES:
        existing_columns = {c["name"] for c in inspector.get_columns(table_name)}
        if "deleted_at" not in existing_columns:
            op.add_column(table_name, sa.Column("deleted_at", sa.DateTime(), nullable=True))
        if "deleted_by_user_id" not in existing_columns:
            op.add_column(table_name, sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_column(table_name, "deleted_by_user_id")
        op.drop_column(table_name, "deleted_at")
