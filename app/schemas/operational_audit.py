"""Contracts for the owner/co-owner operational audit projection."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


class OperationalAuditItemRead(BaseModel):
    source: str
    source_id: int
    area: str
    action: str
    summary: str
    actor_user_id: Optional[int] = None
    actor_name: str
    occurred_at: datetime
    reservation_id: Optional[int] = None
    room_id: Optional[int] = None
    from_room_id: Optional[int] = None
    to_room_id: Optional[int] = None
    reason_code: Optional[str] = None
    reason_note: Optional[str] = None
    origin_room_disposition: Optional[str] = None
    origin_room_status_before: Optional[str] = None
    origin_room_status_after: Optional[str] = None
    payment_method: Optional[str] = None
    transaction_type: Optional[str] = None
    transaction_status: Optional[str] = None
    movement_type: Optional[str] = None
    amount: Optional[Decimal] = None
    currency_code: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class OperationalAuditRead(BaseModel):
    hotel_id: int
    items: list[OperationalAuditItemRead] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
    has_more: bool
