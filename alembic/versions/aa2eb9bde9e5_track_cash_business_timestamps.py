"""track cash business timestamps

Revision ID: aa2eb9bde9e5
Revises: 20261017_local_business_clock
Create Date: 2026-10-17 17:22:46.480563
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'aa2eb9bde9e5'
down_revision: Union[str, None] = '20261017_local_business_clock'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable additions preserve the original real timestamps and allow
    # historical rows to fall back to those values in reports.
    op.add_column("cash_sessions", sa.Column("business_opened_at", sa.DateTime(), nullable=True))
    op.add_column("cash_sessions", sa.Column("business_closed_at", sa.DateTime(), nullable=True))
    op.add_column("cash_movements", sa.Column("business_recorded_at", sa.DateTime(), nullable=True))
    op.add_column("cash_close_reports", sa.Column("business_closed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "cash_close_reports",
        sa.Column("business_successor_float_declared_at", sa.DateTime(), nullable=True),
    )
    op.add_column("cash_custody_handoffs", sa.Column("business_delivered_at", sa.DateTime(), nullable=True))
    op.add_column("cash_custody_handoffs", sa.Column("business_received_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_cash_movements_hotel_business_recorded_at",
        "cash_movements",
        ["hotel_id", "business_recorded_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cash_movements_hotel_business_recorded_at", table_name="cash_movements")
    op.drop_column("cash_custody_handoffs", "business_received_at")
    op.drop_column("cash_custody_handoffs", "business_delivered_at")
    op.drop_column("cash_close_reports", "business_successor_float_declared_at")
    op.drop_column("cash_close_reports", "business_closed_at")
    op.drop_column("cash_movements", "business_recorded_at")
    op.drop_column("cash_sessions", "business_closed_at")
    op.drop_column("cash_sessions", "business_opened_at")
