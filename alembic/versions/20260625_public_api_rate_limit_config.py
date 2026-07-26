"""Add configurable public API rate limit per hotel.

Revision ID: 20260625_public_api_rate_limit_config
Revises: 20260625_reservation_channel_company
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa


revision = "20260625_public_api_rate_limit_config"
down_revision = "20260625_reservation_channel_company"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guarded because some production environments already have this column
    # out-of-band via an old startup self-heal pass while alembic_version
    # stayed on an older revision -- see
    # 20260612_audit_log_and_transaction_fk for the same pattern.
    inspector = sa.inspect(op.get_bind())
    if "public_api_rate_limit_per_minute" not in {c["name"] for c in inspector.get_columns("hotel_configuration")}:
        op.add_column(
            "hotel_configuration",
            sa.Column("public_api_rate_limit_per_minute", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("hotel_configuration", "public_api_rate_limit_per_minute")
