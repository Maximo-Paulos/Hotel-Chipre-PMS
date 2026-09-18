"""SQLite: give shift_handoffs' composite FK a unique parent key.

``shift_handoffs`` (20260910_operational_tasks_handoff) is created on every
dialect with ``FOREIGN KEY (hotel_id, cash_close_report_id) REFERENCES
cash_close_reports (hotel_id, id)``. The unique constraint that key needs,
``uq_cash_close_reports_hotel_id_id``, is only ever added by
20260725_repair_cash_handoff_schema, which returns early on anything but
PostgreSQL. So on a migrated SQLite database the parent key is not unique and,
with ``PRAGMA foreign_keys=ON``, every write to ``cash_close_reports`` fails
with "foreign key mismatch" -- closing a cash session answered 500 in local
development and in the e2e business journey.

SQLite accepts a UNIQUE INDEX as the parent key of a foreign key, so an index
is enough; no table rebuild. ``id`` is the primary key, so ``(hotel_id, id)``
is unique by construction and the index cannot fail on existing data. A scan
of every foreign key in a fully migrated SQLite database found this to be the
only parent key without uniqueness.

PostgreSQL already has the named constraint from the repair migration, so both
directions are no-ops there.

Revision ID: 20260917_sqlite_cash_close_parent_key
Revises: 20260911_whatsapp_crm
Create Date: 2026-09-17 22:47:19.007164
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260917_sqlite_cash_close_parent_key'
down_revision: Union[str, None] = '20260911_whatsapp_crm'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "uq_cash_close_reports_hotel_id_id"


def _has_unique_hotel_id_id(bind) -> bool:
    inspector = sa.inspect(bind)
    wanted = ["hotel_id", "id"]
    return any(item.get("column_names") == wanted for item in inspector.get_unique_constraints("cash_close_reports")) or any(
        item.get("unique") and item.get("column_names") == wanted
        for item in inspector.get_indexes("cash_close_reports")
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    # A database built from the models (create_all) already carries the
    # constraint inline; only migrated SQLite databases are missing it.
    if _has_unique_hotel_id_id(bind):
        return
    op.create_index(INDEX_NAME, "cash_close_reports", ["hotel_id", "id"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        return
    if any(item.get("name") == INDEX_NAME for item in sa.inspect(bind).get_indexes("cash_close_reports")):
        op.drop_index(INDEX_NAME, table_name="cash_close_reports")
