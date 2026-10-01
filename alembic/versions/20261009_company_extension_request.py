"""Track a pending extension request on company reservations.

Revision ID: 20261009_company_extension_request
Revises: 20261008_owner_rate_adjust_default
Create Date: 2026-10-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261009_company_extension_request"
down_revision: Union[str, None] = "20261008_owner_rate_adjust_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "company_extension_request_pending",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("company_extension_request_note", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_column("company_extension_request_note")
        batch_op.drop_column("company_extension_request_pending")
