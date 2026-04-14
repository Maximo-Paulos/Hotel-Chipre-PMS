"""extend payment link tests states

Revision ID: d4f8c21e7b10
Revises: b7c1f0a8f9d2
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4f8c21e7b10"
down_revision: Union[str, None] = "b7c1f0a8f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_link_tests" not in inspector.get_table_names():
        return

    with op.batch_alter_table("payment_link_tests") as batch_op:
        if not _has_column(inspector, "payment_link_tests", "refunded_amount"):
            batch_op.add_column(sa.Column("refunded_amount", sa.Float(), nullable=True))
        if not _has_column(inspector, "payment_link_tests", "expires_at"):
            batch_op.add_column(sa.Column("expires_at", sa.DateTime(), nullable=True))
        if not _has_column(inspector, "payment_link_tests", "refunded_at"):
            batch_op.add_column(sa.Column("refunded_at", sa.DateTime(), nullable=True))
        if not _has_column(inspector, "payment_link_tests", "cancelled_at"):
            batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_link_tests" not in inspector.get_table_names():
        return

    with op.batch_alter_table("payment_link_tests") as batch_op:
        if _has_column(inspector, "payment_link_tests", "cancelled_at"):
            batch_op.drop_column("cancelled_at")
        if _has_column(inspector, "payment_link_tests", "refunded_at"):
            batch_op.drop_column("refunded_at")
        if _has_column(inspector, "payment_link_tests", "expires_at"):
            batch_op.drop_column("expires_at")
        if _has_column(inspector, "payment_link_tests", "refunded_amount"):
            batch_op.drop_column("refunded_amount")
