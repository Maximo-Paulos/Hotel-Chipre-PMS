"""Add missing tenant RLS policies to existing hotel-scoped tables.

Revision ID: 20260820_missing_tenant_rls
Revises: 20260818_notifications
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op


revision: str = "20260820_missing_tenant_rls"
down_revision: Union[str, None] = "20260818_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES = (
    "hotel_api_keys",
    "guest_alerts",
    "reservation_movement_groups",
)


def _install_rls(connection, table_name: str) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
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
