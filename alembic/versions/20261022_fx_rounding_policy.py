"""Persist each hotel's foreign-payment FX rounding policy.

Revision ID: 20261022_fx_rounding_policy
Revises: aa2eb9bde9e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261022_fx_rounding_policy"
down_revision: Union[str, None] = "aa2eb9bde9e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONSTRAINT_NAME = "ck_hotel_configuration_fx_rounding_policy"


def upgrade() -> None:
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "fx_rounding_policy",
            sa.String(length=24),
            nullable=False,
            server_default=sa.text("'keep_remainder'"),
        ),
    )

    check_sql = "fx_rounding_policy IN ('round_up', 'round_down', 'nearest_ten', 'exact', 'keep_remainder')"
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration") as batch_op:
            batch_op.create_check_constraint(CONSTRAINT_NAME, check_sql)
    else:
        op.create_check_constraint(CONSTRAINT_NAME, "hotel_configuration", check_sql)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration") as batch_op:
            batch_op.drop_constraint(CONSTRAINT_NAME, type_="check")
            batch_op.drop_column("fx_rounding_policy")
    else:
        op.drop_constraint(CONSTRAINT_NAME, "hotel_configuration", type_="check")
        op.drop_column("hotel_configuration", "fx_rounding_policy")
