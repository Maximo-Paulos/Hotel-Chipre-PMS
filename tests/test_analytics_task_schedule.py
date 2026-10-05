from __future__ import annotations

from datetime import date
import os
import subprocess
import sys

from app.config import Settings
from app.services import analytics_warehouse
from app.tasks.celery_app import build_beat_schedule, celery_app


_ISOLATED_WORKER_IMPORT = (
    "from app.config import Settings; "
    "Settings.model_config['env_file'] = None; "
    "import app.tasks.celery_app"
)


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
    assert schedule["analytics-cleanup-expired-exports"]["task"] == "analytics.cleanup_expired_exports"


def test_sandbox_has_no_scheduled_network_tasks():
    assert build_beat_schedule(
        Settings(EXTERNAL_EFFECTS_ENABLED=False, CONNECTIONS_ENABLED=False)
    ) == {}
    assert build_beat_schedule(
        Settings(EXTERNAL_EFFECTS_ENABLED=True, CONNECTIONS_ENABLED=False)
    ) == {}


def test_closed_sandbox_with_internal_redis_schedules_only_domain_event_replay():
    schedule = build_beat_schedule(
        Settings(
            EXTERNAL_EFFECTS_ENABLED=False,
            CONNECTIONS_ENABLED=False,
            REALTIME_EVENTS_ENABLED=True,
            REDIS_URL="redis://redis:6379/0",
            CELERY_BROKER_URL="redis://redis:6379/0",
            CELERY_RESULT_BACKEND="redis://redis:6379/0",
        )
    )

    assert set(schedule) == {"domain-events-publish-outbox"}
    assert schedule["domain-events-publish-outbox"] == {
        "task": "domain_events.publish_outbox",
        "schedule": 30.0,
    }


def test_closed_sandbox_keeps_beat_empty_without_explicit_matching_redis():
    settings_without_redis = Settings(
        EXTERNAL_EFFECTS_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        REALTIME_EVENTS_ENABLED=True,
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/0",
    )
    settings_with_mismatched_redis = Settings(
        EXTERNAL_EFFECTS_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        REALTIME_EVENTS_ENABLED=True,
        REDIS_URL="redis://redis:6379/0",
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://results:6379/0",
    )
    settings_with_realtime_disabled = Settings(
        EXTERNAL_EFFECTS_ENABLED=False,
        CONNECTIONS_ENABLED=False,
        REALTIME_EVENTS_ENABLED=False,
        REDIS_URL="redis://redis:6379/0",
        CELERY_BROKER_URL="redis://redis:6379/0",
        CELERY_RESULT_BACKEND="redis://redis:6379/0",
    )

    assert build_beat_schedule(settings_without_redis) == {}
    assert build_beat_schedule(settings_with_mismatched_redis) == {}
    assert build_beat_schedule(settings_with_realtime_disabled) == {}


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
        "REDIS_URL": "redis://redis:6379/0",
        "CELERY_BROKER_URL": "redis://redis:6379/0",
        "CELERY_RESULT_BACKEND": "redis://redis:6379/0",
    }


def test_celery_process_accepts_explicit_closed_production_profile():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"{_ISOLATED_WORKER_IMPORT}; "
            "schedule=app.tasks.celery_app.celery_app.conf.beat_schedule; "
            "assert set(schedule) == {'domain-events-publish-outbox'}; "
            "assert schedule['domain-events-publish-outbox']['task'] == 'domain_events.publish_outbox'; "
            "assert schedule['domain-events-publish-outbox']['schedule'] == 30.0",
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
        [sys.executable, "-c", _ISOLATED_WORKER_IMPORT],
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
