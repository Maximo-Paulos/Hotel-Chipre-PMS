"""add configurable permission for reservation price adjustments

Revision ID: 20261007_reservation_rate_adjust_permission
Revises: 20261006_company_night_surcharges
Create Date: 2026-10-07

The owner and manager receive the new price-adjustment capability by default.
The co-owner default for bounded manual rates is narrowed to match the hotel
owner's instruction; explicit hotel/user overrides remain untouched.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_reservation_rate_adjust_permission"
down_revision: Union[str, None] = "20261006_company_night_surcharges"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSION_CODE = "reservation:rate_adjust"
PERMISSION_DESCRIPTION = "Apply reservation price changes and complimentary upgrades"
ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")
ALLOWED_ROLES = frozenset({"owner", "manager"})


def upgrade() -> None:
    connection = op.get_bind()
    exists = connection.execute(
        sa.text("SELECT 1 FROM permissions WHERE code = :code"),
        {"code": PERMISSION_CODE},
    ).first()
    if exists is None:
        op.bulk_insert(
            sa.table(
                "permissions",
                sa.column("code", sa.String),
                sa.column("description", sa.String),
                sa.column("critical", sa.Boolean),
                sa.column("step_up_required", sa.Boolean),
                sa.column("delegable", sa.Boolean),
            ),
            [{
                "code": PERMISSION_CODE,
                "description": PERMISSION_DESCRIPTION,
                "critical": False,
                "step_up_required": False,
                "delegable": True,
            }],
        )

    existing_defaults = {
        (row[0], row[1])
        for row in connection.execute(
            sa.text(
                "SELECT role, permission_code FROM role_permission_defaults "
                "WHERE permission_code = :code"
            ),
            {"code": PERMISSION_CODE},
        ).all()
    }
    missing_defaults = [
        {"role": role, "permission_code": PERMISSION_CODE, "allowed": role in ALLOWED_ROLES}
        for role in ROLES
        if (role, PERMISSION_CODE) not in existing_defaults
    ]
    if missing_defaults:
        op.bulk_insert(
            sa.table(
                "role_permission_defaults",
                sa.column("role", sa.String),
                sa.column("permission_code", sa.String),
                sa.column("allowed", sa.Boolean),
            ),
            missing_defaults,
        )

    # Runtime seeding intentionally preserves persisted defaults. Apply this
    # one explicit product-policy change to the baseline while leaving any
    # hotel-level or user-level permission overrides intact.
    connection.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
        ),
        {"allowed": False},
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
        ),
        {"allowed": True},
    )
    connection.execute(
        sa.text("DELETE FROM role_permission_defaults WHERE permission_code = :code"),
        {"code": PERMISSION_CODE},
    )
    # Preserve the catalog row if an operator already referenced this
    # permission in an override, temporary grant, or step-up use.
    connection.execute(
        sa.text(
            "DELETE FROM permissions WHERE code = :code "
            "AND NOT EXISTS (SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM user_permission_overrides WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM temporary_action_grants WHERE permission_code = :code) "
            "AND NOT EXISTS (SELECT 1 FROM action_step_up_ticket_uses WHERE permission_code = :code)"
        ),
        {"code": PERMISSION_CODE},
    )
