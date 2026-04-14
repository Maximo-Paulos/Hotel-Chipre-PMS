from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.allocation_policy import (
    AllocationExplanationRead,
    AllocationFeedbackDraftRequest,
    AllocationPolicySuggestionApplyRequest,
    AllocationPolicySuggestionApplyResponse,
    AllocationPolicySuggestionReviewRequest,
    ActiveAllocationPolicyRead,
    AllocationRunDetailRead,
    AllocationQuestionnaireDraftRequest,
    AllocationPolicySuggestionCreate,
    AllocationPolicySuggestionRead,
    AllocationPolicyVersionCreate,
    AllocationPolicyVersionRead,
    SolverMetricRead,
)
from app.services.allocation_learning_service import draft_policy_from_feedback, draft_policy_from_questionnaire
from app.services.allocation_policy_service import (
    AllocationPolicyError,
    apply_policy_suggestion,
    create_policy_suggestion_draft,
    create_policy_version,
    get_active_policy_settings,
    list_policy_suggestions,
    list_policy_versions,
    publish_policy_version,
    review_policy_suggestion,
)
from app.services.allocation_runtime_service import get_allocation_run_details, get_latest_allocation_run_details

router = APIRouter(prefix="/api/allocation/policy", tags=["Allocation Policy"])


def _serialize_policy_version(version) -> AllocationPolicyVersionRead:
    constraints = _load_json_dict(version.constraints_json)
    weights = {key: float(value) for key, value in _load_json_dict(version.weights_json).items()}
    return AllocationPolicyVersionRead(
        id=version.id,
        profile_id=version.profile_id,
        version_number=version.version_number,
        source=version.source,
        constraints=constraints,
        weights=weights,
        prompt_summary=version.prompt_summary,
        is_published=version.is_published,
        created_by_user_id=version.created_by_user_id,
        created_at=version.created_at,
    )


def _serialize_suggestion(suggestion) -> AllocationPolicySuggestionRead:
    return AllocationPolicySuggestionRead(
        id=suggestion.id,
        profile_id=suggestion.profile_id,
        suggestion_type=suggestion.suggestion_type,
        status=suggestion.status.value if hasattr(suggestion.status, "value") else str(suggestion.status),
        source_model=suggestion.source_model,
        input_summary=suggestion.input_summary,
        suggested_policy=_load_json_dict(suggestion.suggested_policy_json),
        explanation=suggestion.explanation,
        reviewed_by_user_id=suggestion.reviewed_by_user_id,
        reviewed_at=suggestion.reviewed_at,
        created_at=suggestion.created_at,
    )


def _serialize_run_details(details) -> AllocationRunDetailRead:
    run = details.run
    return AllocationRunDetailRead(
        run_id=run.id,
        status=run.status.value if hasattr(run.status, "value") else str(run.status),
        trigger_type=run.trigger_type,
        objective_score=run.objective_score,
        solver_summary=run.solver_summary,
        error_message=run.error_message,
        policy_version_id=run.policy_version_id,
        horizon_start=run.horizon_start,
        horizon_end=run.horizon_end,
        created_at=run.created_at,
        explanations=[
            AllocationExplanationRead(
                id=item.id,
                allocation_run_id=item.allocation_run_id,
                reservation_id=item.reservation_id,
                explanation_type=item.explanation_type,
                summary=item.summary,
                details=_load_json_dict(item.details_json),
                created_at=item.created_at,
            )
            for item in details.explanations
        ],
        metrics=[
            SolverMetricRead(metric_key=item.metric_key, metric_value=float(item.metric_value))
            for item in details.metrics
        ],
    )


