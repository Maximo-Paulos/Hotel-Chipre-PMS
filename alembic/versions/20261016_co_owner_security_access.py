"""Give the co-owner the confirmed owner-level administrative defaults.

Revision ID: 20261016_co_owner_security_access
Revises: 20261015_company_nightly_rate_history
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261016_co_owner_security_access"
down_revision: Union[str, None] = "20261015_company_nightly_rate_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERMISSION_CODES = (
    "hotel_settings:security_manage",
    "apikey:manage",
    "reservation:manual_rate",
    "reservation:manual_rate_policy_manage",
    "reservation:paid_total_adjust",
)


def upgrade() -> None:
    connection = op.get_bind()
    for code in PERMISSION_CODES:
        connection.execute(
            sa.text(
                "UPDATE role_permission_defaults SET allowed = true "
                "WHERE role = 'co_owner' AND permission_code = :code"
            ),
            {"code": code},
        )


def downgrade() -> None:
    connection = op.get_bind()
    for code in PERMISSION_CODES:
        connection.execute(
            sa.text(
                "UPDATE role_permission_defaults SET allowed = false "
                "WHERE role = 'co_owner' AND permission_code = :code"
            ),
            {"code": code},
        )
