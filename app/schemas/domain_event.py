from pydantic import BaseModel, Field


class DomainEventRecoveryResponse(BaseModel):
    """Safe cursor response used to repair missed realtime invalidations."""

    latest_cursor: int = Field(ge=0)
    domains: list[str]
    reset_required: bool
    has_more: bool
