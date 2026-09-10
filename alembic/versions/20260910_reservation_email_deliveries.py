"""add auditable reservation guest email deliveries

Revision ID: 20260910_reservation_email_deliveries
Revises: 20260910_operational_tasks_handoff
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260910_reservation_email_deliveries"
down_revision: Union[str, None] = "20260910_operational_tasks_handoff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True)


def _install_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    op.execute('ALTER TABLE "reservation_email_deliveries" ENABLE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "reservation_email_deliveries" FORCE ROW LEVEL SECURITY')
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_reservation_email_deliveries" '
        'ON "reservation_email_deliveries"'
    )
    op.execute(
        '''CREATE POLICY "tenant_isolation_reservation_email_deliveries"
           ON "reservation_email_deliveries"
           USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
           WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
    )


def _remove_rls(connection) -> None:
    if connection.dialect.name != "postgresql":
        return
    op.execute(
        'DROP POLICY IF EXISTS "tenant_isolation_reservation_email_deliveries" '
        'ON "reservation_email_deliveries"'
    )
    op.execute('ALTER TABLE "reservation_email_deliveries" NO FORCE ROW LEVEL SECURITY')
    op.execute('ALTER TABLE "reservation_email_deliveries" DISABLE ROW LEVEL SECURITY')


def upgrade() -> None:
    bind = op.get_bind()
    if "reservation_email_deliveries" in sa.inspect(bind).get_table_names():
        _install_rls(bind)
        return
    op.create_table(
        "reservation_email_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("kind", _enum("reservation_email_kind_enum", "confirmation", "voucher"), nullable=False),
        sa.Column("status", _enum("reservation_email_status_enum", "pending", "accepted", "failed", "unknown"), nullable=False),
        sa.Column("recipient_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_resend", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("accepted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_reservation_email_deliveries_hotel_reservation",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("hotel_id", "id", name="uq_reservation_email_deliveries_hotel_id_id"),
    )
    op.create_index(
        "ix_reservation_email_deliveries_hotel_reservation_created",
        "reservation_email_deliveries",
        ["hotel_id", "reservation_id", "created_at"],
    )
    _install_rls(bind)


def downgrade() -> None:
    bind = op.get_bind()
    _remove_rls(bind)
    if "reservation_email_deliveries" not in sa.inspect(bind).get_table_names():
        return
    op.drop_index(
        "ix_reservation_email_deliveries_hotel_reservation_created",
        table_name="reservation_email_deliveries",
    )
    op.drop_table("reservation_email_deliveries")
