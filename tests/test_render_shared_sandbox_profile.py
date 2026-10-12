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
        assert len(declarations) == 2, f"{key} must be explicit on the web API and SQL cron"


def test_render_keeps_database_migration_in_predeploy() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")

    assert "preDeployCommand: python -m alembic upgrade head" in text


def test_render_budget_profile_uses_one_sql_only_api_and_cron() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert len(re.findall(r"(?m)^  - type: web$", text)) == 1
    assert len(re.findall(r"(?m)^  - type: cron$", text)) == 1
    assert not re.search(r"(?m)^  - type: (?:worker|keyvalue|redis)$", text)
    assert "name: hotel-chipre-pms-api\n    runtime: python\n    plan: starter\n    numInstances: 1" in text
    assert "name: hotel-chipre-pms-scheduled-hotel-jobs\n    runtime: python\n    plan: starter\n    schedule: \"*/5 * * * *\"" in text
    assert "startCommand: python -m app.tasks.run_scheduled_hotel_jobs" in text
    assert "value: postgresql" in text
    assert "value: process" in text
    assert "value: \"\"" in text
    assert "key: CLICKHOUSE_REQUIRED\n        value: \"false\"" in text
    assert "key: CELERY_BROKER_URL" not in text
    assert "key: CELERY_RESULT_BACKEND" not in text


def test_example_realtime_profile_uses_postgresql_and_bounded_fallback() -> None:
    text = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "REALTIME_EVENTS_TRANSPORT=postgresql" in text
    assert "REALTIME_EVENTS_FALLBACK_POLL_SECONDS=60" in text
