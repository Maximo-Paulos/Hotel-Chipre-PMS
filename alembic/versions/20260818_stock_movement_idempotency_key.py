"""add idempotency_key to stock_movements

Revision ID: 20260818_stock_movement_idem
Revises: 20260818_repair_room_company_uq
Create Date: 2026-08-18

Same shape as payment_links.idempotency_key (see
20260812_external_effect_payment_links): a nullable per-hotel-unique key so
a retried "register movement" request returns the first attempt's row
instead of double-counting stock. batch_alter_table's default "auto" recreate
mode already rebuilds the SQLite table when adding a UNIQUE constraint (SQLite
has no ALTER TABLE ADD CONSTRAINT), so this applies on both dialects with one
code path -- no dialect branching needed here.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260818_stock_movement_idem"
down_revision: Union[str, None] = "20260818_repair_room_company_uq"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.add_column(sa.Column("idempotency_key", sa.String(length=100), nullable=True))
        batch_op.create_unique_constraint(
            "uq_stock_movement_idempotency_per_hotel", ["hotel_id", "idempotency_key"]
        )


def downgrade() -> None:
    with op.batch_alter_table("stock_movements") as batch_op:
        batch_op.drop_constraint("uq_stock_movement_idempotency_per_hotel", type_="unique")
        batch_op.drop_column("idempotency_key")
