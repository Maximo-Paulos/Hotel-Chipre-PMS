from __future__ import annotations

from datetime import date
import os
import subprocess
import sys

from app.config import Settings
from app.services import analytics_warehouse
from app.tasks.celery_app import build_beat_schedule, celery_app


def test_derived_analytics_has_incremental_and_nightly_schedules():
    schedule = build_beat_schedule(
        Settings(EXTERNAL_EFFECTS_ENABLED=True, CONNECTIONS_ENABLED=True)
    )

    assert schedule["analytics-derived-facts-incremental"]["task"] == (
        "analytics.project_all_derived_facts_incremental"
    )
    assert schedule["analytics-derived-facts-incremental"]["schedule"] == 300.0
    assert schedule["analytics-derived-facts-nightly-reconciliation"]["task"] == (
        "analytics.reconcile_all_derived_facts_nightly"
    )


def test_sandbox_has_no_scheduled_network_tasks():
    assert build_beat_schedule(
        Settings(EXTERNAL_EFFECTS_ENABLED=False, CONNECTIONS_ENABLED=False)
    ) == {}
    assert build_beat_schedule(
        Settings(EXTERNAL_EFFECTS_ENABLED=True, CONNECTIONS_ENABLED=False)
    ) == {}


def _safe_worker_env() -> dict[str, str]:
    return {
        **os.environ,
        "APP_ENV": "production",
        "APP_BASE_URL": "https://sandbox.example.test",
        "EXTERNAL_EFFECTS_ENABLED": "false",
        "INBOUND_PROVIDER_EVENTS_ENABLED": "false",
        "GOOGLE_LOGIN_ENABLED": "false",
        "APPLE_LOGIN_ENABLED": "false",
        "CONNECTIONS_ENABLED": "false",
        "EMAIL_PROVIDER": "null",
        "AI_ENABLED": "false",
        "AI_PROVIDER": "disabled",
        "GEMMA_ENABLED": "false",
        "GEMMA_PROVIDER": "disabled",
        "PAYPAL_MODE": "sandbox",
        "JWT_SECRET": "worker-jwt-secret-that-is-at-least-32-bytes",
        "MANAGER_PIN": "830527",
        "INTEGRATIONS_ENCRYPTION_KEY": "cXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXFxcXE=",
        "DISTRIBUTED_LOCK_ENABLED": "true",
        "DISTRIBUTED_LOCK_REQUIRED": "true",
        "CLICKHOUSE_ENABLED": "false",
        "CLICKHOUSE_REQUIRED": "false",
    }


def test_celery_process_accepts_explicit_closed_production_profile():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.tasks.celery_app import celery_app; "
            "assert celery_app.conf.beat_schedule == {}",
        ],
        env=_safe_worker_env(),
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_celery_process_rejects_missing_production_policy_before_startup():
    env = _safe_worker_env()
    env.pop("EXTERNAL_EFFECTS_ENABLED")
    result = subprocess.run(
        [sys.executable, "-c", "import app.tasks.celery_app"],
        env=env,
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(__file__)),
    )
    assert result.returncode != 0
    assert "EXTERNAL_EFFECTS_ENABLED" in result.stderr


def test_date_dimension_is_global_and_bounded():
    rows = analytics_warehouse.build_date_dimension_rows(date(2026, 7, 1), date(2026, 7, 3))

    assert [row["calendar_date"] for row in rows] == [
        "2026-07-01",
        "2026-07-02",
        "2026-07-03",
    ]
    assert all("hotel_id" not in row for row in rows)
