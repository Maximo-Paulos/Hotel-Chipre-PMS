"""Bind Master Admin sessions to the global user token version.

Revision ID: 20260927_master_admin_session_token_version
Revises: 20260927_revoke_public_rls_auto_enable
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260927_master_admin_session_token_version"
down_revision: Union[str, None] = "20260927_revoke_public_rls_auto_enable"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "master_admin_sessions" not in inspector.get_table_names():
        return
    if "token_version" not in {
        column["name"] for column in inspector.get_columns("master_admin_sessions")
    }:
        op.add_column(
            "master_admin_sessions",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "master_admin_sessions" not in inspector.get_table_names():
        return
    if "token_version" in {
        column["name"] for column in inspector.get_columns("master_admin_sessions")
    }:
        op.drop_column("master_admin_sessions", "token_version")
