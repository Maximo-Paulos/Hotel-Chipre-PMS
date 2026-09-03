"""Durable worker coordination records for portable job dispatch."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint

from app.database import Base


class JobDispatchRecord(Base):
    __tablename__ = "job_dispatch_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    task_name = Column(String(160), nullable=False)
    deduplication_key = Column(String(255), nullable=False)
    correlation_id = Column(String(128), nullable=False)
    status = Column(String(20), nullable=False, default="queued")
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("hotel_id", "task_name", "deduplication_key", name="uq_job_dispatch_hotel_task_dedupe"),
        CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name="ck_job_dispatch_status"),
        Index("ix_job_dispatch_hotel_status", "hotel_id", "status"),
    )


class ServiceHeartbeat(Base):
    __tablename__ = "service_heartbeats"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    environment = Column(String(32), nullable=False)
    service_name = Column(String(80), nullable=False)
    instance_id = Column(String(160), nullable=False)
    queue_name = Column(String(80), nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    metadata_json = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("environment", "service_name", "instance_id", name="uq_service_heartbeat_identity"),
        Index("ix_service_heartbeats_last_seen", "environment", "last_seen_at"),
    )
