"""Add read access for the privacy-safe housekeeping board.

Revision ID: 20260930_housekeeping_board_permission
Revises: 20260930_housekeeping_status
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260930_housekeeping_board_permission"
down_revision: Union[str, None] = "20260930_housekeeping_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CODE = "housekeeping:board_view"


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
        {
            "code": _CODE,
            "description": "Read the privacy-safe housekeeping daily board",
        },
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
                ('housekeeping', :code, true)
            ON CONFLICT (role, permission_code) DO NOTHING
            """
        ),
        {"code": _CODE},
    )


def downgrade() -> None:
    # Keep authorization state intact if application code is rolled back.
    pass
