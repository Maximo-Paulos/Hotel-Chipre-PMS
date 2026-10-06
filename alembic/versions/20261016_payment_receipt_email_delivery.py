"""Persist idempotent payment receipt email outcomes.

Revision ID: 20261016_payment_receipt_email
Revises: 20261005_laundry_missing
Create Date: 2026-10-16
"""

from alembic import op
import sqlalchemy as sa


revision = "20261016_payment_receipt_email"
down_revision = "20261005_laundry_missing"
branch_labels = None
depends_on = None


TABLE = "payment_receipt_email_deliveries"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("recipient_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("actor_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="sending", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.current_timestamp(),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status in ('sending', 'sent', 'unknown')",
            name="ck_payment_receipt_email_status",
        ),
        sa.CheckConstraint(
            "length(idempotency_key_hash) = 64",
            name="ck_payment_receipt_email_key_hash",
        ),
        sa.CheckConstraint(
            "length(recipient_fingerprint) = 64",
            name="ck_payment_receipt_email_recipient_fingerprint",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["hotel_id", "transaction_id"],
            ["transactions.hotel_id", "transactions.id"],
            name="fk_payment_receipt_email_hotel_transaction",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "hotel_id",
            "idempotency_key_hash",
            name="uq_payment_receipt_email_hotel_idempotency",
        ),
    )
    op.create_index(
        "uq_payment_receipt_email_active_transaction",
        TABLE,
        ["hotel_id", "transaction_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('sending', 'unknown')"),
        postgresql_where=sa.text("status IN ('sending', 'unknown')"),
    )
    op.create_index(
        "ix_payment_receipt_email_hotel_transaction_created",
        TABLE,
        ["hotel_id", "transaction_id", "created_at"],
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        quoted = f'"{TABLE}"'
        policy = f'"tenant_isolation_{TABLE}"'
        op.execute(f"ALTER TABLE {quoted} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {quoted} FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS {policy} ON {quoted}")
        op.execute(
            f"CREATE POLICY {policy} ON {quoted} "
            "USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer) "
            "WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)"
        )


def downgrade() -> None:
    bind = op.get_bind()
    has_deliveries = bind.execute(sa.text(f"SELECT 1 FROM {TABLE} LIMIT 1")).first()
    if has_deliveries:
        raise RuntimeError(
            "Cannot downgrade payment receipt email delivery while delivery outcomes exist; "
            "preserve those idempotency and audit records first."
        )
    if bind.dialect.name == "postgresql":
        op.execute(f'DROP POLICY IF EXISTS "tenant_isolation_{TABLE}" ON "{TABLE}"')
        op.execute(f'ALTER TABLE "{TABLE}" NO FORCE ROW LEVEL SECURITY')
        op.execute(f'ALTER TABLE "{TABLE}" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_payment_receipt_email_hotel_transaction_created", table_name=TABLE)
    op.drop_index("uq_payment_receipt_email_active_transaction", table_name=TABLE)
    op.drop_table(TABLE)
