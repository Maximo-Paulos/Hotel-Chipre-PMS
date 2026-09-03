"""Durable tenant-scoped metadata for private object-storage blobs."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.database import Base


class StoredObjectStatusEnum(str, enum.Enum):
    PENDING_UPLOAD = "pending_upload"
    READY = "ready"
    FAILED = "failed"
    DELETED = "deleted"


class StoredObject(Base):
    """Metadata and lifecycle state; bytes remain outside PostgreSQL."""

    __tablename__ = "stored_objects"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    purpose = Column(String(64), nullable=False)
    object_key = Column(String(512), nullable=False, unique=True)
    backend = Column(String(20), nullable=False)
    content_type = Column(String(160), nullable=False)
    byte_size = Column(Integer, nullable=False, default=0)
    sha256_hex = Column(String(64), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(20), nullable=False, default=StoredObjectStatusEnum.PENDING_UPLOAD.value)
    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="ck_stored_objects_byte_size_nonnegative"),
        CheckConstraint("length(sha256_hex) = 64", name="ck_stored_objects_sha256_length"),
        CheckConstraint("status IN ('pending_upload', 'ready', 'failed', 'deleted')", name="ck_stored_objects_status"),
        UniqueConstraint("hotel_id", "id", name="uq_stored_objects_hotel_id_id"),
        Index("ix_stored_objects_hotel_status", "hotel_id", "status"),
        Index("ix_stored_objects_hotel_purpose", "hotel_id", "purpose"),
    )
