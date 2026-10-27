"""Add elevator knowledge and soft allocation preferences by room.

Revision ID: 20261027_alloc_room_prefs
Revises: 20261027_tariff_history_and_policy
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


revision: str = "20261027_alloc_room_prefs"
down_revision: str | None = "20261027_tariff_history_and_policy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    hotel_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
    if "has_elevator" not in hotel_columns:
        op.add_column("hotel_configuration", sa.Column("has_elevator", sa.Boolean(), nullable=True))

    room_columns = {column["name"] for column in sa.inspect(bind).get_columns("rooms")}
    for name in ("allocation_priority_channel_groups", "allocation_priority_company_ids"):
        if name not in room_columns:
            op.add_column(
                "rooms",
                sa.Column(
                    name,
                    sa.JSON(),
                    nullable=False,
                    server_default=sa.text("'[]'"),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    room_columns = {column["name"] for column in sa.inspect(bind).get_columns("rooms")}
    for name in ("allocation_priority_company_ids", "allocation_priority_channel_groups"):
        if name in room_columns:
            op.drop_column("rooms", name)
    hotel_columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_configuration")}
    if "has_elevator" in hotel_columns:
        op.drop_column("hotel_configuration", "has_elevator")
