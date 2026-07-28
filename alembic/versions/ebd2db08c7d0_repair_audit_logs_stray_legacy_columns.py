"""repair audit_logs stray legacy columns

Revision ID: ebd2db08c7d0
Revises: 6feb3dd16d0f
Create Date: 2026-07-28 18:52:32.240561

Production incident 2026-07-28: DELETE /api/stock/items/{id} returned 204 but
the item was never actually soft-deleted. Root cause traced via Render's live
app logs: every INSERT into audit_logs was failing with

    psycopg2.errors.NotNullViolation: null value in column "resource_type"
    of relation "audit_logs" violates not-null constraint

The current AuditLog model (app/models/audit_log.py) has never had a
resource_type column, and no migration in this repo's history ever added one
to audit_logs (grep confirms). The failing row's own detail dump also showed
over a dozen other NULL columns beyond resource_type that don't exist in the
model either -- production's audit_logs table was created (or altered)
outside of this migration chain entirely, from an older/richer audit-log
design, and every "CREATE TABLE audit_logs IF NOT EXISTS"-style migration
since then silently skipped it because the table already existed.

app/services/audit_log_service.py::safe_create_audit_log() used to call
db.rollback() on any failure here, which -- because it ran in the SAME
session/transaction as the caller's real change -- also discarded whatever
the caller had already flushed (the stock item's deleted_at). That is fixed
separately (safe_create_audit_log now runs in its own SAVEPOINT, so this
class of bug can't silently eat a caller's real write again regardless of
what other schema drift is ever found). This migration fixes the actual
trigger: drop every column on the live audit_logs table that the current
model doesn't define.

Reflection-based rather than a hardcoded DROP COLUMN resource_type, since the
failing row showed several other stray legacy columns too -- this removes
all of them in one pass instead of hitting the next one on the next deploy.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'ebd2db08c7d0'
down_revision: Union[str, None] = '6feb3dd16d0f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Exactly the columns app/models/audit_log.py::AuditLog defines today.
_EXPECTED_COLUMNS = {
    "id",
    "hotel_id",
    "table_name",
    "record_id",
    "action",
    "actor_user_id",
    "payload_before",
    "payload_after",
    "created_at",
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite test/dev databases are always created fresh from the
        # current model via Base.metadata.create_all() -- they never
        # accumulate this kind of pre-Alembic legacy drift.
        return

    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return

    actual_columns = {col["name"] for col in inspector.get_columns("audit_logs")}
    stray_columns = actual_columns - _EXPECTED_COLUMNS
    for column_name in sorted(stray_columns):
        op.execute(f'ALTER TABLE "audit_logs" DROP COLUMN IF EXISTS "{column_name}"')


def downgrade() -> None:
    # No-op: the dropped columns were unused legacy drift left over from a
    # pre-Alembic schema iteration, not part of any migration this repo's
    # history ever intentionally created -- there is nothing to restore.
    pass
