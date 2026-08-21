"""
Application Configuration.
Uses pydantic-settings for environment variable management.
"""
import hmac
import os
from urllib.parse import urlsplit
from cryptography.fernet import Fernet
from pydantic import AliasChoices, Field
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

    # Extra CORS origins (comma-separated), read directly via os.getenv in
    # app/main.py; declared here only so pydantic-settings (extra="forbid" by
    # default) doesn't crash when this documented, commonly-set var is present.
    CORS_ORIGINS: str = ""

    # Database
    DATABASE_URL: str = "postgresql+psycopg2://pms:pms@localhost:5432/hotel_pms"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"
    READ_MODEL_CACHE_ENABLED: bool = True
    READ_MODEL_AVAILABILITY_TTL_SECONDS: int = 15
    READ_MODEL_ANALYTICS_TTL_SECONDS: int = 60
    DISTRIBUTED_LOCK_ENABLED: bool = True
    DISTRIBUTED_LOCK_REQUIRED: bool = False
    DISTRIBUTED_LOCK_DEFAULT_TTL_SECONDS: int = 60
    REALTIME_EVENTS_ENABLED: bool = True
    REALTIME_EVENTS_HEARTBEAT_SECONDS: int = 15
    CLICKHOUSE_ENABLED: bool = False
    CLICKHOUSE_REQUIRED: bool = False
    CLICKHOUSE_URL: str = ""
    CLICKHOUSE_DATABASE: str = "hotel_analytics"
    CLICKHOUSE_USER: str = "default"
    CLICKHOUSE_PASSWORD: str = ""
    CLICKHOUSE_TIMEOUT_SECONDS: float = 5.0

    # NoSQL datastore foundations. Disabled by default; Postgres remains the
    # transactional source of truth.
    MONGO_URL: str = "mongodb://localhost:27017"
    MONGO_DB: str = "hotel_pms"
    MONGO_ENABLED: bool = False
    CASSANDRA_HOSTS: str = "localhost"
    CASSANDRA_KEYSPACE: str = "hotel_pms"
    CASSANDRA_ENABLED: bool = False
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j"
    NEO4J_ENABLED: bool = False

    # MercadoPago
    MP_ACCESS_TOKEN: str = ""
    MP_PUBLIC_KEY: str = ""

    # PayPal
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_MODE: str = "sandbox"  # "sandbox" or "live"
    PAYPAL_WEBHOOK_ID: str = ""

    # OAuth client IDs for connections
    MERCADOPAGO_CLIENT_ID: str = ""
    MERCADOPAGO_CLIENT_SECRET: str = ""
    PAYPAL_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/paypal/callback"
    MERCADOPAGO_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/mercadopago/callback"
    EMAIL_PROVIDER: str = "resend"
    RESEND_API_KEY: str = ""
    SYSTEM_EMAIL_FROM: str = "Hotel Chipre PMS <noreply@auth.hotels-pms.com>"
    SYSTEM_EMAIL_REPLY_TO: str = "hotelxpms@gmail.com"
    DEV_EMAIL_OUTBOX_PATH: str = ""
    GMAIL_CLIENT_ID: str = Field(default="", validation_alias=AliasChoices("GMAIL_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_ID"))
    GMAIL_CLIENT_SECRET: str = Field(default="", validation_alias=AliasChoices("GMAIL_CLIENT_SECRET", "GOOGLE_OAUTH_CLIENT_SECRET"))
    GMAIL_REDIRECT_URI: str = "http://127.0.0.1:8040/api/integrations/oauth/gmail/callback"
    MERCADOPAGO_WEBHOOK_SECRET: str = ""

    # External-effect safety policy. ``None`` is intentionally distinct from
    # ``False``: production must state every decision explicitly, while every
    # runtime guard treats an unset value as disabled (fail closed).
    EXTERNAL_EFFECTS_ENABLED: bool | None = None
    INBOUND_PROVIDER_EVENTS_ENABLED: bool | None = None
    GOOGLE_LOGIN_ENABLED: bool | None = None
    APPLE_LOGIN_ENABLED: bool | None = None

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
    MASTER_ADMIN_EMAIL: str = ""
    MASTER_ADMIN_PASSWORD: str = ""
    MASTER_ADMIN_PIN: str = Field(default="1234", validation_alias=AliasChoices("MASTER_ADMIN_PIN", "MANAGER_PIN"))
    MASTER_ADMIN_COOKIE_SECURE: bool | None = None
    MASTER_ADMIN_SESSION_SECRET: str = ""
    # Absolute master-admin session lifetime; forces periodic re-login even
    # with activity. Keep separate from the shorter high-privilege idle TTL.
    MASTER_ADMIN_SESSION_TTL_MINUTES: int = 8 * 60
    # Master-admin can access data from every hotel, so expire idle sessions
    # quickly when a privileged workstation is left unattended.
    MASTER_ADMIN_IDLE_TTL_MINUTES: int = 20
    MASTER_ADMIN_MAX_ATTEMPTS: int = 5
    MASTER_ADMIN_LOCKOUT_MINUTES: int = 15

    # Generic AI provider for Analytics. When unset, Analytics falls back to the legacy GEMMA_* values.
    AI_ENABLED: bool | None = None
    AI_PROVIDER: str = ""  # disabled, gemma, openai, openai_compatible, auto
    AI_BASE_URL: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_TIMEOUT_SECONDS: float | None = None
    AI_MAX_OUTPUT_TOKENS: int | None = None
    AI_TEMPERATURE: float | None = None
    AI_STRICT_JSON: bool | None = None
    AI_MONTHLY_QUOTA: int | None = None

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
    # Relative to the process working dir (repo root); override with an absolute path in prod.
    ANALYTICS_EXPORTS_DIR: str = "./var/exports/analytics"

    # "Sign in with Google" (Google Identity Services ID-token flow). Only a
    # Client ID is needed -- no secret -- because the frontend gets a signed
    # JWT straight from Google and the backend just verifies its signature.
    GOOGLE_CLIENT_ID: str = ""

    # Sign in with Apple. The private key is never stored in this repository;
    # production points APPLE_PRIVATE_KEY_PATH at a mounted secret file.
    APPLE_CLIENT_ID: str = ""
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""
    APPLE_PRIVATE_KEY_PATH: str = ""
    APPLE_REDIRECT_URI: str = "http://127.0.0.1:8040/api/auth/apple/callback"

    # Auth
    JWT_SECRET: str = "change-me"
    ACCESS_TOKEN_SECRET: str = ""
    SIGNED_TOKEN_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 720  # 12h: there is no refresh flow, so a short TTL logs staff out mid-shift
    DEFAULT_SUBSCRIPTION_PLAN: str = "starter"
    LOGIN_RATE_LIMIT: int = 5  # attempts per window
    SUBSCRIPTION_ENFORCEMENT_ENABLED: bool = False  # legacy flag, kept for backward compatibility
    SUBSCRIPTION_ENFORCEMENT: bool = False  # primary toggle: when False, can_write stays allowed
    CONNECTIONS_ENABLED: bool = True
    INTEGRATIONS_ENCRYPTION_KEY: str = "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA=="  # base64 fernet

    # Notification backend (Task 8). Off by default: a hotel that never
    # configures these must never silently start sending real push/email.
    NOTIFICATION_EMAIL_ENABLED: bool = False
    WEB_PUSH_ENABLED: bool = False
    WEB_PUSH_VAPID_PUBLIC_KEY: str = ""
    WEB_PUSH_VAPID_PRIVATE_KEY: str = ""
    WEB_PUSH_VAPID_SUBJECT: str = ""  # mailto: or https: contact per the Web Push spec

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def _normalized_env_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _has_value(value: str | None) -> bool:
    return bool((value or "").strip())


