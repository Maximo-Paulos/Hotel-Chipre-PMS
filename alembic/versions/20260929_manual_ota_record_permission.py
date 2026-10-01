"""Add a dedicated permission for recording OTA reservations.

Revision ID: 20260929_manual_ota_record_permission
Revises: 20260928_movement_group_revert
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260929_manual_ota_record_permission"
down_revision: Union[str, None] = "20260928_movement_group_revert"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "reservation:ota_record"
_DESCRIPTION = "Record OTA reservations and reported prices"


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
                ('receptionist', :code, true),
                ('housekeeping', :code, false)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    # Keep authorization state intact if the application code is rolled back.
    pass
