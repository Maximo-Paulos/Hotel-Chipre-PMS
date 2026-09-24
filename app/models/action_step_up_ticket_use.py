"""Tenant-scoped replay ledger for MFA step-up tickets."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ActionStepUpTicketUse(Base):
    """Persist only the random ticket id and action binding after first use."""

    __tablename__ = "action_step_up_ticket_uses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticket_id = Column(String(32), nullable=False)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission_code = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)
    path = Column(String(2048), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("ticket_id", name="uq_action_step_up_ticket_use_id"),
        Index("ix_action_step_up_ticket_uses_hotel_expiry", "hotel_id", "expires_at"),
    )
