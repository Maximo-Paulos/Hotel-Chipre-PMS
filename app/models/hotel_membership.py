"""
HotelMembership model: many-to-many between users and hotels with roles.
Roles: owner, co_owner, manager, housekeeping.
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.database import Base


class HotelMembership(Base):
    __tablename__ = "hotel_memberships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False, default="owner")  # owner, co_owner, manager, housekeeping
    status = Column(String(20), nullable=False, default="active")  # active, invited, revoked
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint("hotel_id", "user_id", name="uq_membership_user_hotel"),
        Index("ix_membership_hotel", "hotel_id"),
        Index("ix_membership_user", "user_id"),
    )
