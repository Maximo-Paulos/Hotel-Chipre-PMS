"""Restore the co-owner default for bounded manual reservation rates.

Revision ID: 20261011_co_owner_manual_rate_default
Revises: 20261010_company_night_charge_tenant_keys

The 20261007 migration narrowed this permission, but the accepted hotel policy
allows both the co-owner and manager to apply bounded manual rates. Keep the
new price-adjustment permission defaults separate and preserve scoped overrides.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261011_co_owner_manual_rate_default"
down_revision: Union[str, None] = "20261010_company_night_charge_tenant_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
        ),
        {"allowed": True},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "UPDATE role_permission_defaults SET allowed = :allowed "
            "WHERE role = 'co_owner' AND permission_code = 'reservation:manual_rate_limited'"
        ),
        {"allowed": False},
    )
