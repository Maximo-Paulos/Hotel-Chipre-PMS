from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ai_assistant import AIAssistantActionRun, AIAssistantMessage, AIAssistantSession
from app.services.allocation_policy_service import (
    apply_policy_suggestion,
    create_policy_suggestion_draft,
    get_active_policy_settings,
    get_policy_suggestion,
    review_policy_suggestion,
)


class GemmaActionRunError(RuntimeError):
    """Raised when a suggested action cannot be persisted or executed safely."""


def create_action_runs_for_response(
    db: Session,
    *,
    session: AIAssistantSession,
    hotel_id: int,
    user_id: int | None,
    actions: list[dict[str, Any]],
    preview: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    persisted_actions: list[dict[str, Any]] = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_run = AIAssistantActionRun(
            session_id=session.id,
            hotel_id=hotel_id,
            requested_by_user_id=user_id,
            action_type=str(action.get("action_type") or "unknown"),
            status="pending_confirmation",
            payload_json=json.dumps(action.get("payload") or {}, ensure_ascii=True, sort_keys=True),
            preview_json=json.dumps(preview or {}, ensure_ascii=True, sort_keys=True),
        )
        db.add(action_run)
        db.flush()

        persisted = dict(action)
        persisted["action_run_id"] = action_run.id
        persisted["status"] = action_run.status
        persisted_actions.append(persisted)
    return persisted_actions


def get_action_run(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    action_run_id: int,
) -> AIAssistantActionRun:
    action_run = (
        db.query(AIAssistantActionRun)
        .filter(
            AIAssistantActionRun.id == action_run_id,
            AIAssistantActionRun.hotel_id == hotel_id,
            AIAssistantActionRun.session_id == session_id,
        )
        .first()
    )
    if action_run is None:
        raise GemmaActionRunError("Accion de Gemma no encontrada")
    return action_run


def approve_action_run(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    action_run_id: int,
    approved_by_user_id: int | None,
) -> dict[str, Any]:
    action_run = get_action_run(db, hotel_id=hotel_id, session_id=session_id, action_run_id=action_run_id)
    if action_run.status not in {"pending_confirmation", "draft"}:
        raise GemmaActionRunError("La accion ya no esta pendiente de confirmacion")

    payload = _load_json_dict(action_run.payload_json)
    if action_run.action_type != "allocation_policy.update_preview":
        raise GemmaActionRunError("Solo las propuestas de politica de asignacion son ejecutables en esta fase")

    active_policy = get_active_policy_settings(db, hotel_id)
    merged_constraints = dict(active_policy.constraints)
    merged_constraints.update(_load_json_dict(payload.get("constraints")))
    merged_weights = dict(active_policy.weights)
    merged_weights.update(_coerce_numeric_dict(payload.get("weights")))

    suggestion = create_policy_suggestion_draft(
        db,
        hotel_id=hotel_id,
        suggestion_type="gemma_chat_preview",
        input_summary="Borrador creado desde confirmacion explicita de Gemma",
        suggested_policy={
            "constraints": merged_constraints,
            "weights": merged_weights,
            "policy_meta": {
                "source_kind": "gemma_chat_action_run",
                "action_run_id": action_run.id,
            },
        },
        explanation="Borrador generado desde una propuesta confirmada en el asistente Gemma.",
        source_model="gemma_chat_phase2",
        profile_id=active_policy.profile.id,
    )

    action_run.status = "executed"
    action_run.executed_at = datetime.now(timezone.utc)
    action_run.result_json = json.dumps(
        {
            "created_suggestion_id": suggestion.id,
            "profile_id": active_policy.profile.id,
            "next_step": "review_policy_suggestion",
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    if approved_by_user_id is not None:
        action_run.requested_by_user_id = approved_by_user_id
    _append_action_event_message(
        db,
        action_run=action_run,
        text=f"Gemma dejo listo un borrador de politica (sugerencia #{suggestion.id}) para revision.",
        payload={
            "event_type": "action_run_approved",
            "action_run_id": action_run.id,
            "created_suggestion_id": suggestion.id,
            "profile_id": active_policy.profile.id,
        },
    )
    db.flush()
    return {
        "action_run_id": action_run.id,
        "status": action_run.status,
        "created_suggestion_id": suggestion.id,
        "profile_id": active_policy.profile.id,
    }


def reject_action_run(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    action_run_id: int,
) -> dict[str, Any]:
    action_run = get_action_run(db, hotel_id=hotel_id, session_id=session_id, action_run_id=action_run_id)
    if action_run.status not in {"pending_confirmation", "draft"}:
        raise GemmaActionRunError("La accion ya no puede rechazarse")

    action_run.status = "rejected"
    action_run.result_json = json.dumps(
        {
            "next_step": "send_new_request",
        },
        ensure_ascii=True,
        sort_keys=True,
    )
    _append_action_event_message(
        db,
        action_run=action_run,
        text="La propuesta de Gemma fue rechazada y no genero cambios.",
        payload={
            "event_type": "action_run_rejected",
            "action_run_id": action_run.id,
        },
    )
    db.flush()
    return {
        "action_run_id": action_run.id,
        "status": action_run.status,
    }


def review_action_run_draft(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    action_run_id: int,
    reviewed_by_user_id: int | None,
) -> dict[str, Any]:
    action_run = get_action_run(db, hotel_id=hotel_id, session_id=session_id, action_run_id=action_run_id)
    if action_run.status not in {"executed", "reviewed"}:
        raise GemmaActionRunError("La accion no tiene un borrador listo para revisar")

    result_payload = _load_json_dict(action_run.result_json)
    suggestion_id = _get_created_suggestion_id(result_payload)
    suggestion = review_policy_suggestion(
        db,
        hotel_id=hotel_id,
        suggestion_id=suggestion_id,
        action="review",
        reviewed_by_user_id=reviewed_by_user_id,
    )

    action_run.status = "reviewed"
    result_payload["created_suggestion_id"] = suggestion.id
    result_payload["profile_id"] = suggestion.profile_id
    result_payload["suggestion_status"] = _enum_value_or_text(suggestion.status)
    action_run.result_json = json.dumps(result_payload, ensure_ascii=True, sort_keys=True)
    _append_action_event_message(
        db,
        action_run=action_run,
        text=f"El borrador de politica #{suggestion.id} fue marcado como revisado.",
        payload={
            "event_type": "action_run_reviewed",
            "action_run_id": action_run.id,
            "created_suggestion_id": suggestion.id,
            "suggestion_status": _enum_value_or_text(suggestion.status),
        },
    )
    db.flush()
    return {
        "action_run_id": action_run.id,
        "status": action_run.status,
        "created_suggestion_id": suggestion.id,
        "suggestion_status": _enum_value_or_text(suggestion.status),
        "profile_id": suggestion.profile_id,
    }


def apply_action_run_draft(
    db: Session,
    *,
    hotel_id: int,
    session_id: int,
    action_run_id: int,
    approved_by_user_id: int | None,
    publish: bool,
    prompt_summary: str | None,
) -> dict[str, Any]:
    action_run = get_action_run(db, hotel_id=hotel_id, session_id=session_id, action_run_id=action_run_id)
    if action_run.status not in {"executed", "reviewed", "applied"}:
        raise GemmaActionRunError("La accion no tiene un borrador listo para aplicar")

    result_payload = _load_json_dict(action_run.result_json)
    suggestion_id = _get_created_suggestion_id(result_payload)
    suggestion = get_policy_suggestion(db, hotel_id=hotel_id, suggestion_id=suggestion_id)
    if _enum_value_or_text(suggestion.status) == "rejected":
        raise GemmaActionRunError("El borrador fue rechazado y no puede aplicarse")

    suggestion, version = apply_policy_suggestion(
        db,
        hotel_id=hotel_id,
        suggestion_id=suggestion_id,
        created_by_user_id=approved_by_user_id,
        publish=publish,
        prompt_summary=prompt_summary,
    )

    action_run.status = "applied"
    action_run.executed_at = datetime.now(timezone.utc)
    result_payload.update(
        {
            "created_suggestion_id": suggestion.id,
            "profile_id": suggestion.profile_id,
            "suggestion_status": _enum_value_or_text(suggestion.status),
            "created_version_id": version.id,
            "version_number": version.version_number,
            "is_published": bool(version.is_published),
        }
    )
    action_run.result_json = json.dumps(result_payload, ensure_ascii=True, sort_keys=True)
    _append_action_event_message(
        db,
        action_run=action_run,
        text=(
            f"El borrador de Gemma se aplico como version #{version.id} "
            f"(v{version.version_number}) de la politica de asignacion."
        ),
        payload={
            "event_type": "action_run_applied",
            "action_run_id": action_run.id,
            "created_suggestion_id": suggestion.id,
            "created_version_id": version.id,
            "version_number": version.version_number,
            "is_published": bool(version.is_published),
        },
    )
    db.flush()
    return {
        "action_run_id": action_run.id,
        "status": action_run.status,
        "created_suggestion_id": suggestion.id,
        "suggestion_status": _enum_value_or_text(suggestion.status),
        "created_version_id": version.id,
        "version_number": version.version_number,
        "is_published": bool(version.is_published),
        "profile_id": suggestion.profile_id,
    }


def _load_json_dict(raw_value: Any) -> dict[str, Any]:
    if isinstance(raw_value, dict):
        return raw_value
    if not raw_value:
        return {}
    try:
        loaded = json.loads(raw_value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _coerce_numeric_dict(value: Any) -> dict[str, float]:
    raw = _load_json_dict(value)
    result: dict[str, float] = {}
    for key, item in raw.items():
        try:
            result[str(key)] = float(item)
        except (TypeError, ValueError):
            continue
    return result


def _get_created_suggestion_id(payload: dict[str, Any]) -> int:
    suggestion_id = payload.get("created_suggestion_id")
    if not isinstance(suggestion_id, int) or suggestion_id <= 0:
        raise GemmaActionRunError("La accion no tiene un borrador asociado")
    return suggestion_id


def _enum_value_or_text(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _append_action_event_message(
    db: Session,
    *,
    action_run: AIAssistantActionRun,
    text: str,
    payload: dict[str, Any],
) -> None:
    message = AIAssistantMessage(
        session_id=action_run.session_id,
        hotel_id=action_run.hotel_id,
        role="system",
        raw_text=text,
        redacted_text=text,
        intent_type="action_run_event",
        payload_json=json.dumps(payload, ensure_ascii=True, sort_keys=True),
    )
    db.add(message)
