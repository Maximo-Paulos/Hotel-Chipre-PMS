"""add temporary action grants

Revision ID: 0f85dca5b98b
Revises: 20260820_user_sessions
Create Date: 2026-08-20 15:36:05.597302
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0f85dca5b98b'
down_revision: Union[str, None] = '20260820_user_sessions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_ENUM = sa.Enum(
    "pending",
    "approved",
    "denied",
    "used",
    "expired",
    "revoked",
    name="temporary_action_grant_status_enum",
    create_constraint=True,
)


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "temporary_action_grants" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "temporary_action_grants" FORCE ROW LEVEL SECURITY')
    op.execute(
        '''CREATE POLICY "tenant_isolation_temporary_action_grants"
           ON "temporary_action_grants"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping the table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_temporary_action_grants" '
        'ON "temporary_action_grants"'
    )
    op.execute('ALTER TABLE "temporary_action_grants" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "temporary_action_grants" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    connection = op.get_bind()
    op.create_table(
        "temporary_action_grants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("approver_user_id", sa.Integer(), nullable=True),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", STATUS_ENUM, nullable=False, server_default="pending"),
        sa.Column("token_hash", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_temporary_action_grants_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            name="fk_temporary_action_grants_requester_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["approver_user_id"],
            ["users.id"],
            name="fk_temporary_action_grants_approver_user_id_users",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "requester_user_id"],
            ["hotel_memberships.hotel_id", "hotel_memberships.user_id"],
            name="fk_temporary_action_grants_hotel_requester_membership",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.code"],
            name="fk_temporary_action_grants_permission_code_permissions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_temporary_action_grants_hotel_status_created",
        "temporary_action_grants",
        ["hotel_id", "status", "created_at"],
    )
    op.create_index(
        "ix_temporary_action_grants_hotel_requester_status",
        "temporary_action_grants",
        ["hotel_id", "requester_user_id", "status"],
    )
    op.create_index(
        "ix_temporary_action_grants_hotel_status_expires",
        "temporary_action_grants",
        ["hotel_id", "status", "expires_at"],
    )
    _install_rls(connection)


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    op.drop_index(
        "ix_temporary_action_grants_hotel_status_expires",
        table_name="temporary_action_grants",
    )
    op.drop_index(
        "ix_temporary_action_grants_hotel_requester_status",
        table_name="temporary_action_grants",
    )
    op.drop_index(
        "ix_temporary_action_grants_hotel_status_created",
        table_name="temporary_action_grants",
    )
    op.drop_table("temporary_action_grants")
    if connection.dialect.name == "postgresql":
        STATUS_ENUM.drop(connection, checkfirst=True)
