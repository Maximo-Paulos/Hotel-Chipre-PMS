"""
GuestRestriction — formal, hotel-scoped guest lodging-prohibition entity.

Replaces/wraps the legacy GuestTag(tag_type=PROHIBIDO_ALOJAR) with an
auditable lifecycle (active/resolved), explicit override tracking, and
tenant isolation matching the composite (hotel_id, guest_id) FK pattern used
elsewhere for tenant-scoped guest data (see GuestTag in app/models/guest.py).
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index, Integer, Text,
)

from app.database import Base


class GuestRestrictionStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"


class GuestRestriction(Base):
    """Formal lodging-prohibition record for a guest, scoped to a hotel."""

    __tablename__ = "guest_restrictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    guest_id = Column(Integer, nullable=False)

    status = Column(
        Enum(
            GuestRestrictionStatusEnum,
            name="guest_restriction_status_enum",
            create_constraint=True,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
        default=GuestRestrictionStatusEnum.ACTIVE,
    )
    reason = Column(Text, nullable=False)
    detail = Column(Text, nullable=True)
    valid_until = Column(DateTime, nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    resolved_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_note = Column(Text, nullable=True)

    legacy_guest_tag_id = Column(Integer, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["hotel_id", "guest_id"],
            ["guests.hotel_id", "guests.id"],
            name="fk_guest_restrictions_hotel_guest",
            ondelete="CASCADE",
        ),
        # Composite, not scalar: a restriction must never link to a legacy tag
        # belonging to a different hotel (NULL legacy_guest_tag_id skips the
        # check per standard multi-column FK MATCH SIMPLE semantics).
        ForeignKeyConstraint(
            ["hotel_id", "legacy_guest_tag_id"],
            ["guest_tags.hotel_id", "guest_tags.id"],
            name="fk_guest_restrictions_hotel_legacy_tag",
            ondelete="SET NULL",
        ),
        Index("ix_guest_restrictions_hotel_guest", "hotel_id", "guest_id"),
    )

    def __repr__(self) -> str:
        return f"<GuestRestriction(id={self.id}, guest_id={self.guest_id}, status={self.status})>"
