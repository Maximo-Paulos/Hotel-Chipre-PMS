"""Expand public inquiries with a last-updated retention anchor.

Revision ID: 20260928_public_inquiry_updated_at
Revises: 20260927_ota_credit_data
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260928_public_inquiry_updated_at"
down_revision: Union[str, None] = "20260927_ota_credit_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLE = "public_inquiries"
_INDEX = "ix_public_inquiries_updated_at"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        return

    schema = "public" if dialect == "postgresql" else None
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=schema):
        raise RuntimeError("public_inquiries must exist before adding its retention anchor")

    columns = {column["name"] for column in inspector.get_columns(_TABLE, schema=schema)}
    if "updated_at" not in columns:
        op.add_column(
            _TABLE,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=True,
                # Keep older application instances and SQL writers able to
                # insert while the expand/contract migration rolls forward.
                server_default=sa.text("CURRENT_TIMESTAMP") if dialect == "postgresql" else None,
            ),
            schema=schema,
        )

    indexes = {index["name"] for index in inspector.get_indexes(_TABLE, schema=schema)}
    if _INDEX not in indexes:
        op.create_index(_INDEX, _TABLE, ["updated_at"], schema=schema)


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        return

    schema = "public" if dialect == "postgresql" else None
    inspector = sa.inspect(bind)
    if not inspector.has_table(_TABLE, schema=schema):
        return

    indexes = {index["name"] for index in inspector.get_indexes(_TABLE, schema=schema)}
    if _INDEX in indexes:
        op.drop_index(_INDEX, table_name=_TABLE, schema=schema)

    columns = {column["name"] for column in inspector.get_columns(_TABLE, schema=schema)}
    if "updated_at" in columns:
        if dialect == "sqlite":
            with op.batch_alter_table(_TABLE) as batch_op:
                batch_op.drop_column("updated_at")
        else:
            op.drop_column(_TABLE, "updated_at", schema=schema)
