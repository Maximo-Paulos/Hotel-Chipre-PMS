"""Add guest room-rejection lifecycle and its resolution permission.

Revision ID: 20260830_guest_room_avoidance
Revises: 20260830_room_move_tiers
Create Date: 2026-08-30
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260830_guest_room_avoidance"
down_revision: Union[str, None] = "20260830_room_move_tiers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_ENUM = sa.Enum(
    "active",
    "resolved",
    name="guest_room_avoidance_status_enum",
    create_constraint=True,
)
NEW_PERMISSION = "guest:room_avoidance_resolve"
PERMISSION_DESCRIPTION = "Resolve guest room rejections"
ROLE_DEFAULTS = frozenset({"owner", "co_owner", "manager"})
ROLES = ("owner", "co_owner", "manager", "receptionist", "housekeeping")


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "guest_room_avoidance" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "guest_room_avoidance" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_guest_room_avoidance" '
        'ON "guest_room_avoidance"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_guest_room_avoidance"
           ON "guest_room_avoidance"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping its table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_guest_room_avoidance" '
        'ON "guest_room_avoidance"'
    )
    op.execute('ALTER TABLE "guest_room_avoidance" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "guest_room_avoidance" DISABLE ROW LEVEL SECURITY')


def _insert_permission_rows(connection) -> None:
    permission = sa.table(
        "permissions",
        sa.column("code", sa.String),
        sa.column("description", sa.String),
    )
    exists = connection.execute(
        sa.text("SELECT 1 FROM permissions WHERE code = :code"),
        {"code": NEW_PERMISSION},
    ).scalar_one_or_none()
    if exists is None:
        op.bulk_insert(permission, [{"code": NEW_PERMISSION, "description": PERMISSION_DESCRIPTION}])


def _insert_default_rows(connection) -> None:
    defaults = sa.table(
        "role_permission_defaults",
        sa.column("role", sa.String),
        sa.column("permission_code", sa.String),
        sa.column("allowed", sa.Boolean),
    )
    existing_roles = {
        row[0]
        for row in connection.execute(
            sa.text(
                "SELECT role FROM role_permission_defaults "
                "WHERE permission_code = :permission_code"
            ),
            {"permission_code": NEW_PERMISSION},
        ).all()
    }
    rows = [
        {"role": role, "permission_code": NEW_PERMISSION, "allowed": role in ROLE_DEFAULTS}
        for role in ROLES
        if role not in existing_roles
    ]
    if rows:
        op.bulk_insert(defaults, rows)


def upgrade() -> None:
    op.create_table(
        "guest_room_avoidance",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("guest_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("status", STATUS_ENUM, nullable=False),
        sa.Column("source_move_event_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_guest_room_avoidance_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "guest_id"],
            ["guests.hotel_id", "guests.id"],
            name="fk_guest_room_avoidance_hotel_guest",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "room_id"],
            ["rooms.hotel_id", "rooms.id"],
            name="fk_guest_room_avoidance_hotel_room",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_move_event_id"],
            ["room_move_events.id"],
            name="fk_guest_room_avoidance_source_move_event_id_room_move_events",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_guest_room_avoidance_created_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name="fk_guest_room_avoidance_resolved_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "hotel_id",
            "guest_id",
            "room_id",
            name="uq_guest_room_avoidance_hotel_guest_room",
        ),
    )
    op.create_index(
        "ix_guest_room_avoidance_hotel_guest_status",
        "guest_room_avoidance",
        ["hotel_id", "guest_id", "status"],
    )
    connection = op.get_bind()
    _install_rls(connection)
    _insert_permission_rows(connection)
    _insert_default_rows(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    op.drop_index("ix_guest_room_avoidance_hotel_guest_status", table_name="guest_room_avoidance")
    op.drop_table("guest_room_avoidance")
    if connection.dialect.name == "postgresql":
        STATUS_ENUM.drop(connection, checkfirst=True)

    connection.execute(
        sa.text("DELETE FROM role_permission_defaults WHERE permission_code = :code"),
        {"code": NEW_PERMISSION},
    )
    connection.execute(
        sa.text(
            "DELETE FROM permissions "
            "WHERE code = :code "
            "AND NOT EXISTS ("
            "SELECT 1 FROM hotel_permission_overrides WHERE permission_code = :code"
            ") "
            "AND NOT EXISTS ("
            "SELECT 1 FROM user_permission_overrides WHERE permission_code = :code"
            ")"
        ),
        {"code": NEW_PERMISSION},
    )
