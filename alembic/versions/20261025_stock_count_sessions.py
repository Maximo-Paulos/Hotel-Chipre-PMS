"""Persist general stock counts and require audited approval before adjustment.

Revision ID: 20261025_stock_count_sessions
Revises: 20261025_reservation_cancellation_review
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261025_stock_count_sessions"
down_revision: str | None = "20261025_reservation_cancellation_review"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PERMISSION = "stock:count_confirm"
_DESCRIPTION = "Confirm physical stock counts"


def _install_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"'
    )
    op.execute(
        f'''CREATE POLICY "tenant_isolation_{table_name}" ON "{table_name}"
        USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
        WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_tenant_rls(table_name: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f'DROP POLICY IF EXISTS "tenant_isolation_{table_name}" ON "{table_name}"'
    )
    op.execute(f'ALTER TABLE "{table_name}" NO FORCE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.add_column(
        "hotel_configuration",
        sa.Column(
            "allow_stock_count_self_approval",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.add_column(
        "stock_items",
        sa.Column("movement_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "stock_count_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="open", nullable=False
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("counter_user_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("confirmation_reason", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "self_approved", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("cancelled_by_user_id", sa.Integer(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('open', 'confirmed', 'cancelled')",
            name="ck_stock_count_session_status",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_stock_count_sessions_hotel_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name="fk_stock_count_sessions_created_by_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["counter_user_id"],
            ["users.id"],
            name="fk_stock_count_sessions_counter_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name="fk_stock_count_sessions_confirmed_by_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"],
            ["users.id"],
            name="fk_stock_count_sessions_cancelled_by_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_count_sessions"),
        sa.UniqueConstraint(
            "hotel_id", "id", name="uq_stock_count_sessions_hotel_id_id"
        ),
    )
    op.create_index(
        "ix_stock_count_sessions_hotel_created",
        "stock_count_sessions",
        ["hotel_id", "created_at", "id"],
    )
    op.create_table(
        "stock_count_lines",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("system_quantity_at_count", sa.Numeric(12, 2), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(12, 2), nullable=False),
        sa.Column("movement_version", sa.Integer(), nullable=False),
        sa.Column("counted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("counted_at", sa.DateTime(), nullable=False),
        sa.Column("applied_adjustment", sa.Numeric(12, 2), nullable=True),
        sa.Column("adjusted_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "system_quantity_at_count >= 0",
            name="ck_stock_count_line_system_nonnegative",
        ),
        sa.CheckConstraint(
            "counted_quantity >= 0",
            name="ck_stock_count_line_counted_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "session_id"],
            ["stock_count_sessions.hotel_id", "stock_count_sessions.id"],
            name="fk_stock_count_line_hotel_session",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "item_id"],
            ["stock_items.hotel_id", "stock_items.id"],
            name="fk_stock_count_line_hotel_item",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "location_id"],
            ["stock_locations.hotel_id", "stock_locations.id"],
            name="fk_stock_count_line_hotel_location",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["counted_by_user_id"],
            ["users.id"],
            name="fk_stock_count_lines_counted_by_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_count_lines"),
        sa.UniqueConstraint(
            "hotel_id",
            "session_id",
            "item_id",
            "location_id",
            name="uq_stock_count_line_location",
        ),
    )
    op.create_index(
        "uq_stock_count_line_unlocated",
        "stock_count_lines",
        ["hotel_id", "session_id", "item_id"],
        unique=True,
        sqlite_where=sa.text("location_id IS NULL"),
        postgresql_where=sa.text("location_id IS NULL"),
    )
    op.create_index(
        "ix_stock_count_lines_hotel_session",
        "stock_count_lines",
        ["hotel_id", "session_id", "id"],
    )
    _install_tenant_rls("stock_count_sessions")
    _install_tenant_rls("stock_count_lines")

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO permissions (code, description, critical, step_up_required, delegable) "
            "VALUES (:code, :description, false, false, true) ON CONFLICT (code) DO NOTHING"
        ),
        {"code": _PERMISSION, "description": _DESCRIPTION},
    )
    connection.execute(
        sa.text(
            "INSERT INTO role_permission_defaults (role, permission_code, allowed) VALUES "
            "('owner', :code, true), ('co_owner', :code, true), ('manager', :code, true), "
            "('receptionist', :code, false), ('housekeeping', :code, false) "
            "ON CONFLICT (role, permission_code) DO NOTHING"
        ),
        {"code": _PERMISSION},
    )


def downgrade() -> None:
    _remove_tenant_rls("stock_count_lines")
    _remove_tenant_rls("stock_count_sessions")
    op.drop_index("ix_stock_count_lines_hotel_session", table_name="stock_count_lines")
    op.drop_index("uq_stock_count_line_unlocated", table_name="stock_count_lines")
    op.drop_table("stock_count_lines")
    op.drop_index(
        "ix_stock_count_sessions_hotel_created", table_name="stock_count_sessions"
    )
    op.drop_table("stock_count_sessions")
    op.drop_column("stock_items", "movement_version")
    op.drop_column("hotel_configuration", "allow_stock_count_self_approval")
    # Keep permission metadata/default rows so a later re-upgrade preserves
    # any explicit hotel-specific permissions already configured.
