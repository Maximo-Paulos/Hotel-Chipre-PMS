from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.whatsapp_crm import WhatsAppConversationStatusEnum


class WhatsAppContactRead(BaseModel):
    id: int
    normalized_phone: str
    display_name: str | None = None
    guest_id: int | None = None

    model_config = {"from_attributes": True}


class WhatsAppMessageRead(BaseModel):
    id: int
    direction: str
    status: str
    message_type: str
    text: str | None = None
    actor_user_id: int | None = None
    provider_message_id: str | None = None
    created_at: datetime
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class WhatsAppConversationRead(BaseModel):
    id: int
    hotel_id: int
    status: WhatsAppConversationStatusEnum
    priority: str
    assigned_to_user_id: int | None = None
    department: str | None = None
    shift_key: str | None = None
    human_active: bool
    service_window_expires_at: datetime | None = None
    last_inbound_at: datetime | None = None
    last_message_at: datetime | None = None
    contact: WhatsAppContactRead
    messages: list[WhatsAppMessageRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class WhatsAppConversationListResponse(BaseModel):
    items: list[WhatsAppConversationRead]


class WhatsAppMessageCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    message_type: str = Field(default="text", min_length=1, max_length=40)


class WhatsAppAssignmentUpdate(BaseModel):
    assigned_to_user_id: int | None = None


class WhatsAppNoteCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class WhatsAppConversationStatusUpdate(BaseModel):
    status: WhatsAppConversationStatusEnum


class WhatsAppChannelComplete(BaseModel):
    """Metadata returned by the server-side Embedded Signup exchange."""
    waba_id: str = Field(..., min_length=1, max_length=120)
    phone_number_id: str = Field(..., min_length=1, max_length=120)
    display_phone_number: str | None = Field(default=None, max_length=40)
    display_name: str | None = Field(default=None, max_length=160)
    integration_connection_id: int | None = None
