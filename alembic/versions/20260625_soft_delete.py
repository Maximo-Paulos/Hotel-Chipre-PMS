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
    for table_name in TABLES:
        op.add_column(table_name, sa.Column("deleted_at", sa.DateTime(), nullable=True))
        op.add_column(table_name, sa.Column("deleted_by_user_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    for table_name in reversed(TABLES):
        op.drop_column(table_name, "deleted_by_user_id")
        op.drop_column(table_name, "deleted_at")
