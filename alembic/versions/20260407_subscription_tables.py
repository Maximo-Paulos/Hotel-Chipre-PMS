"""add subscription v2 tables

Revision ID: 20260407_subscription_tables
Revises: 20260404_add_hotel_scope
Create Date: 2026-04-07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260407_subscription_tables"
down_revision: Union[str, None] = "20260404_add_hotel_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=20), nullable=False, server_default="starter"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("room_limit", sa.Integer(), nullable=True),
        sa.Column("staff_limit", sa.Integer(), nullable=True),
        sa.Column("can_write_cache", sa.Boolean(), nullable=False, server_default=sa.sql.expression.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("hotel_id", name="uq_subscriptions_hotel_id"),
        sa.CheckConstraint("plan in ('starter','pro','ultra')", name="ck_subscriptions_plan"),
        sa.CheckConstraint("status in ('active','past_due','suspended','trialing','demo')", name="ck_subscriptions_status"),
    )
    op.create_index("ix_subscriptions_hotel_id", "subscriptions", ["hotel_id"])

    op.create_table(
        "subscription_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["subscription_id"], ["subscriptions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_subscription_events_subscription_id", "subscription_events", ["subscription_id"])
    op.create_index("ix_subscription_events_hotel_id", "subscription_events", ["hotel_id"])


def downgrade() -> None:
    op.drop_index("ix_subscription_events_hotel_id", table_name="subscription_events")
    op.drop_index("ix_subscription_events_subscription_id", table_name="subscription_events")
    op.drop_table("subscription_events")

    op.drop_index("ix_subscriptions_hotel_id", table_name="subscriptions")
    op.drop_table("subscriptions")
