"""
Pydantic schemas for external provider connections.
Ensures credentials/settings remain JSON objects end-to-end.
"""
from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    """Payload to establish/update a provider connection."""
    credentials: Dict[str, Any] = Field(default_factory=dict)
    settings: Dict[str, Any] | None = Field(default_factory=dict)


class ConnectionRead(BaseModel):
    id: int
    provider: str
    status: str
    credentials: Dict[str, Any]
    settings: Dict[str, Any] | None = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
