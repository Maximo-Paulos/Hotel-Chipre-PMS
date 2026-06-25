"""v72 §16.2: add 'company' value to reservation_channel_code_enum.

Adds the corporate/empresa channel so reservations booked on behalf of a
company can be distinguished at the channel level. The reportable origin is
still derived (company_id always wins) — this only widens the channel enum.

On SQLite the channel_code column is stored via a CHECK constraint rather than
a native type, and the model now lists 'company', so no DDL is required there.
On PostgreSQL we ALTER TYPE ... ADD VALUE idempotently.

Revision ID: 20260625_reservation_channel_company
Revises: 20260625_reservation_settlement_due_date
Create Date: 2026-06-25
"""
from alembic import op

revision = "20260625_reservation_channel_company"
down_revision = "20260625_reservation_settlement_due_date"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # ADD VALUE cannot run inside a transaction block on older PG; commit first.
        op.execute("COMMIT")
        op.execute(
            "ALTER TYPE reservation_channel_code_enum ADD VALUE IF NOT EXISTS 'company'"
        )


def downgrade() -> None:
    # PostgreSQL does not support removing a value from an enum type without a
    # full type rebuild; leaving the value in place is safe and idempotent.
    pass