def _cors_contains_wildcard(settings: Settings) -> bool:
    return any(entry.strip() == "*" for entry in (settings.CORS_ORIGINS or "").split(","))


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


def _resend_is_active(settings: Settings) -> bool:
    return _normalized_env_value(settings.EMAIL_PROVIDER) == "resend"


def is_demo_mode() -> bool:
    return _normalized_env_value(os.getenv("DEMO_MODE")) in {"1", "true", "yes", "on"}


def is_testing_mode() -> bool:
    return _normalized_env_value(os.getenv("TESTING")) in {"1", "true", "yes", "on"}


def is_test_mode() -> bool:
    """True for pytest (TESTING=1) and the isolated Playwright E2E backend
    (APP_ENV=test, set by frontend/playwright.config.ts). Used only to allow
    RFC 2606 reserved TLDs (.test, .invalid, .localhost, ...) in synthetic
    email addresses during automated testing -- never in production."""
    return is_testing_mode() or _normalized_env_value(os.getenv("APP_ENV")) == "test"


def is_production_mode(settings: Settings | None = None) -> bool:
    runtime_settings = settings or get_settings()
    env = _normalized_env_value(runtime_settings.APP_ENV or os.getenv("ENVIRONMENT") or os.getenv("APP_ENV"))
    return env in {"prod", "production"}


