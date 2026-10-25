"""Add a dedicated permission for reading company vouchers and signatures.

Revision ID: 20261025_company_documents_read
Revises: 20261024_cash_movement_voids
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261025_company_documents_read"
down_revision: Union[str, None] = "20261024_cash_movement_voids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PERMISSION = "company:documents:read"
_DESCRIPTION = "Read company vouchers and signatures"


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
    # Keep permission rows and overrides after rollback so customized grants
    # remain intact if the migration is applied again later.
    pass
