"""Validation helpers for reservation communication email addresses."""

from __future__ import annotations

import os

import email_validator

from app.config import get_settings, is_preview_qa_mode, is_production_mode, is_test_mode


LOCAL_SYNTHETIC_EMAIL_DOMAIN = "example.test"


def _is_example_test_address(candidate: str) -> bool:
    domain = candidate.rsplit("@", 1)[-1].strip().lower()
    return domain == LOCAL_SYNTHETIC_EMAIL_DOMAIN or domain.endswith(
        f".{LOCAL_SYNTHETIC_EMAIL_DOMAIN}"
    )


def local_synthetic_email_addresses_enabled() -> bool:
    """Allow reserved synthetic addresses only in isolated local/test modes."""
    settings = get_settings()
    if is_production_mode(settings) or is_preview_qa_mode(settings):
        return False
    restricted_labels = {"preview", "qa", "staging", "prod", "production", "live"}
    if any(
        str(value or "").strip().lower() in restricted_labels
        for value in (settings.APP_ENV, os.getenv("APP_ENV"), os.getenv("ENVIRONMENT"))
    ):
        return False
    if is_test_mode():
        return True

    return (
        str(settings.APP_ENV or "").strip().lower() == "development"
        and str(settings.EMAIL_PROVIDER or "").strip().lower() == "null"
        and settings.EXTERNAL_EFFECTS_ENABLED is False
        and settings.CONNECTIONS_ENABLED is False
    )


def normalize_reservation_email(value: object) -> str:
    """Validate and normalize an email, narrowly allowing local ``example.test``.

    The reserved domain is accepted only under explicitly isolated local/test
    settings. Other special-use domains continue to use email-validator's
    normal strict behavior.
    """
    candidate = str(value or "").strip()
    if not candidate:
        raise ValueError("An email address is required")

    allow_synthetic = (
        _is_example_test_address(candidate)
        and local_synthetic_email_addresses_enabled()
    )
    validated = email_validator.validate_email(
        candidate,
        check_deliverability=False,
        test_environment=allow_synthetic,
    )
    return validated.normalized


def is_local_synthetic_reservation_email(value: str) -> bool:
    """Return whether a validated recipient belongs to the local reserved domain."""
    return _is_example_test_address(value)
