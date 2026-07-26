"""Add transaction idempotency key for gateway payments.

Revision ID: 20260613_payment_idempotency
Revises: 20260612_v72_gaps_phase6_payment_tables
Create Date: 2026-06-13

Adds transactions.idempotency_key + partial unique index so a gateway webhook
that fires twice (or two webhooks for the same payment) creates at most one
Transaction. Cash/manual transactions leave the key NULL and are unconstrained.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260613_payment_idempotency"
down_revision: Union[str, Sequence[str], None] = "20260612_v72_gaps_phase6_payment_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    transactions_columns = {c["name"] for c in inspector.get_columns("transactions")}
    with op.batch_alter_table("transactions") as batch_op:
        if "idempotency_key" not in transactions_columns:
            batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))

    if "uq_transactions_hotel_reservation_idempotency_key" not in {ix["name"] for ix in inspector.get_indexes("transactions")}:
        op.create_index(
            "uq_transactions_hotel_reservation_idempotency_key",
            "transactions",
            ["hotel_id", "reservation_id", "idempotency_key"],
            unique=True,
            postgresql_where=sa.text("idempotency_key IS NOT NULL"),
            sqlite_where=sa.text("idempotency_key IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("uq_transactions_hotel_reservation_idempotency_key", table_name="transactions")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("idempotency_key")
