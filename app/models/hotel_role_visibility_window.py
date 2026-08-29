"""Per-role reservation visibility windows for one hotel."""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


VISIBILITY_WINDOW_ROLES = (
    "owner",
    "co_owner",
    "manager",
    "receptionist",
    "housekeeping",
)
VISIBILITY_WINDOW_HOURS = (12, 24, 48, 72, 168)


class HotelRoleVisibilityWindow(Base):
    """Reservation visibility limits configured independently per hotel role.

    A missing row means that role has no visibility limit.  ``NULL`` in either
    hour column means that side of the window is unlimited.
    """

    __tablename__ = "hotel_role_visibility_window"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)
    past_hours = Column(Integer, nullable=True)
    future_hours = Column(Integer, nullable=True)
    updated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("hotel_id", "role", name="uq_hotel_role_visibility_window_hotel_role"),
        CheckConstraint(
            "role IN ('owner', 'co_owner', 'manager', 'receptionist', 'housekeeping')",
            name="ck_hotel_role_visibility_window_role",
        ),
        CheckConstraint(
            "past_hours IS NULL OR past_hours IN (12, 24, 48, 72, 168)",
            name="ck_hotel_role_visibility_window_past_hours",
        ),
        CheckConstraint(
            "future_hours IS NULL OR future_hours IN (12, 24, 48, 72, 168)",
            name="ck_hotel_role_visibility_window_future_hours",
        ),
        Index("ix_hotel_role_visibility_window_hotel_id", "hotel_id"),
    )
