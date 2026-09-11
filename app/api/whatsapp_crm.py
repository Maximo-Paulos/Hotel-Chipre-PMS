"""Authenticated human WhatsApp CRM inbox.

This router never calls Meta directly.  Outbound messages are queued in the
tenant-scoped database for a provider worker; the legacy public bot router is
intentionally left untouched.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_permission
from app.models.whatsapp_crm import WhatsAppChannel, WhatsAppConversationStatusEnum
from app.schemas.whatsapp_crm import (
    WhatsAppAssignmentUpdate,
    WhatsAppChannelComplete,
    WhatsAppConversationListResponse,
    WhatsAppConversationRead,
    WhatsAppConversationStatusUpdate,
    WhatsAppMessageCreate,
    WhatsAppMessageRead,
    WhatsAppNoteCreate,
)
from app.services.permission_service import (
    PERMISSION_WHATSAPP_ASSIGN,
    PERMISSION_WHATSAPP_CLOSE,
    PERMISSION_WHATSAPP_INBOX_ALL,
    PERMISSION_WHATSAPP_INBOX_VIEW,
    PERMISSION_WHATSAPP_MESSAGE_SEND,
    PERMISSION_WHATSAPP_NOTE_MANAGE,
    PERMISSION_WHATSAPP_SETTINGS_MANAGE,
)
from app.services.subscription_entitlements import get_subscription_snapshot, plan_has_feature
from app.services.whatsapp_crm_service import (
    WhatsAppCRMError,
    add_internal_note,
    add_outbound_message,
    assign_conversation,
    complete_embedded_signup,
    list_conversations,
)


router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp CRM"])


def _require_plan(db: Session, hotel_id: int) -> None:
    snapshot = get_subscription_snapshot(db, hotel_id)
    if not plan_has_feature(snapshot, "whatsapp.crm"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="WhatsApp CRM requiere un plan Pro o Ultra")


@router.get("/channel")
def channel_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    _require_plan(db, context.hotel_id)
    channel = db.query(WhatsAppChannel).filter(WhatsAppChannel.hotel_id == context.hotel_id).one_or_none()
    if channel is None:
        return {"status": "ready", "channel": None}
    return {"status": channel.status, "channel": channel}


@router.post("/channel/complete", status_code=status.HTTP_201_CREATED)
def complete_channel(
    payload: WhatsAppChannelComplete,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_SETTINGS_MANAGE)),
):
    """Store metadata after the backend completes Embedded Signup.

    No bearer token or provider secret is accepted here; those remain in the
    server-side Meta adapter and encrypted integration connection.
    """
    _require_plan(db, context.hotel_id)
    try:
        channel = complete_embedded_signup(
            db, hotel_id=context.hotel_id, waba_id=payload.waba_id,
            phone_number_id=payload.phone_number_id,
            display_phone_number=payload.display_phone_number,
            display_name=payload.display_name,
            integration_connection_id=payload.integration_connection_id,
        )
        db.commit()
        db.refresh(channel)
        return channel
    except WhatsAppCRMError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/conversations", response_model=WhatsAppConversationListResponse)
def inbox(
    conversation_status: WhatsAppConversationStatusEnum | None = Query(default=None, alias="status"),
    assigned_to_user_id: int | None = Query(default=None),
    all_conversations: bool = Query(default=False, alias="all"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_INBOX_VIEW)),
):
    _require_plan(db, context.hotel_id)
    from app.services.permission_service import resolve
    can_read_all = resolve(db, context.hotel_id, context.user_role, PERMISSION_WHATSAPP_INBOX_ALL, user_id=context.user_id)
    if (all_conversations or assigned_to_user_id is None) and not can_read_all:
        assigned_to_user_id = context.user_id
    rows = list_conversations(
        db, hotel_id=context.hotel_id, status=conversation_status,
        assigned_to_user_id=assigned_to_user_id, limit=limit, offset=offset,
    )
    return WhatsAppConversationListResponse(items=rows)


@router.post("/conversations/{conversation_id}/messages", response_model=WhatsAppMessageRead, status_code=status.HTTP_201_CREATED)
def send_message(
    conversation_id: int,
    payload: WhatsAppMessageCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_MESSAGE_SEND)),
):
    _require_plan(db, context.hotel_id)
    try:
        message = add_outbound_message(
            db, hotel_id=context.hotel_id, conversation_id=conversation_id,
            text=payload.text, message_type=payload.message_type, actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(message)
        return message
    except WhatsAppCRMError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/notes", status_code=status.HTTP_201_CREATED)
def create_note(
    conversation_id: int,
    payload: WhatsAppNoteCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_NOTE_MANAGE)),
):
    _require_plan(db, context.hotel_id)
    try:
        note = add_internal_note(db, hotel_id=context.hotel_id, conversation_id=conversation_id, author_user_id=context.user_id, body=payload.body)
        db.commit()
        db.refresh(note)
        return {"id": note.id, "conversation_id": note.conversation_id, "body": note.body, "author_user_id": note.author_user_id, "created_at": note.created_at}
    except WhatsAppCRMError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/assignment")
def update_assignment(
    conversation_id: int,
    payload: WhatsAppAssignmentUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_ASSIGN)),
):
    _require_plan(db, context.hotel_id)
    try:
        conversation = assign_conversation(
            db, hotel_id=context.hotel_id, conversation_id=conversation_id,
            assigned_to_user_id=payload.assigned_to_user_id, actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(conversation)
        return conversation
    except WhatsAppCRMError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/conversations/{conversation_id}/status", response_model=WhatsAppConversationRead)
def update_status(
    conversation_id: int,
    payload: WhatsAppConversationStatusUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_WHATSAPP_CLOSE)),
):
    _require_plan(db, context.hotel_id)
    try:
        from app.services.whatsapp_crm_service import _conversation, _event
        conversation = _conversation(db, context.hotel_id, conversation_id)
        conversation.status = payload.status
        conversation.human_active = payload.status != WhatsAppConversationStatusEnum.CLOSED
        _event(db, hotel_id=context.hotel_id, conversation_id=conversation.id, event_type="conversation.status_changed", actor_user_id=context.user_id, payload={"status": payload.status.value})
        db.commit()
        db.refresh(conversation)
        return conversation
    except WhatsAppCRMError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
