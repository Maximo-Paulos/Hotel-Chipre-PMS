"""Separate historical cash receipts from the active drawer and seed access.

Revision ID: 20260929_cash_prior_receipts
Revises: 20260929_manual_ota_record_permission
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260929_cash_prior_receipts"
down_revision: Union[str, None] = "20260929_manual_ota_record_permission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "cash:record_prior_receipt"


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(
            sa.Column("collected_before", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.add_column(sa.Column("collected_on", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("prior_receipt_note", sa.String(length=240), nullable=True))
        batch_op.create_check_constraint(
            "ck_transaction_prior_receipt_consistent",
            "(collected_before = false AND collected_on IS NULL AND prior_receipt_note IS NULL) OR "
            "(collected_before = true AND collected_on IS NOT NULL AND prior_receipt_note IS NOT NULL "
            "AND payment_method = 'cash' AND transaction_type != 'refund' AND status = 'completed')",
        )
    op.create_index(
        "ix_transactions_hotel_prior_receipt_date",
        "transactions",
        ["hotel_id", "collected_before", "collected_on"],
    )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES (:code, :description, false, false, true)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {
            "code": _PERMISSION,
            "description": "Record cash collected before using the system",
        },
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permission_defaults (role, permission_code, allowed)
            VALUES
                ('owner', :code, true),
                ('co_owner', :code, true),
                ('manager', :code, true),
                ('receptionist', :code, false),
                ('housekeeping', :code, false)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    connection = op.get_bind()
    prior_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM transactions WHERE collected_before = true")
    ).scalar_one()
    if prior_count:
        raise RuntimeError(
            "Cannot remove prior-receipt fields while historical cash receipts exist; "
            "export and reconcile those records before rollback."
        )

    op.drop_index("ix_transactions_hotel_prior_receipt_date", table_name="transactions")
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_constraint("ck_transaction_prior_receipt_consistent", type_="check")
        batch_op.drop_column("prior_receipt_note")
        batch_op.drop_column("collected_on")
        batch_op.drop_column("collected_before")

    # Do not delete the permission catalog row or defaults during rollback.
    # A hotel may have assigned overrides after upgrade; preserving authorization
    # records avoids silently deleting operator configuration.
