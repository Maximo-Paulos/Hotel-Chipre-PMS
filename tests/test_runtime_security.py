from app.config import Settings, get_settings, validate_runtime_security


def test_validate_runtime_security_rejects_default_production_secrets():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="change-me",
        MANAGER_PIN="1234",
        APP_BASE_URL="http://localhost:8040",
        INTEGRATIONS_ENCRYPTION_KEY="ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==",
        MERCADOPAGO_WEBHOOK_SECRET="",
    )

    try:
        validate_runtime_security(settings)
    except RuntimeError as exc:
        message = str(exc)
        assert "JWT_SECRET" in message
        assert "MANAGER_PIN" in message
        assert "APP_BASE_URL" in message
        assert "INTEGRATIONS_ENCRYPTION_KEY" in message
        assert "MERCADOPAGO_WEBHOOK_SECRET" in message
    else:
        raise AssertionError("Production security validation should reject insecure defaults")


def test_validate_runtime_security_accepts_strong_production_settings():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MANAGER_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
        MERCADOPAGO_WEBHOOK_SECRET="mp-webhook-secret",
        PAYPAL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/paypal/callback",
        MERCADOPAGO_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/mercadopago/callback",
        GMAIL_REDIRECT_URI="https://hotel-chipre.example.com/api/integrations/oauth/gmail/callback",
    )

    validate_runtime_security(settings)
    get_settings.cache_clear()


def test_validate_runtime_security_rejects_shared_token_secrets():
    settings = Settings(
        APP_ENV="production",
        JWT_SECRET="super-secret-value-for-production-1234567890",
        MANAGER_PIN="654321",
        APP_BASE_URL="https://hotel-chipre.example.com",
        INTEGRATIONS_ENCRYPTION_KEY="fRb9jE74bWw5gAKpNwZrl_uCWhsx2Nl7fNL1jK5vLG8=",
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
