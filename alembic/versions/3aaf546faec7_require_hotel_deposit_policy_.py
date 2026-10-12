"""require hotel deposit policy confirmation

Revision ID: 3aaf546faec7
Revises: 3942765e8560
Create Date: 2026-10-11 07:04:04.874180
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3aaf546faec7'
down_revision: Union[str, None] = '3942765e8560'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "deposit_policy_configured",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("hotel_configuration", "deposit_policy_configured")
