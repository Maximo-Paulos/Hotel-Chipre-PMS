"""add external-effect mode to payment links

Revision ID: 20260812_external_effects
Revises: ebd2db08c7d0
Create Date: 2026-08-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260812_external_effects"
down_revision: Union[str, None] = "ebd2db08c7d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("payment_links") as batch_op:
        batch_op.add_column(
            sa.Column(
                "execution_mode",
                sa.String(length=20),
                nullable=False,
                # Every row that predates this migration came from the legacy
                # provider-link workflow. Backfill that historical fact first;
                # the default is switched to local_only below for new rows.
                server_default="provider",
            )
        )
        batch_op.add_column(
            sa.Column("payable", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))

    # Every preexisting row represents the legacy provider workflow. Only rows
    # that still have a checkout URL and a nonterminal state remain payable.
    op.execute(
        sa.text(
            """
            UPDATE payment_links
               SET payable = true
             WHERE external_checkout_url IS NOT NULL
               AND status NOT IN ('cancelled', 'expired', 'completed', 'paid')
            """
        )
    )

    with op.batch_alter_table("payment_links") as batch_op:
        batch_op.alter_column(
            "execution_mode",
            existing_type=sa.String(length=20),
            nullable=False,
            server_default="local_only",
        )
        batch_op.create_check_constraint(
            "ck_payment_link_execution_mode",
            "execution_mode IN ('local_only', 'provider')",
        )
        batch_op.create_check_constraint(
            "ck_payment_link_payable_provider_mode",
            "NOT payable OR execution_mode = 'provider'",
        )
        batch_op.create_unique_constraint(
            "uq_payment_link_idempotency_per_hotel",
            ["hotel_id", "idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("payment_links") as batch_op:
        batch_op.drop_constraint(
            "uq_payment_link_idempotency_per_hotel",
            type_="unique",
        )
        batch_op.drop_constraint(
            "ck_payment_link_payable_provider_mode",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_payment_link_execution_mode",
            type_="check",
        )
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("payable")
        batch_op.drop_column("execution_mode")
