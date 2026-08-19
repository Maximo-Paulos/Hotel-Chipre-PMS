"""add guest_restrictions table with tenant-scoped composite FK and legacy backfill

Revision ID: 20260813_guest_restrictions
Revises: 20260813_rbac_overrides
Create Date: 2026-08-13
"""
from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260813_guest_restrictions"
down_revision: Union[str, None] = "20260813_rbac_overrides"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_ENUM = sa.Enum("active", "resolved", name="guest_restriction_status_enum")


def _backfill_from_legacy_tags(connection) -> None:
    """Create an active GuestRestriction for every currently-active (non-expired)
    legacy GuestTag(tag_type='prohibido_alojar'). guest_tags is never touched."""
    rows = connection.execute(
        sa.text(
            "SELECT id, hotel_id, guest_id, note, expires_at, created_by_user_id, created_at "
            "FROM guest_tags WHERE tag_type = :tag_type"
        ),
        {"tag_type": "prohibido_alojar"},
    ).mappings().all()

    now = datetime.now(timezone.utc)
    for row in rows:
        expires_at = row["expires_at"]
        if expires_at is not None:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at <= now:
                continue  # expired legacy tag — does not qualify for backfill

        connection.execute(
            sa.text(
                "INSERT INTO guest_restrictions "
                "(hotel_id, guest_id, status, reason, detail, legacy_guest_tag_id, "
                "created_by_user_id, created_at, updated_at) "
                "VALUES (:hotel_id, :guest_id, 'active', 'legacy_prohibido_alojar', :detail, "
                ":legacy_tag_id, :created_by, :created_at, :updated_at)"
            ),
            {
                "hotel_id": row["hotel_id"],
                "guest_id": row["guest_id"],
                "detail": row["note"],
                "legacy_tag_id": row["id"],
                "created_by": row["created_by_user_id"],
                "created_at": row["created_at"] or now,
                "updated_at": now,
            },
        )


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "guest_restrictions" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "guest_restrictions" FORCE ROW LEVEL SECURITY')
    op.execute(
        '''CREATE POLICY "tenant_isolation_guest_restrictions"
           ON "guest_restrictions"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping its table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_guest_restrictions" ON "guest_restrictions"'
    )
    op.execute('ALTER TABLE "guest_restrictions" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "guest_restrictions" DISABLE ROW LEVEL SECURITY')


def _ensure_guest_hotel_id_unique(connection) -> None:
    """The composite tenant FK below needs a unique index on
    guests(hotel_id, id) to bind. PostgreSQL already gets this from
    20260724_core_tenant_composite_fks (which is Postgres-only); SQLite's
    migration-built schema does not, so add it here if missing. Harmless and
    idempotent on both dialects — (hotel_id, id) is trivially unique since
    id already is. Left in place on downgrade rather than dropped.
    """
    inspector = sa.inspect(connection)
    existing = inspector.get_unique_constraints("guests") + [
        item for item in inspector.get_indexes("guests") if item.get("unique")
    ]
    if any(item.get("column_names") == ["hotel_id", "id"] for item in existing):
        return
    if connection.dialect.name == "sqlite":
        # SQLite has no ALTER TABLE ADD CONSTRAINT; batch mode rebuilds the table.
        with op.batch_alter_table("guests", recreate="always") as batch_op:
            batch_op.create_unique_constraint("uq_guest_hotel_id_id", ["hotel_id", "id"])
    else:
        op.create_unique_constraint("uq_guest_hotel_id_id", "guests", ["hotel_id", "id"])


def _ensure_guest_tags_hotel_id_unique(connection) -> None:
    """Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):
    needed so legacy_guest_tag_id can be a composite (hotel_id, legacy_guest_tag_id)
    FK instead of a scalar one that could point at another hotel's tag.
    """
    inspector = sa.inspect(connection)
    existing = inspector.get_unique_constraints("guest_tags") + [
        item for item in inspector.get_indexes("guest_tags") if item.get("unique")
    ]
    if any(item.get("column_names") == ["hotel_id", "id"] for item in existing):
        return
    if connection.dialect.name == "sqlite":
        with op.batch_alter_table("guest_tags", recreate="always") as batch_op:
            batch_op.create_unique_constraint("uq_guest_tag_hotel_id_id", ["hotel_id", "id"])
    else:
        op.create_unique_constraint("uq_guest_tag_hotel_id_id", "guest_tags", ["hotel_id", "id"])


def upgrade() -> None:
    connection = op.get_bind()
    _ensure_guest_hotel_id_unique(connection)
    _ensure_guest_tags_hotel_id_unique(connection)

    op.create_table(
        "guest_restrictions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("status", STATUS_ENUM, nullable=False, server_default="active"),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("valid_until", sa.DateTime(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("legacy_guest_tag_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"],
            name="fk_guest_restrictions_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "guest_id"],
            ["guests.hotel_id", "guests.id"],
            name="fk_guest_restrictions_hotel_guest",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_guest_restrictions_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"],
            name="fk_guest_restrictions_resolved_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "legacy_guest_tag_id"],
            ["guest_tags.hotel_id", "guest_tags.id"],
            name="fk_guest_restrictions_hotel_legacy_tag",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_guest_restrictions_hotel_guest", "guest_restrictions", ["hotel_id", "guest_id"])

    _backfill_from_legacy_tags(connection)
    _install_rls(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    op.drop_index("ix_guest_restrictions_hotel_guest", table_name="guest_restrictions")
    op.drop_table("guest_restrictions")
    if connection.dialect.name == "postgresql":
        STATUS_ENUM.drop(connection, checkfirst=True)
