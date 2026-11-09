"""Pilot contract: WhatsApp is presented as coming soon and has no runtime API."""

import pytest
from fastapi.testclient import TestClient

from app.api import whatsapp_crm, whatsapp_hooks, whatsapp_meta_webhook
from app.main import app
from app.models.hotel_api_key import APIKeyPurposeEnum, HotelAPIKey
from app.services.hotel_api_key_service import HotelAPIKeyError, issue_key


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/public/whatsapp/availability"),
        ("get", "/api/public/whatsapp/prices"),
        ("post", "/api/public/whatsapp/reservations"),
        ("post", "/api/public/whatsapp/payment-links"),
        ("get", "/api/whatsapp/channel"),
        ("post", "/api/whatsapp/channel/complete"),
        ("get", "/api/whatsapp/conversations"),
        ("post", "/api/whatsapp/conversations/1/messages"),
        ("get", "/api/webhooks/meta/whatsapp"),
        ("post", "/api/webhooks/meta/whatsapp"),
    ],
)
def test_whatsapp_public_crm_and_meta_routes_are_unavailable(method: str, path: str):
    response = getattr(TestClient(app), method)(path)

    assert response.status_code in {404, 405}


def test_whatsapp_router_paths_are_not_mounted_or_published():
    disabled_routers = (whatsapp_hooks.router, whatsapp_crm.router, whatsapp_meta_webhook.router)
    disabled_paths = {route.path for router in disabled_routers for route in router.routes}
    blocked_prefixes = (
        "/api/public/whatsapp",
        "/api/whatsapp",
        "/api/webhooks/meta/whatsapp",
    )

    openapi_paths = app.openapi()["paths"]

    assert disabled_paths
    assert not disabled_paths & openapi_paths.keys()
    assert not [
        path
        for path in openapi_paths
        if any(path.startswith(prefix) for prefix in blocked_prefixes)
    ]


def test_whatsapp_bot_api_keys_cannot_be_issued_during_pilot(pg_session):
    with pytest.raises(HotelAPIKeyError, match="WhatsApp.*desarrollo"):
        issue_key(
            pg_session,
            hotel_id=1,
            name="Clave de prueba",
            purpose=APIKeyPurposeEnum.WHATSAPP_BOT,
        )

    assert pg_session.query(HotelAPIKey).count() == 0