@router.get("", response_model=ActiveAllocationPolicyRead)
def get_active_policy(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    settings = get_active_policy_settings(db, context.hotel_id)
    return ActiveAllocationPolicyRead(
        profile_id=settings.profile.id,
        profile_code=settings.profile.code,
        profile_name=settings.profile.name,
        version=_serialize_policy_version(settings.version),
    )


@router.get("/versions", response_model=list[AllocationPolicyVersionRead])
def get_policy_versions(
    profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    versions = list_policy_versions(db, context.hotel_id, profile_id=profile_id)
    return [_serialize_policy_version(version) for version in versions]


@router.post("/versions", response_model=AllocationPolicyVersionRead, status_code=status.HTTP_201_CREATED)
def create_version(
    payload: AllocationPolicyVersionCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        settings = get_active_policy_settings(db, context.hotel_id)
        version = create_policy_version(
            db,
            hotel_id=context.hotel_id,
            profile_id=settings.profile.id,
            constraints=payload.constraints,
            weights=payload.weights,
            prompt_summary=payload.prompt_summary,
            source=payload.source,
            created_by_user_id=context.user_id,
            publish=payload.publish,
        )
        db.commit()
        return _serialize_policy_version(version)
    except AllocationPolicyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/versions/{version_id}/publish", response_model=AllocationPolicyVersionRead)
def publish_version(
    version_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        settings = get_active_policy_settings(db, context.hotel_id)
        version = publish_policy_version(
            db,
            hotel_id=context.hotel_id,
            profile_id=settings.profile.id,
            version_id=version_id,
        )
        db.commit()
        return _serialize_policy_version(version)
    except AllocationPolicyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/suggestions", response_model=list[AllocationPolicySuggestionRead])
def get_policy_suggestions(
    profile_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    suggestions = list_policy_suggestions(
        db,
        context.hotel_id,
        profile_id=profile_id,
        status=status_filter,
    )
    return [_serialize_suggestion(suggestion) for suggestion in suggestions]


@router.post("/suggestions", response_model=AllocationPolicySuggestionRead, status_code=status.HTTP_201_CREATED)
def create_suggestion(
    payload: AllocationPolicySuggestionCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    suggestion = create_policy_suggestion_draft(
        db,
        hotel_id=context.hotel_id,
        suggestion_type=payload.suggestion_type,
        input_summary=payload.input_summary,
        suggested_policy=payload.suggested_policy,
        explanation=payload.explanation,
        source_model=payload.source_model,
        profile_id=payload.profile_id,
    )
    db.commit()
    return _serialize_suggestion(suggestion)


@router.post("/suggestions/{suggestion_id}/review", response_model=AllocationPolicySuggestionRead)
def review_suggestion(
    suggestion_id: int,
    payload: AllocationPolicySuggestionReviewRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        suggestion = review_policy_suggestion(
            db,
            hotel_id=context.hotel_id,
            suggestion_id=suggestion_id,
            action=payload.action,
            reviewed_by_user_id=context.user_id,
        )
        db.commit()
        return _serialize_suggestion(suggestion)
    except AllocationPolicyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/suggestions/{suggestion_id}/apply", response_model=AllocationPolicySuggestionApplyResponse)
def apply_suggestion(
    suggestion_id: int,
    payload: AllocationPolicySuggestionApplyRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        suggestion, version = apply_policy_suggestion(
            db,
            hotel_id=context.hotel_id,
            suggestion_id=suggestion_id,
            created_by_user_id=context.user_id,
            publish=payload.publish,
            prompt_summary=payload.prompt_summary,
        )
        db.commit()
        return AllocationPolicySuggestionApplyResponse(
            suggestion=_serialize_suggestion(suggestion),
            version=_serialize_policy_version(version),
        )
    except AllocationPolicyError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/questionnaire-draft", response_model=AllocationPolicySuggestionRead, status_code=status.HTTP_201_CREATED)
def create_questionnaire_draft(
    payload: AllocationQuestionnaireDraftRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    draft = draft_policy_from_questionnaire(
        db,
        hotel_id=context.hotel_id,
        business_summary=payload.business_summary,
        prioritize_exact_match=payload.prioritize_exact_match,
        minimize_one_night_gaps=payload.minimize_one_night_gaps,
        minimize_moves=payload.minimize_moves,
        preserve_future_availability=payload.preserve_future_availability,
        allow_category_fallback=payload.allow_category_fallback,
        notes=payload.notes,
    )
    db.commit()
    return _serialize_suggestion(draft.suggestion)


@router.post("/feedback-draft", response_model=AllocationPolicySuggestionRead, status_code=status.HTTP_201_CREATED)
def create_feedback_draft(
    payload: AllocationFeedbackDraftRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    draft = draft_policy_from_feedback(
        db,
        hotel_id=context.hotel_id,
        max_events=payload.max_events,
        notes=payload.notes,
    )
    db.commit()
    return _serialize_suggestion(draft.suggestion)


@router.get("/runs/latest", response_model=AllocationRunDetailRead)
def get_latest_run(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    details = get_latest_allocation_run_details(db, hotel_id=context.hotel_id)
    if details is None:
        raise HTTPException(status_code=404, detail="No allocation runs found")
    return _serialize_run_details(details)


@router.get("/runs/{run_id}", response_model=AllocationRunDetailRead)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    details = get_allocation_run_details(db, hotel_id=context.hotel_id, run_id=run_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Allocation run not found")
    return _serialize_run_details(details)


def _load_json_dict(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}
