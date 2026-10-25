"""reservation cancellation policy snapshot

Revision ID: ebaf9d3d2baa
Revises: 20261023_housekeeping_checklists
Create Date: 2026-10-24 00:45:53.259471
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ebaf9d3d2baa'
down_revision: Union[str, None] = '20261023_housekeeping_checklists'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Existing reservations intentionally stay NULL: the current RatePlan is
    # not historical evidence of the terms accepted when those bookings were made.
    op.add_column(
        "reservations",
        sa.Column("cancellation_policy_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reservations", "cancellation_policy_snapshot")
