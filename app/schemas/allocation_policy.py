from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AllocationPolicyVersionCreate(BaseModel):
    constraints: dict[str, Any] = Field(default_factory=dict)
    weights: dict[str, float] = Field(default_factory=dict)
    prompt_summary: Optional[str] = None
    source: str = Field(default="manual", min_length=1, max_length=30)
    publish: bool = False


class AllocationPolicyVersionRead(BaseModel):
    id: int
    profile_id: int
    version_number: int
    source: str
    constraints: dict[str, Any]
    weights: dict[str, float]
    prompt_summary: Optional[str]
    is_published: bool
    created_by_user_id: Optional[int]
    created_at: datetime


class ActiveAllocationPolicyRead(BaseModel):
    profile_id: int
    profile_code: str
    profile_name: str
    version: AllocationPolicyVersionRead


class AllocationPolicySuggestionCreate(BaseModel):
    suggestion_type: str = Field(..., min_length=1, max_length=50)
    input_summary: str = Field(..., min_length=1)
    suggested_policy: dict[str, Any] = Field(default_factory=dict)
    explanation: Optional[str] = None
    source_model: Optional[str] = Field(default=None, max_length=100)
    profile_id: Optional[int] = None


class AllocationPolicySuggestionRead(BaseModel):
    id: int
    profile_id: Optional[int]
    suggestion_type: str
    status: str
    source_model: Optional[str]
    input_summary: Optional[str]
    suggested_policy: dict[str, Any]
    explanation: Optional[str]
    reviewed_by_user_id: Optional[int]
    reviewed_at: Optional[datetime]
    created_at: datetime


class AllocationPolicySuggestionReviewRequest(BaseModel):
    action: str = Field(..., min_length=1, max_length=20)


class AllocationPolicySuggestionApplyRequest(BaseModel):
    publish: bool = False
    prompt_summary: Optional[str] = None


class AllocationPolicySuggestionApplyResponse(BaseModel):
    suggestion: AllocationPolicySuggestionRead
    version: AllocationPolicyVersionRead


class AllocationQuestionnaireDraftRequest(BaseModel):
    business_summary: str = Field(..., min_length=1)
    prioritize_exact_match: int = Field(default=3, ge=1, le=5)
    minimize_one_night_gaps: int = Field(default=3, ge=1, le=5)
    minimize_moves: int = Field(default=3, ge=1, le=5)
    preserve_future_availability: int = Field(default=3, ge=1, le=5)
    allow_category_fallback: bool = True
    notes: Optional[str] = None


class AllocationFeedbackDraftRequest(BaseModel):
    max_events: int = Field(default=25, ge=1, le=200)
    notes: Optional[str] = None


class AllocationExplanationRead(BaseModel):
    id: int
    allocation_run_id: int
    reservation_id: int
    explanation_type: str
    summary: str
    details: dict[str, Any]
    created_at: datetime


class SolverMetricRead(BaseModel):
    metric_key: str
    metric_value: float


class AllocationRunDetailRead(BaseModel):
    run_id: int
    status: str
    trigger_type: str
    objective_score: Optional[float]
    solver_summary: Optional[str]
    error_message: Optional[str]
    policy_version_id: Optional[int]
    horizon_start: Optional[datetime]
    horizon_end: Optional[datetime]
    created_at: datetime
    explanations: list[AllocationExplanationRead] = Field(default_factory=list)
    metrics: list[SolverMetricRead] = Field(default_factory=list)
