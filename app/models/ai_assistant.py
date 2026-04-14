"""
AI assistant session and message models.

Phase 1 keeps Gemma in read-only/proposal mode. We persist conversation
sessions so each hotel owner can work from a scoped history without mixing
tenants or users.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class AIAssistantSession(Base):
    __tablename__ = "ai_assistant_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    mode = Column(String(40), nullable=False, default="owner_copilot")
    status = Column(String(30), nullable=False, default="active")
    title = Column(String(160), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    user = relationship("User", lazy="joined")
    messages = relationship(
        "AIAssistantMessage",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAssistantMessage.created_at.asc()",
    )
    action_runs = relationship(
        "AIAssistantActionRun",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAssistantActionRun.created_at.asc()",
    )
    insights = relationship(
        "AIAssistantInsight",
        back_populates="session",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="AIAssistantInsight.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_ai_assistant_sessions_hotel_id", "hotel_id"),
        Index("ix_ai_assistant_sessions_user_id", "user_id"),
    )


class AIAssistantMessage(Base):
    __tablename__ = "ai_assistant_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("ai_assistant_sessions.id", ondelete="CASCADE"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    raw_text = Column(Text, nullable=False)
    redacted_text = Column(Text, nullable=True)
    intent_type = Column(String(60), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = relationship("AIAssistantSession", back_populates="messages", lazy="joined")

    __table_args__ = (
        Index("ix_ai_assistant_messages_session_id", "session_id"),
        Index("ix_ai_assistant_messages_hotel_id", "hotel_id"),
    )


class AIAssistantActionRun(Base):
    __tablename__ = "ai_assistant_action_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("ai_assistant_sessions.id", ondelete="CASCADE"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action_type = Column(String(80), nullable=False)
    status = Column(String(30), nullable=False, default="pending_confirmation")
    payload_json = Column(Text, nullable=True)
    preview_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    executed_at = Column(DateTime, nullable=True)

    session = relationship("AIAssistantSession", back_populates="action_runs", lazy="joined")
    requested_by = relationship("User", lazy="joined")

    __table_args__ = (
        Index("ix_ai_assistant_action_runs_session_id", "session_id"),
        Index("ix_ai_assistant_action_runs_hotel_id", "hotel_id"),
        Index("ix_ai_assistant_action_runs_status", "status"),
    )


class AIAssistantInsight(Base):
    __tablename__ = "ai_assistant_insights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("ai_assistant_sessions.id", ondelete="CASCADE"), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    insight_type = Column(String(60), nullable=False)
    summary = Column(String(240), nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    session = relationship("AIAssistantSession", back_populates="insights", lazy="joined")

    __table_args__ = (
        Index("ix_ai_assistant_insights_session_id", "session_id"),
        Index("ix_ai_assistant_insights_hotel_id", "hotel_id"),
        Index("ix_ai_assistant_insights_created_at", "created_at"),
    )
