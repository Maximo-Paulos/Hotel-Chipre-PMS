"""repair: create hotel_memberships table (was never migrated)

Revision ID: 20260726_repair_missing_hotel_memberships
Revises: 20260626_repair_reservation_unique_constraint
Branch Labels: None
Depends On: None

`app/models/hotel_membership.py` (HotelMembership, table `hotel_memberships`)
has existed in the codebase since 2026-04-05 and is central to auth/permission
resolution (`app/dependencies/auth.py`), but no migration in this repo's
history ever creates the table -- confirmed by grepping every revision under
alembic/versions/ for "hotel_memberships": the only hit is
20260724_tenant_rls_context.py, which assumes the table already exists and
fails with UndefinedTable when it doesn't (reproduced against a from-scratch
local PostgreSQL 16 instance).

This is why a brand-new database (e.g. a fresh Supabase project) cannot reach
head: the RLS migration errors on `ALTER TABLE hotel_memberships ENABLE ROW
LEVEL SECURITY` before the table exists.

Idempotent by design (CREATE TABLE IF NOT EXISTS / conditional index/FK
creation) because a database where this table already exists via some
out-of-band path (manual creation, an environment that predates strict
migration discipline) must not error on re-application.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260726_repair_missing_hotel_memberships"
down_revision: Union[str, None] = "20260626_repair_reservation_unique_constraint"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name
    inspector = sa.inspect(bind)

    if "hotel_memberships" in inspector.get_table_names():
        return

    if dialect == "postgresql":
        bind.execute(sa.text(
            """
            CREATE TABLE IF NOT EXISTS hotel_memberships (
                id SERIAL PRIMARY KEY,
                hotel_id INTEGER NOT NULL REFERENCES hotel_configuration(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(20) NOT NULL DEFAULT 'owner',
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_membership_user_hotel UNIQUE (hotel_id, user_id)
            )
            """
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_membership_hotel ON hotel_memberships (hotel_id)"
        ))
        bind.execute(sa.text(
            "CREATE INDEX IF NOT EXISTS ix_membership_user ON hotel_memberships (user_id)"
        ))
    else:
        op.create_table(
            "hotel_memberships",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "hotel_id",
                sa.Integer(),
                sa.ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(20), nullable=False, server_default="owner"),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint("hotel_id", "user_id", name="uq_membership_user_hotel"),
        )
        op.create_index("ix_membership_hotel", "hotel_memberships", ["hotel_id"])
        op.create_index("ix_membership_user", "hotel_memberships", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "hotel_memberships" not in inspector.get_table_names():
        return
    op.drop_index("ix_membership_user", table_name="hotel_memberships")
    op.drop_index("ix_membership_hotel", table_name="hotel_memberships")
    op.drop_table("hotel_memberships")
