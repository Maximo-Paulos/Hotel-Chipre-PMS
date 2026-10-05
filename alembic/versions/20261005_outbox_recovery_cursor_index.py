"""Add an index for tenant-scoped outbox cursor recovery polling.

Revision ID: 20261005_outbox_recovery_cursor
Revises: d2a7e93f4c2b
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261005_outbox_recovery_cursor"
down_revision: Union[str, None] = "d2a7e93f4c2b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    index_columns = ["hotel_id", sa.text("coalesce(stream_cursor, id)")]
    if op.get_bind().dialect.name == "postgresql":
        # Avoid blocking writes while a potentially long-lived outbox is indexed.
        with op.get_context().autocommit_block():
            op.create_index(
                "ix_domain_event_outbox_recovery_cursor",
                "domain_event_outbox",
                index_columns,
                unique=False,
                postgresql_concurrently=True,
            )
        return

    op.create_index(
        "ix_domain_event_outbox_recovery_cursor",
        "domain_event_outbox",
        index_columns,
        unique=False,
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.drop_index(
                "ix_domain_event_outbox_recovery_cursor",
                table_name="domain_event_outbox",
                postgresql_concurrently=True,
            )
        return

    op.drop_index("ix_domain_event_outbox_recovery_cursor", table_name="domain_event_outbox")
