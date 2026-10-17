"""Configure official or blue USD quotes by conversion direction.

Revision ID: 20261016_fx_direction_markets
Revises: 20261016_fx_conversion_rate_sides
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261016_fx_direction_markets"
down_revision: Union[str, None] = "20261016_fx_conversion_rate_sides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MARKETS = (
    ("fx_usd_to_ars_rate_type", "ck_hotel_configuration_fx_usd_to_ars_rate_type"),
    ("fx_ars_to_usd_rate_type", "ck_hotel_configuration_fx_ars_to_usd_rate_type"),
)


def upgrade() -> None:
    for column_name, _constraint_name in _MARKETS:
        op.add_column(
            "hotel_configuration",
            sa.Column(
                column_name,
                sa.String(length=20),
                nullable=False,
                server_default=sa.text("'oficial'"),
            ),
        )

    # Preserve each hotel's existing market preference in both directions.
    op.execute(
        sa.text(
            "UPDATE hotel_configuration "
            "SET fx_usd_to_ars_rate_type = CASE "
            "WHEN fx_conversion_rate_type IN ('oficial', 'blue') THEN fx_conversion_rate_type "
            "ELSE 'oficial' END, "
            "fx_ars_to_usd_rate_type = CASE "
            "WHEN fx_conversion_rate_type IN ('oficial', 'blue') THEN fx_conversion_rate_type "
            "ELSE 'oficial' END"
        )
    )

    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration") as batch_op:
            for column_name, constraint_name in _MARKETS:
                batch_op.create_check_constraint(
                    constraint_name,
                    f"{column_name} IN ('oficial', 'blue')",
                )
    else:
        for column_name, constraint_name in _MARKETS:
            op.create_check_constraint(
                constraint_name,
                "hotel_configuration",
                f"{column_name} IN ('oficial', 'blue')",
            )


def downgrade() -> None:
    bind = op.get_bind()
    custom_selection = bind.execute(
        sa.text(
            "SELECT 1 FROM hotel_configuration "
            "WHERE fx_usd_to_ars_rate_type <> fx_conversion_rate_type "
            "OR fx_ars_to_usd_rate_type <> fx_conversion_rate_type LIMIT 1"
        )
    ).first()
    if custom_selection is not None:
        raise RuntimeError(
            "Cannot downgrade FX direction markets while a hotel has a market selection "
            "different from its global reference"
        )

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("hotel_configuration") as batch_op:
            for column_name, constraint_name in reversed(_MARKETS):
                batch_op.drop_constraint(constraint_name, type_="check")
                batch_op.drop_column(column_name)
    else:
        for column_name, constraint_name in reversed(_MARKETS):
            op.drop_constraint(constraint_name, "hotel_configuration", type_="check")
            op.drop_column("hotel_configuration", column_name)
