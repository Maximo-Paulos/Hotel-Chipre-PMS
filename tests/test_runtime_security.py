import pytest

from app.config import Settings, get_settings, validate_runtime_security


def test_validate_runtime_security_rejects_default_production_secrets():
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=True,
        INBOUND_PROVIDER_EVENTS_ENABLED=True,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=False,
        JWT_SECRET="change-me",
        MASTER_ADMIN_PIN="1234",
        APP_BASE_URL="http://localhost:8040",
        INTEGRATIONS_ENCRYPTION_KEY="ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        MERCADOPAGO_WEBHOOK_SECRET="",
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        message = str(exc)
        assert "JWT_SECRET" in message
        assert "MASTER_ADMIN_PIN" in message
        assert "APP_BASE_URL" in message
        assert "INTEGRATIONS_ENCRYPTION_KEY" in message
        # MERCADOPAGO_WEBHOOK_SECRET is only required when MP_ACCESS_TOKEN is configured
        assert "MERCADOPAGO_WEBHOOK_SECRET" not in message
    else:
        raise AssertionError("Production security validation should reject insecure defaults")


def test_validate_runtime_security_rejects_incomplete_apple_configuration():
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=True,
        INBOUND_PROVIDER_EVENTS_ENABLED=True,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=True,
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="null",
    )
    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        message = str(exc)
        assert "APPLE_CLIENT_ID" in message
        assert "APPLE_TEAM_ID" in message
        assert "APPLE_KEY_ID" in message
        assert "APPLE_PRIVATE_KEY_PATH" in message
    else:
        raise AssertionError("Production must reject incomplete Apple credentials")


def test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured():
    """MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set."""
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=True,
        INBOUND_PROVIDER_EVENTS_ENABLED=True,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=False,
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        MP_ACCESS_TOKEN="TEST-access-token",
        MERCADOPAGO_WEBHOOK_SECRET="",  # missing when MP is configured → error
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        assert "MERCADOPAGO_WEBHOOK_SECRET" in str(exc)
    else:
        raise AssertionError("Should require MERCADOPAGO_WEBHOOK_SECRET when MP_ACCESS_TOKEN is set")
    get_settings.cache_clear()


def test_validate_runtime_security_ignores_incomplete_optional_integrations():
    """Partial integration env vars should not block production startup."""
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=False,
        INBOUND_PROVIDER_EVENTS_ENABLED=False,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        AI_ENABLED=False,
        AI_PROVIDER="disabled",
        GEMMA_ENABLED=False,
        GEMMA_PROVIDER="disabled",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="null",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        PAYPAL_CLIENT_ID="paypal-client-id-only",
        GMAIL_CLIENT_SECRET="gmail-secret-only",
        MERCADOPAGO_CLIENT_ID="mp-client-id-only",
        GMAIL_REDIRECT_URI="http://127.0.0.1:8040/api/integrations/oauth/gmail/callback",
        PAYPAL_REDIRECT_URI="http://127.0.0.1:8040/api/integrations/oauth/paypal/callback",
        MERCADOPAGO_REDIRECT_URI="http://127.0.0.1:8040/api/integrations/oauth/mercadopago/callback",
    )

    validate_runtime_security(settings)
    get_settings.cache_clear()


def test_validate_runtime_security_rejects_localhost_redirect_when_service_configured():
    """OAuth redirect URIs are only validated when the corresponding service credentials are set."""
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=True,
        INBOUND_PROVIDER_EVENTS_ENABLED=False,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=False,
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        GMAIL_CLIENT_ID="gmail-client-id",
        GMAIL_CLIENT_SECRET="gmail-client-secret",
        GMAIL_REDIRECT_URI="http://127.0.0.1:8040/api/integrations/oauth/gmail/callback",  # localhost → error
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        assert "GMAIL_REDIRECT_URI" in str(exc)
    else:
        raise AssertionError("Should reject localhost redirect URI when Gmail is configured")
    get_settings.cache_clear()


def test_validate_runtime_security_accepts_strong_production_settings():
    settings = Settings(
        APP_ENV="production",
        EXTERNAL_EFFECTS_ENABLED=False,
        INBOUND_PROVIDER_EVENTS_ENABLED=False,
        GOOGLE_LOGIN_ENABLED=False,
        APPLE_LOGIN_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        AI_ENABLED=False,
        AI_PROVIDER="disabled",
        GEMMA_ENABLED=False,
        GEMMA_PROVIDER="disabled",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="null",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        MERCADOPAGO_WEBHOOK_SECRET="mp-webhook-secret",
        PAYPAL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/paypal/callback",
        MERCADOPAGO_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/mercadopago/callback",
        GMAIL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/gmail/callback",
    )

    validate_runtime_security(settings)
    get_settings.cache_clear()


def test_validate_runtime_security_requires_realtime_events_in_production():
    settings = Settings(
        APP_ENV="production",
        REALTIME_EVENTS_ENABLED=False,
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_ENABLED=True,
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="null",
    )

    with pytest.raises(RuntimeError, match="REALTIME_EVENTS_ENABLED"):
        validate_runtime_security(settings)


