"""Track auditable voids for open-session cash corrections.

Revision ID: 20261024_cash_movement_voids
Revises: 20261024_atomic_payment_corrections
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261024_cash_movement_voids"
down_revision: Union[str, None] = "20261024_atomic_payment_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("cash_movements", sa.Column("voided_at", sa.DateTime(), nullable=True))
    op.add_column(
        "cash_movements",
        sa.Column("voided_by_payment_correction_id", sa.Integer(), nullable=True),
    )
    with op.batch_alter_table("cash_movements") as batch_op:
        batch_op.create_check_constraint(
            "ck_cash_movements_void_metadata",
            "(voided_at IS NULL AND voided_by_payment_correction_id IS NULL) OR "
            "(voided_at IS NOT NULL AND voided_by_payment_correction_id IS NOT NULL)",
        )
        batch_op.create_unique_constraint(
            "uq_cash_movements_hotel_voided_correction",
            ["hotel_id", "voided_by_payment_correction_id"],
        )
        batch_op.create_foreign_key(
            "fk_cash_movements_hotel_payment_correction",
            "payment_corrections",
            ["hotel_id", "voided_by_payment_correction_id"],
            ["hotel_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    connection = op.get_bind()
    has_voided_movements = connection.execute(
        sa.text("SELECT 1 FROM cash_movements WHERE voided_at IS NOT NULL LIMIT 1")
    ).first()
    if has_voided_movements:
        raise RuntimeError(
            "Cannot remove cash movement void history while voided movements exist; "
            "preserve and reconcile that ledger before downgrading."
        )

    with op.batch_alter_table("cash_movements") as batch_op:
        batch_op.drop_constraint("fk_cash_movements_hotel_payment_correction", type_="foreignkey")
        batch_op.drop_constraint("uq_cash_movements_hotel_voided_correction", type_="unique")
        batch_op.drop_constraint("ck_cash_movements_void_metadata", type_="check")
        batch_op.drop_column("voided_by_payment_correction_id")
        batch_op.drop_column("voided_at")
