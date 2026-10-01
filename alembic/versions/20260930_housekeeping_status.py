"""Separate housekeeping state from room availability.

Revision ID: 20260930_housekeeping_status
Revises: 20260929_cash_prior_receipts
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260930_housekeeping_status"
down_revision: Union[str, None] = "20260929_cash_prior_receipts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUS_CHECK = "ck_room_housekeeping_status"


def upgrade() -> None:
    with op.batch_alter_table("rooms") as batch_op:
        batch_op.add_column(
            sa.Column(
                "housekeeping_status",
                sa.String(length=24),
                nullable=False,
                server_default=sa.text("'clean'"),
            )
        )
        batch_op.create_check_constraint(
            _STATUS_CHECK,
            "housekeeping_status IN ('dirty', 'in_progress', 'clean', 'inspected')",
        )

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE rooms SET housekeeping_status = 'in_progress' "
            "WHERE status = 'cleaning'"
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("rooms") as batch_op:
        batch_op.drop_constraint(_STATUS_CHECK, type_="check")
        batch_op.drop_column("housekeeping_status")
