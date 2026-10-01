"""Link the outgoing and incoming ledger rows for atomic stock transfers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261002_stock_transfers"
down_revision: Union[str, None] = "20261001_reservation_groups"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stock_movements", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("transfer_reference", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint(
            "ck_stock_movements_transfer_direction_valid",
            "transfer_reference IS NULL OR movement_type IN ('in', 'out')",
        )
        batch_op.create_index(
            "uq_stock_movement_transfer_direction",
            ["hotel_id", "transfer_reference", "movement_type"],
            unique=True,
            sqlite_where=sa.text("transfer_reference IS NOT NULL"),
            postgresql_where=sa.text("transfer_reference IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("stock_movements", recreate="auto") as batch_op:
        batch_op.drop_index("uq_stock_movement_transfer_direction")
        batch_op.drop_constraint("ck_stock_movements_transfer_direction_valid", type_="check")
        batch_op.drop_column("transfer_reference")
