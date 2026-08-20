"""Add first-name indexes for the tenant-scoped guest search hot path.

Revision ID: 20260820_guest_search_first_name_index
Revises: 20260820_permission_metadata
Create Date: 2026-08-20
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260820_guest_search_first_name_index"
down_revision: Union[str, None] = "20260820_permission_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    existing_indexes = {index["name"] for index in inspector.get_indexes("guests")}

    if "ix_guest_hotel_first_name" not in existing_indexes:
        op.create_index(
            "ix_guest_hotel_first_name",
            "guests",
            ["hotel_id", "first_name"],
        )

    if op.get_bind().dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        if "ix_guests_first_name_trgm" not in existing_indexes:
            op.create_index(
                "ix_guests_first_name_trgm",
                "guests",
                ["first_name"],
                unique=False,
                postgresql_using="gin",
                postgresql_ops={"first_name": "gin_trgm_ops"},
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {index["name"] for index in inspector.get_indexes("guests")}

    if "ix_guests_first_name_trgm" in existing_indexes:
        op.drop_index("ix_guests_first_name_trgm", table_name="guests")
    if "ix_guest_hotel_first_name" in existing_indexes:
        op.drop_index("ix_guest_hotel_first_name", table_name="guests")
