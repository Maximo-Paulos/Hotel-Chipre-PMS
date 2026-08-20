"""Persisted staff invitations and their one-time acceptance state."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StaffInvitation(Base):
    __tablename__ = "staff_invitations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    email = Column(String(200), nullable=False)
    role = Column(String(20), nullable=False)
    inviter_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    inviter_email = Column(String(200), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    hotel = relationship("HotelConfiguration")
    user = relationship("User", foreign_keys=[user_id])
    inviter = relationship("User", foreign_keys=[inviter_user_id])

    __table_args__ = (
        Index("ix_staff_invitations_hotel_email", "hotel_id", "email"),
        Index(
            "uq_staff_invitations_pending_email",
            "hotel_id",
            "email",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_staff_invitations_token_status", "token_hash", "status"),
    )
