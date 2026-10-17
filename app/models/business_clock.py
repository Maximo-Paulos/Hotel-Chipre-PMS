"""Opt-in local business date for one synthetic hotel."""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer

from app.database import Base


class HotelBusinessClock(Base):
    """Persist the latest simulated business date for a single hotel.

    The row is inert unless the process is explicitly configured for local
    development, SQLite, and this hotel id. `advanced_at` records real UTC
    wall-clock time; the simulation changes dates only, never instants.
    """

    __tablename__ = "hotel_business_clock"

    hotel_id = Column(
        Integer,
        ForeignKey("hotel_configuration.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    business_date = Column(Date, nullable=False)
    advanced_at = Column(DateTime(timezone=True), nullable=False)
    advanced_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
