from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.gemma_chat import (
    GemmaActionApplyDraftRequest,
    GemmaActionApplyDraftResponse,
    GemmaActionApproveRequest,
    GemmaActionApproveResponse,
    GemmaActionRejectRequest,
    GemmaActionRejectResponse,
    GemmaActionReviewDraftRequest,
    GemmaActionReviewDraftResponse,
    GemmaChatEnvelopeRead,
    GemmaChatMessageRead,
    GemmaChatMessageRequest,
    GemmaInsightRead,
    GemmaRuntimeStatusRead,
    GemmaChatSessionSummaryRead,
)
from app.services.gemma_action_run_service import (
    GemmaActionRunError,
    apply_action_run_draft,
    approve_action_run,
    reject_action_run,
    review_action_run_draft,
)
from app.services.gemma_orchestrator import GemmaChatError, GemmaOrchestrator


router = APIRouter(prefix="/api/gemma/chat", tags=["Gemma Chat"])


def _get_orchestrator() -> GemmaOrchestrator:
    return GemmaOrchestrator()


@router.get("/history", response_model=list[GemmaChatSessionSummaryRead])
def get_chat_history(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    sessions = orchestrator.list_sessions(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        limit=limit,
    )
    return [_serialize_session_summary(item) for item in sessions]


@router.get("/insights", response_model=list[GemmaInsightRead])
def get_chat_insights(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    insights = orchestrator.list_insights(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        limit=limit,
    )
    return [_serialize_insight(item) for item in insights]


@router.post("/session/{session_id}/archive", response_model=GemmaChatSessionSummaryRead)
def archive_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    try:
        session = orchestrator.archive_session(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            session_id=session_id,
        )
        db.commit()
    except GemmaChatError as exc:
        db.rollback()
        raise HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))
    return _serialize_session_summary(session)


