"""add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

When a company reservation is created/confirmed with payment_deferred, the
service computes a settlement due date (check_out + company.deferred_days) and
flags settlement_status='deferred'. The "register collection" action transitions
settlement_status to 'settled'.

Revision ID: 20260625_reservation_settlement_due_date
Revises: 20260625_drop_payment_surcharge_configs
Create Date: 2026-06-25
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260625_reservation_settlement_due_date"
down_revision: Union[str, Sequence[str], None] = "20260625_drop_payment_surcharge_configs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reservations",
        sa.Column("settlement_due_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reservations", "settlement_due_date")
