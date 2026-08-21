"""add Apple subject and first-authorization display name

Revision ID: 20260821_apple_sign_in
Revises: 20260820_guest_search_first_name_index
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260821_apple_sign_in"
down_revision: Union[str, None] = "20260820_tech0063_oltp_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "apple_sub" not in columns:
        op.add_column("users", sa.Column("apple_sub", sa.String(length=255), nullable=True))
    if "display_name" not in columns:
        op.add_column("users", sa.Column("display_name", sa.String(length=255), nullable=True))
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_apple_sub" not in indexes:
        op.create_index("ix_users_apple_sub", "users", ["apple_sub"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("users")}
    if "ix_users_apple_sub" in indexes:
        op.drop_index("ix_users_apple_sub", table_name="users")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("users")}
    if "display_name" in columns:
        op.drop_column("users", "display_name")
    if "apple_sub" in columns:
        op.drop_column("users", "apple_sub")
