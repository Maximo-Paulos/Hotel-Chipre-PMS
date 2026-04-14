"""
Allocation policy profile and feedback service.

This layer makes policy profiles usable before any LLM integration exists:
- seeds deterministic defaults
- versions policy settings cleanly
- records manual override reasons and feedback events
- stores draft suggestions that a future Gemma flow can populate
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.allocation import (
    AllocationPolicyProfile,
    AllocationPolicyVersion,
    LLMFeedbackEvent,
    LLMPolicySuggestionStatusEnum,
    LLMPolicySuggestion,
    ManualOverrideReason,
)
from app.models.user import User


DEFAULT_ALLOCATION_CONSTRAINTS: dict[str, Any] = {
    "no_overlap": True,
    "respect_locked_assignments": True,
    "allow_category_fallback": True,
}

DEFAULT_ALLOCATION_WEIGHTS: dict[str, float] = {
    "prefer_exact_match": 500.0,
    "stability": 5.0,
    "room_usage_penalty": 50.0,
    "unassigned_penalty": 10000.0,
    "fallback_priority_penalty": 25.0,
}


@dataclass(slots=True)
class AllocationPolicySettings:
    profile: AllocationPolicyProfile
    version: AllocationPolicyVersion
    constraints: dict[str, Any]
    weights: dict[str, float]


class AllocationPolicyError(ValueError):
    """Raised when allocation policy settings are invalid."""


def ensure_default_policy_profile(db: Session, hotel_id: int) -> AllocationPolicyProfile:
    profile = (
        db.query(AllocationPolicyProfile)
        .filter(
            AllocationPolicyProfile.hotel_id == hotel_id,
            AllocationPolicyProfile.code == "default",
        )
        .first()
    )
    if profile:
        return profile

    profile = AllocationPolicyProfile(
        hotel_id=hotel_id,
        code="default",
        name="Default allocation policy",
        description="Base deterministic policy for room assignment",
        is_active=True,
    )
    db.add(profile)
    db.flush()
    return profile


def ensure_default_policy_version(db: Session, hotel_id: int) -> AllocationPolicyVersion:
    profile = ensure_default_policy_profile(db, hotel_id)
    version = (
        db.query(AllocationPolicyVersion)
        .filter(AllocationPolicyVersion.profile_id == profile.id)
        .order_by(AllocationPolicyVersion.version_number.desc())
        .first()
    )
    if version:
        return version

    version = AllocationPolicyVersion(
        hotel_id=hotel_id,
        profile_id=profile.id,
        version_number=1,
        source="seeded_default",
        constraints_json=json.dumps(DEFAULT_ALLOCATION_CONSTRAINTS, ensure_ascii=True, sort_keys=True),
        weights_json=json.dumps(DEFAULT_ALLOCATION_WEIGHTS, ensure_ascii=True, sort_keys=True),
        prompt_summary="Default deterministic allocation policy",
        is_published=True,
    )
    db.add(version)
    db.flush()
    return version


def get_active_policy_settings(db: Session, hotel_id: int) -> AllocationPolicySettings:
    profile = (
        db.query(AllocationPolicyProfile)
        .filter(
            AllocationPolicyProfile.hotel_id == hotel_id,
            AllocationPolicyProfile.is_active == True,
        )
        .order_by(AllocationPolicyProfile.id.asc())
        .first()
    )
    if not profile:
        version = ensure_default_policy_version(db, hotel_id)
        profile = version.profile
    else:
        version = (
            db.query(AllocationPolicyVersion)
            .filter(
                AllocationPolicyVersion.profile_id == profile.id,
                AllocationPolicyVersion.is_published == True,
            )
            .order_by(AllocationPolicyVersion.version_number.desc())
            .first()
        )
        if not version:
            version = ensure_default_policy_version(db, hotel_id)
            profile = version.profile

    constraints = DEFAULT_ALLOCATION_CONSTRAINTS | _load_json_dict(version.constraints_json)
    weights_raw = DEFAULT_ALLOCATION_WEIGHTS | _load_json_dict(version.weights_json)
    weights = {key: float(value) for key, value in weights_raw.items()}
    return AllocationPolicySettings(
        profile=profile,
        version=version,
        constraints=constraints,
        weights=weights,
    )


def list_policy_versions(
    db: Session,
    hotel_id: int,
    *,
    profile_id: Optional[int] = None,
) -> list[AllocationPolicyVersion]:
    if profile_id is None:
        profile_id = ensure_default_policy_profile(db, hotel_id).id
    return (
        db.query(AllocationPolicyVersion)
        .filter(
            AllocationPolicyVersion.hotel_id == hotel_id,
            AllocationPolicyVersion.profile_id == profile_id,
        )
        .order_by(AllocationPolicyVersion.version_number.desc())
        .all()
    )


def list_policy_suggestions(
    db: Session,
    hotel_id: int,
    *,
    profile_id: Optional[int] = None,
    status: Optional[str] = None,
) -> list[LLMPolicySuggestion]:
    query = db.query(LLMPolicySuggestion).filter(LLMPolicySuggestion.hotel_id == hotel_id)
    if profile_id is not None:
        query = query.filter(LLMPolicySuggestion.profile_id == profile_id)
    if status:
        query = query.filter(LLMPolicySuggestion.status == status)
    return query.order_by(LLMPolicySuggestion.created_at.desc(), LLMPolicySuggestion.id.desc()).all()


def create_policy_version(
    db: Session,
    *,
    hotel_id: int,
    profile_id: int,
    constraints: dict[str, Any] | None = None,
    weights: dict[str, Any] | None = None,
    prompt_summary: str | None = None,
    source: str = "manual",
    created_by_user_id: Optional[int] = None,
    publish: bool = False,
) -> AllocationPolicyVersion:
    profile = (
        db.query(AllocationPolicyProfile)
        .filter(
            AllocationPolicyProfile.id == profile_id,
            AllocationPolicyProfile.hotel_id == hotel_id,
        )
        .first()
    )
    if not profile:
        raise AllocationPolicyError("Allocation policy profile not found for hotel")

    current_version = (
        db.query(AllocationPolicyVersion)
        .filter(AllocationPolicyVersion.profile_id == profile.id)
        .order_by(AllocationPolicyVersion.version_number.desc())
        .first()
    )
    next_version_number = 1 if current_version is None else current_version.version_number + 1

    resolved_user_id = _resolve_existing_user_id(db, created_by_user_id)

    version = AllocationPolicyVersion(
        hotel_id=hotel_id,
        profile_id=profile.id,
        version_number=next_version_number,
        source=source,
        constraints_json=json.dumps(constraints or DEFAULT_ALLOCATION_CONSTRAINTS, ensure_ascii=True, sort_keys=True),
        weights_json=json.dumps(weights or DEFAULT_ALLOCATION_WEIGHTS, ensure_ascii=True, sort_keys=True),
        prompt_summary=prompt_summary,
        is_published=publish,
        created_by_user_id=resolved_user_id,
    )
    db.add(version)
    db.flush()
    if publish:
        publish_policy_version(db, hotel_id=hotel_id, profile_id=profile.id, version_id=version.id)
    return version


def publish_policy_version(db: Session, *, hotel_id: int, profile_id: int, version_id: int) -> AllocationPolicyVersion:
    versions = (
        db.query(AllocationPolicyVersion)
        .filter(
            AllocationPolicyVersion.hotel_id == hotel_id,
            AllocationPolicyVersion.profile_id == profile_id,
        )
        .all()
    )
    if not versions:
        raise AllocationPolicyError("No policy versions found for profile")

    selected = None
    for version in versions:
        is_target = version.id == version_id
        version.is_published = is_target
        if is_target:
            selected = version
    if selected is None:
        raise AllocationPolicyError("Requested policy version not found for profile")
    db.flush()
    return selected


def record_manual_override_feedback(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    override_type: str,
    reason_code: str | None,
    notes: str | None,
    created_by_user_id: Optional[int] = None,
    allocation_run_id: Optional[int] = None,
    source_model: str | None = None,
) -> tuple[ManualOverrideReason, LLMFeedbackEvent]:
    override = ManualOverrideReason(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        override_type=override_type,
        reason_code=reason_code,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(override)
    db.flush()

    payload = {
        "override_type": override_type,
        "reason_code": reason_code,
        "notes": notes,
    }
    feedback = LLMFeedbackEvent(
        hotel_id=hotel_id,
        reservation_id=reservation_id,
        allocation_run_id=allocation_run_id,
        manual_override_reason_id=override.id,
        event_type="manual_override",
        payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
        source_model=source_model,
    )
    db.add(feedback)
    db.flush()
    return override, feedback


def create_policy_suggestion_draft(
    db: Session,
    *,
    hotel_id: int,
    suggestion_type: str,
    input_summary: str,
    suggested_policy: dict[str, Any],
    explanation: str | None = None,
    source_model: str | None = None,
    profile_id: Optional[int] = None,
) -> LLMPolicySuggestion:
    suggestion = LLMPolicySuggestion(
        hotel_id=hotel_id,
        profile_id=profile_id,
        suggestion_type=suggestion_type,
        status="draft",
        source_model=source_model,
        input_summary=input_summary,
        suggested_policy_json=json.dumps(suggested_policy, ensure_ascii=True, sort_keys=True),
        explanation=explanation,
    )
    db.add(suggestion)
    db.flush()
    return suggestion


def get_policy_suggestion(db: Session, *, hotel_id: int, suggestion_id: int) -> LLMPolicySuggestion:
    suggestion = (
        db.query(LLMPolicySuggestion)
        .filter(
            LLMPolicySuggestion.id == suggestion_id,
            LLMPolicySuggestion.hotel_id == hotel_id,
        )
        .first()
    )
    if not suggestion:
        raise AllocationPolicyError("Policy suggestion not found")
    return suggestion


def review_policy_suggestion(
    db: Session,
    *,
    hotel_id: int,
    suggestion_id: int,
    action: str,
    reviewed_by_user_id: Optional[int] = None,
) -> LLMPolicySuggestion:
    normalized_action = (action or "").strip().lower()
    if normalized_action not in {"review", "reject"}:
        raise AllocationPolicyError("Unsupported suggestion review action")

    suggestion = get_policy_suggestion(db, hotel_id=hotel_id, suggestion_id=suggestion_id)
    resolved_user_id = _resolve_existing_user_id(db, reviewed_by_user_id)
    if normalized_action == "review":
        suggestion.status = LLMPolicySuggestionStatusEnum.REVIEWED
    else:
        suggestion.status = LLMPolicySuggestionStatusEnum.REJECTED
    suggestion.reviewed_by_user_id = resolved_user_id
    suggestion.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return suggestion


def apply_policy_suggestion(
    db: Session,
    *,
    hotel_id: int,
    suggestion_id: int,
    created_by_user_id: Optional[int] = None,
    publish: bool = False,
    prompt_summary: str | None = None,
) -> tuple[LLMPolicySuggestion, AllocationPolicyVersion]:
    suggestion = get_policy_suggestion(db, hotel_id=hotel_id, suggestion_id=suggestion_id)
    if suggestion.status == LLMPolicySuggestionStatusEnum.REJECTED:
        raise AllocationPolicyError("Rejected suggestions cannot be applied")

    resolved_user_id = _resolve_existing_user_id(db, created_by_user_id)
    profile_id = suggestion.profile_id or ensure_default_policy_profile(db, hotel_id).id
    payload = _load_json_dict(suggestion.suggested_policy_json)
    constraints = payload.get("constraints")
    weights = payload.get("weights")
    if not isinstance(constraints, dict) or not isinstance(weights, dict):
        raise AllocationPolicyError("Suggested policy payload is missing constraints or weights")

    version = create_policy_version(
        db,
        hotel_id=hotel_id,
        profile_id=profile_id,
        constraints=constraints,
        weights=weights,
        prompt_summary=prompt_summary or suggestion.input_summary or suggestion.explanation,
        source=f"suggestion:{suggestion.suggestion_type}",
        created_by_user_id=resolved_user_id,
        publish=publish,
    )
    suggestion.status = LLMPolicySuggestionStatusEnum.ACCEPTED
    suggestion.reviewed_by_user_id = resolved_user_id
    suggestion.reviewed_at = datetime.now(timezone.utc)

    accepted_suggestions = (
        db.query(LLMPolicySuggestion)
        .filter(
            LLMPolicySuggestion.hotel_id == hotel_id,
            LLMPolicySuggestion.profile_id == profile_id,
            LLMPolicySuggestion.id != suggestion.id,
            LLMPolicySuggestion.status == LLMPolicySuggestionStatusEnum.ACCEPTED,
        )
        .all()
    )
    for other in accepted_suggestions:
        other.status = LLMPolicySuggestionStatusEnum.SUPERSEDED
        if other.reviewed_at is None:
            other.reviewed_at = datetime.now(timezone.utc)
            other.reviewed_by_user_id = resolved_user_id

    db.flush()
    return suggestion, version


def _load_json_dict(raw_value: str | None) -> dict[str, Any]:
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _resolve_existing_user_id(db: Session, user_id: Optional[int]) -> Optional[int]:
    if user_id is None:
        return None
    exists = db.query(User.id).filter(User.id == user_id).first()
    return user_id if exists else None