@router.get("/runtime-status", response_model=GemmaRuntimeStatusRead)
def get_runtime_status(
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    _ = context
    return GemmaRuntimeStatusRead(**orchestrator.get_runtime_status())


@router.get("/session/{session_id}", response_model=GemmaChatEnvelopeRead)
def get_chat_session(
    session_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    try:
        session = orchestrator.get_session(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            session_id=session_id,
        )
    except GemmaChatError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return _serialize_session_envelope(session)


@router.post("/message", response_model=GemmaChatEnvelopeRead, status_code=status.HTTP_201_CREATED)
def send_chat_message(
    payload: GemmaChatMessageRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
    orchestrator: GemmaOrchestrator = Depends(_get_orchestrator),
):
    try:
        result = orchestrator.send_message(
            db,
            hotel_id=context.hotel_id,
            user_id=context.user_id,
            user_role=context.user_role,
            message=payload.message,
            session_id=payload.session_id,
        )
        db.commit()
    except GemmaChatError as exc:
        db.rollback()
        raise HTTPException(status_code=getattr(exc, "status_code", 400), detail=str(exc))
    except Exception:
        db.rollback()
        raise
    return GemmaChatEnvelopeRead(
        session=_serialize_session_summary(result.session),
        messages=[_serialize_message(item) for item in result.session.messages],
        answer=result.assistant_message.raw_text,
        mode=str(result.response_payload.get("mode") or "analysis"),
        intent_type=result.assistant_message.intent_type,
        summary=result.response_payload.get("summary"),
        requires_confirmation=bool(result.response_payload.get("requires_confirmation") or False),
        actions=_serialize_actions(result.response_payload.get("actions"), result.session),
        preview=result.response_payload.get("preview"),
        warnings=list(result.response_payload.get("warnings") or []),
        missing_information=list(result.response_payload.get("missing_information") or []),
        confidence=result.response_payload.get("confidence"),
        metadata=dict(result.response_payload.get("metadata") or {}),
    )


@router.post("/actions/{action_run_id}/approve", response_model=GemmaActionApproveResponse)
def approve_chat_action(
    action_run_id: int,
    payload: GemmaActionApproveRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        result = approve_action_run(
            db,
            hotel_id=context.hotel_id,
            session_id=payload.session_id,
            action_run_id=action_run_id,
            approved_by_user_id=context.user_id,
        )
        db.commit()
    except GemmaActionRunError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise
    return GemmaActionApproveResponse(**result)


@router.post("/actions/{action_run_id}/reject", response_model=GemmaActionRejectResponse)
def reject_chat_action(
    action_run_id: int,
    payload: GemmaActionRejectRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        result = reject_action_run(
            db,
            hotel_id=context.hotel_id,
            session_id=payload.session_id,
            action_run_id=action_run_id,
        )
        db.commit()
    except GemmaActionRunError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise
    return GemmaActionRejectResponse(**result)


@router.post("/actions/{action_run_id}/review-draft", response_model=GemmaActionReviewDraftResponse)
def review_chat_action_draft(
    action_run_id: int,
    payload: GemmaActionReviewDraftRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        result = review_action_run_draft(
            db,
            hotel_id=context.hotel_id,
            session_id=payload.session_id,
            action_run_id=action_run_id,
            reviewed_by_user_id=context.user_id,
        )
        db.commit()
    except GemmaActionRunError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise
    return GemmaActionReviewDraftResponse(**result)


@router.post("/actions/{action_run_id}/apply-draft", response_model=GemmaActionApplyDraftResponse)
def apply_chat_action_draft(
    action_run_id: int,
    payload: GemmaActionApplyDraftRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        result = apply_action_run_draft(
            db,
            hotel_id=context.hotel_id,
            session_id=payload.session_id,
            action_run_id=action_run_id,
            approved_by_user_id=context.user_id,
            publish=payload.publish,
            prompt_summary=payload.prompt_summary,
        )
        db.commit()
    except GemmaActionRunError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        db.rollback()
        raise
    return GemmaActionApplyDraftResponse(**result)


def _serialize_session_summary(session) -> GemmaChatSessionSummaryRead:
    last_message_preview = None
    if session.messages:
        last_message_preview = session.messages[-1].raw_text[:180]
    return GemmaChatSessionSummaryRead(
        id=session.id,
        mode=session.mode,
        status=session.status,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        last_message_preview=last_message_preview,
        message_count=len(session.messages),
    )


def _serialize_message(message) -> GemmaChatMessageRead:
    return GemmaChatMessageRead(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        text=message.raw_text,
        intent_type=message.intent_type,
        created_at=message.created_at,
    )


def _serialize_session_envelope(session) -> GemmaChatEnvelopeRead:
    last_assistant = next((item for item in reversed(session.messages) if item.role == "assistant"), None)
    payload = _load_payload(last_assistant.payload_json if last_assistant else None)
    actions = _serialize_actions(payload.get("actions"), session)
    return GemmaChatEnvelopeRead(
        session=_serialize_session_summary(session),
        messages=[_serialize_message(item) for item in session.messages],
        answer=last_assistant.raw_text if last_assistant else None,
        mode=str(payload.get("mode") or "analysis"),
        intent_type=last_assistant.intent_type if last_assistant else None,
        summary=payload.get("summary"),
        requires_confirmation=bool(payload.get("requires_confirmation") or False),
        actions=actions,
        preview=payload.get("preview"),
        warnings=list(payload.get("warnings") or []),
        missing_information=list(payload.get("missing_information") or []),
        confidence=payload.get("confidence"),
        metadata=dict(payload.get("metadata") or {}),
    )


def _load_payload(raw_value: str | None) -> dict:
    if not raw_value:
        return {}
    try:
        payload = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _serialize_actions(raw_actions, session) -> list[dict]:
    if not isinstance(raw_actions, list):
        return []
    action_runs = {item.id: item for item in getattr(session, "action_runs", [])}
    serialized: list[dict] = []
    for item in raw_actions:
        if not isinstance(item, dict):
            continue
        serialized_item = dict(item)
        action_run_id = serialized_item.get("action_run_id")
        action_run = action_runs.get(action_run_id) if isinstance(action_run_id, int) else None
        if action_run is not None:
            serialized_item["status"] = action_run.status
            result_payload = _load_payload(action_run.result_json)
            if result_payload:
                serialized_item["result"] = result_payload
        serialized.append(serialized_item)
    return serialized


def _serialize_insight(insight) -> GemmaInsightRead:
    return GemmaInsightRead(
        id=insight.id,
        session_id=insight.session_id,
        insight_type=insight.insight_type,
        summary=insight.summary,
        details=_load_payload(insight.details_json),
        created_at=insight.created_at,
    )
