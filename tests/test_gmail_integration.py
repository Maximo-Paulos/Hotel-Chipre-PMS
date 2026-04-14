from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.integration import IntegrationCatalog, IntegrationConnection
from app.services.integration_service import (
    GMAIL_SEND_SCOPE,
    build_redirect_url,
    encrypt_payload,
    validate_gmail_credentials,
    verify_connection_health,
)
from app.config import get_settings


class _Response:
    def __init__(self, ok: bool, payload: dict, text: str = ""):
        self.ok = ok
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_build_redirect_url_for_gmail_requests_offline_access(monkeypatch):
    monkeypatch.setenv('GMAIL_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'client-secret')
    get_settings.cache_clear()

    integration = SimpleNamespace(provider='gmail', scopes=f'openid email profile {GMAIL_SEND_SCOPE}')
    redirect = build_redirect_url(integration, redirect_uri='https://app.example.com/oauth/gmail/callback', state='state-123')
    parsed = urlparse(redirect)
    params = parse_qs(parsed.query)

    assert parsed.netloc == 'accounts.google.com'
    assert params['access_type'] == ['offline']
    assert params['include_granted_scopes'] == ['true']
    assert params['prompt'] == ['consent']
    assert params['state'] == ['state-123']
    assert GMAIL_SEND_SCOPE in params['scope'][0]


def test_validate_gmail_credentials_enriches_identity(monkeypatch):
    monkeypatch.setenv('GMAIL_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'client-secret')
    get_settings.cache_clear()

    def fake_get(url, headers=None, timeout=None):
        assert url == 'https://openidconnect.googleapis.com/v1/userinfo'
        assert headers['Authorization'] == 'Bearer access-123'
        return _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel Sender', 'sub': 'google-sub'})

    monkeypatch.setattr('app.services.integration_service.requests.get', fake_get)

    enriched = validate_gmail_credentials(
        {
            'access_token': 'access-123',
            'refresh_token': 'refresh-123',
            'scope': f'openid email profile {GMAIL_SEND_SCOPE}',
            'expires_in': 3600,
        }
    )

    assert enriched['account_email'] == 'hotel@example.com'
    assert enriched['account_name'] == 'Hotel Sender'
    assert enriched['account_sub'] == 'google-sub'
    assert enriched['refresh_token'] == 'refresh-123'
    assert 'expires_at' in enriched


def test_validate_gmail_credentials_requires_send_scope(monkeypatch):
    monkeypatch.setenv('GMAIL_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'client-secret')
    get_settings.cache_clear()

    monkeypatch.setattr(
        'app.services.integration_service.requests.get',
        lambda *args, **kwargs: _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel Sender', 'sub': 'google-sub'}),
    )

    with pytest.raises(ValueError):
        validate_gmail_credentials(
            {
                'access_token': 'access-123',
                'refresh_token': 'refresh-123',
                'scope': 'openid email profile',
                'expires_in': 3600,
            }
        )


def test_verify_connection_health_for_gmail_updates_connection(db, monkeypatch):
    monkeypatch.setenv('GMAIL_CLIENT_ID', 'client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'client-secret')
    get_settings.cache_clear()

    db.add(HotelConfiguration(id=1, subscription_active=True))
    integration = IntegrationCatalog(
        provider='gmail',
        display_name='Gmail',
        auth_type='oauth_code',
        scopes=f'openid email profile {GMAIL_SEND_SCOPE}',
        doc_url='https://developers.google.com/workspace/gmail/api/guides/sending',
    )
    db.add(integration)
    db.flush()
    connection = IntegrationConnection(
        hotel_id=1,
        integration_id=integration.id,
        status='connected',
        auth_payload=encrypt_payload(
            {
                'access_token': 'access-123',
                'refresh_token': 'refresh-123',
                'scope': f'openid email profile {GMAIL_SEND_SCOPE}',
                'expires_in': 3600,
                'issued_at': datetime.now(timezone.utc).isoformat(),
            }
        ),
    )
    db.add(connection)
    db.commit()

    monkeypatch.setattr(
        'app.services.integration_service.requests.get',
        lambda *args, **kwargs: _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel Sender', 'sub': 'google-sub'}),
    )

    conn, message = verify_connection_health(db, 1, integration.id)
    assert conn.status == 'connected'
    assert 'hotel@example.com' in message
    assert conn.last_error is None
    assert conn.last_checked_at is not None
