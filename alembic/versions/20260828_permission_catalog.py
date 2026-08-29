"""seed section visibility permissions and their role defaults

Revision ID: 20260828_permission_catalog
Revises: 20260821_apple_sign_in
Create Date: 2026-08-28

The permission service also seeds these rows on application startup. This
migration makes the catalog available to existing installations before the
next request and only inserts missing defaults, preserving hotel overrides.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260828_permission_catalog"
down_revision: Union[str, None] = "20260821_apple_sign_in"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS: dict[str, str] = {
    "analytics:view": "Read analytics overview",
    "analytics:advanced:view": "Read advanced analytics views",
    "analytics:ai:view": "Use analytics AI assistant",
    "dashboard:view": "Read dashboard overview",
    "occupancy:view": "Read occupancy planning",
    "waitlist:view": "Read waitlist",
    "waitlist:manage": "Manage waitlist entries",
    "cash:view": "Read cash register",
    "company:view": "Read companies and documents",
    "settings:users:view": "Read staff users and roles",
    "settings:users:manage": "Manage staff users and roles",
    "settings:integrations:view": "Read integration connections",
    "settings:integrations:manage": "Manage integration connections",
    "settings:subscription:view": "Read subscription and plan details",
    "settings:security:view": "Read security settings",
    "settings:sessions:view": "Read active sessions",
    "settings:notifications:view": "Read notifications",
    "settings:assistant:view": "Read and use the operations assistant",
    "settings:tests:view": "Read test tools and settings",
}

ROLE_DEFAULTS: dict[str, frozenset[str]] = {
    "analytics:view": frozenset({"owner", "co_owner"}),
    "analytics:advanced:view": frozenset({"owner", "co_owner"}),
    "analytics:ai:view": frozenset({"owner", "co_owner"}),
    "dashboard:view": frozenset({"owner", "co_owner", "manager", "receptionist"}),
    "occupancy:view": frozenset({"owner", "co_owner", "manager", "receptionist"}),
    "waitlist:view": frozenset({"owner", "co_owner", "manager", "receptionist"}),
    "waitlist:manage": frozenset({"owner", "co_owner", "manager", "receptionist"}),
    "cash:view": frozenset({"owner", "co_owner", "receptionist"}),
    "company:view": frozenset({"owner", "co_owner"}),
    "settings:users:view": frozenset({"owner", "co_owner"}),
    "settings:users:manage": frozenset({"owner", "co_owner"}),
    "settings:integrations:view": frozenset({"owner", "co_owner"}),
    "settings:integrations:manage": frozenset({"owner", "co_owner"}),
    "settings:subscription:view": frozenset({"owner", "co_owner"}),
    "settings:security:view": frozenset({"owner", "co_owner"}),
    "settings:sessions:view": frozenset({"owner", "co_owner"}),
    "settings:notifications:view": frozenset({"owner", "co_owner", "manager", "receptionist"}),
    "settings:assistant:view": frozenset({"owner", "co_owner", "manager"}),
    "settings:tests:view": frozenset({"owner", "co_owner"}),
}
ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")


def _insert_permission_rows(connection) -> None:
    permission = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    existing = set(connection.execute(sa.text("SELECT code FROM permissions")).scalars())
    rows = [
        {"code": code, "description": description}
        for code, description in NEW_PERMISSIONS.items()
        if code not in existing
    ]
    if rows:
        op.bulk_insert(permission, rows)


def _insert_default_rows(connection) -> None:
    existing = {
        (row[0], row[1])
        for row in connection.execute(
            sa.text("SELECT role, permission_code FROM role_permission_defaults")
        ).all()
    }
    defaults = sa.table(
        "role_permission_defaults",
        sa.column("role", sa.String),
        sa.column("permission_code", sa.String),
        sa.column("allowed", sa.Boolean),
    )
    rows = [
        {"role": role, "permission_code": code, "allowed": role in ROLE_DEFAULTS[code]}
        for role in ROLES
        for code in NEW_PERMISSIONS
        if (role, code) not in existing
    ]
    if rows:
        op.bulk_insert(defaults, rows)


def upgrade() -> None:
    connection = op.get_bind()
    _insert_permission_rows(connection)
    _insert_default_rows(connection)


def downgrade() -> None:
    connection = op.get_bind()
    codes = tuple(NEW_PERMISSIONS)
    placeholders = ", ".join(f":code_{index}" for index, _ in enumerate(codes))
    params = {f"code_{index}": code for index, code in enumerate(codes)}

    connection.execute(
        sa.text(
            f"DELETE FROM role_permission_defaults WHERE permission_code IN ({placeholders})"
        ),
        params,
    )
    # Keep a catalog row when an operator has already used the permission in a
    # hotel- or user-level override. This makes downgrade data-safe while a
    # clean upgrade/downgrade remains fully reversible.
    for code in codes:
        connection.execute(
            sa.text(
                "DELETE FROM permissions "
                "WHERE code = :code "
                "AND NOT EXISTS ("
                "SELECT 1 FROM hotel_permission_overrides "
                "WHERE permission_code = :code"
                ") "
                "AND NOT EXISTS ("
                "SELECT 1 FROM user_permission_overrides "
                "WHERE permission_code = :code"
                ")"
            ),
            {"code": code},
        )
