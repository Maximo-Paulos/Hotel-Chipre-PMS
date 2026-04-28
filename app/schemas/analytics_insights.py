from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyticsInsightRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date | None = None
    date_to: date | None = None
    currency_display: Literal["ARS", "USD", "BOTH"] = Field(default="ARS")
    compare_previous: bool = Field(default=True)
    compare_yoy: bool = Field(default=False)
    room_id: int | None = None
    category_id: int | None = None
    company_id: int | None = None

    @model_validator(mode="after")
    def _validate_dates(self) -> "AnalyticsInsightRequest":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to debe ser mayor o igual a date_from")
        return self


class AnalyticsInsightStatusRead(BaseModel):
    hotel_id: int
    analytics_ai_enabled: bool
    provider: str
    runtime_healthy: bool
    effective_model: str | None = None
    quota_monthly: int
    quota_used: int
    quota_remaining: int
    runtime_status: str
    fallback_reason: str | None = None


class AnalyticsInsightRead(BaseModel):
    hotel_id: int
    insight_code: Literal["home", "anomalies", "pricing"]
    date_from: date | None = None
    date_to: date | None = None
    analytics_ai_enabled: bool
    provider: str
    runtime_healthy: bool
    effective_model: str | None = None
    quota_monthly: int
    quota_used: int
    quota_remaining: int
    generated_at: datetime
    summary: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class AnalyticsAIChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=1000)
    date_from: date | None = None
    date_to: date | None = None
    currency_display: Literal["ARS", "USD", "BOTH"] = Field(default="ARS")
    compare_previous: bool = Field(default=True)
    compare_yoy: bool = Field(default=False)

    @model_validator(mode="after")
    def _validate_dates(self) -> "AnalyticsAIChatRequest":
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("date_to debe ser mayor o igual a date_from")
        return self


class AnalyticsAIChatRead(BaseModel):
    hotel_id: int
    answer: str
    warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime
