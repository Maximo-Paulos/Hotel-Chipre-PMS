"""ai assistant insights

Revision ID: 20260412_ai_assistant_insights
Revises: 20260411_ai_assistant_sessions
Create Date: 2026-04-12 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260412_ai_assistant_insights"
down_revision: Union[str, None] = "20260411_ai_assistant_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_assistant_insights",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("hotel_id", sa.Integer(), nullable=False),
        sa.Column("insight_type", sa.String(length=60), nullable=False),
        sa.Column("summary", sa.String(length=240), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["hotel_id"], ["hotel_configuration.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["ai_assistant_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_assistant_insights_session_id", "ai_assistant_insights", ["session_id"], unique=False)
    op.create_index("ix_ai_assistant_insights_hotel_id", "ai_assistant_insights", ["hotel_id"], unique=False)
    op.create_index("ix_ai_assistant_insights_created_at", "ai_assistant_insights", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_ai_assistant_insights_created_at", table_name="ai_assistant_insights")
    op.drop_index("ix_ai_assistant_insights_hotel_id", table_name="ai_assistant_insights")
    op.drop_index("ix_ai_assistant_insights_session_id", table_name="ai_assistant_insights")
    op.drop_table("ai_assistant_insights")
