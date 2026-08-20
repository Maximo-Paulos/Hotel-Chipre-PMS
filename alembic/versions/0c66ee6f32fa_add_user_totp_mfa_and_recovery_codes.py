"""add user TOTP MFA and recovery codes

Revision ID: 0c66ee6f32fa
Revises: 20260820_missing_tenant_rls
Create Date: 2026-08-20 13:11:15.061373
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0c66ee6f32fa'
down_revision: Union[str, None] = '20260820_missing_tenant_rls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_mfa_secrets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("encrypted_secret", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("last_used_step", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_mfa_secrets_user_id"),
    )
    op.create_index("ix_user_mfa_secrets_user_id", "user_mfa_secrets", ["user_id"], unique=False)

    op.create_table(
        "user_mfa_recovery_codes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mfa_secret_id", sa.Integer(), nullable=False),
        sa.Column("code_hash", sa.Text(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["mfa_secret_id"], ["user_mfa_secrets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_mfa_recovery_codes_user_id", "user_mfa_recovery_codes", ["user_id"], unique=False)
    op.create_index(
        "ix_user_mfa_recovery_codes_mfa_secret_id",
        "user_mfa_recovery_codes",
        ["mfa_secret_id"],
        unique=False,
    )
    op.create_index("ix_user_mfa_recovery_codes_used_at", "user_mfa_recovery_codes", ["used_at"], unique=False)
    op.create_index(
        "ix_user_mfa_recovery_codes_user_unused",
        "user_mfa_recovery_codes",
        ["user_id", "used_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_mfa_recovery_codes_user_unused", table_name="user_mfa_recovery_codes")
    op.drop_index("ix_user_mfa_recovery_codes_used_at", table_name="user_mfa_recovery_codes")
    op.drop_index("ix_user_mfa_recovery_codes_mfa_secret_id", table_name="user_mfa_recovery_codes")
    op.drop_index("ix_user_mfa_recovery_codes_user_id", table_name="user_mfa_recovery_codes")
    op.drop_table("user_mfa_recovery_codes")
    op.drop_index("ix_user_mfa_secrets_user_id", table_name="user_mfa_secrets")
    op.drop_table("user_mfa_secrets")
