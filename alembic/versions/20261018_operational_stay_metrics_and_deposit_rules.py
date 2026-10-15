"""Persist configurable deposit bands and stay-night counts.

Revision ID: 20261018_stay_metrics_deposit_rules
Revises: 20261017_analytics_fact_refresh_queue
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261018_stay_metrics_deposit_rules"
down_revision: Union[str, None] = "20261017_analytics_fact_refresh_queue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hotel_configuration", sa.Column("deposit_policy_rules", sa.JSON(), nullable=True))
    op.add_column(
        "reservations",
        sa.Column("reserved_nights", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column("reservations", sa.Column("used_nights", sa.Integer(), nullable=True))

    bind = op.get_bind()
    # Direct check-in now always requires full settlement. Normalize legacy
    # settings so the existing settings form can continue submitting its full
    # config object without carrying a value the API no longer accepts.
    bind.execute(
        sa.text(
            "UPDATE hotel_configuration SET checkin_payment_policy = 'total' "
            "WHERE checkin_payment_policy IN ('deposit', 'free')"
        )
    )
    if bind.dialect.name == "sqlite":
        bind.execute(
            sa.text(
                "UPDATE reservations SET reserved_nights = "
                "MAX(1, CAST(julianday(check_out_date) - julianday(check_in_date) AS INTEGER))"
            )
        )
    else:
        bind.execute(
            sa.text("UPDATE reservations SET reserved_nights = GREATEST(1, check_out_date - check_in_date)")
        )

    hotel_table = sa.table(
        "hotel_configuration",
        sa.column("id", sa.Integer()),
        sa.column("deposit_percentage", sa.Float()),
        sa.column("deposit_policy_rules", sa.JSON()),
    )
    for hotel_id, percentage in bind.execute(
        sa.select(hotel_table.c.id, hotel_table.c.deposit_percentage)
    ).all():
        bind.execute(
            hotel_table.update()
            .where(hotel_table.c.id == hotel_id)
            .values(
                deposit_policy_rules=[
                    {"max_nights": None, "calculation": "percentage", "value": float(percentage or 0)}
                ]
            )
        )


def downgrade() -> None:
    op.drop_column("reservations", "used_nights")
    op.drop_column("reservations", "reserved_nights")
    op.drop_column("hotel_configuration", "deposit_policy_rules")
