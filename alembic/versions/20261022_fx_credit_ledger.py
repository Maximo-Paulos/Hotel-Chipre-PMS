"""Record FX rounding credit and manual credit refunds separately.

Revision ID: 20261022_fx_credit_ledger
Revises: 20261022_fx_rounding_policy
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_fx_credit_ledger"
down_revision: Union[str, None] = "20261022_fx_rounding_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.add_column(
                sa.Column("rounding_credit_amount", sa.Numeric(12, 2), nullable=False, server_default="0")
            )
            batch_op.add_column(
                sa.Column("credit_refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0")
            )
            batch_op.add_column(
                sa.Column("refund_component", sa.String(length=24), nullable=False, server_default="payment")
            )
            batch_op.drop_constraint("ck_transaction_amount_nonzero", type_="check")
            batch_op.create_check_constraint(
                "ck_transaction_amount_nonzero_or_credit_refund",
                "amount != 0 OR (transaction_type = 'refund' AND "
                "refund_component = 'rounding_credit' AND credit_refund_amount > 0)",
            )
            batch_op.create_check_constraint(
                "ck_transaction_rounding_credit_fields_consistent",
                "rounding_credit_amount >= 0 AND credit_refund_amount >= 0 AND "
                "(rounding_credit_amount = 0 OR transaction_type != 'refund') AND "
                "((refund_component = 'payment' AND credit_refund_amount = 0) OR "
                "(refund_component = 'rounding_credit' AND transaction_type = 'refund' "
                "AND amount = 0 AND credit_refund_amount > 0 AND tender_amount = credit_refund_amount))",
            )
            batch_op.create_check_constraint(
                "ck_transaction_refund_component",
                "refund_component IN ('payment', 'rounding_credit')",
            )
        return

    op.add_column(
        "transactions",
        sa.Column("rounding_credit_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "transactions",
        sa.Column("credit_refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "transactions",
        sa.Column("refund_component", sa.String(length=24), nullable=False, server_default="payment"),
    )
    op.drop_constraint("ck_transaction_amount_nonzero", "transactions", type_="check")
    op.create_check_constraint(
        "ck_transaction_amount_nonzero_or_credit_refund",
        "transactions",
        "amount != 0 OR (transaction_type = 'refund' AND "
        "refund_component = 'rounding_credit' AND credit_refund_amount > 0)",
    )
    op.create_check_constraint(
        "ck_transaction_rounding_credit_fields_consistent",
        "transactions",
        "rounding_credit_amount >= 0 AND credit_refund_amount >= 0 AND "
        "(rounding_credit_amount = 0 OR transaction_type != 'refund') AND "
        "((refund_component = 'payment' AND credit_refund_amount = 0) OR "
        "(refund_component = 'rounding_credit' AND transaction_type = 'refund' "
        "AND amount = 0 AND credit_refund_amount > 0 AND tender_amount = credit_refund_amount))",
    )
    op.create_check_constraint(
        "ck_transaction_refund_component",
        "transactions",
        "refund_component IN ('payment', 'rounding_credit')",
    )


def downgrade() -> None:
    bind = op.get_bind()
    credit_rows = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM transactions "
            "WHERE COALESCE(rounding_credit_amount, 0) > 0 "
            "OR COALESCE(credit_refund_amount, 0) > 0 "
            "OR refund_component = 'rounding_credit'"
        )
    ).scalar_one()
    if credit_rows:
        raise RuntimeError(
            "Cannot downgrade FX credit ledger while rounding-credit issuance or refunds exist; "
            "doing so would erase financial history."
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.drop_constraint("ck_transaction_amount_nonzero_or_credit_refund", type_="check")
            batch_op.drop_constraint("ck_transaction_rounding_credit_fields_consistent", type_="check")
            batch_op.drop_constraint("ck_transaction_refund_component", type_="check")
            batch_op.drop_column("rounding_credit_amount")
            batch_op.drop_column("credit_refund_amount")
            batch_op.drop_column("refund_component")
            batch_op.create_check_constraint("ck_transaction_amount_nonzero", "amount != 0")
        return

    op.drop_constraint("ck_transaction_amount_nonzero_or_credit_refund", "transactions", type_="check")
    op.drop_constraint("ck_transaction_rounding_credit_fields_consistent", "transactions", type_="check")
    op.drop_constraint("ck_transaction_refund_component", "transactions", type_="check")
    op.drop_column("transactions", "rounding_credit_amount")
    op.drop_column("transactions", "credit_refund_amount")
    op.drop_column("transactions", "refund_component")
    op.create_check_constraint("ck_transaction_amount_nonzero", "transactions", "amount != 0")
