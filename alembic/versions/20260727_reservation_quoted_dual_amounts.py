"""Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA
pricing, independent of total_amount/currency_code).

Revision ID: 20260727_res_quoted_dual_amt
Revises: 513720cf2551
Create Date: 2026-07-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260727_res_quoted_dual_amt"
down_revision: Union[str, Sequence[str], None] = "513720cf2551"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = {col["name"] for col in sa.inspect(op.get_bind()).get_columns("reservations")}
    with op.batch_alter_table("reservations", schema=None) as batch_op:
        if "quoted_amount_ars" not in columns:
            batch_op.add_column(sa.Column("quoted_amount_ars", sa.Numeric(12, 2), nullable=True))
        if "quoted_amount_usd" not in columns:
            batch_op.add_column(sa.Column("quoted_amount_usd", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reservations", schema=None) as batch_op:
        batch_op.drop_column("quoted_amount_usd")
        batch_op.drop_column("quoted_amount_ars")
