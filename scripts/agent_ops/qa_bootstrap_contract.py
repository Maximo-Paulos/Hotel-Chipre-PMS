"""Shared, secret-safe binding for the Render QA bootstrap configuration."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping


BOOTSTRAP_CONFIGURATION_VERSION = "qa-bootstrap-config-v2"
BOOTSTRAP_CONFIGURATION_KEYS = (
    "AI_ENABLED",
    "AI_PROVIDER",
    "APP_ENV",
    "CONNECTIONS_ENABLED",
    "DATABASE_URL",
    "EMAIL_PROVIDER",
    "GEMMA_ENABLED",
    "GEMMA_PROVIDER",
    "INTEGRATIONS_ENCRYPTION_KEY",
    "JWT_SECRET",
    "MASTER_ADMIN_COOKIE_SECURE",
    "MASTER_ADMIN_EMAIL",
    "MASTER_ADMIN_PASSWORD",
    "MASTER_ADMIN_PIN",
    "READ_MODEL_CACHE_ENABLED",
    "MONGO_ENABLED",
    "CASSANDRA_ENABLED",
    "NEO4J_ENABLED",
    "PAYPAL_MODE",
    "QA_EMAIL_DOMAIN",
    "QA_EMAIL_DOMAIN_IS_DEDICATED",
    "QA_HOUSEKEEPING_EMAIL",
    "QA_HOUSEKEEPING_PASSWORD",
    "QA_MANAGER_EMAIL",
    "QA_MANAGER_PASSWORD",
    "QA_MASTER_ADMIN_EMAIL",
    "QA_MASTER_ADMIN_PASSWORD",
    "QA_MASTER_ADMIN_PIN",
    "QA_OWNER_EMAIL",
    "QA_OWNER_PASSWORD",
    "QA_RECEPTION_EMAIL",
    "QA_RECEPTION_PASSWORD",
    "QA_RUN_ID",
    "QA_RUN_MIGRATIONS",
)
SAFE_QA_ENV_VALUES = {
    "AI_ENABLED": "false",
    "AI_PROVIDER": "disabled",
    "CONNECTIONS_ENABLED": "false",
    "EMAIL_PROVIDER": "null",
    "GEMMA_ENABLED": "false",
    "GEMMA_PROVIDER": "disabled",
    "MASTER_ADMIN_COOKIE_SECURE": "true",
    "READ_MODEL_CACHE_ENABLED": "false",
    "MONGO_ENABLED": "false",
    "CASSANDRA_ENABLED": "false",
    "NEO4J_ENABLED": "false",
    "PAYPAL_MODE": "sandbox",
}
FORBIDDEN_QA_CREDENTIAL_KEYS = {
    "AI_API_KEY",
    "AI_BASE_URL",
    "BOOKING_PASSWORD",
    "BOOKING_USERNAME",
    "EXPEDIA_API_KEY",
    "EXPEDIA_HOTEL_ID",
    "GEMMA_API_KEY",
    "GEMMA_ENDPOINT_URL",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "MERCADOPAGO_CLIENT_ID",
    "MERCADOPAGO_CLIENT_SECRET",
    "MERCADOPAGO_WEBHOOK_SECRET",
    "MP_ACCESS_TOKEN",
    "MP_PUBLIC_KEY",
    "PAYPAL_CLIENT_ID",
    "PAYPAL_CLIENT_SECRET",
    "PAYPAL_WEBHOOK_ID",
    "QA_PROVIDER_EVIDENCE_PRIVATE_KEY",
    "QA_PROVIDER_EVIDENCE_TOKEN",
    "RESEND_API_KEY",
    "REDIS_URL",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "MONGO_URL",
    "MONGO_DB",
    "CASSANDRA_HOSTS",
    "CASSANDRA_KEYSPACE",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
}
FINGERPRINT_RE = re.compile(r"sha256:[0-9a-f]{64}")


class BootstrapConfigurationError(ValueError):
    pass


def bootstrap_configuration_fingerprint(values: Mapping[str, str]) -> str:
    """Hash the exact provider-observed values without exposing them individually."""

    bound: dict[str, str] = {}
    for key in BOOTSTRAP_CONFIGURATION_KEYS:
        value = values.get(key)
        if not isinstance(value, str) or not value:
            raise BootstrapConfigurationError(
                f"QA bootstrap environment variable {key} is missing"
            )
        if "\x00" in value or "\r" in value or "\n" in value:
            raise BootstrapConfigurationError(
                f"QA bootstrap environment variable {key} is invalid"
            )
        bound[key] = value
    canonical = json.dumps(
        {"version": BOOTSTRAP_CONFIGURATION_VERSION, "values": bound},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()
