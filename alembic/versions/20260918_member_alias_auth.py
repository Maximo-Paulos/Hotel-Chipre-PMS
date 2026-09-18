"""Add hotel-scoped staff aliases and password-login capability state.

Revision ID: 20260918_member_alias_auth
Revises: 20260917_sqlite_cash_close_parent_key
Create Date: 2026-09-18

The schema change is intentionally forward-only: retaining these additive
columns on application rollback preserves operator aliases and auth state.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260918_member_alias_auth"
down_revision: Union[str, None] = "20260917_sqlite_cash_close_parent_key"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ALIAS_INDEX = "uq_membership_hotel_alias_key"


def _columns(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    user_columns = _columns(bind, "users")
    if "password_login_enabled" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "password_login_enabled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
        )

    membership_columns = _columns(bind, "hotel_memberships")
    if "alias" not in membership_columns:
        op.add_column("hotel_memberships", sa.Column("alias", sa.String(length=80), nullable=True))
    if "alias_key" not in membership_columns:
        op.add_column("hotel_memberships", sa.Column("alias_key", sa.String(length=240), nullable=True))

    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("hotel_memberships")}
    existing_constraints = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("hotel_memberships")
    }
    if ALIAS_INDEX not in existing_indexes and ALIAS_INDEX not in existing_constraints:
        op.create_index(
            ALIAS_INDEX,
            "hotel_memberships",
            ["hotel_id", "alias_key"],
            unique=True,
        )


def downgrade() -> None:
    # The older application ignores these additive fields. Removing them would
    # erase aliases or auth state; upgrade is idempotent for a later re-upgrade.
    pass
