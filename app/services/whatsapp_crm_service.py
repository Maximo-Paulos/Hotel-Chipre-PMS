"""Human WhatsApp CRM domain services.

Provider transport is deliberately outside this module.  Meta adapters may
call these functions after verifying a webhook, while authenticated inbox
routes use the same tenant and idempotency boundaries.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.whatsapp_crm import (
    WhatsAppChannel,
    WhatsAppChannelStatusEnum,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppConversationEvent,
    WhatsAppConversationNote,
    WhatsAppConversationStatusEnum,
    WhatsAppMessage,
    WhatsAppMessageDirectionEnum,
    WhatsAppMessageStatusEnum,
    WhatsAppOutboundOutbox,
    WhatsAppProviderRoute,
)


class WhatsAppCRMError(ValueError):
    pass


@dataclass(frozen=True)
class InboundMessageResult:
    conversation: WhatsAppConversation
    message: WhatsAppMessage
    created: bool


def normalize_phone(value: str) -> str:
    normalized = re.sub(r"\D", "", str(value or ""))
    if not normalized or len(normalized) < 7 or len(normalized) > 20:
        raise WhatsAppCRMError("El teléfono de WhatsApp no es válido")
    return normalized


def complete_embedded_signup(
    db: Session,
    *,
    hotel_id: int,
    waba_id: str,
    phone_number_id: str,
    display_phone_number: str | None = None,
    display_name: str | None = None,
    integration_connection_id: int | None = None,
) -> WhatsAppChannel:
    """Persist only the metadata returned after a server-side Meta exchange."""
    if not waba_id.strip() or not phone_number_id.strip():
        raise WhatsAppCRMError("Meta no devolvió la cuenta o el número de WhatsApp")
    if integration_connection_id is not None:
        from app.models.integration import IntegrationConnection
        connection = db.query(IntegrationConnection).filter(
            IntegrationConnection.id == integration_connection_id,
            IntegrationConnection.hotel_id == hotel_id,
        ).one_or_none()
        if connection is None:
            raise WhatsAppCRMError("La conexión de Meta no pertenece a este hotel")
    channel = db.query(WhatsAppChannel).filter(WhatsAppChannel.hotel_id == hotel_id).one_or_none()
    if channel is None:
        channel = WhatsAppChannel(hotel_id=hotel_id)
        db.add(channel)
        db.flush()
    duplicate = db.query(WhatsAppProviderRoute).filter(
        WhatsAppProviderRoute.phone_number_id == phone_number_id,
        WhatsAppProviderRoute.channel_id != channel.id,
    ).one_or_none()
    if duplicate is not None:
        raise WhatsAppCRMError("El número de WhatsApp ya está conectado a otro hotel")
    channel.waba_id = waba_id.strip()
    channel.phone_number_id = phone_number_id.strip()
    channel.display_phone_number = display_phone_number.strip() if display_phone_number else None
    channel.display_name = display_name.strip() if display_name else None
    channel.integration_connection_id = integration_connection_id
    channel.status = WhatsAppChannelStatusEnum.TEST_PENDING
    channel.onboarding_step = "test"
    route = db.query(WhatsAppProviderRoute).filter(WhatsAppProviderRoute.channel_id == channel.id).one_or_none()
    if route is None:
        db.add(WhatsAppProviderRoute(hotel_id=hotel_id, channel_id=channel.id, phone_number_id=phone_number_id.strip()))
    else:
        route.hotel_id = hotel_id
        route.phone_number_id = phone_number_id.strip()
    db.flush()
    return channel


def _channel(db: Session, hotel_id: int, channel_id: int) -> WhatsAppChannel:
    channel = db.query(WhatsAppChannel).filter(WhatsAppChannel.hotel_id == hotel_id, WhatsAppChannel.id == channel_id).one_or_none()
    if channel is None:
        raise WhatsAppCRMError("Canal de WhatsApp no encontrado")
    return channel


def _conversation(db: Session, hotel_id: int, conversation_id: int) -> WhatsAppConversation:
    conversation = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.hotel_id == hotel_id, WhatsAppConversation.id == conversation_id,
    ).one_or_none()
    if conversation is None:
        raise WhatsAppCRMError("Conversación no encontrada")
    return conversation


def _event(db: Session, *, hotel_id: int, conversation_id: int, event_type: str, actor_user_id: int | None = None, payload: dict | None = None) -> None:
    db.add(WhatsAppConversationEvent(
        hotel_id=hotel_id,
        conversation_id=conversation_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload_json=json.dumps(payload or {}, sort_keys=True),
    ))


def ingest_inbound_message(
    db: Session,
    *,
    hotel_id: int,
    channel_id: int,
    from_phone: str,
    provider_message_id: str,
    text: str | None = None,
    message_type: str = "text",
    occurred_at: datetime | None = None,
    display_name: str | None = None,
) -> InboundMessageResult:
    """Create-or-return one inbound message, conversation and contact.

    The provider message ID is the idempotency key.  A retry never creates a
    second message or conversation, and all lookups are constrained by hotel.
    """
    if not provider_message_id or len(provider_message_id) > 180:
        raise WhatsAppCRMError("Falta el identificador del mensaje de Meta")
    channel = _channel(db, hotel_id, channel_id)
    existing = db.query(WhatsAppMessage).filter(
        WhatsAppMessage.hotel_id == hotel_id,
        WhatsAppMessage.provider_message_id == provider_message_id,
    ).one_or_none()
    if existing is not None:
        conversation = _conversation(db, hotel_id, existing.conversation_id)
        return InboundMessageResult(conversation=conversation, message=existing, created=False)

    normalized_phone = normalize_phone(from_phone)
    contact = db.query(WhatsAppContact).filter(
        WhatsAppContact.hotel_id == hotel_id,
        WhatsAppContact.channel_id == channel.id,
        WhatsAppContact.normalized_phone == normalized_phone,
    ).one_or_none()
    if contact is None:
        contact = WhatsAppContact(
            hotel_id=hotel_id, channel_id=channel.id,
            normalized_phone=normalized_phone, display_name=(display_name or None),
        )
        db.add(contact)
        db.flush()
    elif display_name and not contact.display_name:
        contact.display_name = display_name

    conversation = db.query(WhatsAppConversation).filter(
        WhatsAppConversation.hotel_id == hotel_id,
        WhatsAppConversation.channel_id == channel.id,
        WhatsAppConversation.contact_id == contact.id,
    ).one_or_none()
    now = occurred_at or datetime.now(timezone.utc)
    if conversation is None:
        conversation = WhatsAppConversation(
            hotel_id=hotel_id, channel_id=channel.id, contact_id=contact.id,
            status=WhatsAppConversationStatusEnum.NEW,
        )
        db.add(conversation)
        db.flush()
        _event(db, hotel_id=hotel_id, conversation_id=conversation.id, event_type="conversation.created")
    else:
        if conversation.status == WhatsAppConversationStatusEnum.CLOSED:
            conversation.status = WhatsAppConversationStatusEnum.OPEN

    message = WhatsAppMessage(
        hotel_id=hotel_id,
        conversation_id=conversation.id,
        provider_message_id=provider_message_id,
        direction=WhatsAppMessageDirectionEnum.INBOUND,
        status=WhatsAppMessageStatusEnum.RECEIVED,
        message_type=message_type,
        text=text,
        occurred_at=now,
    )
    db.add(message)
    conversation.last_inbound_at = now
    conversation.last_message_at = now
    conversation.updated_at = now
    db.flush()
    _event(db, hotel_id=hotel_id, conversation_id=conversation.id, event_type="message.received")
    # Notification payload contains identifiers only; the durable notification
    # service applies the recipient's WhatsApp permission and preferences.
    from app.models.notification import NotificationChannelEnum, NotificationSeverityEnum
    from app.services.notification_service import enqueue_notifications_for_event
    from app.services.permission_service import ROLE_CODES
    enqueue_notifications_for_event(
        db,
        hotel_id=hotel_id,
        event_type="whatsapp.message.received",
        dedupe_key=f"whatsapp:message:{provider_message_id}",
        title="Nuevo mensaje de WhatsApp",
        severity=NotificationSeverityEnum.INFO,
        entity_type="whatsapp_conversation",
        entity_id=conversation.id,
        payload={"conversation_id": conversation.id, "source": "whatsapp"},
        recipient_roles=ROLE_CODES,
        channels=(NotificationChannelEnum.IN_APP, NotificationChannelEnum.PUSH),
    )
    return InboundMessageResult(conversation=conversation, message=message, created=True)


def add_outbound_message(
    db: Session,
    *,
    hotel_id: int,
    conversation_id: int,
    text: str,
    actor_user_id: int,
    provider_message_id: str | None = None,
    status: WhatsAppMessageStatusEnum = WhatsAppMessageStatusEnum.QUEUED,
    message_type: str = "text",
) -> WhatsAppMessage:
    if not str(text or "").strip():
        raise WhatsAppCRMError("El mensaje no puede estar vacío")
    conversation = _conversation(db, hotel_id, conversation_id)
    now = datetime.now(timezone.utc)
    message = WhatsAppMessage(
        hotel_id=hotel_id, conversation_id=conversation.id,
        provider_message_id=provider_message_id,
        direction=WhatsAppMessageDirectionEnum.OUTBOUND,
        status=status, message_type=message_type, text=text.strip(), actor_user_id=actor_user_id,
        occurred_at=now,
    )
    db.add(message)
    conversation.human_active = True
    conversation.status = WhatsAppConversationStatusEnum.ASSIGNED if conversation.assigned_to_user_id else WhatsAppConversationStatusEnum.OPEN
    conversation.last_message_at = now
    conversation.updated_at = now
    db.flush()
    db.add(WhatsAppOutboundOutbox(hotel_id=hotel_id, message_id=message.id))
    db.flush()
    _event(db, hotel_id=hotel_id, conversation_id=conversation.id, event_type="message.queued", actor_user_id=actor_user_id)
    return message


def assign_conversation(db: Session, *, hotel_id: int, conversation_id: int, assigned_to_user_id: int | None, actor_user_id: int | None = None) -> WhatsAppConversation:
    conversation = _conversation(db, hotel_id, conversation_id)
    if assigned_to_user_id is not None:
        from app.models.hotel_membership import HotelMembership
        active = db.query(HotelMembership).filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.user_id == assigned_to_user_id,
            HotelMembership.status == "active",
        ).one_or_none()
        if active is None:
            raise WhatsAppCRMError("El usuario no pertenece activamente a este hotel")
    conversation.assigned_to_user_id = assigned_to_user_id
    conversation.status = WhatsAppConversationStatusEnum.ASSIGNED if assigned_to_user_id else WhatsAppConversationStatusEnum.OPEN
    _event(db, hotel_id=hotel_id, conversation_id=conversation.id, event_type="conversation.assigned", actor_user_id=actor_user_id, payload={"assigned_to_user_id": assigned_to_user_id})
    db.flush()
    return conversation


def add_internal_note(db: Session, *, hotel_id: int, conversation_id: int, author_user_id: int, body: str) -> WhatsAppConversationNote:
    conversation = _conversation(db, hotel_id, conversation_id)
    normalized = str(body or "").strip()
    if not normalized or len(normalized) > 4000:
        raise WhatsAppCRMError("La nota debe tener entre 1 y 4000 caracteres")
    note = WhatsAppConversationNote(hotel_id=hotel_id, conversation_id=conversation.id, author_user_id=author_user_id, body=normalized)
    db.add(note)
    _event(db, hotel_id=hotel_id, conversation_id=conversation.id, event_type="note.created", actor_user_id=author_user_id)
    db.flush()
    return note


def list_conversations(db: Session, *, hotel_id: int, status: WhatsAppConversationStatusEnum | None = None, assigned_to_user_id: int | None = None, limit: int = 50, offset: int = 0) -> list[WhatsAppConversation]:
    query = db.query(WhatsAppConversation).filter(WhatsAppConversation.hotel_id == hotel_id)
    if status is not None:
        query = query.filter(WhatsAppConversation.status == status)
    if assigned_to_user_id is not None:
        query = query.filter(WhatsAppConversation.assigned_to_user_id == assigned_to_user_id)
    return query.order_by(WhatsAppConversation.last_message_at.desc().nullslast(), WhatsAppConversation.id.desc()).offset(offset).limit(limit).all()
