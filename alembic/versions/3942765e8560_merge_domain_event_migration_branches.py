"""merge domain event migration branches

Revision ID: 3942765e8560
Revises: 20261007_domain_event_origin, 20261009_domain_event_notify
Create Date: 2026-10-11 07:04:02.344844
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3942765e8560'
down_revision: Union[str, None] = ('20261007_domain_event_origin', '20261009_domain_event_notify')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
