"""Persist the latest shared DolarAPI rates for bounded outage fallback.

Revision ID: 20261029_fx_rate_cache
Revises: 20261027_alloc_room_prefs
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "20261029_fx_rate_cache"
down_revision: str | None = "20261027_alloc_room_prefs"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "fx_rate_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("rate_type", sa.String(length=30), nullable=False),
        sa.Column("provider_market", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("buy", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("sell", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("provider_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_derived", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("source_quotes", sa.JSON(), nullable=True),
        sa.Column(
            "cache_source",
            sa.String(length=30),
            server_default="on_demand",
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "currency", "rate_type", name="uq_fx_rate_cache_currency_type"
        ),
    )
    op.create_index("ix_fx_rate_cache_observed_at", "fx_rate_cache", ["observed_at"])


def downgrade() -> None:
    op.drop_index("ix_fx_rate_cache_observed_at", table_name="fx_rate_cache")
    op.drop_table("fx_rate_cache")
