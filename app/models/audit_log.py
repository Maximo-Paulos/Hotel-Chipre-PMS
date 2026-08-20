"""
Tenant-scoped audit log for tracking mutations across core tables.
Every write to audit_logs is append-only — no updates, no deletes via app.
Retention policy: rows older than hotel.audit_retention_days are pruned by a
background job; the (hotel_id, created_at) index makes that scan cheap.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AuditActionEnum(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    STATUS_CHANGE = "status_change"


class AuditLog(Base):
    """
    Append-only record of every significant mutation within a hotel tenant.
    Do NOT expose update/delete routes for this table.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="RESTRICT"),
        nullable=False,
    )
    table_name = Column(String(100), nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(
        Enum(
            AuditActionEnum,
            name="audit_action_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload_before = Column(Text, nullable=True)
    payload_after = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    hotel = relationship("HotelConfiguration", lazy="select")
    actor = relationship("User", lazy="select")

    __table_args__ = (
        Index("ix_audit_logs_hotel_created", "hotel_id", "created_at"),
        Index("ix_audit_logs_hotel_table_record", "hotel_id", "table_name", "record_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id={self.id}, hotel={self.hotel_id}, "
            f"action={self.action}, table={self.table_name}, record={self.record_id})>"
        )
