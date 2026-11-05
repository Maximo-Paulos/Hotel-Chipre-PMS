from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.config import get_settings
from app.services import integration_service
from app.services.payment_link_test_service import mercadopago_checkout_url


def test_mercadopago_redirect_requests_platform_authorization_and_offline_access(monkeypatch):
    monkeypatch.setattr(integration_service, "require_external_connections", lambda *_args: None)
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "synthetic-platform-client")
    monkeypatch.setenv("MERCADOPAGO_CLIENT_SECRET", "synthetic-platform-secret")
    monkeypatch.setenv(
        "MERCADOPAGO_REDIRECT_URI",
        "https://pms-piloto.example.test/api/integrations/oauth/mercadopago/callback",
    )
    get_settings.cache_clear()
    try:
        url = integration_service.build_redirect_url(
            SimpleNamespace(provider="mercadopago", scopes="offline_access payments write"),
            state="synthetic-signed-state",
        )
    finally:
        get_settings.cache_clear()

    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert parsed.netloc == "auth.mercadopago.com"
    assert params["client_id"] == ["synthetic-platform-client"]
    assert params["platform_id"] == ["mp"]
    assert params["state"] == ["synthetic-signed-state"]
    assert params["scope"] == ["offline_access payments write"]
    assert params["redirect_uri"] == [
        "https://pms-piloto.example.test/api/integrations/oauth/mercadopago/callback"
    ]


def test_mercadopago_refresh_rotates_both_tokens_and_sets_expiration(monkeypatch):
    monkeypatch.setattr(integration_service, "require_external_connections", lambda *_args: None)
    monkeypatch.setenv("MERCADOPAGO_CLIENT_ID", "synthetic-platform-client")
    monkeypatch.setenv("MERCADOPAGO_CLIENT_SECRET", "synthetic-platform-secret")
    get_settings.cache_clear()
    calls: list[dict] = []

    def fake_http(operation, _request, url, **kwargs):
        calls.append({"operation": operation, "url": url, **kwargs})
        return SimpleNamespace(
            ok=True,
            json=lambda: {
                "access_token": "APP_USR-synthetic-rotated-access",
                "refresh_token": "TG-synthetic-rotated-refresh",
                "expires_in": 15552000,
                "scope": "offline_access payments write",
                "user_id": 987654,
                "live_mode": True,
            },
        )

    monkeypatch.setattr(integration_service, "observed_http_call", fake_http)
    try:
        payload = integration_service.refresh_mercadopago_access_token(
            {
                "access_token": "APP_USR-synthetic-old-access",
                "refresh_token": "TG-synthetic-old-refresh",
                "user_id": 987654,
                "account_nickname": "Synthetic Hotel",
            }
        )
    finally:
        get_settings.cache_clear()

    assert len(calls) == 1
    assert calls[0]["operation"] == "mercadopago.oauth_refresh"
    assert calls[0]["url"] == "https://api.mercadopago.com/oauth/token"
    assert calls[0]["data"]["grant_type"] == "refresh_token"
    assert calls[0]["data"]["refresh_token"] == "TG-synthetic-old-refresh"
    assert payload["access_token"] == "APP_USR-synthetic-rotated-access"
    assert payload["refresh_token"] == "TG-synthetic-rotated-refresh"
    assert payload["account_nickname"] == "Synthetic Hotel"
    assert datetime.fromisoformat(payload["expires_at"]).astimezone(timezone.utc) > datetime.now(
        timezone.utc
    )


def test_mercadopago_refresh_without_refresh_grant_requires_owner_reauthorization(monkeypatch):
    monkeypatch.setattr(integration_service, "require_external_connections", lambda *_args: None)
    monkeypatch.setattr(
        integration_service,
        "observed_http_call",
        lambda *_args, **_kwargs: pytest.fail("must not call Mercado Pago without a refresh grant"),
    )

    with pytest.raises(
        integration_service.MercadoPagoReauthorizationRequired,
        match="Owner debe volver a conectar",
    ):
        integration_service.refresh_mercadopago_access_token({"access_token": "APP_USR-synthetic"})


def test_sandbox_checkout_url_is_never_replaced_by_production_init_point():
    payload = {
        "init_point": "https://www.mercadopago.com.ar/checkout/start?pref_id=synthetic",
        "sandbox_init_point": "https://sandbox.mercadopago.com/checkout/pay?pref_id=synthetic",
    }

    assert mercadopago_checkout_url(payload, access_token="TEST-synthetic-token") == payload[
        "sandbox_init_point"
    ]
    assert mercadopago_checkout_url(payload, access_token="APP_USR-synthetic-token") == payload[
        "init_point"
    ]
    assert (
        mercadopago_checkout_url(
            {"init_point": payload["init_point"]}, access_token="TEST-synthetic-token"
        )
        is None
    )