def is_preview_qa_mode(settings: Settings | None = None) -> bool:
    runtime_settings = settings or get_settings()
    env = _normalized_env_value(
        runtime_settings.APP_ENV or os.getenv("ENVIRONMENT") or os.getenv("APP_ENV")
    )
    return env in {"preview", "qa", "staging"}


def _validate_preview_qa_security(runtime_settings: Settings) -> None:
    """Fail closed when a cloud QA service could reach a live integration."""

    errors: list[str] = []

    exact_values = {
        "EMAIL_PROVIDER": (runtime_settings.EMAIL_PROVIDER, "null"),
        "PAYPAL_MODE": (runtime_settings.PAYPAL_MODE, "sandbox"),
        "AI_PROVIDER": (runtime_settings.AI_PROVIDER, "disabled"),
        "GEMMA_PROVIDER": (runtime_settings.GEMMA_PROVIDER, "disabled"),
    }
    for name, (value, expected) in exact_values.items():
        if _normalized_env_value(value) != expected:
            errors.append(f"{name} must be {expected} in preview QA")
    if runtime_settings.CONNECTIONS_ENABLED:
        errors.append("CONNECTIONS_ENABLED must be false in preview QA")
    if runtime_settings.EXTERNAL_EFFECTS_ENABLED is not False:
        errors.append("EXTERNAL_EFFECTS_ENABLED must be explicitly false in preview QA")
    if runtime_settings.INBOUND_PROVIDER_EVENTS_ENABLED is not False:
        errors.append("INBOUND_PROVIDER_EVENTS_ENABLED must be explicitly false in preview QA")
    if runtime_settings.GOOGLE_LOGIN_ENABLED is not False:
        errors.append("GOOGLE_LOGIN_ENABLED must be explicitly false in preview QA")
    if runtime_settings.APPLE_LOGIN_ENABLED is not False:
        errors.append("APPLE_LOGIN_ENABLED must be explicitly false in preview QA")
    if runtime_settings.AI_ENABLED is not False:
        errors.append("AI_ENABLED must be explicitly false in preview QA")
    if runtime_settings.GEMMA_ENABLED:
        errors.append("GEMMA_ENABLED must be false in preview QA")
    if runtime_settings.READ_MODEL_CACHE_ENABLED:
        errors.append("READ_MODEL_CACHE_ENABLED must be false in preview QA")
    if runtime_settings.MONGO_ENABLED:
        errors.append("MONGO_ENABLED must be false in preview QA")
    if runtime_settings.CASSANDRA_ENABLED:
        errors.append("CASSANDRA_ENABLED must be false in preview QA")
    if runtime_settings.NEO4J_ENABLED:
        errors.append("NEO4J_ENABLED must be false in preview QA")
    if runtime_settings.MASTER_ADMIN_COOKIE_SECURE is not True:
        errors.append("MASTER_ADMIN_COOKIE_SECURE must be true in preview QA")
    if _cors_contains_wildcard(runtime_settings):
        errors.append("CORS_ORIGINS must not contain * in preview QA")

    if (
        not runtime_settings.JWT_SECRET
        or runtime_settings.JWT_SECRET == "change-me"
        or len(runtime_settings.JWT_SECRET.strip()) < 32
    ):
        errors.append("JWT_SECRET must be set to a strong preview-only value")
    try:
        Fernet(runtime_settings.INTEGRATIONS_ENCRYPTION_KEY.encode())
    except Exception:
        errors.append("INTEGRATIONS_ENCRYPTION_KEY must be a valid Fernet key in preview QA")
    else:
        if runtime_settings.INTEGRATIONS_ENCRYPTION_KEY == "ZGVmYXVsdC1pbnRlZ3JhdGlvbnMta2V5LXNlY3JldA==":
            errors.append("INTEGRATIONS_ENCRYPTION_KEY cannot use the bundled default in preview QA")
    if not _has_value(runtime_settings.MASTER_ADMIN_EMAIL) or "@" not in runtime_settings.MASTER_ADMIN_EMAIL:
        errors.append("MASTER_ADMIN_EMAIL must be a distinct QA identity")
    if len((runtime_settings.MASTER_ADMIN_PASSWORD or "").strip()) < 12:
        errors.append("MASTER_ADMIN_PASSWORD must be a strong preview-only value")
    manager_pin = str(runtime_settings.MASTER_ADMIN_PIN or "").strip()
    if not manager_pin.isdigit() or len(manager_pin) < 6 or manager_pin == "1234":
        errors.append("MASTER_ADMIN_PIN must be at least 6 digits and not the default in preview QA")
    if (
        runtime_settings.ACCESS_TOKEN_SECRET
        and runtime_settings.SIGNED_TOKEN_SECRET
        and hmac.compare_digest(
            runtime_settings.ACCESS_TOKEN_SECRET,
            runtime_settings.SIGNED_TOKEN_SECRET,
        )
    ):
        errors.append("ACCESS_TOKEN_SECRET and SIGNED_TOKEN_SECRET must be distinct in preview QA")

    local_url_fields = {
        "REDIS_URL": runtime_settings.REDIS_URL,
        "CELERY_BROKER_URL": runtime_settings.CELERY_BROKER_URL,
        "CELERY_RESULT_BACKEND": runtime_settings.CELERY_RESULT_BACKEND,
        "MONGO_URL": runtime_settings.MONGO_URL,
        "NEO4J_URI": runtime_settings.NEO4J_URI,
    }
    for name, value in local_url_fields.items():
        hostname = (urlsplit(value).hostname or "").lower()
        if hostname not in {"localhost", "127.0.0.1", "::1"}:
            errors.append(f"{name} must remain loopback-only while disabled in preview QA")
    cassandra_hosts = {
        value.strip().lower().removeprefix("[").removesuffix("]")
        for value in runtime_settings.CASSANDRA_HOSTS.split(",")
        if value.strip()
    }
    if not cassandra_hosts or not cassandra_hosts <= {"localhost", "127.0.0.1", "::1"}:
        errors.append("CASSANDRA_HOSTS must remain loopback-only while disabled in preview QA")

    forbidden_values = {
        "AI_API_KEY": runtime_settings.AI_API_KEY,
        "AI_BASE_URL": runtime_settings.AI_BASE_URL,
        "BOOKING_USERNAME": runtime_settings.BOOKING_USERNAME,
        "BOOKING_PASSWORD": runtime_settings.BOOKING_PASSWORD,
        "EXPEDIA_API_KEY": runtime_settings.EXPEDIA_API_KEY,
        "EXPEDIA_HOTEL_ID": runtime_settings.EXPEDIA_HOTEL_ID,
        "GMAIL_CLIENT_ID": runtime_settings.GMAIL_CLIENT_ID,
        "GMAIL_CLIENT_SECRET": runtime_settings.GMAIL_CLIENT_SECRET,
        "GEMMA_API_KEY": runtime_settings.GEMMA_API_KEY,
        "GEMMA_ENDPOINT_URL": runtime_settings.GEMMA_ENDPOINT_URL,
        "MERCADOPAGO_CLIENT_ID": runtime_settings.MERCADOPAGO_CLIENT_ID,
        "MERCADOPAGO_CLIENT_SECRET": runtime_settings.MERCADOPAGO_CLIENT_SECRET,
        "MERCADOPAGO_WEBHOOK_SECRET": runtime_settings.MERCADOPAGO_WEBHOOK_SECRET,
        "MP_ACCESS_TOKEN": runtime_settings.MP_ACCESS_TOKEN,
        "MP_PUBLIC_KEY": runtime_settings.MP_PUBLIC_KEY,
        "PAYPAL_CLIENT_ID": runtime_settings.PAYPAL_CLIENT_ID,
        "PAYPAL_CLIENT_SECRET": runtime_settings.PAYPAL_CLIENT_SECRET,
        "PAYPAL_WEBHOOK_ID": runtime_settings.PAYPAL_WEBHOOK_ID,
        "RESEND_API_KEY": runtime_settings.RESEND_API_KEY,
        "WEB_PUSH_VAPID_PRIVATE_KEY": runtime_settings.WEB_PUSH_VAPID_PRIVATE_KEY,
    }
    configured = sorted(name for name, value in forbidden_values.items() if _has_value(value))
    if configured:
        errors.append(
            "live integration credentials must be absent in preview QA: "
            + ", ".join(configured)
        )
    if errors:
        raise RuntimeError("Invalid preview QA security configuration: " + "; ".join(errors))


