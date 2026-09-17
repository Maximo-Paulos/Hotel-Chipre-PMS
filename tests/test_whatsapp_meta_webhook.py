"""HTTP boundary tests for the Meta Cloud API WhatsApp webhook.

The endpoint had no coverage: it verifies Meta's HMAC before parsing, and one
unusable message inside a delivery must not discard the rest of the batch.
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - registers every model on Base.metadata
from app.config import get_settings
from app.database import Base, get_db
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.whatsapp_crm import (
    WhatsAppChannel,
    WhatsAppChannelStatusEnum,
    WhatsAppMessage,
    WhatsAppProviderRoute,
)

APP_SECRET = "meta-app-secret-for-tests"
PHONE_NUMBER_ID = "111222333"


def _signature(body: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()


def _post(client: TestClient, payload: dict, *, signature: str | None = None):
    body = json.dumps(payload).encode()
    return client.post(
        "/api/webhooks/meta/whatsapp",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": signature if signature is not None else _signature(body),
        },
    )


def _message(message_id: str, sender: str, text: str) -> dict:
    return {"id": message_id, "from": sender, "type": "text", "text": {"body": text}}


def _delivery(messages: list[dict], contacts: list[dict] | None = None) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                            "contacts": contacts or [],
                            "messages": messages,
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def webhook_client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "true")
    get_settings.cache_clear()
    patched_settings = get_settings().model_copy(update={"META_WHATSAPP_APP_SECRET": APP_SECRET})
    monkeypatch.setattr("app.api.whatsapp_meta_webhook.get_settings", lambda: patched_settings)

    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.flush()
    channel = WhatsAppChannel(
        hotel_id=1,
        phone_number_id=PHONE_NUMBER_ID,
        status=WhatsAppChannelStatusEnum.ACTIVE,
    )
    db.add(channel)
    db.flush()
    db.add(
        WhatsAppProviderRoute(hotel_id=1, channel_id=channel.id, phone_number_id=PHONE_NUMBER_ID)
    )
    db.commit()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    try:
        yield client, db
    finally:
        fastapi_app.dependency_overrides.clear()
        get_settings.cache_clear()
        db.close()
        engine.dispose()


def test_rejects_a_delivery_whose_signature_does_not_match(webhook_client):
    client, db = webhook_client

    response = _post(client, _delivery([_message("wamid.1", "5491122334455", "hola")]), signature="sha256=deadbeef")

    assert response.status_code == 401
    assert db.query(WhatsAppMessage).count() == 0


def test_ingests_a_signed_inbound_message(webhook_client):
    client, db = webhook_client

    response = _post(
        client,
        _delivery(
            [_message("wamid.1", "5491122334455", "hola")],
            contacts=[{"wa_id": "5491122334455", "profile": {"name": "Ana"}}],
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "processed": 1, "skipped": 0}
    stored = db.query(WhatsAppMessage).one()
    assert stored.provider_message_id == "wamid.1"
    assert stored.text == "hola"


def test_one_unusable_message_does_not_discard_the_rest_of_the_batch(webhook_client):
    """Regression: a bad phone used to raise 400 and roll the whole batch back.

    Meta then replays the identical batch, so the good messages beside it were
    never persisted.
    """
    client, db = webhook_client

    response = _post(
        client,
        _delivery(
            [
                _message("wamid.bad", "no-es-un-telefono", "rota"),
                _message("wamid.good", "5491122334455", "hola"),
            ]
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "processed": 1, "skipped": 1}
    stored = db.query(WhatsAppMessage).one()
    assert stored.provider_message_id == "wamid.good"


def test_tolerates_a_payload_whose_nested_fields_are_not_objects(webhook_client):
    """``text`` and ``profile`` arriving as strings must not raise a 500."""
    client, db = webhook_client

    response = _post(
        client,
        _delivery(
            [{"id": "wamid.odd", "from": "5491122334455", "type": "text", "text": "plano"}],
            contacts=[{"wa_id": "5491122334455", "profile": "Ana"}],
        ),
    )

    assert response.status_code == 200
    assert response.json() == {"received": True, "processed": 1, "skipped": 0}
    stored = db.query(WhatsAppMessage).one()
    assert stored.text is None


def test_replayed_delivery_is_idempotent(webhook_client):
    client, db = webhook_client
    payload = _delivery([_message("wamid.1", "5491122334455", "hola")])

    first = _post(client, payload)
    second = _post(client, payload)

    assert first.json()["processed"] == 1
    assert second.json()["processed"] == 0
    assert db.query(WhatsAppMessage).count() == 1
