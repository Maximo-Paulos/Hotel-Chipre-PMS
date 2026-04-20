"""
Application Configuration.
Uses pydantic-settings for environment variable management.
"""
import os
from cryptography.fernet import Fernet
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # Environment / runtime mode
    APP_ENV: str = "development"

    # Public app URL used in redirects/webhooks (backend)
    APP_BASE_URL: str = "http://127.0.0.1:8040"

    # Frontend public URL used in emails (invitation links, password reset, etc.)
    FRONTEND_URL: str = "http://localhost:5173"

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://pms:pms@localhost:5432/hotel_pms"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # MercadoPago
    MP_ACCESS_TOKEN: str = ""
    MP_PUBLIC_KEY: str = ""

    # PayPal
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_MODE: str = "sandbox"  # "sandbox" or "live"

    # OAuth client IDs for connections
    MERCADOPAGO_CLIENT_ID: str = ""
    MERCADOPAGO_CLIENT_SECRET: str = ""
    PAYPAL_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/paypal/callback"
    MERCADOPAGO_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/mercadopago/callback"
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/gmail/callback"
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # OTA Credentials
    BOOKING_API_URL: str = "https://supply-xml.booking.com/hotels/xml"
    BOOKING_USERNAME: str = ""
    BOOKING_PASSWORD: str = ""

    EXPEDIA_API_URL: str = "https://services.expediapartnercentral.com"
    EXPEDIA_API_KEY: str = ""
    EXPEDIA_HOTEL_ID: str = ""

    # Hotel defaults
    DEFAULT_DEPOSIT_PERCENT: float = 30.0
    HOTEL_NAME: str = "Hotel PMS"
    HOTEL_TIMEZONE: str = "America/Argentina/Buenos_Aires"
    MANAGER_PIN: str = "1234"

    # Gemma / policy-learning assistant
    GEMMA_ENABLED: bool = False
    GEMMA_PROVIDER: str = "disabled"  # disabled, openai_compatible, google_gemini_api, auto
    GEMMA_ENDPOINT_URL: str = ""
    GEMMA_MODEL: str = ""
    GEMMA_API_KEY: str = ""
    GEMMA_TIMEOUT_SECONDS: float = 20.0
    GEMMA_MAX_OUTPUT_TOKENS: int = 1024
    GEMMA_TEMPERATURE: float = 0.2
    GEMMA_STRICT_JSON: bool = True
    GEMMA_MAX_CONVERSATION_MESSAGES: int = 6
    GEMMA_MAX_INPUT_CHARS: int = 4000
    GEMMA_RATE_LIMIT_WINDOW_SECONDS: int = 300
    GEMMA_RATE_LIMIT_MAX_MESSAGES: int = 20

    # SMTP / Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "Hotel PMS <noreply@example.com>"
    SMTP_STARTUP_NOTIFY: bool = False

    # Pilot / onboarding flags
    # Opt-in: when True new users are auto-verified on register so the piloto
    # can proceed without a working outbound-email channel.
    PILOT_AUTO_VERIFY: bool = False
    # Opt-in: when True AND SMTP is not configured, password-reset and
    # verification endpoints include the code in the JSON response so the UI
    # can complete the flow without a mailbox. Intended for trusted pilot
    # users only; leave False when exposing the deployment publicly.
    EXPOSE_AUTH_CODES_WHEN_NO_SMTP: bool = False

    # Auth
    JWT_SECRET: str = "change-me"
    ACCESS_TOKEN_SECRET: str = ""
    SIGNED_TOKEN_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 60
    DEFAULT_SUBSCRIPTION_PLAN: str = "starter"
    LOGIN_RATE_LIMIT: int = 5  # attempts per window
    SUBSCRIPTION_ENFORCEMENT_ENABLED: bool = False  # legacy flag, kept for backward compatibility
    SUBSCRIPTION_ENFORCEMENT: bool = False  # primary toggle: when False, can_write stays allowed
    CONNECTIONS_ENABLED: bool = True
    INTEGRATIONS_ENCRYPTION_KEY: str = "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA=="  # base64 fernet

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def _normalized_env_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _has_value(value: str | None) -> bool:
    return bool((value or "").strip())


def _is_public_https_url(value: str | None) -> bool:
    normalized = (value or "").strip()
    return normalized.startswith("https://") and not any(host in normalized for host in ("localhost", "127.0.0.1"))


