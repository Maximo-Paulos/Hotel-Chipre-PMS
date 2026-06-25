"""drop orphan payment_surcharge_configs table (R5b).

main carries TWO surcharge implementations:
  - canonical `payment_surcharges` (app/models/payment_surcharge.py) wired to API+service
  - orphan `payment_surcharge_configs` (created by 20260612_v72_gaps_phase1) — never
    wired to any service or API.

This drops the orphan table. Downgrade recreates it for reversibility (mirrors the
DDL from 20260612_v72_gaps_phase1).

Revision ID: 20260625_drop_payment_surcharge_configs
Revises: 20260625_reservation_waitlist_flags
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_drop_payment_surcharge_configs"
down_revision: Union[str, Sequence[str], None] = "20260625_reservation_waitlist_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_surcharge_hotel_id", table_name="payment_surcharge_configs")
    op.drop_table("payment_surcharge_configs")


def downgrade() -> None:
    op.create_table(
        "payment_surcharge_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer, sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_method", sa.String(30), nullable=False),
        sa.Column("surcharge_pct", sa.Numeric(5, 4), nullable=True),
        sa.Column("surcharge_fixed", sa.Numeric(12, 2), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.CheckConstraint(
            "surcharge_pct IS NULL OR (surcharge_pct >= 0 AND surcharge_pct < 1)",
            name="ck_surcharge_pct_range",
        ),
        sa.CheckConstraint("surcharge_fixed IS NULL OR surcharge_fixed >= 0", name="ck_surcharge_fixed_nonneg"),
        sa.UniqueConstraint("hotel_id", "payment_method", name="uq_surcharge_hotel_method"),
    )
    op.create_index("ix_surcharge_hotel_id", "payment_surcharge_configs", ["hotel_id"])
