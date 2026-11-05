"""Record cash change currency and support paired cash movement corrections.

Revision ID: 20261104_cash_change_settlement
Revises: 20261029_rate_prices_numeric
Create Date: 2026-11-04
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261104_cash_change_settlement"
down_revision: str | Sequence[str] | None = "20261029_rate_prices_numeric"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SETTLEMENT_CONSTRAINT = (
    "(cash_received_amount IS NULL AND cash_change_settled_amount IS NULL "
    "AND cash_change_settled_currency IS NULL AND cash_change_fx_rate_snapshot IS NULL) OR "
    "(cash_received_amount IS NOT NULL AND cash_change_settled_amount IS NOT NULL "
    "AND cash_change_settled_currency IS NOT NULL "
    "AND cash_change_settled_currency = UPPER(cash_change_settled_currency) "
    "AND LENGTH(cash_change_settled_currency) = 3 "
    "AND cash_change_settled_amount >= 0 "
    "AND ((cash_change_amount = 0 AND cash_change_settled_amount = 0 "
    "AND (cash_change_fx_rate_snapshot IS NULL OR cash_change_fx_rate_snapshot > 0)) "
    "OR (cash_change_amount > 0 AND cash_change_fx_rate_snapshot > 0 "
    "AND ROUND(cash_change_amount * cash_change_fx_rate_snapshot, 2) = "
    "ROUND(cash_change_settled_amount, 2))) "
    "AND payment_method = 'cash' AND transaction_type != 'refund')"
)


def upgrade() -> None:
    # A single cross-currency cash payment has both an income movement in the
    # tender drawer and a change expense in the hotel's base-currency drawer.
    # One audited correction must be able to void both rows.
    op.drop_constraint(
        "uq_cash_movements_hotel_voided_correction",
        "cash_movements",
        type_="unique",
    )
    op.add_column(
        "transactions",
        sa.Column("cash_change_settled_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("cash_change_settled_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("cash_change_fx_rate_snapshot", sa.Numeric(24, 12), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE transactions "
            "SET cash_change_settled_amount = cash_change_amount, "
            "cash_change_settled_currency = UPPER(COALESCE(tender_currency, currency, 'ARS')), "
            "cash_change_fx_rate_snapshot = 1 "
            "WHERE cash_received_amount IS NOT NULL"
        )
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.create_check_constraint(
            "ck_transaction_cash_change_settlement_consistent",
            SETTLEMENT_CONSTRAINT,
        )


def downgrade() -> None:
    has_multi_movement_corrections = op.get_bind().execute(
        sa.text(
            "SELECT 1 FROM cash_movements "
            "WHERE voided_by_payment_correction_id IS NOT NULL "
            "GROUP BY hotel_id, voided_by_payment_correction_id "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if has_multi_movement_corrections:
        raise RuntimeError(
            "Cannot restore the single-movement correction constraint while a payment correction "
            "has reversed multiple cash movements."
        )
    op.create_unique_constraint(
        "uq_cash_movements_hotel_voided_correction",
        "cash_movements",
        ["hotel_id", "voided_by_payment_correction_id"],
    )
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint(
            "ck_transaction_cash_change_settlement_consistent",
            type_="check",
        )
    op.drop_column("transactions", "cash_change_fx_rate_snapshot")
    op.drop_column("transactions", "cash_change_settled_currency")
    op.drop_column("transactions", "cash_change_settled_amount")
