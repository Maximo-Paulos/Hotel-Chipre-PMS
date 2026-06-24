"""v72 section 12.3 - payment_surcharges table.

Revision ID: 20260624_payment_surcharges
Revises: 20260624_daily_rates
Create Date: 2026-06-24
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_payment_surcharges"
down_revision: Union[str, Sequence[str], None] = "20260624_daily_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_surcharges",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "hotel_id",
            sa.Integer(),
            sa.ForeignKey("hotel_configuration.id"),
            nullable=False,
        ),
        sa.Column("payment_method", sa.String(50), nullable=False),
        sa.Column(
            "surcharge_type",
            sa.Enum("fixed", "percentage", name="payment_surcharge_type_enum"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False, server_default="ARS"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("hotel_id", "payment_method", name="uq_surcharge_hotel_method"),
    )


def downgrade() -> None:
    op.drop_table("payment_surcharges")
    op.execute("DROP TYPE IF EXISTS payment_surcharge_type_enum")
