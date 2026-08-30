"""Align section defaults and remove the self-session catalog permission.

Revision ID: 20260829_permission_enforcement
Revises: 20260828_query_shape_indexes
Create Date: 2026-08-29

The two default changes are deliberately applied to the global role defaults,
not to hotel overrides. An existing hotel override therefore remains the
operator's explicit decision and continues to win during permission resolution.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260829_permission_enforcement"
down_revision: Union[str, None] = "20260828_query_shape_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SESSION_PERMISSION = "settings:sessions:view"
_DEFAULT_CHANGES = (
    ("housekeeping", "occupancy:view"),
    ("manager", "company:view"),
)
_ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")


def _set_role_default(connection, *, role: str, permission_code: str, allowed: bool) -> None:
    result = connection.execute(
        sa.text(
            "UPDATE role_permission_defaults "
            "SET allowed = :allowed "
            "WHERE role = :role AND permission_code = :permission_code"
        ),
        {"allowed": allowed, "role": role, "permission_code": permission_code},
    )
    if result.rowcount:
        return

    connection.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) "
            "SELECT :role, :permission_code, :allowed "
            "WHERE EXISTS (SELECT 1 FROM permissions WHERE code = :permission_code) "
            "AND NOT EXISTS ("
            "SELECT 1 FROM role_permission_defaults "
            "WHERE role = :role AND permission_code = :permission_code"
            ")"
        ),
        {"allowed": allowed, "role": role, "permission_code": permission_code},
    )


def _restore_session_permission(connection) -> None:
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description) "
            "SELECT :code, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ),
        {"code": _SESSION_PERMISSION, "description": "Read active sessions"},
    )
    for role in _ROLES:
        _set_role_default(
            connection,
            role=role,
            permission_code=_SESSION_PERMISSION,
            allowed=role in {"owner", "co_owner"},
        )


def upgrade() -> None:
    connection = op.get_bind()

    # Backfill the authorised defaults for existing installations. Updating
    # only role_permission_defaults preserves every hotel-level override row.
    for role, permission_code in _DEFAULT_CHANGES:
        _set_role_default(connection, role=role, permission_code=permission_code, allowed=True)

    # This capability was never valid for the caller-owned sessions endpoint.
    # Remove dependent overrides first so the catalog delete is FK-safe. The
    # cleanup is intentional and cannot restore obsolete operator overrides on
    # downgrade; the permission itself and its role defaults are restored.
    for table in ("hotel_permission_overrides", "user_permission_overrides"):
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE permission_code = :permission_code"),
            {"permission_code": _SESSION_PERMISSION},
        )
    connection.execute(
        sa.text(
            "DELETE FROM role_permission_defaults WHERE permission_code = :permission_code"
        ),
        {"permission_code": _SESSION_PERMISSION},
    )
    connection.execute(
        sa.text("DELETE FROM permissions WHERE code = :permission_code"),
        {"permission_code": _SESSION_PERMISSION},
    )


def downgrade() -> None:
    connection = op.get_bind()

    _restore_session_permission(connection)
    for role, permission_code in _DEFAULT_CHANGES:
        _set_role_default(connection, role=role, permission_code=permission_code, allowed=False)

