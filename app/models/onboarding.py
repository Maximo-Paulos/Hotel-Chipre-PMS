"""
Onboarding state scoped by hotel.
Tracks completion of setup steps and stores draft configuration payloads.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app.database import Base


class OnboardingState(Base):
    __tablename__ = "onboarding_state"

    hotel_id = Column(Integer, primary_key=True, autoincrement=False)

    owner_name = Column(String(150), nullable=True)
    owner_email = Column(String(200), nullable=True)
    owner_phone = Column(String(80), nullable=True)
    owner_role = Column(String(120), nullable=True)

    hotel_identity_json = Column(Text, nullable=True)
    deposit_policy_json = Column(Text, nullable=True)
    payment_methods_json = Column(Text, nullable=True)
    ota_channels_json = Column(Text, nullable=True)
    subscription_choice_json = Column(Text, nullable=True)
    staff_json = Column(Text, nullable=True)

    identity_set = Column(Boolean, nullable=False, default=False)
    policy_set = Column(Boolean, nullable=False, default=False)
    payments_set = Column(Boolean, nullable=False, default=False)
    ota_set = Column(Boolean, nullable=False, default=False)
    subscription_set = Column(Boolean, nullable=False, default=False)
    finished = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    @staticmethod
    def _decode(value: str | None):
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _encode(payload) -> str:
        return json.dumps(payload)

    def get_staff(self) -> List[Dict]:
        decoded = self._decode(self.staff_json)
        return decoded if isinstance(decoded, list) else []

    def set_staff(self, staff: List[Dict]) -> None:
        self.staff_json = self._encode(staff)

    def get_hotel_identity(self) -> Dict:
        decoded = self._decode(self.hotel_identity_json)
        return decoded if isinstance(decoded, dict) else {}

    def set_hotel_identity(self, payload: Dict) -> None:
        self.hotel_identity_json = self._encode(payload)

    def get_deposit_policy(self) -> Dict:
        decoded = self._decode(self.deposit_policy_json)
        return decoded if isinstance(decoded, dict) else {}

    def set_deposit_policy(self, payload: Dict) -> None:
        self.deposit_policy_json = self._encode(payload)

    def get_payment_methods(self) -> Dict:
        decoded = self._decode(self.payment_methods_json)
        return decoded if isinstance(decoded, dict) else {}

    def set_payment_methods(self, payload: Dict) -> None:
        self.payment_methods_json = self._encode(payload)

    def get_ota_channels(self) -> Dict:
        decoded = self._decode(self.ota_channels_json)
        return decoded if isinstance(decoded, dict) else {}

    def set_ota_channels(self, payload: Dict) -> None:
        self.ota_channels_json = self._encode(payload)

    def get_subscription_choice(self) -> Dict:
        decoded = self._decode(self.subscription_choice_json)
        return decoded if isinstance(decoded, dict) else {}

    def set_subscription_choice(self, payload: Dict) -> None:
        self.subscription_choice_json = self._encode(payload)

    def __repr__(self) -> str:
        return f"<OnboardingState(hotel_id={self.hotel_id}, finished={self.finished})>"
