from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class AnalyticsComparisonWindowRead(BaseModel):
    requested: bool
    available: bool
    date_from: date | None = None
    date_to: date | None = None

    model_config = {"from_attributes": True}


class AnalyticsComparisonStateRead(BaseModel):
    previous: AnalyticsComparisonWindowRead
    yoy: AnalyticsComparisonWindowRead

    model_config = {"from_attributes": True}


class AnalyticsMetricCardRead(BaseModel):
    card_code: str
    label: str
    value_ars: str | None = None
    value_pct: float | None = None
    value_count: int | None = None

    model_config = {"from_attributes": True}


class AnalyticsStarterSummaryDataRead(BaseModel):
    cards: list[AnalyticsMetricCardRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AnalyticsStarterSummaryRead(BaseModel):
    hotel_id: int
    date_from: date
    date_to: date
    data: AnalyticsStarterSummaryDataRead
    generated_at: datetime

    model_config = {"from_attributes": True}


class AnalyticsResponseEnvelopeRead(BaseModel):
    hotel_id: int
    date_from: date
    date_to: date
    currency_display: str | None = None
    comparison: AnalyticsComparisonStateRead | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime

    model_config = {"from_attributes": True}

