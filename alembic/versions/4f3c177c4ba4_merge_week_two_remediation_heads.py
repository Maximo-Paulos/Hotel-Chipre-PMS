"""Merge week two remediation heads

Revision ID: 4f3c177c4ba4
Revises: 20261005_outbox_recovery_cursor, 20261016_payment_receipt_email
Create Date: 2026-10-05 19:19:10.401478
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4f3c177c4ba4'
down_revision: Union[str, None] = ('20261005_outbox_recovery_cursor', '20261016_payment_receipt_email')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This revision only joins two independent schema histories; both parent
    # revisions have already applied their own DDL.
    pass


def downgrade() -> None:
    # Alembic moves back onto one parent branch; no schema operation belongs
    # to the merge revision itself.
    pass
