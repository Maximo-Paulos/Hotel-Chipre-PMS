"""add permission metadata and optimistic override versions

Revision ID: 20260820_permission_metadata
Revises: 20260820_user_sessions
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260820_permission_metadata"
down_revision: Union[str, None] = "20260820_user_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OWNER_ONLY_CODES = (
    "permissions:manage",
    "hotel_settings:property_manage",
    "hotel_settings:security_manage",
    "apikey:manage",
)


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    permission_columns = {column["name"] for column in inspector.get_columns("permissions")}
    if "critical" not in permission_columns:
        op.add_column("permissions", sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "step_up_required" not in permission_columns:
        op.add_column(
            "permissions",
            sa.Column("step_up_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "delegable" not in permission_columns:
        op.add_column("permissions", sa.Column("delegable", sa.Boolean(), nullable=False, server_default=sa.true()))

    for table_name in ("hotel_permission_overrides", "user_permission_overrides"):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "version" not in columns:
            op.add_column(table_name, sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE permissions "
            "SET critical = :critical, step_up_required = :step_up_required, delegable = :delegable "
            "WHERE code IN (:code_0, :code_1, :code_2, :code_3)"
        ),
        {
            "critical": True,
            "step_up_required": True,
            "delegable": False,
            **{f"code_{index}": code for index, code in enumerate(OWNER_ONLY_CODES)},
        },
    )


def downgrade() -> None:
    op.drop_column("user_permission_overrides", "version")
    op.drop_column("hotel_permission_overrides", "version")
    op.drop_column("permissions", "delegable")
    op.drop_column("permissions", "step_up_required")
    op.drop_column("permissions", "critical")
