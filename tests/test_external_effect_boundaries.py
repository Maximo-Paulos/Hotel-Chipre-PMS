"""Fail-closed boundary tests: disabled lanes do no parsing, DB work or network."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.auth import apple_login, google_login
from app.api.ota_webhooks import _guarded_json_payload
from app.api.payment_link_tests import mercadopago_webhook as payment_test_webhook
from app.api.payment_links import _mercadopago_webhook_impl
from app.config import Settings, get_settings
from app.master_admin.router import stripe_webhook
from app.schemas.auth import AppleAuthRequest, GoogleAuthRequest
from app.schemas.payment_link_test import PaymentLinkTestCreate
from app.services.email.providers import EmailProviderError, ResendEmailProvider
from app.services.external_effects_policy import ExternalEffectsDisabled
from app.services.hotel_outbound_email_service import (
    HotelOutboundEmailError,
    send_hotel_email,
)
from app.services.integration_service import get_connection_payload
from app.services.payment_link_test_service import (
    PaymentLinkTestError,
    create_mercadopago_payment_link_test,
)


class ExplodingDB:
    def __getattr__(self, name):
        raise AssertionError(f"DB access is forbidden while the lane is closed: {name}")


class ExplodingRequest:
    query_params: dict[str, str] = {}
    headers: dict[str, str] = {}

    async def json(self):
        raise AssertionError("request.json must not be called while callbacks are closed")

    async def body(self):
        raise AssertionError("request.body must not be called while callbacks are closed")


@pytest.fixture(autouse=True)
def _closed_provider_lanes(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("INBOUND_PROVIDER_EVENTS_ENABLED", "false")
    monkeypatch.setenv("GOOGLE_LOGIN_ENABLED", "false")
    monkeypatch.setenv("APPLE_LOGIN_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_credential_access_and_email_stop_before_db_or_network(monkeypatch):
    with pytest.raises(ExternalEffectsDisabled):
        get_connection_payload(ExplodingDB(), 1, "gmail")

    with pytest.raises(HotelOutboundEmailError, match="EXTERNAL_EFFECTS_ENABLED"):
        send_hotel_email(
            ExplodingDB(),
            1,
            to="guest@example.com",
            subject="Blocked",
            body="Blocked",
        )

    monkeypatch.setattr(
        "app.services.email.providers.requests.post",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Resend network must not be called")
        ),
    )
    provider = ResendEmailProvider(
        Settings(
            EXTERNAL_EFFECTS_ENABLED=False,
            EMAIL_PROVIDER="resend",
            RESEND_API_KEY="preserved-but-inactive",
        )
    )
    with pytest.raises(EmailProviderError, match="EXTERNAL_EFFECTS_ENABLED"):
        provider.send("guest@example.com", "Blocked", "Blocked")


def test_connections_flag_alone_closes_credential_lane(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    with pytest.raises(ExternalEffectsDisabled, match="CONNECTIONS_ENABLED"):
        get_connection_payload(ExplodingDB(), 1, "gmail")


def test_payment_link_test_stops_before_db_or_provider():
    with pytest.raises(PaymentLinkTestError, match="EXTERNAL_EFFECTS_ENABLED"):
        create_mercadopago_payment_link_test(
            ExplodingDB(),
            1,
            PaymentLinkTestCreate(
                recipient_email="guest@example.com",
                amount=10,
            ),
        )


def test_google_login_stops_before_transport_or_db(monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.google_requests.Request",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("Google transport must not be constructed")
        ),
    )
    with pytest.raises(HTTPException) as raised:
        google_login(GoogleAuthRequest(id_token="provider-token"), db=ExplodingDB())
    assert raised.value.status_code == 503


def test_apple_login_stops_before_jwks_or_db(monkeypatch):
    monkeypatch.setattr(
        "app.api.auth.verify_apple_id_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Apple JWKS must not be called")),
    )
    with pytest.raises(HTTPException) as raised:
        apple_login(AppleAuthRequest(id_token="provider-token"), db=ExplodingDB())
    assert raised.value.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "callback",
    [
        lambda request, db: _mercadopago_webhook_impl(request, db),
        lambda request, db: payment_test_webhook(request=request, db=db),
        lambda request, db: stripe_webhook(request=request, db=db),
    ],
)
async def test_provider_callbacks_stop_before_body_parse(callback):
    with pytest.raises(HTTPException) as raised:
        await callback(ExplodingRequest(), ExplodingDB())
    assert raised.value.status_code == 503


@pytest.mark.asyncio
async def test_ota_callback_stops_before_json_parse():
    with pytest.raises(HTTPException) as raised:
        await _guarded_json_payload("booking", ExplodingRequest())
    assert raised.value.status_code == 503
