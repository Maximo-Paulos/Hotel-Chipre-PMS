from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class GemmaChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: int | None = Field(default=None, ge=1)


class GemmaChatMessageRead(BaseModel):
    id: int
    session_id: int
    role: str
    text: str
    intent_type: str | None = None
    created_at: datetime


class GemmaChatSessionSummaryRead(BaseModel):
    id: int
    mode: str
    status: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_preview: str | None = None
    message_count: int = 0


class GemmaRuntimeStatusRead(BaseModel):
    enabled: bool
    configured: bool
    provider: str
    model: str | None = None
    endpoint_url: str | None = None
    status: str
    reachable: bool = False
    strict_json: bool = True
    timeout_seconds: float | None = None
    max_conversation_messages: int | None = None
    max_input_chars: int | None = None
    fallback_reason: str | None = None
    probe_error: str | None = None


class GemmaChatSessionDetailRead(GemmaChatSessionSummaryRead):
    messages: list[GemmaChatMessageRead] = Field(default_factory=list)


class GemmaInsightRead(BaseModel):
    id: int
    session_id: int
    insight_type: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class GemmaChatEnvelopeRead(BaseModel):
    session: GemmaChatSessionSummaryRead
    messages: list[GemmaChatMessageRead] = Field(default_factory=list)
    answer: str | None = None
    mode: str
    intent_type: str | None = None
    summary: str | None = None
    requires_confirmation: bool = False
    actions: list[dict[str, Any]] = Field(default_factory=list)
    preview: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GemmaActionApproveRequest(BaseModel):
    session_id: int = Field(..., ge=1)


class GemmaActionApproveResponse(BaseModel):
    action_run_id: int
    status: str
    created_suggestion_id: int
    profile_id: int


class GemmaActionRejectRequest(BaseModel):
    session_id: int = Field(..., ge=1)


class GemmaActionRejectResponse(BaseModel):
    action_run_id: int
    status: str


class GemmaActionReviewDraftRequest(BaseModel):
    session_id: int = Field(..., ge=1)


class GemmaActionReviewDraftResponse(BaseModel):
    action_run_id: int
    status: str
    created_suggestion_id: int
    suggestion_status: str
    profile_id: int


class GemmaActionApplyDraftRequest(BaseModel):
    session_id: int = Field(..., ge=1)
    publish: bool = False
    prompt_summary: str | None = None


class GemmaActionApplyDraftResponse(BaseModel):
    action_run_id: int
    status: str
    created_suggestion_id: int
    suggestion_status: str
    created_version_id: int
    version_number: int
    is_published: bool
    profile_id: int
