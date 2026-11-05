"""Pilot contract: WhatsApp remains visible as coming soon but has no runtime API."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.hotel_api_key import APIKeyPurposeEnum
from app.services.hotel_api_key_service import HotelAPIKeyError, issue_key


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/public/whatsapp/availability"),
        ("get", "/api/public/whatsapp/prices"),
        ("get", "/api/public/whatsapp/options"),
        ("get", "/api/public/whatsapp/options/prices"),
        ("post", "/api/public/whatsapp/reservations"),
        ("post", "/api/public/whatsapp/payment-links"),
        ("post", "/api/public/whatsapp/payment-link"),
        ("post", "/api/public/whatsapp/payment-confirmation"),
        ("post", "/api/public/whatsapp/payment-confirmations"),
        ("get", "/api/whatsapp/channel"),
        ("post", "/api/whatsapp/channel/complete"),
        ("get", "/api/whatsapp/conversations"),
        ("get", "/api/whatsapp/conversations/1/messages"),
        ("post", "/api/whatsapp/conversations/1/messages"),
        ("post", "/api/whatsapp/conversations/1/notes"),
        ("post", "/api/whatsapp/conversations/1/assignment"),
        ("post", "/api/whatsapp/conversations/1/status"),
        ("get", "/api/webhooks/meta/whatsapp"),
        ("post", "/api/webhooks/meta/whatsapp"),
    ],
)
def test_whatsapp_public_crm_and_webhook_routes_are_unavailable(method: str, path: str):
    response = getattr(TestClient(app), method)(path)

    # The application's generic API fallback returns 405 for unsupported
    # methods on an unknown path; no WhatsApp handler may answer successfully.
    assert response.status_code in {404, 405}


def test_whatsapp_router_prefixes_are_not_registered():
    blocked_prefixes = (
        "/api/public/whatsapp",
        "/api/whatsapp",
        "/api/webhooks/meta/whatsapp",
    )

    registered_paths = app.openapi()["paths"]

    assert not [
        path
        for path in registered_paths
        if any(path.startswith(prefix) for prefix in blocked_prefixes)
    ]


def test_whatsapp_bot_api_keys_cannot_be_issued_during_pilot():
    with pytest.raises(HotelAPIKeyError, match="WhatsApp.*desarrollo"):
        issue_key(
            None,  # Validation must reject the purpose before any database access.
            hotel_id=1,
            name="Clave de prueba",
            purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
        )
