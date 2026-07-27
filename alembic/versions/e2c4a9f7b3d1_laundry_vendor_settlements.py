"""laundry vendor settlements (quarterly paid/not-paid mark)

Revision ID: e2c4a9f7b3d1
Revises: f3bdaadd3d15
Create Date: 2026-07-27 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "e2c4a9f7b3d1"
down_revision: Union[str, None] = "f3bdaadd3d15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "laundry_vendor_settlements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("vendor_id", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("paid", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("paid_by_user_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["hotel_id"], ["hotel_configuration.id"], name="fk_laundry_vendor_settlements_hotel_id"
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "vendor_id"],
            ["laundry_vendors.hotel_id", "laundry_vendors.id"],
            name="fk_laundry_vendor_settlements_hotel_vendor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["paid_by_user_id"],
            ["users.id"],
            name="fk_laundry_vendor_settlements_paid_by_user_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_laundry_vendor_settlements"),
        sa.UniqueConstraint(
            "hotel_id", "vendor_id", "period_start", name="uq_laundry_vendor_settlements_hotel_vendor_period"
        ),
    )
    op.create_index(
        "ix_laundry_vendor_settlements_hotel_id", "laundry_vendor_settlements", ["hotel_id"], unique=False
    )

    # This migration runs after the RLS baseline (20260724_tenant_rls_context,
    # which already lists this table name in TENANT_TABLES for the metadata
    # contract but skips it there because the table did not exist yet), so it
    # owns installing its own policy -- same pattern as 795e124adaad.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute('ALTER TABLE "laundry_vendor_settlements" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "laundry_vendor_settlements" FORCE ROW LEVEL SECURITY')
        op.execute(
            '''CREATE POLICY "tenant_isolation_laundry_vendor_settlements" ON "laundry_vendor_settlements"
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            'DROP POLICY IF EXISTS "tenant_isolation_laundry_vendor_settlements" ON "laundry_vendor_settlements"'
        )
        op.execute('ALTER TABLE "laundry_vendor_settlements" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "laundry_vendor_settlements" DISABLE ROW LEVEL SECURITY')

    op.drop_index("ix_laundry_vendor_settlements_hotel_id", table_name="laundry_vendor_settlements")
    op.drop_table("laundry_vendor_settlements")
