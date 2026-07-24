"""Add private bank-transfer proof workflow.

Revision ID: 20260724_payment_proofs
Revises: 20260724_tenant_rls_context
Create Date: 2026-07-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260724_payment_proofs"
down_revision: Union[str, None] = "20260724_tenant_rls_context"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "payment_proofs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_method", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("submitted_by_user_id", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payment_proofs_amount_positive"),
        sa.CheckConstraint("file_size_bytes > 0", name="ck_payment_proofs_file_size_positive"),
        sa.CheckConstraint("payment_method = 'bank_transfer'", name="ck_payment_proofs_bank_transfer_only"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["submitted_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["hotel_id", "reservation_id"],
            ["reservations.hotel_id", "reservations.id"],
            name="fk_payment_proofs_hotel_reservation",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("transaction_id"),
        sa.UniqueConstraint("storage_key"),
        sa.UniqueConstraint("hotel_id", "sha256_hex", name="uq_payment_proofs_hotel_sha256"),
    )
    op.create_index("ix_payment_proofs_hotel_id", "payment_proofs", ["hotel_id"], unique=False)
    op.create_index("ix_payment_proofs_reservation_id", "payment_proofs", ["reservation_id"], unique=False)
    op.create_index("ix_payment_proofs_status", "payment_proofs", ["status"], unique=False)
    op.create_index(
        "ix_payment_proofs_hotel_reservation_status",
        "payment_proofs",
        ["hotel_id", "reservation_id", "status"],
        unique=False,
    )

    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "payment_proofs" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "payment_proofs" FORCE ROW LEVEL SECURITY')
        op.execute('''CREATE POLICY "tenant_isolation_payment_proofs" ON "payment_proofs"
            USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
            WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)''')


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute('DROP POLICY IF EXISTS "tenant_isolation_payment_proofs" ON "payment_proofs"')
        op.execute('ALTER TABLE "payment_proofs" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "payment_proofs" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_payment_proofs_hotel_reservation_status", table_name="payment_proofs")
    op.drop_index("ix_payment_proofs_status", table_name="payment_proofs")
    op.drop_index("ix_payment_proofs_reservation_id", table_name="payment_proofs")
    op.drop_index("ix_payment_proofs_hotel_id", table_name="payment_proofs")
    op.drop_table("payment_proofs")
