"""add security tokens table

Revision ID: 20260408_security_tokens
Revises: d4f8c21e7b10
Create Date: 2026-04-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260408_security_tokens"
down_revision: Union[str, None] = "d4f8c21e7b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = inspector.get_table_names()

    if "security_tokens" not in table_names:
        op.create_table(
            "security_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("token_type", sa.String(length=50), nullable=False),
            sa.Column("subject_key", sa.String(length=255), nullable=False),
            sa.Column("code_hash", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_security_tokens_token_type", "security_tokens", ["token_type"])
        op.create_index("ix_security_tokens_subject_key", "security_tokens", ["subject_key"])
        op.create_index("ix_security_tokens_expires_at", "security_tokens", ["expires_at"])
        op.create_index("ix_security_tokens_consumed_at", "security_tokens", ["consumed_at"])
        op.create_index(
            "ix_security_tokens_lookup",
            "security_tokens",
            ["token_type", "subject_key", "consumed_at"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "security_tokens" in inspector.get_table_names():
        op.drop_index("ix_security_tokens_lookup", table_name="security_tokens")
        op.drop_index("ix_security_tokens_consumed_at", table_name="security_tokens")
        op.drop_index("ix_security_tokens_expires_at", table_name="security_tokens")
        op.drop_index("ix_security_tokens_subject_key", table_name="security_tokens")
        op.drop_index("ix_security_tokens_token_type", table_name="security_tokens")
        op.drop_table("security_tokens")
