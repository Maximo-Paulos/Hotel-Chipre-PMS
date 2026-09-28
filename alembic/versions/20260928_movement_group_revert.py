"""Add a dedicated permission for reverting room-movement groups.

Revision ID: 20260928_movement_group_revert
Revises: 20260928_public_inquiry_retention_anchor
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260928_movement_group_revert"
down_revision: Union[str, None] = "20260928_public_inquiry_retention_anchor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "reservation:movement_group_revert"
_DESCRIPTION = "Revert allocation movement groups"


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES (:code, :description, false, false, true)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"code": _PERMISSION, "description": _DESCRIPTION},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permission_defaults (role, permission_code, allowed)
            VALUES
                ('owner', :code, true),
                ('co_owner', :code, true),
                ('manager', :code, true),
                ('receptionist', :code, false),
                ('housekeeping', :code, false)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    # Permission grants may have been customized after deployment. Preserve
    # the catalog/default rows so rolling back application code cannot erase
    # operator-managed authorization state.
    pass
