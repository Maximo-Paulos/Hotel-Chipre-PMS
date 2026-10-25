"""Track Mercado Pago checkout revocation separately from local cancellation.

Revision ID: 20261022_payment_link_revocation
Revises: 20261022_fx_credit_ledger
Create Date: 2026-10-22
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261022_payment_link_revocation"
down_revision: str | None = "20261022_fx_credit_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("payment_links") as batch_op:
        batch_op.add_column(
            sa.Column(
                "provider_revocation_status",
                sa.String(length=20),
                nullable=False,
                server_default="not_required",
            )
        )
        batch_op.add_column(
            sa.Column(
                "provider_revocation_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("provider_revocation_last_attempt_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("provider_revocation_error", sa.String(length=80), nullable=True))
        batch_op.create_check_constraint(
            "ck_payment_link_provider_revocation_status",
            "provider_revocation_status IN ('not_required', 'pending', 'processing', 'succeeded', 'failed')",
        )
        batch_op.create_check_constraint(
            "ck_payment_link_provider_revocation_attempts_nonnegative",
            "provider_revocation_attempts >= 0",
        )
        batch_op.create_index(
            "ix_payment_links_provider_revocation_work",
            ["hotel_id", "provider_revocation_status", "id"],
        )

    # Reconcile legacy cancellations before enabling the periodic recovery
    # worker. Before this column existed, cancelling a reservation could leave
    # its provider checkout active, while direct link cancellation only changed
    # local state. Keep completed, expired, local-only and unrelated active
    # links untouched. This only queues provider work; it does not call MP or
    # change payments/ledger records.
    op.execute(
        sa.text(
            """
            UPDATE payment_links
               SET status = 'cancelled',
                   payable = false,
                   cancelled_at = COALESCE(cancelled_at, CURRENT_TIMESTAMP),
                   provider_revocation_status = 'pending',
                   provider_revocation_error = NULL
             WHERE execution_mode = 'provider'
               AND replace(lower(provider), 'mercadopago', 'mercado_pago') = 'mercado_pago'
               AND external_checkout_url IS NOT NULL
               AND (
                    status = 'cancelled'
                    OR (
                        status IN ('active', 'pending', 'partially_paid')
                        AND payable = true
                        AND EXISTS (
                            SELECT 1
                              FROM reservations
                             WHERE reservations.hotel_id = payment_links.hotel_id
                               AND reservations.id = payment_links.reservation_id
                               AND reservations.status = 'cancelled'
                        )
                    )
               )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("payment_links") as batch_op:
        batch_op.drop_index("ix_payment_links_provider_revocation_work")
        batch_op.drop_constraint("ck_payment_link_provider_revocation_attempts_nonnegative", type_="check")
        batch_op.drop_constraint("ck_payment_link_provider_revocation_status", type_="check")
        batch_op.drop_column("provider_revocation_error")
        batch_op.drop_column("provider_revocation_last_attempt_at")
        batch_op.drop_column("provider_revocation_attempts")
        batch_op.drop_column("provider_revocation_status")
