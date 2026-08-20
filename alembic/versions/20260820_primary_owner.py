"""Add an explicit per-hotel Primary Owner membership.

Revision ID: 20260820_primary_owner
Revises: 20260820_permission_metadata
Create Date: 2026-08-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260820_primary_owner"
down_revision: Union[str, None] = "0f85dca5b98b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PRIMARY_INDEX = "uq_membership_primary_owner_active"


def _backfill_primary_owners(connection) -> None:
    hotel_ids = connection.execute(
        sa.text(
            """
            SELECT DISTINCT hotel_id
            FROM hotel_memberships
            WHERE role = 'owner' AND status = 'active'
            ORDER BY hotel_id
            """
        )
    ).scalars()

    for hotel_id in hotel_ids:
        already_primary = connection.execute(
            sa.text(
                """
                SELECT 1
                FROM hotel_memberships
                WHERE hotel_id = :hotel_id
                  AND role = 'owner'
                  AND status = 'active'
                  AND is_primary_owner IS TRUE
                LIMIT 1
                """
            ),
            {"hotel_id": hotel_id},
        ).scalar()
        if already_primary is not None:
            continue

        # Prefer the legacy configured owner email when it matches an owner
        # membership; otherwise choose the oldest active owner deterministically.
        winner_id = connection.execute(
            sa.text(
                """
                SELECT hm.id
                FROM hotel_memberships AS hm
                JOIN hotel_configuration AS hc ON hc.id = hm.hotel_id
                JOIN users AS u ON u.id = hm.user_id
                WHERE hm.hotel_id = :hotel_id
                  AND hm.role = 'owner'
                  AND hm.status = 'active'
                ORDER BY
                    CASE WHEN lower(u.email) = lower(hc.owner_email) THEN 0 ELSE 1 END,
                    hm.id
                LIMIT 1
                """
            ),
            {"hotel_id": hotel_id},
        ).scalar()
        if winner_id is not None:
            connection.execute(
                sa.text(
                    "UPDATE hotel_memberships SET is_primary_owner = TRUE WHERE id = :membership_id"
                ),
                {"membership_id": winner_id},
            )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("hotel_memberships")}
    if "is_primary_owner" not in columns:
        op.add_column(
            "hotel_memberships",
            sa.Column("is_primary_owner", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    _backfill_primary_owners(bind)

    index_names = {index["name"] for index in sa.inspect(bind).get_indexes("hotel_memberships")}
    if _PRIMARY_INDEX not in index_names:
        op.create_index(
            _PRIMARY_INDEX,
            "hotel_memberships",
            ["hotel_id"],
            unique=True,
            sqlite_where=sa.text("is_primary_owner = 1 AND status = 'active'"),
            postgresql_where=sa.text("is_primary_owner IS TRUE AND status = 'active'"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hotel_memberships" not in inspector.get_table_names():
        return

    index_names = {index["name"] for index in inspector.get_indexes("hotel_memberships")}
    if _PRIMARY_INDEX in index_names:
        op.drop_index(_PRIMARY_INDEX, table_name="hotel_memberships")
    columns = {column["name"] for column in sa.inspect(bind).get_columns("hotel_memberships")}
    if "is_primary_owner" in columns:
        op.drop_column("hotel_memberships", "is_primary_owner")
