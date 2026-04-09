from __future__ import annotations

from cryptography.fernet import Fernet
import pytest

from app.config import get_settings
from app.services.integration_service import decrypt_payload


def test_decrypt_payload_returns_empty_dict_in_development_for_corrupted_ciphertext(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("INTEGRATIONS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()

    assert decrypt_payload({"ciphertext": "not-a-valid-token"}) == {}
    get_settings.cache_clear()


def test_decrypt_payload_raises_in_production_for_corrupted_ciphertext(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INTEGRATIONS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()

    with pytest.raises(ValueError):
        decrypt_payload({"ciphertext": "not-a-valid-token"})
    get_settings.cache_clear()
