"""Shared, secret-safe binding for the Render QA bootstrap configuration."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping


BOOTSTRAP_CONFIGURATION_VERSION = "qa-bootstrap-config-v1"
BOOTSTRAP_CONFIGURATION_KEYS = (
    "AI_ENABLED",
    "AI_PROVIDER",
    "APP_ENV",
    "CONNECTIONS_ENABLED",
    "EMAIL_PROVIDER",
    "GEMMA_ENABLED",
    "GEMMA_PROVIDER",
    "MASTER_ADMIN_EMAIL",
    "MASTER_ADMIN_PASSWORD",
    "MASTER_ADMIN_PIN",
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
