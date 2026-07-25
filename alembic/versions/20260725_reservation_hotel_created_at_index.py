"""Add (hotel_id, created_at) index on reservations for A2 recent-order paging.

Revision ID: 20260725_res_hotel_created_idx
Revises: 20260725_transaction_created_by_user
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260725_res_hotel_created_idx"
down_revision: Union[str, Sequence[str], None] = "20260725_transaction_created_by_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_reservation_hotel_created_at",
        "reservations",
        ["hotel_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reservation_hotel_created_at", table_name="reservations")
