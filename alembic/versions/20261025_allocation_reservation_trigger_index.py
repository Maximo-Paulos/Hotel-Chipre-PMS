"""Coalesce pending automatic room-optimization proposals per hotel.

Revision ID: 20261025_allocation_reservation_trigger_index
Revises: 20261025_company_reservation_terms
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20261025_allocation_reservation_trigger_index"
down_revision: str | None = "20261025_company_reservation_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_INDEX = "uq_allocation_runs_pending_reservation_create_hotel"
_PREDICATE = (
    "status = 'pending' AND trigger_type IN "
    "('reservation_created_auto_proposal', 'new_reservation', "
    "'reservation_date_change', 'reservation_update', "
    "'reservation_room_move', 'reservation_group_created')"
)


def upgrade() -> None:
    op.create_index(
        _INDEX,
        "allocation_runs",
        ["hotel_id"],
        unique=True,
        postgresql_where=sa.text(_PREDICATE),
        sqlite_where=sa.text(_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(_INDEX, table_name="allocation_runs")
