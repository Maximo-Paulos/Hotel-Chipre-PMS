"""extend onboarding state for wizard flow

Revision ID: 20260419_onboarding_wizard_state
Revises: 20260412_ai_assistant_insights, 20260419_subscription_trial_comped
Create Date: 2026-04-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260419_onboarding_wizard_state"
down_revision: Union[str, Sequence[str], None] = (
    "20260412_ai_assistant_insights",
    "20260419_subscription_trial_comped",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("onboarding_state", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("hotel_identity_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("deposit_policy_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("payment_methods_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("ota_channels_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("subscription_choice_json", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("identity_set", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("policy_set", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("payments_set", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("ota_set", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("subscription_set", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("onboarding_state", recreate="always") as batch_op:
        batch_op.drop_column("subscription_set")
        batch_op.drop_column("ota_set")
        batch_op.drop_column("payments_set")
        batch_op.drop_column("policy_set")
        batch_op.drop_column("identity_set")
        batch_op.drop_column("subscription_choice_json")
        batch_op.drop_column("ota_channels_json")
        batch_op.drop_column("payment_methods_json")
        batch_op.drop_column("deposit_policy_json")
        batch_op.drop_column("hotel_identity_json")
