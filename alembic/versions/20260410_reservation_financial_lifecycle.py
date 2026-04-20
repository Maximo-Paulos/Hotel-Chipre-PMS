"""reservation financial lifecycle

Revision ID: 20260410_reservation_financial_lifecycle
Revises: dee1bd0660f6
Create Date: 2026-04-10 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260410_reservation_financial_lifecycle"
down_revision: Union[str, None] = "dee1bd0660f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("payment_collection_model", sa.String(length=40), nullable=False, server_default="hotel_collect"))
        batch_op.add_column(sa.Column("settlement_status", sa.String(length=40), nullable=False, server_default="not_applicable"))

    op.execute(
        """
        UPDATE reservations
        SET
            payment_collection_model = CASE
                WHEN source = 'direct' THEN 'hotel_collect'
                ELSE 'unknown'
            END,
            settlement_status = CASE
                WHEN source = 'direct' THEN 'not_applicable'
                ELSE 'pending'
            END
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("reservations", recreate="auto") as batch_op:
        batch_op.drop_column("settlement_status")
        batch_op.drop_column("payment_collection_model")
