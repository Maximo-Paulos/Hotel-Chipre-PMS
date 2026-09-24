"""Persist short-lived MFA step-up ticket use to prevent cross-worker replay."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260924_action_stepup_single_use"
down_revision: Union[str, None] = "20260924_invitation_token_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_POLICY = "tenant_isolation_action_step_up_ticket_uses"


def upgrade() -> None:
    op.create_table(
        "action_step_up_ticket_uses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticket_id", sa.String(length=32), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission_code", sa.String(length=100), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_id", name="uq_action_step_up_ticket_use_id"),
    )
    op.create_index(
        "ix_action_step_up_ticket_uses_hotel_expiry",
        "action_step_up_ticket_uses",
        ["hotel_id", "expires_at"],
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute('ALTER TABLE "action_step_up_ticket_uses" ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "action_step_up_ticket_uses" FORCE ROW LEVEL SECURITY')
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON "action_step_up_ticket_uses"')
        op.execute(
            f'''CREATE POLICY "{_POLICY}" ON "action_step_up_ticket_uses"
                USING (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)
                WITH CHECK (hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer)'''
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f'DROP POLICY IF EXISTS "{_POLICY}" ON "action_step_up_ticket_uses"')
        op.execute('ALTER TABLE "action_step_up_ticket_uses" NO FORCE ROW LEVEL SECURITY')
        op.execute('ALTER TABLE "action_step_up_ticket_uses" DISABLE ROW LEVEL SECURITY')
    op.drop_index("ix_action_step_up_ticket_uses_hotel_expiry", table_name="action_step_up_ticket_uses")
    op.drop_table("action_step_up_ticket_uses")
