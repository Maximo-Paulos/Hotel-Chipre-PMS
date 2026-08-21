"""Add soft-delete metadata to guests and payments for TECH-0110.

The columns are nullable so existing rows and deployments remain compatible.
This migration intentionally does not add delete endpoints or alter payment
ledger semantics; it only preserves the records if a future controlled
retention workflow needs to archive them without losing audit evidence.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260821_tech0110_operational_soft_delete"
down_revision: Union[str, Sequence[str], None] = "20260820_tech0063_oltp_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = {
    "guests": "ix_guest_hotel_deleted_at",
    "payments": "ix_payment_hotel_deleted_at",
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name, index_name in TABLES.items():
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        with op.batch_alter_table(table_name, recreate="auto") as batch_op:
            if "deleted_at" not in existing_columns:
                batch_op.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
            if "deleted_by_user_id" not in existing_columns:
                batch_op.add_column(
                    sa.Column(
                        "deleted_by_user_id",
                        sa.Integer(),
                        sa.ForeignKey(
                            "users.id",
                            name=f"fk_{table_name}_deleted_by_user_id",
                            ondelete="SET NULL",
                        ),
                        nullable=True,
                    )
                )

        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name not in existing_indexes:
            op.create_index(index_name, table_name, ["hotel_id", "deleted_at"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name, index_name in reversed(tuple(TABLES.items())):
        existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=table_name)

        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        with op.batch_alter_table(table_name, recreate="auto") as batch_op:
            if "deleted_by_user_id" in existing_columns:
                batch_op.drop_column("deleted_by_user_id")
            if "deleted_at" in existing_columns:
                batch_op.drop_column("deleted_at")
