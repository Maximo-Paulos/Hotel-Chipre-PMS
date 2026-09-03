from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.company_document import CompanyDocumentStatusEnum, CompanyDocumentTypeEnum


class CompanyDocumentCreate(BaseModel):
    reservation_id: int
    company_id: int | None = None
    doc_type: CompanyDocumentTypeEnum = CompanyDocumentTypeEnum.OTHER
    file_name: str | None = Field(default=None, max_length=300)
    file_url: str | None = Field(default=None, max_length=1000)
    stored_object_id: str | None = Field(default=None, max_length=36)
    requires_signature: bool = False
    notes: str | None = None


class CompanyDocumentStatusUpdate(BaseModel):
    status: CompanyDocumentStatusEnum


class CompanyDocumentRead(BaseModel):
    id: int
    hotel_id: int
    reservation_id: int
    company_id: int | None = None
    doc_type: CompanyDocumentTypeEnum
    status: CompanyDocumentStatusEnum
    file_name: str | None = None
    file_url: str | None = None
    stored_object_id: str | None = None
    requires_signature: bool
    signed_at: datetime | None = None
    signed_by_user_id: int | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    created_by_user_id: int | None = None

    model_config = {"from_attributes": True}
