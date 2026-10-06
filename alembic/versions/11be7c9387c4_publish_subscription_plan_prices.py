"""Publish owner-approved monthly subscription prices.

Revision ID: 11be7c9387c4
Revises: 4f3c177c4ba4
Create Date: 2026-10-05 19:30:39.530744
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '11be7c9387c4'
down_revision: Union[str, None] = '4f3c177c4ba4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep the complete prior configuration for rows this migration changes,
    # so downgrade can restore nullable price/currency and any billing period.
    op.create_table(
        "_r2_subscription_price_backup",
        sa.Column("code", sa.String(length=40), primary_key=True),
        sa.Column("price_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("billing_period", sa.String(length=20), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        "INSERT INTO _r2_subscription_price_backup "
        "(code, price_amount, currency, billing_period, updated_at) "
        "SELECT code, price_amount, currency, billing_period, updated_at FROM marketing_pricing_plans "
        "WHERE code IN ('starter', 'pro', 'ultra') AND price_amount IS NULL"
    )

    # Publish only where no explicit price exists. Master-admin prices already
    # configured for a plan remain authoritative.
    op.execute(
        "UPDATE marketing_pricing_plans "
        "SET price_amount = 20, currency = 'USD', billing_period = 'month' "
        "WHERE code = 'starter' AND price_amount IS NULL"
    )
    op.execute(
        "UPDATE marketing_pricing_plans "
        "SET price_amount = 100, currency = 'USD', billing_period = 'month' "
        "WHERE code = 'pro' AND price_amount IS NULL"
    )
    op.execute(
        "UPDATE marketing_pricing_plans "
        "SET price_amount = 200, currency = 'USD', billing_period = 'month' "
        "WHERE code = 'ultra' AND price_amount IS NULL"
    )


def downgrade() -> None:
    # Restore only rows that still contain the exact values introduced by this
    # revision. A price edited later from master admin is left untouched.
    for code, amount in (("starter", 20), ("pro", 100), ("ultra", 200)):
        op.execute(
            "UPDATE marketing_pricing_plans "
            "SET price_amount = (SELECT price_amount FROM _r2_subscription_price_backup "
            f"WHERE code = '{code}'), "
            "currency = (SELECT currency FROM _r2_subscription_price_backup "
            f"WHERE code = '{code}'), "
            "billing_period = (SELECT billing_period FROM _r2_subscription_price_backup "
            f"WHERE code = '{code}') "
            f"WHERE code = '{code}' AND EXISTS (SELECT 1 FROM _r2_subscription_price_backup "
            f"WHERE code = '{code}') AND price_amount = {amount} "
            "AND currency = 'USD' AND billing_period = 'month' "
            "AND updated_at = (SELECT updated_at FROM _r2_subscription_price_backup "
            f"WHERE code = '{code}')"
        )
    op.drop_table("_r2_subscription_price_backup")
