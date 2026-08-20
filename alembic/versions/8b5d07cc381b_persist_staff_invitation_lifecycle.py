"""persist staff invitation lifecycle

Revision ID: 8b5d07cc381b
Revises: 20260820_permission_metadata
Create Date: 2026-08-20 17:04:21.166693
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '8b5d07cc381b'
down_revision: Union[str, None] = '20260820_guest_search_first_name_index'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "staff_invitations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("inviter_user_id", sa.Integer(), nullable=True),
        sa.Column("inviter_email", sa.String(length=200), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_staff_invitations_hotel_email",
        "staff_invitations",
        ["hotel_id", "email"],
        unique=False,
    )
    op.create_index(
        "uq_staff_invitations_pending_email",
        "staff_invitations",
        ["hotel_id", "email"],
        unique=True,
        sqlite_where=sa.text("status = 'pending'"),
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "ix_staff_invitations_token_status",
        "staff_invitations",
        ["token_hash", "status"],
        unique=False,
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE "staff_invitations" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "staff_invitations" FORCE ROW LEVEL SECURITY')
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_staff_invitations" ON "staff_invitations"')
        op.execute(
            '''CREATE POLICY "tenant_isolation_staff_invitations" ON "staff_invitations"
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_staff_invitations" ON "staff_invitations"')
        op.execute('ALTER TABLE "staff_invitations" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "staff_invitations" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_staff_invitations_token_status", table_name="staff_invitations")
    op.drop_index("uq_staff_invitations_pending_email", table_name="staff_invitations")
    op.drop_index("ix_staff_invitations_hotel_email", table_name="staff_invitations")
    op.drop_table("staff_invitations")
