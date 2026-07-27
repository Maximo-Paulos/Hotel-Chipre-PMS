"""merge stock kind fix and laundry vendor settlements

Revision ID: 513720cf2551
Revises: 20260727_stock_kind_fix, e2c4a9f7b3d1
Create Date: 2026-07-27 20:29:57.662433
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '513720cf2551'
down_revision: Union[str, None] = ('20260727_stock_kind_fix', 'e2c4a9f7b3d1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
