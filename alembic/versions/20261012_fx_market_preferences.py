"""Store hotel FX market preferences and conversion provenance.

Revision ID: 20261012_fx_market_preferences
Revises: 20261011_co_owner_manual_rate_default
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261012_fx_market_preferences"
down_revision: Union[str, None] = "20261011_co_owner_manual_rate_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "fx_conversion_rate_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'oficial'"),
        ),
    )
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "fx_display_rate_types",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"oficial\"]'"),
        ),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("provider_market", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("provider_updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("selected_side", sa.String(length=10), nullable=True),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("base_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("quote_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "fx_rate_snapshots",
        sa.Column("applied_rate", sa.Numeric(precision=20, scale=8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fx_rate_snapshots", "applied_rate")
    op.drop_column("fx_rate_snapshots", "quote_currency")
    op.drop_column("fx_rate_snapshots", "base_currency")
    op.drop_column("fx_rate_snapshots", "selected_side")
    op.drop_column("fx_rate_snapshots", "provider_updated_at")
    op.drop_column("fx_rate_snapshots", "provider_market")
    op.drop_column("hotel_configuration", "fx_display_rate_types")
    op.drop_column("hotel_configuration", "fx_conversion_rate_type")
