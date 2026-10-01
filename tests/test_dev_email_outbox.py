from __future__ import annotations

import json
from types import SimpleNamespace

import app.master_admin.email_provider as email_provider


def test_closed_nonproduction_without_outbox_override_uses_temp_file(monkeypatch, tmp_path):
    settings = SimpleNamespace(
        APP_ENV="development",
        DEV_EMAIL_OUTBOX_PATH="",
        EMAIL_PROVIDER="null",
        SYSTEM_EMAIL_FROM="",
        SYSTEM_EMAIL_REPLY_TO="",
    )
    provider = SimpleNamespace(provider_name="null")
    monkeypatch.setattr(email_provider, "get_settings", lambda: settings)
    monkeypatch.setattr(email_provider, "is_production_mode", lambda _: False)
    monkeypatch.setattr(email_provider, "external_effects_enabled", lambda _: False)
    monkeypatch.setattr(email_provider, "get_email_provider", lambda *_: provider)
    monkeypatch.setattr(email_provider.tempfile, "gettempdir", lambda: str(tmp_path))

    result = email_provider.send_system_email(
        None,
        "owner@test.com",
        "Verify local owner",
        "Synthetic verification code: 123456",
    )

    outbox = tmp_path / "hotel-chipre-dev-email-outbox.jsonl"
    messages = [json.loads(line) for line in outbox.read_text(encoding="utf-8").splitlines()]
    assert result["channel"] == "dev_noop"
    assert messages[0]["to"] == ["owner@test.com"]
    assert "123456" in messages[0]["body"]
