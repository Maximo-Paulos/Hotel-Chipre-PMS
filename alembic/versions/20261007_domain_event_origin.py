"""Add request correlation keys to durable realtime events.

Revision ID: 20261007_domain_event_origin
Revises: db9b84864700
Create Date: 2026-10-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_domain_event_origin"
down_revision: Union[str, None] = "db9b84864700"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "domain_event_outbox",
        sa.Column("origin_key", sa.String(length=36), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("domain_event_outbox", "origin_key")
