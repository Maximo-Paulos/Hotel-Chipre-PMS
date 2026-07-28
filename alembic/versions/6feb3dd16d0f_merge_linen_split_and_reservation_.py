"""merge linen split and reservation quoted dual amounts

Revision ID: 6feb3dd16d0f
Revises: 20260727_linen_split, 20260727_res_quoted_dual_amt
Create Date: 2026-07-27 21:24:06.577759
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6feb3dd16d0f'
down_revision: Union[str, None] = ('20260727_linen_split', '20260727_res_quoted_dual_amt')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
