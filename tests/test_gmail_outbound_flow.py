from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import integrations as integrations_api
from app.database import Base
from app.main import app as fastapi_app
import app.models  # noqa: F401
from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.integration import IntegrationCatalog, IntegrationConnection
from app.models.user import User
from app.services.hotel_outbound_email_service import send_hotel_email
from app.services.integration_service import build_redirect_url, encrypt_payload, validate_gmail_credentials
from app.dependencies.auth import AuthContext
from app.services.security import hash_password


def _integration_client():
    engine = create_engine(
        'sqlite:///:memory:', connect_args={'check_same_thread': False}, poolclass=StaticPool
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    owner = User(email='owner@test.com', password_hash=hash_password('pw'), role='owner', is_verified=True)
    db.add(owner)
    db.flush()
    hotel = HotelConfiguration(id=1, owner_email=owner.email, subscription_active=True)
    db.add(hotel)
    db.add(HotelMembership(hotel_id=hotel.id, user_id=owner.id, role='owner', status='active'))
    gmail = IntegrationCatalog(
        id=1,
        provider='gmail',
        display_name='Gmail',
        auth_type='oauth_code',
        scopes='openid email profile https://www.googleapis.com/auth/gmail.send',
        doc_url='https://developers.google.com/workspace/gmail/api/guides/sending',
    )
    db.add(gmail)
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    from app.database import get_db
    from app.dependencies.auth import get_auth_context

    def override_auth_context():
        return AuthContext(
            hotel_id=hotel.id,
            user_id=owner.id,
            user_email=owner.email,
            user_role='owner',
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth_context
    client = TestClient(fastapi_app)
    return client, db, owner, gmail


class _Response:
    def __init__(self, ok: bool, payload: dict):
        self.ok = ok
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_build_redirect_url_for_gmail_includes_state_and_offline_access(monkeypatch):
    monkeypatch.setenv('GMAIL_CLIENT_ID', 'google-client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'google-client-secret')
    monkeypatch.setenv('GMAIL_REDIRECT_URI', 'https://app.pmspaulus.com/api/integrations/oauth/gmail/callback')
    from app.config import get_settings
    get_settings.cache_clear()

    integration = IntegrationCatalog(
        provider='gmail',
        display_name='Gmail',
        auth_type='oauth_code',
        scopes='openid email profile https://www.googleapis.com/auth/gmail.send',
    )

    redirect = build_redirect_url(integration, state='signed-state-token')
    parsed = urlparse(redirect)
    params = parse_qs(parsed.query)

    assert parsed.netloc == 'accounts.google.com'
    assert params['access_type'] == ['offline']
    assert params['prompt'] == ['consent']
    assert params['state'] == ['signed-state-token']
    assert 'https://www.googleapis.com/auth/gmail.send' in params['scope'][0]


def test_validate_gmail_credentials_rejects_missing_send_scope(monkeypatch):
    monkeypatch.setattr(
        'app.services.integration_service.requests.get',
        lambda *args, **kwargs: _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel', 'sub': 'abc'}),
    )

    try:
        validate_gmail_credentials({'access_token': 'token', 'refresh_token': 'refresh-token', 'scope': 'openid email profile'})
        assert False, 'Expected ValueError for missing gmail.send scope'
    except ValueError as exc:
        assert 'gmail.send' in str(exc)



def test_send_hotel_email_uses_connected_gmail(monkeypatch, db):
    hotel = HotelConfiguration(id=1, owner_email='owner@test.com', hotel_name='Hotel Demo', subscription_active=True)
    catalog = IntegrationCatalog(
        id=10,
        provider='gmail',
        display_name='Gmail',
        auth_type='oauth_code',
        scopes='openid email profile https://www.googleapis.com/auth/gmail.send',
    )
    connection = IntegrationConnection(
        hotel_id=1,
        integration_id=10,
        status='connected',
        auth_payload=encrypt_payload({
            'access_token': 'access-token',
            'refresh_token': 'refresh-token',
            'scope': 'openid email profile https://www.googleapis.com/auth/gmail.send',
            'account_email': 'hotel@example.com',
            'account_name': 'Hotel Demo',
        }),
    )
    db.add_all([hotel, catalog, connection])
    db.commit()

    monkeypatch.setattr(
        'app.services.hotel_outbound_email_service.requests.get',
        lambda *args, **kwargs: _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel Demo', 'sub': 'abc'}),
    )
    monkeypatch.setattr(
        'app.services.hotel_outbound_email_service.requests.post',
        lambda *args, **kwargs: _Response(True, {'id': 'gmail-message-1'}),
    )

    result = send_hotel_email(
        db,
        1,
        to='guest@example.com',
        subject='Link de pago',
        body='Hola',
    )

    assert result.channel == 'gmail_hotel'
    assert result.sender_email == 'hotel@example.com'



def test_gmail_oauth_callback_uses_signed_state(monkeypatch):
    client, db, owner, gmail = _integration_client()

    monkeypatch.setenv('GMAIL_CLIENT_ID', 'google-client-id')
    monkeypatch.setenv('GMAIL_CLIENT_SECRET', 'google-client-secret')
    monkeypatch.setenv('GMAIL_REDIRECT_URI', 'http://testserver/api/integrations/oauth/gmail/callback')
    from app.config import get_settings
    get_settings.cache_clear()

    captured = {}

    def fake_store(db_session, hotel_id, integration_id, provider, code):
        captured['hotel_id'] = hotel_id
        captured['integration_id'] = integration_id
        captured['provider'] = provider
        captured['code'] = code

    monkeypatch.setattr(integrations_api, '_store_oauth_code', fake_store)

    start = client.post('/api/integrations/1/connect', json={'payload': {}})
    assert start.status_code == 200
    redirect_url = start.json()['redirect_url']
    state = parse_qs(urlparse(redirect_url).query)['state'][0]

    callback = client.get(f'/api/integrations/oauth/gmail/callback?code=test-code&state={state}')
    assert callback.status_code == 200
    assert 'integration-oauth-result' in callback.text
    assert captured == {
        'hotel_id': 1,
        'integration_id': 1,
        'provider': 'gmail',
        'code': 'test-code',
    }