def test_validate_runtime_security_rejects_unsafe_production_sandbox_profile():
    base = {
        "APP_ENV": "production",
        "EXTERNAL_EFFECTS_ENABLED": False,
        "INBOUND_PROVIDER_EVENTS_ENABLED": False,
        "GOOGLE_LOGIN_ENABLED": False,
        "APPLE_LOGIN_ENABLED": False,
        "CONNECTIONS_ENABLED": False,
        "AI_ENABLED": False,
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": False,
        "GEMMA_PROVIDER": "disabled",
        "PAYPAL_MODE": "sandbox",
        "EMAIL_PROVIDER": "null",
        "JWT_SECRET": "super-secret-value-for-production-1234567890",
        "MASTER_ADMIN_PIN": "654321",
        "APP_BASE_URL": "https://hotel-chipre.example.com",
        "DISTRIBUTED_LOCK_REQUIRED": True,
        "INTEGRATIONS_ENCRYPTION_KEY": "fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
    }
    unsafe = {
        "INBOUND_PROVIDER_EVENTS_ENABLED": True,
        "GOOGLE_LOGIN_ENABLED": True,
        "CONNECTIONS_ENABLED": True,
        "AI_ENABLED": None,
        "AI_PROVIDER": "openai",
        "GEMMA_ENABLED": True,
        "GEMMA_PROVIDER": "google_gemini_api",
        "PAYPAL_MODE": "live",
        "EMAIL_PROVIDER": "resend",
    }

    for field, value in unsafe.items():
        settings = Settings(**{**base, field: value})
        try:
            validate_runtime_security(settings)
        except RuntimeError as exc:
            assert field in str(exc)
        else:
            raise AssertionError(f"Production sandbox must reject {field}={value!r}")


def test_validate_runtime_security_rejects_insecure_cookie_override_and_cors_wildcard():
    base = {
        "APP_ENV": "production",
        "EXTERNAL_EFFECTS_ENABLED": False,
        "INBOUND_PROVIDER_EVENTS_ENABLED": False,
        "GOOGLE_LOGIN_ENABLED": False,
        "APPLE_LOGIN_ENABLED": False,
        "CONNECTIONS_ENABLED": False,
        "AI_ENABLED": False,
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": False,
        "GEMMA_PROVIDER": "disabled",
        "PAYPAL_MODE": "sandbox",
        "EMAIL_PROVIDER": "null",
        "JWT_SECRET": "super-secret-value-for-production-1234567890",
        "MASTER_ADMIN_PIN": "654321",
        "APP_BASE_URL": "https://hotel-chipre.example.com",
        "DISTRIBUTED_LOCK_REQUIRED": True,
        "INTEGRATIONS_ENCRYPTION_KEY": "fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
    }

    for field, value in (("MASTER_ADMIN_COOKIE_SECURE", False), ("CORS_ORIGINS", "*")):
        settings = Settings(**{**base, field: value})
        try:
            validate_runtime_security(settings)
        except RuntimeError as exc:
            assert field in str(exc)
        else:
            raise AssertionError(f"Production security validation should reject {field}={value!r}")


def test_validate_runtime_security_requires_explicit_external_policy_flags():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        DISTRIBUTED_LOCK_REQUIRED=True,
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="null",
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        message = str(exc)
        assert "EXTERNAL_EFFECTS_ENABLED" in message
        assert "INBOUND_PROVIDER_EVENTS_ENABLED" in message
        assert "GOOGLE_LOGIN_ENABLED" in message
    else:
        raise AssertionError("Production must reject an implicit external-effect policy")


def test_validate_runtime_security_rejects_weak_master_admin_password_in_production():
    """Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but
    production only checked the PIN - a weak bootstrap password/email in a
    real production deploy went unnoticed."""
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        MASTER_ADMIN_EMAIL="not-an-email",
        MASTER_ADMIN_PASSWORD="weak",
        APP_BASE_URL="https://hotel-chipre.example.com",
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        MERCADOPAGO_WEBHOOK_SECRET="mp-webhook-secret",
        PAYPAL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/paypal/callback",
        MERCADOPAGO_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/mercadopago/callback",
        GMAIL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/gmail/callback",
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        message = str(exc)
        assert "MASTER_ADMIN_PASSWORD" in message
        assert "MASTER_ADMIN_EMAIL" in message
    else:
        raise AssertionError("Production security validation should reject a weak master admin bootstrap")
    get_settings.cache_clear()


def test_validate_runtime_security_rejects_shared_token_secrets():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MASTER_ADMIN_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        EMAIL_PROVIDER="resend",
        RESEND_API_KEY="re_test_key",
        SYSTEM_EMAIL_FROM="Hotel Chipre PMS <noreply@auth.hotels-pms.com>",
        SYSTEM_EMAIL_REPLY_TO="hotelxpms@gmail.com",
        MERCADOPAGO_WEBHOOK_SECRET="mp-webhook-secret",
        PAYPAL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/paypal/callback",
        MERCADOPAGO_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/mercadopago/callback",
        GMAIL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/gmail/callback",
        ACCESS_TOKEN_SECRET="shared-token-secret",
        SIGNED_TOKEN_SECRET="shared-token-secret",
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        assert "ACCESS_TOKEN_SECRET" in str(exc)
    else:
        raise AssertionError("Production security validation should reject shared token secrets")
    get_settings.cache_clear()
