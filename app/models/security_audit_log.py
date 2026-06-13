"""Security / access audit log — free-form operational security events.

Distinct from `audit_logs` (AuditLog), which is the enum-typed row-mutation
ledger. This table records security events with a free-form `action` string
(e.g. permission.override.updated, permission.denied) and a denormalized
actor `user_id` WITHOUT a FK — audit rows must survive user deletion and must
never block on actor-lookup integrity.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, ForeignKeyConstraint, Index, Integer, String, Text,
)

from app.database import Base


class SecurityAuditLog(Base):
    __tablename__ = "security_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=True)  # denormalized actor id, intentionally no FK
    action = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id"],
            ["hotel_configuration.id"],
            name="fk_security_audit_logs_hotel_id_hotel_configuration",
            ondelete="CASCADE",
        ),
        Index("ix_security_audit_logs_hotel_created", "hotel_id", "created_at"),
        Index("ix_security_audit_logs_hotel_action", "hotel_id", "action"),
    )
