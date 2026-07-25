"""Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for B2 occupancy grid.

Revision ID: 20260725_res_hotel_room_dates_idx
Revises: 20260725_res_hotel_created_idx
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260725_res_hotel_room_dates_idx"
down_revision: Union[str, Sequence[str], None] = "20260725_res_hotel_created_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_reservation_hotel_room_dates",
        "reservations",
        ["hotel_id", "room_id", "check_in_date", "check_out_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_reservation_hotel_room_dates", table_name="reservations")
