from datetime import datetime, timezone

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.models.whatsapp_crm import (
    WhatsAppChannel,
    WhatsAppChannelStatusEnum,
    WhatsAppConversationStatusEnum,
    WhatsAppMessageDirectionEnum,
    WhatsAppOutboundOutbox,
)
from app.services.whatsapp_crm_service import (
    WhatsAppCRMError,
    add_internal_note,
    assign_conversation,
    ingest_inbound_message,
    list_conversations,
    add_outbound_message,
    complete_embedded_signup,
)
from app.services.subscription_entitlements import plan_has_feature


def _hotel_and_user(db, hotel_id=1, role="manager"):
    hotel = HotelConfiguration(id=hotel_id, subscription_active=True)
    user = User(email=f"wa-{hotel_id}@example.test", password_hash="test", is_verified=True, is_active=True)
    db.add_all([hotel, user])
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user.id, role=role, status="active"))
    db.flush()
    return hotel, user


def test_inbound_message_is_idempotent_and_keeps_tenant_scope(db):
    _hotel_and_user(db, 1)
    _hotel_and_user(db, 2)
    channel = WhatsAppChannel(
        hotel_id=1,
        display_name="Hotel 1",
        phone_number_id="phone-1",
        status=WhatsAppChannelStatusEnum.ACTIVE,
    )
    db.add(channel)
    db.flush()

    first = ingest_inbound_message(
        db,
        hotel_id=1,
        channel_id=channel.id,
        from_phone="+54 (9) 11 5555-0000",
        provider_message_id="wamid-1",
        text="Hola, ¿hay disponibilidad?",
        occurred_at=datetime.now(timezone.utc),
    )
    duplicate = ingest_inbound_message(
        db,
        hotel_id=1,
        channel_id=channel.id,
        from_phone="5491155550000",
        provider_message_id="wamid-1",
        text="Hola, ¿hay disponibilidad?",
    )
    assert first.message.id == duplicate.message.id
    assert duplicate.created is False
    assert first.conversation.contact.normalized_phone == "5491155550000"
    assert len(first.conversation.messages) == 1


def test_assign_and_note_are_auditable_and_cross_tenant_safe(db):
    _hotel_and_user(db, 1)
    _, user_two = _hotel_and_user(db, 2)
    channel = WhatsAppChannel(hotel_id=1, phone_number_id="phone-1", status=WhatsAppChannelStatusEnum.ACTIVE)
    db.add(channel)
    db.flush()
    result = ingest_inbound_message(
        db, hotel_id=1, channel_id=channel.id, from_phone="5491111111111", provider_message_id="wamid-2", text="Hola"
    )
    with pytest.raises(WhatsAppCRMError):
        assign_conversation(db, hotel_id=1, conversation_id=result.conversation.id, assigned_to_user_id=user_two.id)
    with pytest.raises(WhatsAppCRMError):
        add_internal_note(db, hotel_id=2, conversation_id=result.conversation.id, author_user_id=user_two.id, body="No cruzar")


def test_list_conversations_filters_by_hotel_and_status(db):
    _hotel_and_user(db, 1)
    channel = WhatsAppChannel(hotel_id=1, phone_number_id="phone-1", status=WhatsAppChannelStatusEnum.ACTIVE)
    db.add(channel)
    db.flush()
    ingest_inbound_message(db, hotel_id=1, channel_id=channel.id, from_phone="5491111111111", provider_message_id="wamid-3", text="A")
    assert [row.hotel_id for row in list_conversations(db, hotel_id=1, status=WhatsAppConversationStatusEnum.NEW)] == [1]
    assert list_conversations(db, hotel_id=2) == []


def test_whatsapp_feature_is_only_pro_or_ultra():
    assert plan_has_feature({"plan": "starter"}, "whatsapp.crm") is False
    assert plan_has_feature({"plan": "pro"}, "whatsapp.crm") is True
    assert plan_has_feature({"plan": "ultra"}, "whatsapp.crm") is True


def test_outbound_message_is_queued_in_durable_outbox(db):
    _hotel_and_user(db, 1)
    channel = WhatsAppChannel(hotel_id=1, phone_number_id="phone-1", status=WhatsAppChannelStatusEnum.ACTIVE)
    db.add(channel)
    db.flush()
    inbound = ingest_inbound_message(db, hotel_id=1, channel_id=channel.id, from_phone="5491111111111", provider_message_id="wamid-outbox", text="Hola")
    outbound = add_outbound_message(db, hotel_id=1, conversation_id=inbound.conversation.id, text="Te ayudamos", actor_user_id=1)
    row = db.query(WhatsAppOutboundOutbox).filter(WhatsAppOutboundOutbox.message_id == outbound.id).one()
    assert row.status == "pending"


def test_provider_route_is_unique_and_resolves_to_its_hotel(db):
    _hotel_and_user(db, 1)
    _hotel_and_user(db, 2)
    complete_embedded_signup(db, hotel_id=1, waba_id="waba-1", phone_number_id="phone-route")
    with pytest.raises(WhatsAppCRMError):
        complete_embedded_signup(db, hotel_id=2, waba_id="waba-2", phone_number_id="phone-route")
