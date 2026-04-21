from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MasterAdminSession(Base):
    __tablename__ = "master_admin_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    session_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    csrf_token_hash = Column(String(128), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)
    ip_address = Column(String(64), nullable=True)
    user_agent = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    user = relationship("User")


class MasterAdminAuditEvent(Base):
    __tablename__ = "master_admin_audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    target_type = Column(String(80), nullable=True)
    target_id = Column(String(80), nullable=True)
    outcome = Column(String(30), nullable=False, default="success")
    request_path = Column(String(255), nullable=True)
    request_method = Column(String(16), nullable=True)
    request_id = Column(String(80), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    actor = relationship("User")

    __table_args__ = (
        Index("ix_master_admin_audit_events_actor_user_id", "actor_user_id"),
        Index("ix_master_admin_audit_events_action", "action"),
    )


class MasterAdminAuthLockout(Base):
    __tablename__ = "master_admin_auth_lockouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    login_identifier = Column(String(200), nullable=False, unique=True)
    failed_attempts = Column(Integer, nullable=False, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    last_failed_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_reason = Column(String(120), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        Index("ix_master_admin_lockouts_login_identifier", "login_identifier"),
    )


class MasterBillingPolicy(Base):
    __tablename__ = "master_billing_policies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    policy_key = Column(String(50), nullable=False, unique=True, default="default")
    enabled = Column(Boolean, nullable=False, default=True)
    allow_active = Column(Boolean, nullable=False, default=True)
    allow_trialing = Column(Boolean, nullable=False, default=True)
    allow_demo = Column(Boolean, nullable=False, default=True)
    allow_comped = Column(Boolean, nullable=False, default=True)
    allow_past_due_grace = Column(Boolean, nullable=False, default=False)
    exempt_hotel_ids_json = Column(Text, nullable=False, default="[]")
    notes = Column(Text, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    updater = relationship("User")

    __table_args__ = (
        Index("ix_master_billing_policies_policy_key", "policy_key"),
    )


class MasterStripeWebhookEvent(Base):
    __tablename__ = "master_stripe_webhook_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(120), nullable=False, unique=True)
    event_type = Column(String(120), nullable=False)
    signature_header = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False)
    delivery_status = Column(String(40), nullable=False, default="received")
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    __table_args__ = (
        Index("ix_master_stripe_webhook_events_event_type", "event_type"),
    )

