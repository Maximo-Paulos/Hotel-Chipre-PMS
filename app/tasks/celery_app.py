"""
Celery application configuration and async tasks for OTA synchronization.
"""
from urllib.parse import urlsplit

from celery import Celery
from celery.schedules import crontab
from app.config import Settings, get_settings, validate_runtime_security
from app.services.external_effects_policy import external_connections_enabled

settings = get_settings()
# FastAPI validates the runtime during application startup. Workers and beat do
# not execute that lifecycle, so they must enforce the same fail-closed contract
# before constructing a broker client or importing any task module.
validate_runtime_security(settings)

celery_app = Celery(
    "hotel_pms",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone=settings.HOTEL_TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="critical",
    task_routes={
        "domain_events.publish_outbox": {"queue": "critical"},
        "notifications.process_outbox": {"queue": "critical"},
        "notifications.generate_daily_reports": {"queue": "heavy"},
        "reports.*": {"queue": "heavy"},
        "analytics.*": {"queue": "heavy"},
        "ota.*": {"queue": "heavy"},
    },
    task_annotations={
        "domain_events.publish_outbox": {"rate_limit": "30/m", "time_limit": 60, "soft_time_limit": 30},
        "notifications.process_outbox": {"rate_limit": "30/m", "time_limit": 60, "soft_time_limit": 30},
    },
)


def _redis_endpoint(url: str) -> tuple[str, str, int | None] | None:
    """Return a Redis endpoint identity without exposing URL credentials."""

    try:
        parsed = urlsplit(url.strip())
        port = parsed.port
    except (AttributeError, ValueError):
        return None
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        return None
    return parsed.scheme, parsed.hostname.casefold(), port


def _sandbox_domain_event_replay_enabled(runtime_settings: Settings) -> bool:
    """Allow only internal outbox recovery in a closed sandbox with Redis wired.

    The application Redis, Celery broker, and Celery result backend URLs must
    be explicitly supplied and resolve to the same endpoint. Beat uses the
    broker to enqueue the task, the task publishes through the application's
    Redis connection, and Celery may store the task result in its backend.
    Default localhost values alone are not evidence that the deployed broker
    exists.
    """

    if (
        runtime_settings.EXTERNAL_EFFECTS_ENABLED is not False
        or runtime_settings.CONNECTIONS_ENABLED is not False
        or runtime_settings.REALTIME_EVENTS_ENABLED is not True
    ):
        return False
    redis_fields = {"CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "REDIS_URL"}
    if not redis_fields.issubset(runtime_settings.model_fields_set):
        return False

    configured_endpoints = (
        _redis_endpoint(runtime_settings.CELERY_BROKER_URL),
        _redis_endpoint(runtime_settings.CELERY_RESULT_BACKEND),
        _redis_endpoint(runtime_settings.REDIS_URL),
    )
    broker_endpoint = configured_endpoints[0]
    return broker_endpoint is not None and all(
        endpoint == broker_endpoint for endpoint in configured_endpoints[1:]
    )


def build_beat_schedule(runtime_settings: Settings) -> dict:
    """Return provider work or only safe internal replay for a closed sandbox.

    `notifications.process_outbox` also creates in-app Notification rows
    (no network egress), but it is kept under the same closed-sandbox gate
    as provider work. The one exception is durable domain-event replay, and
    only when the closed sandbox explicitly configures the same Redis endpoint
    for the application, Celery broker, and Celery result backend. That task
    touches PostgreSQL and the app's Redis only; it does not invoke providers.
    """

    if not external_connections_enabled(runtime_settings):
        if _sandbox_domain_event_replay_enabled(runtime_settings):
            return {
                "domain-events-publish-outbox": {
                    "task": "domain_events.publish_outbox",
                    "schedule": 30.0,
                }
            }
        return {}
    return {
        # Derived analytics is replayable from PostgreSQL. ClickPipes CDC remains
        # the production low-latency path; these jobs provide bounded recovery and
        # an explicit reconciliation signal every five minutes and nightly.
        "analytics-derived-facts-incremental": {
            "task": "analytics.project_all_derived_facts_incremental",
            "schedule": 300.0,
        },
        "analytics-derived-facts-nightly-reconciliation": {
            "task": "analytics.reconcile_all_derived_facts_nightly",
            "schedule": crontab(hour=2, minute=30),
        },
        "analytics-cleanup-expired-exports": {
            "task": "analytics.cleanup_expired_exports",
            "schedule": crontab(hour=4, minute=30),
        },
        "operational-morning-reports": {
            "task": "reports.send_morning_reports",
            "schedule": crontab(hour=8, minute=0),
        },
        "operational-nightly-reports": {
            "task": "reports.send_nightly_reports",
            "schedule": crontab(hour=23, minute=0),
        },
        "notifications-process-outbox": {
            "task": "notifications.process_outbox",
            "schedule": 60.0,
        },
        "notifications-generate-daily-reports": {
            "task": "notifications.generate_daily_reports",
            "schedule": crontab(minute="*/15"),
        },
        # Bounded recovery for the realtime after-commit fast path: replays
        # any domain_event_outbox row still pending (process crash or a
        # transient Redis outage between the business commit and its first
        # publish attempt). No network egress by itself, but kept under the
        # same closed-sandbox gate as everything else here.
        "domain-events-publish-outbox": {
            "task": "domain_events.publish_outbox",
            "schedule": 30.0,
        },
    }


# §15.1 Scheduled operational reports. Times are interpreted in the hotel
# timezone configured above (Celery `timezone`).
celery_app.conf.beat_schedule = build_beat_schedule(settings)

# Eager imports so Celery registers module-level tasks without autodiscovery.
import app.tasks.ota_tasks  # noqa: F401,E402
import app.tasks.analytics_tasks  # noqa: F401,E402
import app.tasks.report_tasks  # noqa: F401,E402
import app.tasks.notification_tasks  # noqa: F401,E402
import app.tasks.domain_event_tasks  # noqa: F401,E402
