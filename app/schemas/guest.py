"""
Pydantic schemas for Guest and companions.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import date, datetime

from app.models.guest import DocumentTypeEnum


class GuestCompanionBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    document_type: Optional[DocumentTypeEnum] = None
    document_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    relationship_to_guest: Optional[str] = None


class GuestCompanionCreate(GuestCompanionBase):
    pass


class GuestCompanionRead(GuestCompanionBase):
    id: int
    guest_id: int
    model_config = {"from_attributes": True}


class GuestBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    document_type: Optional[DocumentTypeEnum] = None
    document_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    terms_accepted: bool = False
    digital_signature: Optional[str] = None
    special_requests: Optional[str] = None
    observations: Optional[str] = None


class GuestCreate(GuestBase):
    companions: list[GuestCompanionCreate] = []


class GuestUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    document_type: Optional[DocumentTypeEnum] = None
    document_number: Optional[str] = None
    nationality: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state_province: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    terms_accepted: Optional[bool] = None
    digital_signature: Optional[str] = None
    special_requests: Optional[str] = None
    observations: Optional[str] = None


class GuestRead(GuestBase):
    id: int
    created_at: Optional[datetime] = None
    retention_until: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    companions: list[GuestCompanionRead] = []
    model_config = {"from_attributes": True}
