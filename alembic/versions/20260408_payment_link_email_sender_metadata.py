"""add sender metadata to payment link tests

Revision ID: 20260408_payment_link_email_sender_metadata
Revises: 20260408_launch_security_hardening
Create Date: 2026-04-08 20:45:00
"""
from alembic import op
import sqlalchemy as sa


revision = "20260408_payment_link_email_sender_metadata"
down_revision = "20260408_launch_security_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("payment_link_tests") as batch_op:
        batch_op.add_column(sa.Column("sender_channel", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("sender_email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("payment_link_tests") as batch_op:
        batch_op.drop_column("sender_email")
        batch_op.drop_column("sender_channel")
