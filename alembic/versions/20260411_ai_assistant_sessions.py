"""ai assistant sessions

Revision ID: 20260411_ai_assistant_sessions
Revises: 20260410_reservation_financial_lifecycle
Create Date: 2026-04-11 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260411_ai_assistant_sessions"
down_revision: Union[str, None] = "20260410_reservation_financial_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_assistant_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("mode", sa.String(length=40), nullable=False, server_default="owner_copilot"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("title", sa.String(length=160), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_sessions_hotel_id", "ai_assistant_sessions", ["hotel_id"], unique=False)
    op.create_index("ix_ai_assistant_sessions_user_id", "ai_assistant_sessions", ["user_id"], unique=False)

    op.create_table(
        "ai_assistant_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("redacted_text", sa.Text(), nullable=True),
        sa.Column("intent_type", sa.String(length=60), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["ai_assistant_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_messages_session_id", "ai_assistant_messages", ["session_id"], unique=False)
    op.create_index("ix_ai_assistant_messages_hotel_id", "ai_assistant_messages", ["hotel_id"], unique=False)

    op.create_table(
        "ai_assistant_action_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_user_id", sa.Integer(), nullable=True),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_confirmation"),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("preview_json", sa.Text(), nullable=True),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["session_id"], ["ai_assistant_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_action_runs_session_id", "ai_assistant_action_runs", ["session_id"], unique=False)
    op.create_index("ix_ai_assistant_action_runs_hotel_id", "ai_assistant_action_runs", ["hotel_id"], unique=False)
    op.create_index("ix_ai_assistant_action_runs_status", "ai_assistant_action_runs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_assistant_action_runs_status", table_name="ai_assistant_action_runs")
    op.drop_index("ix_ai_assistant_action_runs_hotel_id", table_name="ai_assistant_action_runs")
    op.drop_index("ix_ai_assistant_action_runs_session_id", table_name="ai_assistant_action_runs")
    op.drop_table("ai_assistant_action_runs")
    op.drop_index("ix_ai_assistant_messages_hotel_id", table_name="ai_assistant_messages")
    op.drop_index("ix_ai_assistant_messages_session_id", table_name="ai_assistant_messages")
    op.drop_table("ai_assistant_messages")
    op.drop_index("ix_ai_assistant_sessions_user_id", table_name="ai_assistant_sessions")
    op.drop_index("ix_ai_assistant_sessions_hotel_id", table_name="ai_assistant_sessions")
    op.drop_table("ai_assistant_sessions")
