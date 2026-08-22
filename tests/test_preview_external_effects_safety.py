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
        "EXTERNAL_EFFECTS_ENABLED": False,
        "INBOUND_PROVIDER_EVENTS_ENABLED": False,
        "GOOGLE_LOGIN_ENABLED": False,
        "APPLE_LOGIN_ENABLED": False,
        "PAYPAL_MODE": "sandbox",
        "AI_ENABLED": False,
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": False,
        "GEMMA_PROVIDER": "disabled",
        "READ_MODEL_CACHE_ENABLED": False,
        "MONGO_ENABLED": False,
        "CASSANDRA_ENABLED": False,
        "NEO4J_ENABLED": False,
        "JWT_SECRET": "qa-jwt-secret-that-is-at-least-32-bytes-long",
        "INTEGRATIONS_ENCRYPTION_KEY": "cXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXE=",
        "MASTER_ADMIN_EMAIL": "master-admin@qa.example.test",
        "MASTER_ADMIN_PASSWORD": "MasterAdminQaPass005!",
        "MASTER_ADMIN_PIN": "830527",
        "MASTER_ADMIN_COOKIE_SECURE": True,
    }
    values.update(overrides)
    # _env_file=None so the developer's local .env cannot leak live credentials
    # (AI_BASE_URL, provider keys) into a fixture that exists to assert they are
    # absent.
    return Settings(_env_file=None, **values)


def test_preview_runtime_accepts_explicitly_disabled_external_effects() -> None:
    validate_runtime_security(safe_preview_settings())


@pytest.mark.parametrize(
    ("field", "unsafe_value"),
    [
        ("EMAIL_PROVIDER", "resend"),
        ("CONNECTIONS_ENABLED", True),
        ("EXTERNAL_EFFECTS_ENABLED", True),
        ("INBOUND_PROVIDER_EVENTS_ENABLED", True),
        ("GOOGLE_LOGIN_ENABLED", True),
        ("APPLE_LOGIN_ENABLED", True),
        ("PAYPAL_MODE", "live"),
        ("AI_ENABLED", None),
        ("AI_PROVIDER", "openai"),
        ("GEMMA_ENABLED", True),
        ("GEMMA_PROVIDER", "google_gemini_api"),
        ("READ_MODEL_CACHE_ENABLED", True),
        ("MONGO_ENABLED", True),
        ("CASSANDRA_ENABLED", True),
        ("NEO4J_ENABLED", True),
        ("MASTER_ADMIN_COOKIE_SECURE", False),
        ("JWT_SECRET", "too-short"),
        (
            "INTEGRATIONS_ENCRYPTION_KEY",
            "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==",
        ),
        ("MASTER_ADMIN_PASSWORD", "short"),
        ("MASTER_ADMIN_PIN", "1234"),
        ("REDIS_URL", "redis://shared.example.invalid:6379/0"),
        ("CELERY_BROKER_URL", "redis://shared.example.invalid:6379/0"),
        ("CELERY_RESULT_BACKEND", "redis://shared.example.invalid:6379/1"),
        ("MONGO_URL", "mongodb://shared.example.invalid:27017"),
        ("CASSANDRA_HOSTS", "shared.example.invalid"),
        ("NEO4J_URI", "bolt://shared.example.invalid:7687"),
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
