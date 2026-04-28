"""guest legal profile

Revision ID: 9c0d2f3e1a44
Revises: 3eaf48a79290
Create Date: 2026-04-17 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9c0d2f3e1a44"
down_revision: Union[str, None] = "3eaf48a79290"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


guest_document_type_enum = sa.Enum(
    "DNI",
    "PASSPORT",
    "CEDULA",
    name="guest_document_type_enum",
    create_constraint=True,
)


def upgrade() -> None:
    with op.batch_alter_table("guests") as batch_op:
        batch_op.add_column(sa.Column("retention_until", sa.DateTime(), nullable=True))
        batch_op.alter_column(
            "document_type",
            existing_type=sa.String(length=30),
            type_=guest_document_type_enum,
            existing_nullable=True,
            postgresql_using="document_type::guest_document_type_enum",
        )

    with op.batch_alter_table("guest_companions") as batch_op:
        batch_op.alter_column(
            "document_type",
            existing_type=sa.String(length=30),
            type_=guest_document_type_enum,
            existing_nullable=True,
            postgresql_using="document_type::guest_document_type_enum",
        )


def downgrade() -> None:
    with op.batch_alter_table("guest_companions") as batch_op:
        batch_op.alter_column(
            "document_type",
            existing_type=guest_document_type_enum,
            type_=sa.String(length=30),
            existing_nullable=True,
            postgresql_using="document_type::text",
        )

    with op.batch_alter_table("guests") as batch_op:
        batch_op.alter_column(
            "document_type",
            existing_type=guest_document_type_enum,
            type_=sa.String(length=30),
            existing_nullable=True,
            postgresql_using="document_type::text",
        )
        batch_op.drop_column("retention_until")
