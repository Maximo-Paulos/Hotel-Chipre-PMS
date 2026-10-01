"""Record laundry locations and link atomic linen transfers

Revision ID: 6259a93c6205
Revises: 20261003_manual_rate_policy
Create Date: 2026-09-30 10:52:58.427299
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6259a93c6205'
down_revision: Union[str, None] = '20261003_manual_rate_policy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("laundry_remitos", recreate="auto") as batch_op:
        # Nullable to preserve existing history. Old remito movements were not
        # linked to their parent row, so their house location cannot be
        # backfilled without guessing.
        batch_op.add_column(sa.Column("house_location_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_laundry_remitos_hotel_house_location",
            "linen_locations",
            ["hotel_id", "house_location_id"],
            ["hotel_id", "id"],
        )

    with op.batch_alter_table("linen_movements", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("transfer_reference", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint(
            "ck_linen_movements_transfer_direction_valid",
            "transfer_reference IS NULL OR movement_type IN ('in', 'out')",
        )
        batch_op.create_index(
            "uq_linen_movement_transfer_direction",
            ["hotel_id", "transfer_reference", "movement_type"],
            unique=True,
            sqlite_where=sa.text("transfer_reference IS NOT NULL"),
            postgresql_where=sa.text("transfer_reference IS NOT NULL"),
        )


def downgrade() -> None:
    with op.batch_alter_table("linen_movements", recreate="auto") as batch_op:
        batch_op.drop_index("uq_linen_movement_transfer_direction")
        batch_op.drop_constraint("ck_linen_movements_transfer_direction_valid", type_="check")
        batch_op.drop_column("transfer_reference")
    with op.batch_alter_table("laundry_remitos", recreate="auto") as batch_op:
        batch_op.drop_constraint("fk_laundry_remitos_hotel_house_location", type_="foreignkey")
        batch_op.drop_column("house_location_id")
