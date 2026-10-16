"""Add direction-specific USD conversion rate sides.

Revision ID: 20261016_fx_conversion_rate_sides
Revises: 20261018_fact_company_channel_enum
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261016_fx_conversion_rate_sides"
down_revision: Union[str, None] = "20261018_fact_company_channel_enum"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SIDES = (
    ("fx_usd_to_ars_rate_side", "ck_hotel_configuration_fx_usd_to_ars_rate_side"),
    ("fx_ars_to_usd_rate_side", "ck_hotel_configuration_fx_ars_to_usd_rate_side"),
)


def upgrade() -> None:
    for column_name, _constraint_name in _SIDES:
        op.add_column(
            "hotel_configuration",
            sa.Column(
                column_name,
                sa.String(length=10),
                nullable=False,
                server_default=sa.text("'venta'"),
            ),
        )

    if op.get_bind().dialect.name == "sqlite":
        # SQLite cannot add a CHECK constraint in place, so Alembic rebuilds
        # this single existing configuration table while retaining its rows.
        with op.batch_alter_table("hotel_configuration") as batch_op:
            for column_name, constraint_name in _SIDES:
                batch_op.create_check_constraint(
                    constraint_name,
                    f"{column_name} IN ('compra', 'venta')",
                )
    else:
        for column_name, constraint_name in _SIDES:
            op.create_check_constraint(
                constraint_name,
                "hotel_configuration",
                f"{column_name} IN ('compra', 'venta')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    customized = bind.execute(
        sa.text(
            "SELECT 1 FROM hotel_configuration "
            "WHERE fx_usd_to_ars_rate_side <> 'venta' "
            "OR fx_ars_to_usd_rate_side <> 'venta' LIMIT 1"
        )
    ).first()
    if customized is not None:
        raise RuntimeError(
            "Cannot downgrade FX conversion side settings while a hotel has a non-default selection"
        )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration") as batch_op:
            for column_name, constraint_name in reversed(_SIDES):
                batch_op.drop_constraint(constraint_name, type_="check")
                batch_op.drop_column(column_name)
    else:
        for column_name, constraint_name in reversed(_SIDES):
            op.drop_constraint(
                constraint_name,
                "hotel_configuration",
                type_="check",
            )
            op.drop_column("hotel_configuration", column_name)
