"""add durable realtime domain event outbox

Revision ID: 20260901_domain_event_outbox
Revises: 20260830_fix_receptionist_move_default
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_domain_event_outbox"
down_revision: Union[str, None] = "20260830_fix_receptionist_move_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PAYLOAD_TYPE = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _install_rls(connection) -> None:
    """Install the PostgreSQL tenant policy; no-op on other dialects."""
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "domain_event_outbox" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "domain_event_outbox" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_domain_event_outbox" '
        'ON "domain_event_outbox"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_domain_event_outbox"
           ON "domain_event_outbox"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    """Remove the PostgreSQL tenant policy before dropping its table."""
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_domain_event_outbox" '
        'ON "domain_event_outbox"'
    )
    op.execute('ALTER TABLE "domain_event_outbox" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "domain_event_outbox" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    op.create_table(
        "domain_event_outbox",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("domain", sa.String(length=50), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", PAYLOAD_TYPE, nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_domain_event_outbox_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "revision >= 0",
            name="ck_domain_event_outbox_revision_nonnegative",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_domain_event_outbox_attempts_nonnegative",
        ),
    )
    op.create_index(
        "ix_domain_event_outbox_pending",
        "domain_event_outbox",
        ["hotel_id", "published_at", "id"],
    )
    _install_rls(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    _remove_rls(connection)
    op.drop_index("ix_domain_event_outbox_pending", table_name="domain_event_outbox")
    op.drop_table("domain_event_outbox")
