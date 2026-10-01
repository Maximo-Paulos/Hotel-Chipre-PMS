"""Add separately guarded, MFA-protected manual cash adjustments.

Revision ID: 20261013_cash_adjustment_permission
Revises: 20261012_fx_market_preferences
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20261013_cash_adjustment_permission"
down_revision: Union[str, None] = "20261012_fx_market_preferences"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CODE = "cash:adjustment_manage"
_DESCRIPTION = "Manage manual cash balance adjustments"


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (code, description, critical, step_up_required, delegable)
            VALUES (:code, :description, false, true, true)
            ON CONFLICT (code) DO UPDATE SET
                description = excluded.description,
                critical = false,
                step_up_required = true,
                delegable = true
            """
        ),
        {"code": _CODE, "description": _DESCRIPTION},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permission_defaults (role, permission_code, allowed)
            VALUES
                ('owner', :code, true),
                ('co_owner', :code, true),
                ('manager', :code, false),
                ('receptionist', :code, false),
                ('housekeeping', :code, false)
            ON CONFLICT (role, permission_code) DO UPDATE SET
                allowed = excluded.allowed
            """
        ),
        {"code": _CODE},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM role_permission_defaults WHERE permission_code = :code"),
        {"code": _CODE},
    )
    # Retain the catalog entry if hotel/user delegation or an MFA ticket has
    # already referenced it; deleting it would cascade away active policy.
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE code = :code "
            "AND NOT EXISTS (SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM user_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM temporary_action_grants WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM action_step_up_ticket_uses WHERE permission_code = :code)"
        ),
        {"code": _CODE},
    )
