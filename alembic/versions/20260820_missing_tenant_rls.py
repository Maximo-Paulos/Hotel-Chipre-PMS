"""Add missing tenant RLS policies to existing hotel-scoped tables.

Revision ID: 20260820_missing_tenant_rls
Revises: 20260818_notifications
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260820_missing_tenant_rls"
down_revision: Union[str, None] = "7b14658560e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# `guest_alerts` and `reservation_movement_groups` were never created by the
# schema and have no ORM models. Their real tables are `guest_restrictions`
# (created and protected by `20260813_guest_restrictions`) and
# `room_movement_groups` (created by `20260612_v72_gaps_phase3` and protected
# by `20260724_tenant_rls_context`), respectively. Neither phantom belongs in
# this inventory.
_TABLES = (
    "hotel_api_keys",
)


def _install_rls(connection, table_name: str) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{table_name}"
           ON "{table_name}"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection, table_name: str) -> None:
    """Remove the PostgreSQL tenant policy before restoring the prior state."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"')
    op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()
    for table_name in _TABLES:
        _install_rls(connection, table_name)


def downgrade() -> None:
    connection = op.get_bind()
    for table_name in reversed(_TABLES):
        _remove_rls(connection, table_name)
