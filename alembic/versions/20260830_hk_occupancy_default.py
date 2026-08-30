"""Tighten housekeeping's default access to occupancy planning.

Revision ID: 20260830_hk_occupancy_default
Revises: 20260829_permission_enforcement
Create Date: 2026-08-30

Cleaning staff do not receive guest or reservation data by default, so the
occupancy planner is intentionally removed from housekeeping's defaults. The
occupancy-grid endpoint continues to require both room:read and occupancy:view.
An owner may still grant occupancy:view for a particular hotel through the
hotel permission matrix; this migration does not alter those explicit overrides.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260830_hk_occupancy_default"
down_revision: Union[str, None] = "20260829_permission_enforcement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ROLE = "housekeeping"
_PERMISSION = "occupancy:view"


def _set_role_default(connection, *, allowed: bool) -> None:
    """Set one global default without creating duplicate rows on reruns."""
    result = connection.execute(
        sa.text(
            "UPDATE role_permission_defaults "
            "SET allowed = :allowed "
            "WHERE role = :role AND permission_code = :permission_code"
        ),
        {"allowed": allowed, "role": _ROLE, "permission_code": _PERMISSION},
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
        {"allowed": allowed, "role": _ROLE, "permission_code": _PERMISSION},
    )


def upgrade() -> None:
    connection = op.get_bind()

    # Deliberate product tightening: cleaning staff must not see the planner's
    # guest names and reservations by default. Touch only the global default;
    # a hotel's explicit hotel_permission_overrides row remains authoritative.
    _set_role_default(connection, allowed=False)


def downgrade() -> None:
    connection = op.get_bind()
    _set_role_default(connection, allowed=True)
