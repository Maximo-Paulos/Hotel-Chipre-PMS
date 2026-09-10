"""add public marketing pricing plans and early-access leads

Revision ID: 20260910_marketing_pricing_and_leads
Revises: 20260910_reservation_email_deliveries
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_marketing_pricing_and_leads"
down_revision: Union[str, None] = "20260910_reservation_email_deliveries"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Both tables are global, not tenant-scoped: they describe the public website,
# not any one hotel. They carry no hotel_id, so there is no tenant-isolation
# policy to install -- same shape as the master_* tables.


def upgrade() -> None:
    op.create_table(
        "marketing_pricing_plans",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        # Nullable so the site can render "Consultar" until a price is set.
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("billing_period", sa.String(length=20), nullable=False, server_default="month"),
        sa.Column("headline", sa.String(length=160), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("features_json", sa.Text(), nullable=True),
        sa.Column("room_limit", sa.Integer(), nullable=True),
        sa.Column("staff_limit", sa.Integer(), nullable=True),
        sa.Column("cta_label", sa.String(length=60), nullable=True),
        sa.Column("cta_kind", sa.String(length=20), nullable=False, server_default="early_access"),
        sa.Column("highlight", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("code", name="uq_marketing_pricing_plans_code"),
        sa.CheckConstraint("price_amount IS NULL OR price_amount >= 0", name="ck_marketing_pricing_plans_price_positive"),
    )
    op.create_index("ix_marketing_pricing_plans_code", "marketing_pricing_plans", ["code"])
    op.create_index("ix_marketing_pricing_plans_sort_order", "marketing_pricing_plans", ["sort_order"])

    op.create_table(
        "marketing_leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("hotel_name", sa.String(length=160), nullable=True),
        sa.Column("rooms_estimate", sa.Integer(), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("source", sa.String(length=60), nullable=False, server_default="landing"),
        sa.Column("utm_json", sa.Text(), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_marketing_leads_email"),
    )
    op.create_index("ix_marketing_leads_email", "marketing_leads", ["email"])
    op.create_index("ix_marketing_leads_created_at", "marketing_leads", ["created_at"])

    # Seed the three plans that already exist in PLAN_CATALOG so the public
    # endpoint has something to serve. Room and staff limits are the real
    # enforced ones; price and currency stay NULL until the owner sets them.
    op.execute(
        """
        INSERT INTO marketing_pricing_plans
            (code, name, is_public, sort_order, billing_period, room_limit, staff_limit, cta_kind, highlight)
        VALUES
            ('starter', 'Starter', true, 10, 'month', 15, 3, 'early_access', false),
            ('pro', 'Pro', true, 20, 'month', 40, 8, 'early_access', true),
            ('ultra', 'Ultra', true, 30, 'month', 80, 20, 'early_access', false)
        """
    )


def downgrade() -> None:
    op.drop_index("ix_marketing_leads_created_at", table_name="marketing_leads")
    op.drop_index("ix_marketing_leads_email", table_name="marketing_leads")
    op.drop_table("marketing_leads")
    op.drop_index("ix_marketing_pricing_plans_sort_order", table_name="marketing_pricing_plans")
    op.drop_index("ix_marketing_pricing_plans_code", table_name="marketing_pricing_plans")
    op.drop_table("marketing_pricing_plans")