def _mercadopago_is_active(settings: Settings) -> bool:
    # Mercado Pago is considered active only when the integration is actually configured.
    return _has_value(settings.MP_ACCESS_TOKEN) or (
        _has_value(settings.MERCADOPAGO_CLIENT_ID) and _has_value(settings.MERCADOPAGO_CLIENT_SECRET)
    )


def _paypal_is_active(settings: Settings) -> bool:
    return _has_value(settings.PAYPAL_CLIENT_ID) and _has_value(settings.PAYPAL_CLIENT_SECRET)


def _gmail_is_active(settings: Settings) -> bool:
    return _has_value(settings.GMAIL_CLIENT_ID) and _has_value(settings.GMAIL_CLIENT_SECRET)


def is_demo_mode() -> bool:
    return _normalized_env_value(os.getenv("DEMO_MODE")) in {"1", "true", "yes", "on"}


def is_testing_mode() -> bool:
    return _normalized_env_value(os.getenv("TESTING")) in {"1", "true", "yes", "on"}


def is_production_mode(settings: Settings | None = None) -> bool:
    runtime_settings = settings or get_settings()
    env = _normalized_env_value(runtime_settings.APP_ENV or os.getenv("ENVIRONMENT") or os.getenv("APP_ENV"))
    return env in {"prod", "production"}


def validate_runtime_security(settings: Settings | None = None) -> None:
    """
    Fail fast if the app is being started in production with placeholder secrets.
    Dev/test/demo are intentionally permissive so the local harness keeps working.
    """
    runtime_settings = settings or get_settings()
    if not is_production_mode(runtime_settings):
        return

    errors: list[str] = []

    if not runtime_settings.JWT_SECRET or runtime_settings.JWT_SECRET == "change-me" or len(runtime_settings.JWT_SECRET.strip()) < 32:
        errors.append("JWT_SECRET must be set to a strong production value")

    if (
        runtime_settings.ACCESS_TOKEN_SECRET
        and runtime_settings.SIGNED_TOKEN_SECRET
        and runtime_settings.ACCESS_TOKEN_SECRET == runtime_settings.SIGNED_TOKEN_SECRET
    ):
        errors.append("ACCESS_TOKEN_SECRET and SIGNED_TOKEN_SECRET must be distinct in production")

    manager_pin = str(runtime_settings.MANAGER_PIN or "").strip()
    if not manager_pin or manager_pin == "1234" or len(manager_pin) < 6 or not manager_pin.isdigit():
        errors.append("MANAGER_PIN must be at least 6 digits and not the default")

    try:
        Fernet(runtime_settings.INTEGRATIONS_ENCRYPTION_KEY.encode())
    except Exception:
        errors.append("INTEGRATIONS_ENCRYPTION_KEY must be a valid Fernet key in production")
    else:
        if runtime_settings.INTEGRATIONS_ENCRYPTION_KEY == "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==":
            errors.append("INTEGRATIONS_ENCRYPTION_KEY cannot use the bundled default in production")

    if not _is_public_https_url(runtime_settings.APP_BASE_URL):
        errors.append("APP_BASE_URL must be a public https URL in production")

    # Optional integrations only become mandatory when their real credentials are configured.
    mercadopago_active = _mercadopago_is_active(runtime_settings)
    paypal_active = _paypal_is_active(runtime_settings)
    gmail_active = _gmail_is_active(runtime_settings)

    if mercadopago_active and not runtime_settings.MERCADOPAGO_WEBHOOK_SECRET.strip():
        errors.append("MERCADOPAGO_WEBHOOK_SECRET must be configured when Mercado Pago is enabled")

    # OAuth redirect URIs: only validate when the respective service is configured
    # (only check when the integration is truly enabled)
    conditional_redirect_uris = [
        ("PAYPAL_REDIRECT_URI", runtime_settings.PAYPAL_REDIRECT_URI, paypal_active),
        ("MERCADOPAGO_REDIRECT_URI", runtime_settings.MERCADOPAGO_REDIRECT_URI, mercadopago_active),
        ("GMAIL_REDIRECT_URI", runtime_settings.GMAIL_REDIRECT_URI, gmail_active),
    ]
    for name, value, service_configured in conditional_redirect_uris:
        if service_configured and not _is_public_https_url(value):
            errors.append(f"{name} must be a public https URL when the integration is enabled")

    if errors:
        raise RuntimeError("Invalid production security configuration: " + "; ".join(errors))
