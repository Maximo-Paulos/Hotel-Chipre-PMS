"""Add (hotel_id, created_at) index on reservations for A2 recent-order paging.

Revision ID: 20260725_res_hotel_created_idx
Revises: 20260725_transaction_created_by_user
Create Date: 2026-07-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260725_res_hotel_created_idx"
down_revision: Union[str, Sequence[str], None] = "20260725_transaction_created_by_user"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already have this index
    # out-of-band via an old startup self-heal pass while alembic_version
    # stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    if "ix_reservation_hotel_created_at" not in {ix["name"] for ix in inspector.get_indexes("reservations")}:
        op.create_index(
            "ix_reservation_hotel_created_at",
            "reservations",
            ["hotel_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_reservation_hotel_created_at", table_name="reservations")
