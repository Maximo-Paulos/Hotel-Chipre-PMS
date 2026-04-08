"""
Application Configuration.
Uses pydantic-settings for environment variable management.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Global application settings loaded from environment variables."""

    # Public app URL used in redirects/webhooks
    APP_BASE_URL: str = "http://127.0.0.1:8040"

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
    PAYPAL_REDIRECT_URI: str = "http://localhost:8000/api/integrations/paypal/callback"
    MERCADOPAGO_REDIRECT_URI: str = "http://localhost:8000/api/integrations/mercadopago/callback"
    GMAIL_CLIENT_ID: str = ""
    GMAIL_CLIENT_SECRET: str = ""
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/api/integrations/gmail/callback"
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

    # SMTP / Email
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_FROM: str = "Hotel PMS <noreply@example.com>"
    SMTP_STARTUP_NOTIFY: bool = False

    # Auth
    JWT_SECRET: str = "change-me"
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