def validate_runtime_security(settings: Settings | None = None) -> None:
    """
    Fail fast if the app is being started in production with placeholder secrets.
    Dev/test/demo are intentionally permissive so the local harness keeps working.
    """
    runtime_settings = settings or get_settings()
    if is_preview_qa_mode(runtime_settings):
        _validate_preview_qa_security(runtime_settings)
        return
    if not is_production_mode(runtime_settings):
        return

    errors: list[str] = []

    for flag_name in (
        "EXTERNAL_EFFECTS_ENABLED",
        "INBOUND_PROVIDER_EVENTS_ENABLED",
        "GOOGLE_LOGIN_ENABLED",
        "APPLE_LOGIN_ENABLED",
    ):
        if getattr(runtime_settings, flag_name) is None:
            errors.append(f"{flag_name} must be explicitly true or false in production")

    # A production-labelled sandbox is selected by explicitly disabling the
    # global outbound lane. It must then match the complete non-live provider
    # profile; retaining credentials is allowed, but no setting may make them
    # usable. A future real production deployment remains possible only by
    # explicitly setting EXTERNAL_EFFECTS_ENABLED=true.
    if runtime_settings.EXTERNAL_EFFECTS_ENABLED is False:
        sandbox_exact_values = {
            "EMAIL_PROVIDER": (runtime_settings.EMAIL_PROVIDER, "null"),
            "AI_PROVIDER": (runtime_settings.AI_PROVIDER, "disabled"),
            "GEMMA_PROVIDER": (runtime_settings.GEMMA_PROVIDER, "disabled"),
            "PAYPAL_MODE": (runtime_settings.PAYPAL_MODE, "sandbox"),
        }
        for name, (value, expected) in sandbox_exact_values.items():
            if _normalized_env_value(value) != expected:
                errors.append(
                    f"{name} must be {expected} when EXTERNAL_EFFECTS_ENABLED=false in production"
                )
        sandbox_false_values = {
            "INBOUND_PROVIDER_EVENTS_ENABLED": runtime_settings.INBOUND_PROVIDER_EVENTS_ENABLED,
            "GOOGLE_LOGIN_ENABLED": runtime_settings.GOOGLE_LOGIN_ENABLED,
            "APPLE_LOGIN_ENABLED": runtime_settings.APPLE_LOGIN_ENABLED,
            "CONNECTIONS_ENABLED": runtime_settings.CONNECTIONS_ENABLED,
            "AI_ENABLED": runtime_settings.AI_ENABLED,
            "GEMMA_ENABLED": runtime_settings.GEMMA_ENABLED,
        }
        for name, value in sandbox_false_values.items():
            if value is not False:
                errors.append(
                    f"{name} must be explicitly false when EXTERNAL_EFFECTS_ENABLED=false in production"
                )

    if not runtime_settings.DISTRIBUTED_LOCK_ENABLED or not runtime_settings.DISTRIBUTED_LOCK_REQUIRED:
        errors.append("DISTRIBUTED_LOCK_ENABLED and DISTRIBUTED_LOCK_REQUIRED must be true in production")
    if runtime_settings.MASTER_ADMIN_COOKIE_SECURE is False:
        errors.append("MASTER_ADMIN_COOKIE_SECURE must not be false in production")
    if _cors_contains_wildcard(runtime_settings):
        errors.append("CORS_ORIGINS must not contain * in production")
    if runtime_settings.CLICKHOUSE_REQUIRED and (
        not runtime_settings.CLICKHOUSE_ENABLED or not runtime_settings.CLICKHOUSE_URL.strip()
    ):
        errors.append("CLICKHOUSE_ENABLED and CLICKHOUSE_URL must be configured when CLICKHOUSE_REQUIRED=true")

    if not runtime_settings.JWT_SECRET or runtime_settings.JWT_SECRET == "change-me" or len(runtime_settings.JWT_SECRET.strip()) < 32:
        errors.append("JWT_SECRET must be set to a strong production value")

    if (
        runtime_settings.ACCESS_TOKEN_SECRET
        and runtime_settings.SIGNED_TOKEN_SECRET
        and runtime_settings.ACCESS_TOKEN_SECRET == runtime_settings.SIGNED_TOKEN_SECRET
    ):
        errors.append("ACCESS_TOKEN_SECRET and SIGNED_TOKEN_SECRET must be distinct in production")

    manager_pin = str(runtime_settings.MASTER_ADMIN_PIN or "").strip()
    if not manager_pin or manager_pin == "1234" or len(manager_pin) < 6 or not manager_pin.isdigit():
        errors.append("MASTER_ADMIN_PIN must be at least 6 digits and not the default")

    # Bootstrap master-admin login is optional in production (an empty
    # password disables it, since _bootstrap_master_credentials_match
    # requires both fields truthy), but if it IS configured it must be as
    # strong as the preview QA requirement, not just "whatever was typed".
    if _has_value(runtime_settings.MASTER_ADMIN_EMAIL) and "@" not in runtime_settings.MASTER_ADMIN_EMAIL:
        errors.append("MASTER_ADMIN_EMAIL must be a valid email address")
    if _has_value(runtime_settings.MASTER_ADMIN_PASSWORD) and len(runtime_settings.MASTER_ADMIN_PASSWORD.strip()) < 12:
        errors.append("MASTER_ADMIN_PASSWORD must be a strong value (12+ chars) when configured")

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
    resend_active = _resend_is_active(runtime_settings)

    if (
        runtime_settings.INBOUND_PROVIDER_EVENTS_ENABLED is True
        and mercadopago_active
        and not runtime_settings.MERCADOPAGO_WEBHOOK_SECRET.strip()
    ):
        errors.append("MERCADOPAGO_WEBHOOK_SECRET must be configured when Mercado Pago is enabled")

    if runtime_settings.EXTERNAL_EFFECTS_ENABLED is True and resend_active:
        if not _has_value(runtime_settings.RESEND_API_KEY):
            errors.append("RESEND_API_KEY must be configured when EMAIL_PROVIDER=resend")
        if not _has_value(runtime_settings.SYSTEM_EMAIL_FROM):
            errors.append("SYSTEM_EMAIL_FROM must be configured when EMAIL_PROVIDER=resend")
        if not _has_value(runtime_settings.SYSTEM_EMAIL_REPLY_TO):
            errors.append("SYSTEM_EMAIL_REPLY_TO must be configured when EMAIL_PROVIDER=resend")

    # OAuth redirect URIs: only validate when the respective service is configured
    # (only check when the integration is truly enabled)
    conditional_redirect_uris = [
        (
            "PAYPAL_REDIRECT_URI",
            runtime_settings.PAYPAL_REDIRECT_URI,
            runtime_settings.EXTERNAL_EFFECTS_ENABLED is True and paypal_active,
        ),
        (
            "MERCADOPAGO_REDIRECT_URI",
            runtime_settings.MERCADOPAGO_REDIRECT_URI,
            runtime_settings.EXTERNAL_EFFECTS_ENABLED is True and mercadopago_active,
        ),
        (
            "GMAIL_REDIRECT_URI",
            runtime_settings.GMAIL_REDIRECT_URI,
            runtime_settings.EXTERNAL_EFFECTS_ENABLED is True and gmail_active,
        ),
    ]
    for name, value, service_configured in conditional_redirect_uris:
        if service_configured and not _is_public_https_url(value):
            errors.append(f"{name} must be a public https URL when the integration is enabled")

    if runtime_settings.GOOGLE_LOGIN_ENABLED is True and not _has_value(runtime_settings.GOOGLE_CLIENT_ID):
        errors.append("GOOGLE_CLIENT_ID must be configured when GOOGLE_LOGIN_ENABLED=true")

    if runtime_settings.APPLE_LOGIN_ENABLED is True:
        apple_required = {
            "APPLE_CLIENT_ID": runtime_settings.APPLE_CLIENT_ID,
            "APPLE_TEAM_ID": runtime_settings.APPLE_TEAM_ID,
            "APPLE_KEY_ID": runtime_settings.APPLE_KEY_ID,
            "APPLE_PRIVATE_KEY_PATH": runtime_settings.APPLE_PRIVATE_KEY_PATH,
            "APPLE_REDIRECT_URI": runtime_settings.APPLE_REDIRECT_URI,
        }
        for name, value in apple_required.items():
            if not _has_value(value):
                errors.append(f"{name} must be configured when APPLE_LOGIN_ENABLED=true")
        if _has_value(runtime_settings.APPLE_REDIRECT_URI) and not _is_public_https_url(runtime_settings.APPLE_REDIRECT_URI):
            errors.append("APPLE_REDIRECT_URI must be a public https URL when APPLE_LOGIN_ENABLED=true")

    if errors:
        raise RuntimeError("Invalid production security configuration: " + "; ".join(errors))
