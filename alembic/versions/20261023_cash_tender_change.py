"""Persist cash received, change, and explicitly retained tip separately.

Revision ID: 20261023_cash_tender_change
Revises: 20261022_payment_link_revocation
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20261023_cash_tender_change"
down_revision: str | None = "20261022_payment_link_revocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TRANSACTION_CHECK = "ck_transaction_cash_received_change_consistent"
GROUP_BATCH_CHECK = "ck_group_payment_batch_cash_received_change_consistent"
TRANSACTION_CHECK_SQL = (
    "(cash_received_amount IS NULL AND cash_change_amount IS NULL AND cash_tip_amount = 0) OR "
    "(cash_received_amount IS NOT NULL AND cash_change_amount IS NOT NULL "
    "AND cash_received_amount > 0 AND cash_change_amount >= 0 "
    "AND cash_change_amount <= cash_received_amount "
    "AND cash_received_amount >= COALESCE(gross_amount, amount) "
    "AND cash_tip_amount >= 0 "
    "AND cash_tip_amount <= cash_received_amount - COALESCE(gross_amount, amount) "
    "AND ROUND(cash_change_amount, 2) = "
    "ROUND(cash_received_amount - COALESCE(gross_amount, amount) - cash_tip_amount, 2) "
    "AND payment_method = 'cash' AND transaction_type != 'refund')"
)
GROUP_BATCH_CHECK_SQL = (
    "(cash_received_amount IS NULL AND cash_change_amount IS NULL AND cash_tip_amount = 0 "
    "AND gross_amount IS NULL) OR "
    "(cash_received_amount IS NOT NULL AND cash_change_amount IS NOT NULL "
    "AND cash_received_amount > 0 AND cash_change_amount >= 0 "
    "AND cash_change_amount <= cash_received_amount AND gross_amount IS NOT NULL "
    "AND gross_amount > 0 AND cash_tip_amount >= 0 "
    "AND cash_tip_amount <= cash_received_amount - gross_amount "
    "AND ROUND(cash_change_amount, 2) = "
    "ROUND(cash_received_amount - gross_amount - cash_tip_amount, 2) "
    "AND payment_method = 'cash')"
)


def _add_transaction_columns_and_check() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(
            sa.Column("cash_received_amount", sa.Numeric(12, 2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cash_change_amount", sa.Numeric(12, 2), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "cash_tip_amount",
                sa.Numeric(12, 2),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.create_check_constraint(
            TRANSACTION_CHECK,
            TRANSACTION_CHECK_SQL,
        )


def _add_group_batch_columns_and_check() -> None:
    with op.batch_alter_table("reservation_group_payment_batches") as batch_op:
        batch_op.add_column(
            sa.Column("cash_received_amount", sa.Numeric(12, 2), nullable=True)
        )
        batch_op.add_column(
            sa.Column("cash_change_amount", sa.Numeric(12, 2), nullable=True)
        )
        batch_op.add_column(sa.Column("gross_amount", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(
            sa.Column(
                "cash_tip_amount",
                sa.Numeric(12, 2),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.create_check_constraint(
            GROUP_BATCH_CHECK,
            GROUP_BATCH_CHECK_SQL,
        )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        _add_transaction_columns_and_check()
        _add_group_batch_columns_and_check()
        return

    op.add_column(
        "transactions",
        sa.Column("cash_received_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("cash_change_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column(
            "cash_tip_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        TRANSACTION_CHECK,
        "transactions",
        TRANSACTION_CHECK_SQL,
    )

    op.add_column(
        "reservation_group_payment_batches",
        sa.Column("cash_received_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reservation_group_payment_batches",
        sa.Column("cash_change_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reservation_group_payment_batches",
        sa.Column("gross_amount", sa.Numeric(12, 2), nullable=True),
    )
    op.add_column(
        "reservation_group_payment_batches",
        sa.Column(
            "cash_tip_amount",
            sa.Numeric(12, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.create_check_constraint(
        GROUP_BATCH_CHECK,
        "reservation_group_payment_batches",
        GROUP_BATCH_CHECK_SQL,
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table_name in ("transactions", "reservation_group_payment_batches"):
        recorded_pair = bind.execute(
            sa.text(
                f"SELECT 1 FROM {table_name} "
                "WHERE cash_received_amount IS NOT NULL "
                "OR cash_change_amount IS NOT NULL "
                "OR cash_tip_amount > 0 "
                + ("OR gross_amount IS NOT NULL " if table_name == "reservation_group_payment_batches" else "")
                + "LIMIT 1"
            )
        ).first()
        if recorded_pair is not None:
            raise RuntimeError(
                "Cannot downgrade cash tender/change migration while "
                f"{table_name} contains "
                "a recorded cash receipt pair; doing so would erase financial history."
            )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("reservation_group_payment_batches") as batch_op:
            batch_op.drop_constraint(GROUP_BATCH_CHECK, type_="check")
            batch_op.drop_column("cash_tip_amount")
            batch_op.drop_column("cash_change_amount")
            batch_op.drop_column("cash_received_amount")
            batch_op.drop_column("gross_amount")
        with op.batch_alter_table("transactions") as batch_op:
            batch_op.drop_constraint(TRANSACTION_CHECK, type_="check")
            batch_op.drop_column("cash_tip_amount")
            batch_op.drop_column("cash_change_amount")
            batch_op.drop_column("cash_received_amount")
        return

    op.drop_constraint(
        GROUP_BATCH_CHECK, "reservation_group_payment_batches", type_="check"
    )
    op.drop_column("reservation_group_payment_batches", "cash_tip_amount")
    op.drop_column("reservation_group_payment_batches", "cash_change_amount")
    op.drop_column("reservation_group_payment_batches", "cash_received_amount")
    op.drop_column("reservation_group_payment_batches", "gross_amount")
    op.drop_constraint(TRANSACTION_CHECK, "transactions", type_="check")
    op.drop_column("transactions", "cash_tip_amount")
    op.drop_column("transactions", "cash_change_amount")
    op.drop_column("transactions", "cash_received_amount")
