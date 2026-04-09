from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models.hotel_config import HotelConfiguration
from app.models.integration import IntegrationCatalog, IntegrationConnection
from app.schemas.payment_link_test import PaymentLinkTestCreate
from app.services.hotel_outbound_email_service import HotelOutboundEmailError, send_hotel_email
from app.services.integration_service import GMAIL_SEND_SCOPE, encrypt_payload
from app.services.payment_link_test_service import PaymentLinkTestError, create_mercadopago_payment_link_test


class _Response:
    def __init__(self, ok: bool, payload: dict, text: str = ""):
        self.ok = ok
        self._payload = payload
        self.text = text
        self.status_code = 200 if ok else 400

    def json(self):
        return self._payload


def _seed_gmail_connection(db, hotel_id: int = 1) -> None:
    if not db.get(HotelConfiguration, hotel_id):
        db.add(HotelConfiguration(id=hotel_id, hotel_name='Hotel Demo', subscription_active=True))
        db.flush()
    integration = db.query(IntegrationCatalog).filter_by(provider='gmail').first()
    if not integration:
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
        hotel_id=hotel_id,
        integration_id=integration.id,
        status='connected',
        auth_payload=encrypt_payload(
            {
                'access_token': 'gmail-access',
                'refresh_token': 'gmail-refresh',
                'scope': f'openid email profile {GMAIL_SEND_SCOPE}',
                'account_email': 'hotel@example.com',
                'account_name': 'Hotel Demo',
                'issued_at': datetime.now(timezone.utc).isoformat(),
                'expires_in': 3600,
            }
        ),
    )
    db.add(connection)
    db.commit()


def _seed_mercadopago_connection(db, hotel_id: int = 1) -> None:
    if not db.get(HotelConfiguration, hotel_id):
        db.add(HotelConfiguration(id=hotel_id, hotel_name='Hotel Demo', subscription_active=True))
        db.flush()
    integration = db.query(IntegrationCatalog).filter_by(provider='mercadopago').first()
    if not integration:
        integration = IntegrationCatalog(
            provider='mercadopago',
            display_name='MercadoPago',
            auth_type='oauth_code',
            scopes='payments offline_access',
            doc_url='https://www.mercadopago.com.ar/developers/en',
        )
        db.add(integration)
        db.flush()
    connection = IntegrationConnection(
        hotel_id=hotel_id,
        integration_id=integration.id,
        status='connected',
        auth_payload=encrypt_payload({'access_token': 'mp-access', 'account_email': 'collector@example.com'}),
    )
    db.add(connection)
    db.commit()


def test_send_hotel_email_requires_gmail_connection(db):
    db.add(HotelConfiguration(id=1, hotel_name='Hotel Demo', subscription_active=True))
    db.commit()
    with pytest.raises(HotelOutboundEmailError):
        send_hotel_email(db, 1, to='guest@example.com', subject='Hola', body='Prueba')


def test_send_hotel_email_uses_connected_gmail(db, monkeypatch):
    _seed_gmail_connection(db)

    def fake_get(url, headers=None, timeout=None):
        return _Response(True, {'email': 'hotel@example.com', 'name': 'Hotel Demo', 'sub': 'google-sub'})

    sent_payload = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        sent_payload['url'] = url
        sent_payload['headers'] = headers
        sent_payload['json'] = json
        return _Response(True, {'id': 'gmail-message-1'})

    monkeypatch.setattr('app.services.hotel_outbound_email_service.requests.get', fake_get)
    monkeypatch.setattr('app.services.hotel_outbound_email_service.requests.post', fake_post)

    result = send_hotel_email(db, 1, to='guest@example.com', subject='Pago', body='Hola mundo')
    assert result.channel == 'gmail_hotel'
    assert result.sender_email == 'hotel@example.com'
    assert sent_payload['url'].endswith('/gmail/v1/users/me/messages/send')
    assert sent_payload['headers']['Authorization'] == 'Bearer gmail-access'
    assert 'raw' in sent_payload['json']


def test_payment_link_test_requires_hotel_gmail_connection(db):
    _seed_mercadopago_connection(db)
    with pytest.raises(PaymentLinkTestError):
        create_mercadopago_payment_link_test(
            db,
            1,
            PaymentLinkTestCreate(recipient_email='guest@example.com', amount=1000, currency='ARS', description='Se?a'),
        )
