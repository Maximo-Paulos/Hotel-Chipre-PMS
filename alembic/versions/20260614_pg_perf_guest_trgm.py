"""Add PostgreSQL trigram indexes for guest search hot path.

Revision ID: 20260614_pg_perf_guest_trgm
Revises: 20260613_cash_open_idx
Create Date: 2026-06-14
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260614_pg_perf_guest_trgm"
down_revision: Union[str, Sequence[str], None] = "20260613_cash_open_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRIGRAM_INDEXES = (
    ("ix_guests_document_number_trgm", "document_number"),
    ("ix_guests_phone_trgm", "phone"),
    ("ix_guests_email_trgm", "email"),
    ("ix_guests_last_name_trgm", "last_name"),
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for index_name, column_name in TRIGRAM_INDEXES:
        op.create_index(
            index_name,
            "guests",
            [column_name],
            unique=False,
            postgresql_using="gin",
            postgresql_ops={column_name: "gin_trgm_ops"},
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for index_name, _column_name in reversed(TRIGRAM_INDEXES):
        op.drop_index(index_name, table_name="guests")
