"""Fail-closed safeguards for cloud QA external integrations."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import Settings, get_settings, validate_runtime_security
from app.master_admin.stripe import save_stripe_settings


def safe_preview_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "preview",
        "EMAIL_PROVIDER": "null",
        "CONNECTIONS_ENABLED": False,
        "PAYPAL_MODE": "sandbox",
        "AI_ENABLED": False,
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": False,
        "GEMMA_PROVIDER": "disabled",
    }
    values.update(overrides)
    return Settings(**values)


def test_preview_runtime_accepts_explicitly_disabled_external_effects() -> None:
    validate_runtime_security(safe_preview_settings())


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("EMAIL_PROVIDER", "resend"),
        ("CONNECTIONS_ENABLED", True),
        ("PAYPAL_MODE", "live"),
        ("AI_ENABLED", None),
        ("AI_PROVIDER", "openai"),
        ("GEMMA_ENABLED", True),
        ("GEMMA_PROVIDER", "google_gemini_api"),
        ("RESEND_API_KEY", "configured-live-key"),
        ("MP_ACCESS_TOKEN", "configured-live-token"),
        ("GMAIL_CLIENT_SECRET", "configured-live-secret"),
        ("BOOKING_PASSWORD", "configured-live-password"),
        ("AI_API_KEY", "configured-live-key"),
        ("GEMMA_ENDPOINT_URL", "https://example.invalid/v1"),
    ],
)
def test_preview_runtime_rejects_external_effects_configuration(
    field: str,
    unsafe_value: object,
) -> None:
    with pytest.raises(RuntimeError, match=field):
        validate_runtime_security(safe_preview_settings(**{field: unsafe_value}))


def test_stripe_connect_is_blocked_before_network_when_connections_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    get_settings.cache_clear()

    def unexpected_network(*args: object, **kwargs: object) -> object:
        raise AssertionError("Stripe network call must not occur")

    monkeypatch.setattr("app.master_admin.stripe.requests.get", unexpected_network)
    with pytest.raises(HTTPException) as raised:
        save_stripe_settings(None, {"stripe_secret_key": "sk_live_must_not_leave"})  # type: ignore[arg-type]

    assert raised.value.status_code == 503
    get_settings.cache_clear()
