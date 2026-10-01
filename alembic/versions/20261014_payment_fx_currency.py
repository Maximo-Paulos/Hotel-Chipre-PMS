"""Record payment tender separately from reservation balance currency.

Revision ID: 20261014_payment_fx_currency
Revises: 20261013_cash_adjustment_permission
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261014_payment_fx_currency"
down_revision: Union[str, Sequence[str], None] = "20261013_cash_adjustment_permission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    transaction_columns = {column["name"] for column in inspector.get_columns("transactions")}
    if "tender_amount" not in transaction_columns:
        op.add_column("transactions", sa.Column("tender_amount", sa.Numeric(12, 2), nullable=True))
    if "tender_currency" not in transaction_columns:
        op.add_column("transactions", sa.Column("tender_currency", sa.String(3), nullable=True))
    if "fx_quote_details" not in transaction_columns:
        op.add_column("transactions", sa.Column("fx_quote_details", sa.JSON(), nullable=True))

    cash_indexes = {index["name"] for index in inspector.get_indexes("cash_sessions")}
    if "uq_cash_sessions_one_open_per_hotel" in cash_indexes:
        op.drop_index("uq_cash_sessions_one_open_per_hotel", table_name="cash_sessions")
    cash_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("cash_sessions")}
    if "uq_cash_sessions_open_currency" not in cash_indexes:
        op.create_index(
            "uq_cash_sessions_open_currency",
            "cash_sessions",
            ["hotel_id", "currency_code"],
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
            sqlite_where=sa.text("status = 'open'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    incompatible_sessions = bind.execute(
        sa.text(
            "SELECT hotel_id FROM cash_sessions "
            "WHERE status = 'open' GROUP BY hotel_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if incompatible_sessions is not None:
        raise RuntimeError(
            "Cannot downgrade payment FX migration while multiple currency drawers are open for a hotel"
        )

    transaction_columns = {column["name"] for column in sa.inspect(bind).get_columns("transactions")}
    if {"tender_currency", "currency"}.issubset(transaction_columns):
        foreign_tender = bind.execute(
            sa.text(
                "SELECT id FROM transactions "
                "WHERE tender_currency IS NOT NULL "
                "AND UPPER(tender_currency) <> UPPER(currency) LIMIT 1"
            )
        ).first()
        if foreign_tender is not None:
            raise RuntimeError(
                "Cannot downgrade payment FX migration while foreign-currency tender records exist"
            )

    inspector = sa.inspect(op.get_bind())
    cash_indexes = {index["name"] for index in inspector.get_indexes("cash_sessions")}
    if "uq_cash_sessions_open_currency" in cash_indexes:
        op.drop_index("uq_cash_sessions_open_currency", table_name="cash_sessions")
    cash_indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("cash_sessions")}
    if "uq_cash_sessions_one_open_per_hotel" not in cash_indexes:
        op.create_index(
            "uq_cash_sessions_one_open_per_hotel",
            "cash_sessions",
            ["hotel_id"],
            unique=True,
            postgresql_where=sa.text("status = 'open'"),
            sqlite_where=sa.text("status = 'open'"),
        )

    transaction_columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("transactions")}
    for column_name in ("fx_quote_details", "tender_currency", "tender_amount"):
        if column_name in transaction_columns:
            op.drop_column("transactions", column_name)
