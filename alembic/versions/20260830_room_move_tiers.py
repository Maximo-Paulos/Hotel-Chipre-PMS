"""Add nested authorization tiers for reservation room moves.

Revision ID: 20260830_room_move_tiers
Revises: 20260830_hk_occupancy_default
Create Date: 2026-08-30

The migration is additive: it only inserts missing catalog/default rows and
never changes an operator's hotel-level override decision.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260830_room_move_tiers"
down_revision: Union[str, None] = "20260830_hk_occupancy_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_PERMISSIONS: dict[str, str] = {
    "reservation:move_category": "Move reservations to another category with equal capacity",
    "reservation:move_capacity": "Move reservations to another category with different capacity",
}
ROLE_DEFAULTS: dict[str, frozenset[str]] = {
    "reservation:move_category": frozenset({"owner", "co_owner", "manager"}),
    "reservation:move_capacity": frozenset({"owner", "co_owner", "manager"}),
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
    # Preserve catalog rows still referenced by operator-created overrides;
    # otherwise a clean downgrade removes every row added by this revision.
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
