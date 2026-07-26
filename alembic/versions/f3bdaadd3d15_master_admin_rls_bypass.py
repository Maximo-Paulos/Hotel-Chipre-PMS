"""master admin rls bypass

Adds a session-scoped bypass to the tenant-isolation RLS policies on the
tables the master-admin platform panel (app/master_admin/router.py) reads
and writes across every hotel: subscriptions, subscription_events (written
transitively by app/services/subscription_entitlements.py when a snapshot
read triggers a trial-expiry side effect) and hotel_subscriptions (legacy
mirror kept in sync by the same service).

Without this, a request authenticated via require_master_admin() never set
app.hotel_id, so the baseline policy from 20260724_tenant_rls_context
(``hotel_id = current_setting('app.hotel_id')``) evaluates to NULL and
returns/allows zero rows for every hotel -- the master-admin dashboard's
subscription counts silently read as 0 under FORCE ROW LEVEL SECURITY. A
correctness bug, not only a security gap, if RLS is applied in production.

The bypass is opt-in: it only activates when the *session* explicitly sets
``app.master_admin = 'true'`` (see app/services/tenant_context.py::
set_master_admin_context, wired into app/master_admin/security.py::
require_master_admin -- called only after a verified platform_admin cookie
session passes CSRF/lockout checks). No other code path sets this setting,
so ordinary tenant-scoped requests (app.hotel_id set, app.master_admin
unset) are unaffected -- ``current_setting('app.master_admin', true)``
returns '' for them, so the OR short-circuits to the original clause.

Revision ID: f3bdaadd3d15
Revises: 890876b925a7
Create Date: 2026-07-25
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = 'f3bdaadd3d15'
down_revision: Union[str, None] = '890876b925a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables actually queried (directly, in app/master_admin/router.py, or
# transitively via app/services/subscription_entitlements.py) by the
# master-admin panel. Keep in sync if new tenant-scoped reads are added
# to that router.
MASTER_ADMIN_BYPASS_TABLES: tuple[str, ...] = (
    "subscriptions",
    "subscription_events",
    "hotel_subscriptions",
)


def _policy_name(table_name: str) -> str:
    return f"tenant_isolation_{table_name}"


def _quoted_table(table_name: str) -> str:
    # The table names are the reviewed static tuple above, not user input.
    return f'"{table_name}"'


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    existing_tables = set(inspect(bind).get_table_names())
    for table_name in MASTER_ADMIN_BYPASS_TABLES:
        if table_name not in existing_tables:
            continue
        table = _quoted_table(table_name)
        policy = _policy_name(table_name)
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON {table}')
        op.execute(
            f'''CREATE POLICY "{policy}" ON {table}
                USING (
                    current_setting('app.master_admin', true) = 'true'
                    OR hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer
                )
                WITH CHECK (
                    current_setting('app.master_admin', true) = 'true'
                    OR hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer
                )'''
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    existing_tables = set(inspect(bind).get_table_names())
    for table_name in MASTER_ADMIN_BYPASS_TABLES:
        if table_name not in existing_tables:
            continue
        table = _quoted_table(table_name)
        policy = _policy_name(table_name)
        op.execute(f'DROP POLICY IF EXISTS "{policy}" ON {table}')
        op.execute(
            f'''CREATE POLICY "{policy}" ON {table}
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )
