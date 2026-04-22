"""
Pydantic schemas for the onboarding flow.
"""
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.room import RoomCategoryCreate
from app.services.timezones import normalize_timezone


class OwnerPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    email: str = Field(..., min_length=3, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=80)
    role: Optional[str] = Field(default=None, max_length=120)


class HotelIdentityPayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    timezone: str = Field(..., min_length=3, max_length=100)
    currency: str = Field(..., min_length=3, max_length=3)
    languages: List[str] = Field(default_factory=list, min_length=1)
    jurisdiction_code: str = Field(..., min_length=2, max_length=3)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("timezone")
    @classmethod
    def normalize_timezone_value(cls, value: str) -> str:
        return normalize_timezone(value)

    @field_validator("jurisdiction_code")
    @classmethod
    def normalize_jurisdiction(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("languages")
    @classmethod
    def normalize_languages(cls, value: List[str]) -> List[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("At least one language is required")
        return cleaned


class DepositPolicyPayload(BaseModel):
    deposit_percentage: float = Field(..., ge=0, le=100)
    free_cancellation_hours: int = Field(..., ge=0, le=168)
    cancellation_penalty_percentage: float = Field(..., ge=0, le=100)


class ProviderSetupPayload(BaseModel):
    enabled: bool = False
    credentials: Dict[str, str] = Field(default_factory=dict)


class PaymentMethodsPayload(BaseModel):
    mercado_pago: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)
    paypal: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)
    stripe: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)


class OTAChannelsPayload(BaseModel):
    booking: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)
    expedia: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)
    despegar: ProviderSetupPayload = Field(default_factory=ProviderSetupPayload)


class SubscriptionChoicePayload(BaseModel):
    plan_code: str = Field(..., min_length=3, max_length=20)
    start_trial: bool = False

    @field_validator("plan_code")
    @classmethod
    def normalize_plan_code(cls, value: str) -> str:
        return value.strip().lower()


class CategoriesPayload(BaseModel):
    categories: List[RoomCategoryCreate]


class RoomInput(BaseModel):
    room_number: str = Field(..., min_length=1, max_length=10)
    floor: int = Field(ge=0)
    category_code: str = Field(..., min_length=1, max_length=20)


class RoomsPayload(BaseModel):
    rooms: List[RoomInput]


class StaffMember(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    role: Optional[str] = Field(default=None, max_length=120)
    email: Optional[str] = Field(default=None, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=80)


class StaffPayload(BaseModel):
    staff: List[StaffMember]


class OnboardingStatus(BaseModel):
    hotel_id: int
    completed: bool
    steps: Dict[str, bool]
    missing_steps: List[str]
    gates: Optional[dict] = None
    counts: Dict[str, int]
    owner: Optional[dict] = None
    hotel_identity: Optional[dict] = None
    deposit_policy: Optional[dict] = None
    payment_methods: Optional[dict] = None
    ota_channels: Optional[dict] = None
    subscription_choice: Optional[dict] = None
    current_subscription: Optional[dict] = None
    categories: List[dict] = Field(default_factory=list)
    rooms: List[dict] = Field(default_factory=list)
    staff: List[dict] = Field(default_factory=list)
