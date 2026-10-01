"""cash successor float

Revision ID: f595b2191009
Revises: 6259a93c6205
Create Date: 2026-09-30 18:15:07.432994
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f595b2191009'
down_revision: Union[str, None] = '6259a93c6205'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("cash_close_reports") as batch_op:
        batch_op.add_column(sa.Column("successor_float_declared_amount", sa.Numeric(12, 2), nullable=True))
        batch_op.add_column(sa.Column("successor_float_declared_by_user_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("successor_float_declared_at", sa.DateTime(), nullable=True))
        batch_op.create_check_constraint(
            "ck_cash_close_successor_float_nonneg",
            "successor_float_declared_amount IS NULL OR successor_float_declared_amount >= 0",
        )
        batch_op.create_foreign_key(
            "fk_cash_close_reports_successor_float_declared_by_user",
            "users",
            ["successor_float_declared_by_user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("cash_close_reports") as batch_op:
        batch_op.drop_constraint("fk_cash_close_reports_successor_float_declared_by_user", type_="foreignkey")
        batch_op.drop_constraint("ck_cash_close_successor_float_nonneg", type_="check")
        batch_op.drop_column("successor_float_declared_at")
        batch_op.drop_column("successor_float_declared_by_user_id")
        batch_op.drop_column("successor_float_declared_amount")
