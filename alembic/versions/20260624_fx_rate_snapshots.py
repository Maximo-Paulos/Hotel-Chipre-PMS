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
    # Guarded because some production environments already created this
    # table out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    if "fx_rate_snapshots" not in inspector.get_table_names():
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
    fx_indexes = {ix["name"] for ix in inspector.get_indexes("fx_rate_snapshots")} if inspector.has_table("fx_rate_snapshots") else set()
    if "ix_fx_snapshot_type_date" not in fx_indexes:
        op.create_index("ix_fx_snapshot_type_date", "fx_rate_snapshots", ["rate_type", "fetched_at"])
    if "ix_fx_snapshot_hotel_id" not in fx_indexes:
        op.create_index("ix_fx_snapshot_hotel_id", "fx_rate_snapshots", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_fx_snapshot_hotel_id", table_name="fx_rate_snapshots")
    op.drop_index("ix_fx_snapshot_type_date", table_name="fx_rate_snapshots")
    op.drop_table("fx_rate_snapshots")
