"""Add daily rates and price periods.

Revision ID: 20260624_daily_rates
Revises: 20260614_pg_perf_guest_trgm
Create Date: 2026-06-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260624_daily_rates"
down_revision: Union[str, Sequence[str], None] = "20260614_pg_perf_guest_trgm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already created these
    # tables out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())

    if "daily_rates" not in inspector.get_table_names():
        op.create_table(
            "daily_rates",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("date", sa.Date(), nullable=False),
            sa.Column("price", sa.Float(), nullable=False),
            sa.Column("price_cash", sa.Float(), nullable=True),
            sa.Column("price_transfer", sa.Float(), nullable=True),
            sa.Column("price_mercadopago", sa.Float(), nullable=True),
            sa.Column("price_paypal", sa.Float(), nullable=True),
            sa.Column("price_credit_card", sa.Float(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("hotel_id", "category_id", "date", name="uq_daily_rate"),
        )
    if "ix_daily_rate_hotel_cat_date" not in ({ix["name"] for ix in inspector.get_indexes("daily_rates")} if inspector.has_table("daily_rates") else set()):
        op.create_index(
            "ix_daily_rate_hotel_cat_date",
            "daily_rates",
            ["hotel_id", "category_id", "date"],
            unique=False,
        )

    if "price_periods" not in inspector.get_table_names():
        op.create_table(
            "price_periods",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column("price_per_night", sa.Float(), nullable=False),
            sa.Column("priority", sa.Integer(), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["category_id"], ["room_categories.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    if "ix_price_period_hotel_cat" not in ({ix["name"] for ix in inspector.get_indexes("price_periods")} if inspector.has_table("price_periods") else set()):
        op.create_index(
            "ix_price_period_hotel_cat",
            "price_periods",
            ["hotel_id", "category_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_price_period_hotel_cat", table_name="price_periods")
    op.drop_table("price_periods")
    op.drop_index("ix_daily_rate_hotel_cat_date", table_name="daily_rates")
    op.drop_table("daily_rates")
