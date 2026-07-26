"""Add transactions.created_by_user_id for payment audit trail.

Transaction had created_at/processed_at (WHEN) but no column recording WHO
(which staff user) triggered a money-moving state change -- actor_user_id
was already threaded through process_payment() for the cash-register side
effect only and silently dropped everywhere else. NULL is a legitimate,
expected value for gateway/webhook-initiated transactions (no human actor).

Revision ID: 20260725_transaction_created_by_user
Revises: 20260725_user_token_version
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260725_transaction_created_by_user"
down_revision: Union[str, None] = "20260725_user_token_version"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already have this column
    # out-of-band via an old startup self-heal pass while alembic_version
    # stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    if "created_by_user_id" not in {c["name"] for c in inspector.get_columns("transactions")}:
        op.add_column(
            "transactions",
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("transactions", "created_by_user_id")
