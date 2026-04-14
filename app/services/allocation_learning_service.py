from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.allocation import LLMFeedbackEvent, LLMPolicySuggestion
from app.services.allocation_policy_service import (
    create_policy_suggestion_draft,
    ensure_default_policy_profile,
    get_active_policy_settings,
)
from app.services.gemma_service import GemmaService


@dataclass(slots=True)
class AllocationQuestionnaireDraft:
    suggestion: LLMPolicySuggestion
    suggested_policy: dict


@dataclass(slots=True)
class AllocationFeedbackDraft:
    suggestion: LLMPolicySuggestion
    suggested_policy: dict


def draft_policy_from_questionnaire(
    db: Session,
    *,
    hotel_id: int,
    business_summary: str,
    prioritize_exact_match: int,
    minimize_one_night_gaps: int,
    minimize_moves: int,
    preserve_future_availability: int,
    allow_category_fallback: bool,
    notes: str | None = None,
) -> AllocationQuestionnaireDraft:
    profile = ensure_default_policy_profile(db, hotel_id)
    gemma_service = GemmaService()
    gemma_draft = gemma_service.suggest_policy_from_questionnaire(
        hotel_id=hotel_id,
        business_summary=business_summary,
        prioritize_exact_match=prioritize_exact_match,
        minimize_one_night_gaps=minimize_one_night_gaps,
        minimize_moves=minimize_moves,
        preserve_future_availability=preserve_future_availability,
        allow_category_fallback=allow_category_fallback,
        notes=notes,
    )
    suggestion = create_policy_suggestion_draft(
        db,
        hotel_id=hotel_id,
        profile_id=profile.id,
        suggestion_type="questionnaire_ingest",
        input_summary=gemma_service.redact_text_for_llm(business_summary, limit=500),
        suggested_policy=gemma_draft.suggested_policy,
        explanation=gemma_draft.explanation,
        source_model=gemma_draft.source_model,
    )
    return AllocationQuestionnaireDraft(
        suggestion=suggestion,
        suggested_policy=gemma_draft.suggested_policy,
    )


def draft_policy_from_feedback(
    db: Session,
    *,
    hotel_id: int,
    max_events: int = 25,
    notes: str | None = None,
) -> AllocationFeedbackDraft:
    profile = ensure_default_policy_profile(db, hotel_id)
    active_settings = get_active_policy_settings(db, hotel_id)
    feedback_rows = (
        db.query(LLMFeedbackEvent)
        .filter(LLMFeedbackEvent.hotel_id == hotel_id)
        .order_by(LLMFeedbackEvent.created_at.desc(), LLMFeedbackEvent.id.desc())
        .limit(max_events)
        .all()
    )
    feedback_events: list[dict] = []
    for row in feedback_rows:
        payload = {}
        if row.payload_json:
            try:
                loaded = json.loads(row.payload_json)
            except json.JSONDecodeError:
                loaded = {}
            if isinstance(loaded, dict):
                payload = loaded
        feedback_events.append(
            {
                "event_type": row.event_type,
                "reservation_id": row.reservation_id,
                "allocation_run_id": row.allocation_run_id,
                "source_model": row.source_model,
                "payload": payload,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )

    gemma_draft = GemmaService().suggest_policy_from_feedback(
        hotel_id=hotel_id,
        current_constraints=active_settings.constraints,
        current_weights=active_settings.weights,
        feedback_events=feedback_events,
        notes=notes,
    )
    input_summary = (
        f"Feedback-driven draft from {len(feedback_events)} event(s)."
        if feedback_events
        else "Feedback-driven draft with no events yet; active policy carried forward."
    )
    suggestion = create_policy_suggestion_draft(
        db,
        hotel_id=hotel_id,
        profile_id=profile.id,
        suggestion_type="feedback_learning",
        input_summary=input_summary,
        suggested_policy=gemma_draft.suggested_policy,
        explanation=gemma_draft.explanation,
        source_model=gemma_draft.source_model,
    )
    return AllocationFeedbackDraft(
        suggestion=suggestion,
        suggested_policy=gemma_draft.suggested_policy,
    )
