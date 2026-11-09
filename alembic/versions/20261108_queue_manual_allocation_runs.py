"""Queue manual room-allocation runs instead of blocking the API request.

Revision ID: 20261108_queue_manual_allocation_runs
Revises: 20261104_cash_change_settlement
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261108_queue_manual_allocation_runs"
down_revision: str | None = "20261104_cash_change_settlement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEX = "uq_allocation_runs_pending_reservation_create_hotel"
_OLD_PREDICATE = (
    "status = 'pending' AND trigger_type IN "
    "('reservation_created_auto_proposal', 'new_reservation', "
    "'reservation_date_change', 'reservation_update', "
    "'reservation_room_move', 'reservation_group_created')"
)
_NEW_PREDICATE = (
    "status = 'pending' AND trigger_type IN "
    "('reservation_created_auto_proposal', 'new_reservation', "
    "'reservation_date_change', 'reservation_update', "
    "'reservation_room_move', 'reservation_group_created', "
    "'manual_api_recalculate', 'manual_api_preview')"
)


def upgrade() -> None:
    op.drop_index(_INDEX, table_name="allocation_runs")
    op.create_index(
        _INDEX,
        "allocation_runs",
        ["hotel_id"],
        unique=True,
        postgresql_where=sa.text(_NEW_PREDICATE),
        sqlite_where=sa.text(_NEW_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="allocation_runs")
    op.create_index(
        _INDEX,
        "allocation_runs",
        ["hotel_id"],
        unique=True,
        postgresql_where=sa.text(_OLD_PREDICATE),
        sqlite_where=sa.text(_OLD_PREDICATE),
    )
