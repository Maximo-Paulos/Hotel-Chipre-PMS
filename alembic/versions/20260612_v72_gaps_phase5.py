"""v72 gaps phase 5: optimistic locking on reservations

Revision ID: 20260612_v72_gaps_phase5
Revises: 20260612_v72_gaps_phase4
Create Date: 2026-06-12

Changes:
- reservations.version (Integer, default=0) — optimistic locking (security-audit §6)
"""
from alembic import op
import sqlalchemy as sa


revision = "20260612_v72_gaps_phase5"
down_revision = "20260612_v72_gaps_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    with op.batch_alter_table("reservations") as batch_op:
        batch_op.drop_column("version")
