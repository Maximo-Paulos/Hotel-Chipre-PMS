"""add role visibility windows

Revision ID: 3bc5882f756d
Revises: 20260828_permission_catalog
Create Date: 2026-08-28 15:00:43.561622
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '3bc5882f756d'
down_revision: Union[str, None] = '20260828_permission_catalog'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on SQLite."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "hotel_role_visibility_window" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "hotel_role_visibility_window" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_hotel_role_visibility_window" '
        'ON "hotel_role_visibility_window"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_hotel_role_visibility_window"
           ON "hotel_role_visibility_window"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping the table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_hotel_role_visibility_window" '
        'ON "hotel_role_visibility_window"'
    )
    op.execute('ALTER TABLE "hotel_role_visibility_window" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "hotel_role_visibility_window" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.create_table(
        "hotel_role_visibility_window",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("past_hours", sa.Integer(), nullable=True),
        sa.Column("future_hours", sa.Integer(), nullable=True),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "role IN ('owner', 'co_owner', 'manager', 'receptionist', 'housekeeping')",
            name="ck_hotel_role_visibility_window_role",
        ),
        sa.CheckConstraint(
            "past_hours IS NULL OR past_hours IN (12, 24, 48, 72, 168)",
            name="ck_hotel_role_visibility_window_past_hours",
        ),
        sa.CheckConstraint(
            "future_hours IS NULL OR future_hours IN (12, 24, 48, 72, 168)",
            name="ck_hotel_role_visibility_window_future_hours",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_hotel_role_visibility_window_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"],
            ["users.id"],
            name="fk_hotel_role_visibility_window_updated_by_user_id_users",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id",
            "role",
            name="uq_hotel_role_visibility_window_hotel_role",
        ),
    )
    _install_rls(op.get_bind())
    op.create_index(
        "ix_hotel_role_visibility_window_hotel_id",
        "hotel_role_visibility_window",
        ["hotel_id"],
        unique=False,
    )

    # These columns were dead scaffolding.  Batch mode rebuilds the table on
    # SQLite and emits ALTER TABLE on PostgreSQL, keeping both dialects
    # reversible without backfilling or changing reservation access.
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch_op:
        batch_op.drop_column("receptionist_view_past_days")
        batch_op.drop_column("receptionist_view_future_days")


def downgrade() -> None:
    _remove_rls(op.get_bind())
    op.drop_index(
        "ix_hotel_role_visibility_window_hotel_id",
        table_name="hotel_role_visibility_window",
    )
    op.drop_table("hotel_role_visibility_window")

    # Restore the removed scaffolding columns with their former defaults so a
    # downgrade leaves the pre-migration schema usable.  There is no data
    # backfill because the columns were not part of any runtime behavior.
    with op.batch_alter_table("hotel_configuration", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column(
                "receptionist_view_past_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(
            sa.Column(
                "receptionist_view_future_days",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("7"),
            )
        )
