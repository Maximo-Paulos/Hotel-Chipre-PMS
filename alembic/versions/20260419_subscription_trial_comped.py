"""add trial and comped fields to subscriptions

Revision ID: 20260419_subscription_trial_comped
Revises: 20260408_security_tokens, a7f3d2c1b9e8
Create Date: 2026-04-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260419_subscription_trial_comped"
down_revision: Union[str, Sequence[str], None] = ("20260408_security_tokens", "a7f3d2c1b9e8")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATUS_CHECK = "status in ('active','past_due','suspended','trialing','demo','comped')"
DOWNGRADE_STATUS_CHECK = "status in ('active','past_due','suspended','trialing','demo')"


def upgrade() -> None:
    with op.batch_alter_table("subscriptions", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("trial_end_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.drop_constraint("ck_subscriptions_status", type_="check")
        batch_op.create_check_constraint("ck_subscriptions_status", STATUS_CHECK)


def downgrade() -> None:
    with op.batch_alter_table("subscriptions", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_subscriptions_status", type_="check")
        batch_op.create_check_constraint("ck_subscriptions_status", DOWNGRADE_STATUS_CHECK)
        batch_op.drop_column("trial_end_at")
        batch_op.drop_column("trial_started_at")
