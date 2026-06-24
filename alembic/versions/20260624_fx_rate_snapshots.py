"""v72 fx rate snapshots table.

Revision ID: 20260624_fx_rate_snapshots
Revises: 20260624_payment_surcharges
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_fx_rate_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260624_payment_surcharges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fx_rate_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "hotel_id",
            sa.Integer(),
            sa.ForeignKey("hotel_configuration.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rate_type", sa.String(length=30), nullable=False),
        sa.Column("moneda", sa.String(length=10), nullable=False, server_default="USD"),
        sa.Column("compra", sa.Float(), nullable=True),
        sa.Column("venta", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="dolarapi.com"),
    )
    op.create_index("ix_fx_snapshot_type_date", "fx_rate_snapshots", ["rate_type", "fetched_at"])
    op.create_index("ix_fx_snapshot_hotel_id", "fx_rate_snapshots", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_fx_snapshot_hotel_id", table_name="fx_rate_snapshots")
    op.drop_index("ix_fx_snapshot_type_date", table_name="fx_rate_snapshots")
    op.drop_table("fx_rate_snapshots")
