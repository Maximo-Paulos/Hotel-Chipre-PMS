"""Add tenant-scoped indexes for TECH-0063 OLTP hot paths.

The indexes mirror the predicates and ordering used by reservation, room,
reporting, and cash-register queries. The operations are guarded so this
revision remains safe for databases that received an index out of band.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260820_tech0063_oltp_idx"
down_revision: Union[str, Sequence[str], None] = "20260820_primary_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEXES = (
    ("ix_room_hotel_deleted_at", "rooms", ("hotel_id", "deleted_at")),
    ("ix_transactions_hotel_status_created_at", "transactions", ("hotel_id", "status", "created_at")),
    (
        "ix_cash_movements_hotel_session_recorded_at",
        "cash_movements",
        ("hotel_id", "session_id", "recorded_at", "id"),
    ),
    ("ix_reservation_hotel_check_in", "reservations", ("hotel_id", "check_in_date")),
    ("ix_reservation_hotel_check_out", "reservations", ("hotel_id", "check_out_date")),
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for index_name, table_name, columns in INDEXES:
        if index_name not in {index["name"] for index in inspector.get_indexes(table_name)}:
            op.create_index(index_name, table_name, list(columns), unique=False)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for index_name, table_name, _columns in reversed(INDEXES):
        if index_name in {index["name"] for index in inspector.get_indexes(table_name)}:
            op.drop_index(index_name, table_name=table_name)
