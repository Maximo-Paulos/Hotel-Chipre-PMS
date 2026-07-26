"""Add one-open-cash-session partial unique index.

Revision ID: 20260613_cash_open_idx
Revises: 20260613_laundry_stock
Create Date: 2026-06-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_cash_open_idx"
down_revision: Union[str, Sequence[str], None] = "20260613_laundry_stock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "uq_cash_sessions_one_open_per_hotel" not in {ix["name"] for ix in inspector.get_indexes("cash_sessions")}:
        op.create_index(
            "uq_cash_sessions_one_open_per_hotel",
            "cash_sessions",
            ["hotel_id"],
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
            sqlite_where=sa.text("status = 'open'"),
        )


def downgrade() -> None:
    op.drop_index("uq_cash_sessions_one_open_per_hotel", table_name="cash_sessions")
