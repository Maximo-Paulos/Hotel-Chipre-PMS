"""Shared Fernet encryption for secrets stored in the database.

The integration encryption key is intentionally reused for TOTP secrets in
this first MFA slice. Runtime security validation already requires this key
to be a strong, operator-provided Fernet key in preview and production.
"""
import base64
import hashlib

from cryptography.fernet import Fernet

from app.config import get_settings, is_production_mode


def get_encryption_fernet() -> Fernet:
    """Return the repository's existing Fernet instance for stored secrets."""
    raw_key = get_settings().INTEGRATIONS_ENCRYPTION_KEY.encode()
    try:
        return Fernet(raw_key)
    except ValueError:
        if is_production_mode():
            raise ValueError("INTEGRATIONS_ENCRYPTION_KEY must be a valid Fernet key in production")
        # Keep local/dev setups stable even if the env value is not already a Fernet key.
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key).digest())
        return Fernet(derived)
