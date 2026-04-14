"""add payment link tests

Revision ID: b7c1f0a8f9d2
Revises: 9b0becb6c658
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c1f0a8f9d2"
down_revision: Union[str, None] = "9b0becb6c658"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_link_tests" not in inspector.get_table_names():
        op.create_table(
            "payment_link_tests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("hotel_id", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(length=50), nullable=False, server_default="mercadopago"),
            sa.Column("recipient_email", sa.String(length=255), nullable=False),
            sa.Column("amount", sa.Float(), nullable=False),
            sa.Column("currency", sa.String(length=3), nullable=False, server_default="ARS"),
            sa.Column("description", sa.String(length=255), nullable=False, server_default="Senia de prueba"),
            sa.Column("external_reference", sa.String(length=120), nullable=False),
            sa.Column("preference_id", sa.String(length=120), nullable=True),
            sa.Column("payment_link", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
            sa.Column("external_status", sa.String(length=120), nullable=True),
            sa.Column("external_payment_id", sa.String(length=120), nullable=True),
            sa.Column("gateway_response", sa.JSON(), nullable=True),
            sa.Column("email_sent_at", sa.DateTime(), nullable=True),
            sa.Column("last_checked_at", sa.DateTime(), nullable=True),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("external_reference", name="uq_payment_link_tests_external_reference"),
        )
        op.create_index("ix_payment_link_tests_hotel_id", "payment_link_tests", ["hotel_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "payment_link_tests" in inspector.get_table_names():
        op.drop_index("ix_payment_link_tests_hotel_id", table_name="payment_link_tests")
        op.drop_table("payment_link_tests")
