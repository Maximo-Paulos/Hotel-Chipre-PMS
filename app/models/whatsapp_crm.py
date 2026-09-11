"""Tenant-scoped WhatsApp CRM persistence.

The legacy public bot hooks remain separate.  These records represent the
human inbox and provider delivery lifecycle; credentials stay in the existing
encrypted integration connection and are never copied into this model.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, ForeignKeyConstraint, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WhatsAppChannelStatusEnum(str, enum.Enum):
    NOT_ENABLED = "not_enabled"
    READY = "ready"
    IN_META = "in_meta"
    WAITING_VERIFICATION = "waiting_verification"
    WAITING_PAYMENT_METHOD = "waiting_payment_method"
    CONNECTING_WEBHOOKS = "connecting_webhooks"
    TEST_PENDING = "test_pending"
    ACTIVE = "active"
    ATTENTION = "attention"
    PAUSED = "paused"
    DISCONNECTED = "disconnected"


class WhatsAppConversationStatusEnum(str, enum.Enum):
    NEW = "new"
    OPEN = "open"
    ASSIGNED = "assigned"
    PENDING = "pending"
    CLOSED = "closed"


class WhatsAppMessageDirectionEnum(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    INTERNAL = "internal"
    SYSTEM = "system"


class WhatsAppMessageStatusEnum(str, enum.Enum):
    RECEIVED = "received"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class WhatsAppChannel(Base):
    __tablename__ = "whatsapp_channels"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    integration_connection_id = Column(Integer, nullable=True)
    waba_id = Column(String(120), nullable=True)
    phone_number_id = Column(String(120), nullable=True)
    display_phone_number = Column(String(40), nullable=True)
    display_name = Column(String(160), nullable=True)
    status = Column(
        Enum(WhatsAppChannelStatusEnum, name="whatsapp_channel_status_enum", native_enum=False,
             create_constraint=True, values_callable=lambda cls: [item.value for item in cls]),
        nullable=False, default=WhatsAppChannelStatusEnum.NOT_ENABLED,
    )
    onboarding_step = Column(String(60), nullable=True)
    last_error_code = Column(String(80), nullable=True)
    last_error = Column(String(300), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    contacts = relationship("WhatsAppContact", back_populates="channel", cascade="all, delete-orphan", lazy="selectin")
    conversations = relationship("WhatsAppConversation", back_populates="channel", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("hotel_id", name="uq_whatsapp_channels_hotel"),
        UniqueConstraint("hotel_id", "id", name="uq_whatsapp_channels_hotel_id"),
        UniqueConstraint("hotel_id", "phone_number_id", name="uq_whatsapp_channels_hotel_phone"),
        Index("ix_whatsapp_channels_hotel_status", "hotel_id", "status"),
        ForeignKeyConstraint(["hotel_id", "integration_connection_id"], ["integration_connections.hotel_id", "integration_connections.id"], name="fk_whatsapp_channels_hotel_integration", ondelete="SET NULL"),
    )


class WhatsAppProviderRoute(Base):
    """Provider-ID routing index used before a tenant context is known.

    It contains only non-PII Meta identifiers.  The webhook handler resolves
    the hotel through this unique index, sets tenant context, and only then
    reads the channel or conversation tables protected by RLS.
    """
    __tablename__ = "whatsapp_provider_routes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(Integer, nullable=False)
    phone_number_id = Column(String(120), nullable=False, unique=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"], ondelete="CASCADE"),
        Index("ix_whatsapp_provider_routes_hotel", "hotel_id"),
    )


class WhatsAppContact(Base):
    __tablename__ = "whatsapp_contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(Integer, nullable=False)
    normalized_phone = Column(String(40), nullable=False)
    display_name = Column(String(160), nullable=True)
    guest_id = Column(Integer, nullable=True)
    association_confirmed_at = Column(DateTime, nullable=True)
    association_confirmed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    channel = relationship(
        "WhatsAppChannel",
        primaryjoin="and_(WhatsAppContact.channel_id == WhatsAppChannel.id, WhatsAppContact.hotel_id == WhatsAppChannel.hotel_id)",
        foreign_keys=[channel_id], viewonly=True, lazy="joined",
    )
    conversations = relationship("WhatsAppConversation", back_populates="contact", lazy="selectin")

    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"],
                             name="fk_whatsapp_contacts_hotel_channel", ondelete="CASCADE"),
        ForeignKeyConstraint(["hotel_id", "guest_id"], ["guests.hotel_id", "guests.id"],
                             name="fk_whatsapp_contacts_hotel_guest", ondelete="SET NULL"),
        UniqueConstraint("hotel_id", "channel_id", "normalized_phone", name="uq_whatsapp_contacts_phone"),
        UniqueConstraint("hotel_id", "id", name="uq_whatsapp_contacts_hotel_id"),
        Index("ix_whatsapp_contacts_hotel_guest", "hotel_id", "guest_id"),
    )


class WhatsAppConversation(Base):
    __tablename__ = "whatsapp_conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(Integer, nullable=False)
    contact_id = Column(Integer, nullable=False)
    status = Column(
        Enum(WhatsAppConversationStatusEnum, name="whatsapp_conversation_status_enum", native_enum=False,
             create_constraint=True, values_callable=lambda cls: [item.value for item in cls]),
        nullable=False, default=WhatsAppConversationStatusEnum.NEW,
    )
    priority = Column(String(20), nullable=False, default="normal", server_default="normal")
    assigned_to_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    department = Column(String(60), nullable=True)
    shift_key = Column(String(80), nullable=True)
    human_active = Column(Boolean, nullable=False, default=False, server_default="0")
    service_window_expires_at = Column(DateTime, nullable=True)
    last_inbound_at = Column(DateTime, nullable=True)
    last_message_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    channel = relationship("WhatsAppChannel", viewonly=True, lazy="joined")
    contact = relationship("WhatsAppContact", back_populates="conversations", viewonly=True, lazy="joined")
    messages = relationship("WhatsAppMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="WhatsAppMessage.created_at.asc()", lazy="selectin")
    notes = relationship("WhatsAppConversationNote", back_populates="conversation", cascade="all, delete-orphan", order_by="WhatsAppConversationNote.created_at.asc()", lazy="selectin")
    events = relationship("WhatsAppConversationEvent", back_populates="conversation", cascade="all, delete-orphan", order_by="WhatsAppConversationEvent.created_at.asc()", lazy="selectin")

    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "channel_id"], ["whatsapp_channels.hotel_id", "whatsapp_channels.id"],
                             name="fk_whatsapp_conversations_hotel_channel", ondelete="CASCADE"),
        ForeignKeyConstraint(["hotel_id", "contact_id"], ["whatsapp_contacts.hotel_id", "whatsapp_contacts.id"],
                             name="fk_whatsapp_conversations_hotel_contact", ondelete="CASCADE"),
        UniqueConstraint("hotel_id", "id", name="uq_whatsapp_conversations_hotel_id"),
        UniqueConstraint("hotel_id", "channel_id", "contact_id", name="uq_whatsapp_conversations_contact"),
        Index("ix_whatsapp_conversations_inbox", "hotel_id", "status", "assigned_to_user_id", "last_message_at"),
        Index("ix_whatsapp_conversations_shift", "hotel_id", "shift_key", "status"),
    )


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, nullable=False)
    provider_message_id = Column(String(180), nullable=True)
    direction = Column(
        Enum(WhatsAppMessageDirectionEnum, name="whatsapp_message_direction_enum", native_enum=False,
             create_constraint=True, values_callable=lambda cls: [item.value for item in cls]), nullable=False,
    )
    status = Column(
        Enum(WhatsAppMessageStatusEnum, name="whatsapp_message_status_enum", native_enum=False,
             create_constraint=True, values_callable=lambda cls: [item.value for item in cls]),
        nullable=False, default=WhatsAppMessageStatusEnum.RECEIVED,
    )
    message_type = Column(String(40), nullable=False, default="text", server_default="text")
    text = Column(Text, nullable=True)
    media_object_key = Column(String(300), nullable=True)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    error_code = Column(String(80), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    occurred_at = Column(DateTime, nullable=True)

    conversation = relationship("WhatsAppConversation", back_populates="messages", viewonly=True, lazy="joined")

    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "conversation_id"], ["whatsapp_conversations.hotel_id", "whatsapp_conversations.id"],
                             name="fk_whatsapp_messages_hotel_conversation", ondelete="CASCADE"),
        UniqueConstraint("hotel_id", "provider_message_id", name="uq_whatsapp_messages_provider_id"),
        UniqueConstraint("hotel_id", "id", name="uq_whatsapp_messages_hotel_id"),
        Index("ix_whatsapp_messages_conversation_created", "hotel_id", "conversation_id", "created_at"),
    )


class WhatsAppConversationNote(Base):
    __tablename__ = "whatsapp_conversation_notes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, nullable=False)
    author_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    conversation = relationship("WhatsAppConversation", back_populates="notes", viewonly=True, lazy="joined")
    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "conversation_id"], ["whatsapp_conversations.hotel_id", "whatsapp_conversations.id"],
                             name="fk_whatsapp_notes_hotel_conversation", ondelete="CASCADE"),
        Index("ix_whatsapp_notes_conversation", "hotel_id", "conversation_id", "created_at"),
    )


class WhatsAppConversationEvent(Base):
    __tablename__ = "whatsapp_conversation_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(Integer, nullable=False)
    event_type = Column(String(80), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    conversation = relationship("WhatsAppConversation", back_populates="events", viewonly=True, lazy="joined")
    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "conversation_id"], ["whatsapp_conversations.hotel_id", "whatsapp_conversations.id"],
                             name="fk_whatsapp_events_hotel_conversation", ondelete="CASCADE"),
        Index("ix_whatsapp_events_conversation", "hotel_id", "conversation_id", "created_at"),
    )


class WhatsAppOutboundOutbox(Base):
    """Durable provider-delivery queue; a worker owns all external effects."""
    __tablename__ = "whatsapp_outbound_outbox"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    message_id = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="pending", server_default="pending")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at = Column(DateTime, nullable=True)
    last_error_code = Column(String(80), nullable=True)
    last_error = Column(String(300), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    __table_args__ = (
        ForeignKeyConstraint(["hotel_id", "message_id"], ["whatsapp_messages.hotel_id", "whatsapp_messages.id"], name="fk_whatsapp_outbox_hotel_message", ondelete="CASCADE"),
        UniqueConstraint("hotel_id", "message_id", name="uq_whatsapp_outbox_message"),
        Index("ix_whatsapp_outbox_pending", "hotel_id", "status", "next_attempt_at"),
    )
