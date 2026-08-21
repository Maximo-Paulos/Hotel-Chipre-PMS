from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SAFE_VALUES = {
    "EXTERNAL_EFFECTS_ENABLED": "false",
    "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
    "CONNECTIONS_ENABLED": "false",
    "GOOGLE_LOGIN_ENABLED": "false",
    "APPLE_LOGIN_ENABLED": "false",
    "EMAIL_PROVIDER": "null",
    "AI_ENABLED": "false",
    "AI_PROVIDER": "disabled",
    "GEMMA_ENABLED": "false",
    "GEMMA_PROVIDER": "disabled",
    "PAYPAL_MODE": "sandbox",
}


def test_every_python_render_service_declares_the_safe_sandbox_profile() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")

    for key, value in SAFE_VALUES.items():
        declarations = re.findall(
            rf"- key: {re.escape(key)}\s+value: [\"']?{re.escape(value)}[\"']?\s*$",
            text,
            flags=re.MULTILINE,
        )
        assert len(declarations) == 3, f"{key} must be explicit on web, worker and beat"


def test_render_keeps_database_migration_in_predeploy() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "preDeployCommand: python -m alembic upgrade head" in text
