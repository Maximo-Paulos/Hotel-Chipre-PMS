"""Allow downward stock adjustments.

Previously "adjustment" stock movements could only increase quantity
(current_stock treated any non-"out" type as positive), so an owner
correcting a physical count that found *fewer* units than the system had no
way to record it without abusing "out" (which skips the adjust permission
and the audit label). This adds "adjustment_out" as a distinct, permission
gated movement type that decreases stock, matching "adjustment" (increase).

Revision ID: 20260725_stock_adjustment_out
Revises: 20260725_repair_cash_handoff_schema
Create Date: 2026-07-25 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "20260725_stock_adjustment_out"
down_revision: Union[str, None] = "20260725_repair_cash_handoff_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_VALUES = ("in", "out", "adjustment")
_NEW_VALUES = ("in", "out", "adjustment", "adjustment_out")


def _constraint(values: tuple[str, ...]) -> str:
    return "movement_type IN ({})".format(", ".join(repr(value) for value in values))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("stock_movements", recreate="always") as batch:
            batch.drop_constraint("ck_stock_movements_type_valid", type_="check")
            batch.create_check_constraint("ck_stock_movements_type_valid", _constraint(_NEW_VALUES))
    else:
        op.drop_constraint("ck_stock_movements_type_valid", "stock_movements", type_="check")
        op.create_check_constraint("ck_stock_movements_type_valid", "stock_movements", _constraint(_NEW_VALUES))


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        with op.batch_alter_table("stock_movements", recreate="always") as batch:
            batch.drop_constraint("ck_stock_movements_type_valid", type_="check")
            batch.create_check_constraint("ck_stock_movements_type_valid", _constraint(_OLD_VALUES))
    else:
        op.drop_constraint("ck_stock_movements_type_valid", "stock_movements", type_="check")
        op.create_check_constraint("ck_stock_movements_type_valid", "stock_movements", _constraint(_OLD_VALUES))
