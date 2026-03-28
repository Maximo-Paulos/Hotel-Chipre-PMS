"""
Onboarding state scoped by hotel.
Tracks completion of required steps so the dashboard can be gated until ready.
"""
import json
from datetime import datetime, timezone
from typing import List, Dict

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text

from app.database import Base


class OnboardingState(Base):
    __tablename__ = "onboarding_state"

    hotel_id = Column(Integer, primary_key=True, autoincrement=False)

    owner_name = Column(String(150), nullable=True)
    owner_email = Column(String(200), nullable=True)
    owner_phone = Column(String(80), nullable=True)
    owner_role = Column(String(120), nullable=True)

    staff_json = Column(Text, nullable=True)
    finished = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_staff(self) -> List[Dict]:
        """Return the stored staff list (empty list if none)."""
        if not self.staff_json:
            return []
        try:
            return json.loads(self.staff_json)
        except json.JSONDecodeError:
            return []

    def set_staff(self, staff: List[Dict]) -> None:
        """Persist staff list as JSON."""
        self.staff_json = json.dumps(staff)

    def __repr__(self) -> str:
        return f"<OnboardingState(hotel_id={self.hotel_id}, finished={self.finished})>"
