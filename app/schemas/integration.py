from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class IntegrationCatalogRead(BaseModel):
    id: int
    provider: str
    display_name: str
    auth_type: str
    scopes: Optional[str] = None
    doc_url: Optional[str] = None

    class Config:
        from_attributes = True


class IntegrationConnectionRead(BaseModel):
    id: int
    integration: IntegrationCatalogRead
    status: str
    expires_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None
    account_label: Optional[str] = None

    class Config:
        from_attributes = True


class IntegrationConnectRequest(BaseModel):
    payload: dict[str, Any] | None = None


class IntegrationConnectResponse(BaseModel):
    redirect_url: Optional[str] = None
    status: str


class IntegrationRefreshResponse(BaseModel):
    status: str
    message: str
    last_checked_at: Optional[datetime] = None
    last_error: Optional[str] = None


class IntegrationStatusResponse(BaseModel):
    catalog: list[IntegrationCatalogRead]
    connections: list[IntegrationConnectionRead]
