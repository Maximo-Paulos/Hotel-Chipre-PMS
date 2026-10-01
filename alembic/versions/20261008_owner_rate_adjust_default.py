"""Make complimentary rate adjustments manager-only by default.

Revision ID: 20261008_owner_rate_adjust_default
Revises: 20261007_reservation_rate_adjust_permission
Create Date: 2026-10-08

Hotel role and user overrides remain untouched, so an owner can explicitly
configure this capability through the existing permission settings screen.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261008_owner_rate_adjust_default"
down_revision: Union[str, None] = "20261007_reservation_rate_adjust_permission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'owner' AND permission_code = 'reservation:rate_adjust'"
        ).bindparams(allowed=False)
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'owner' AND permission_code = 'reservation:rate_adjust'"
        ).bindparams(allowed=True)
    )
