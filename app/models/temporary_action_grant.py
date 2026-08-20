"""Tenant-scoped, single-use temporary authorization grants."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
)

from app.database import Base


class TemporaryActionGrantStatusEnum(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    USED = "used"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TemporaryActionGrant(Base):
    """One short-lived authorization for one requester and one permission."""

    __tablename__ = "temporary_action_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        nullable=False,
    )
    requester_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    approver_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    permission_code = Column(String(100), nullable=False)
    resource_type = Column(String(100), nullable=True)
    resource_id = Column(String(100), nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(
        Enum(
            TemporaryActionGrantStatusEnum,
            name="temporary_action_grant_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=TemporaryActionGrantStatusEnum.PENDING,
        server_default=TemporaryActionGrantStatusEnum.PENDING.value,
    )
    token_hash = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    approved_at = Column(DateTime, nullable=True)
    used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    __table_args__ = (
        # A requester must belong to the same hotel as the grant. This is the
        # same composite tenant-membership guard used by user overrides.
        ForeignKeyConstraint(
            ["hotel_id", "requester_user_id"],
            ["hotel_memberships.hotel_id", "hotel_memberships.user_id"],
            name="fk_temporary_action_grants_hotel_requester_membership",
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["permission_code"],
            ["permissions.code"],
            name="fk_temporary_action_grants_permission_code_permissions",
            ondelete="CASCADE",
        ),
        Index(
            "ix_temporary_action_grants_hotel_status_created",
            "hotel_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_temporary_action_grants_hotel_requester_status",
            "hotel_id",
            "requester_user_id",
            "status",
        ),
        Index(
            "ix_temporary_action_grants_hotel_status_expires",
            "hotel_id",
            "status",
            "expires_at",
        ),
    )
