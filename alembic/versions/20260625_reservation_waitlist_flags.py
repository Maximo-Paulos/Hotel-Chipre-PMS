"""reservation waitlist flags (BRM v72 §9).

Add denormalized waitlist flags to reservations so overbooking / waitlist
state can be queried directly on the reservation while WaitlistEntry remains
the queue/detail model. Kept in sync by the service layer.

Revision ID: 20260625_reservation_waitlist_flags
Revises: 20260625_soft_delete
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_reservation_waitlist_flags"
down_revision: Union[str, Sequence[str], None] = "20260625_soft_delete"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Guarded because some production environments already have these
    # columns out-of-band via an old startup self-heal pass while
    # alembic_version stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    reservations_columns = {c["name"] for c in inspector.get_columns("reservations")}
    if "is_wait_listed" not in reservations_columns:
        op.add_column(
            "reservations",
            sa.Column(
                "is_wait_listed",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    if "wait_list_reason" not in reservations_columns:
        op.add_column(
            "reservations",
            sa.Column("wait_list_reason", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("reservations", "wait_list_reason")
    op.drop_column("reservations", "is_wait_listed")
