"""
Celery application configuration and async tasks for OTA synchronization.
"""
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
)

def build_beat_schedule(runtime_settings: Settings) -> dict:
    """Return no scheduled provider/network work for a closed sandbox.

    `notifications.process_outbox` also creates in-app Notification rows
    (no network egress), but it is kept under the same closed-sandbox gate
    as everything else here -- this function's tested contract is "closed
    sandbox means an empty beat_schedule", not "empty unless the task claims
    to be network-free". Callers that need in-app delivery inside a closed
    sandbox call `app.services.notification_service.process_pending_outbox`
    directly instead of relying on beat.
    """

    if not external_connections_enabled(runtime_settings):
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
    }


# §15.1 Scheduled operational reports. Times are interpreted in the hotel
# timezone configured above (Celery `timezone`).
celery_app.conf.beat_schedule = build_beat_schedule(settings)

# Eager imports so Celery registers module-level tasks without autodiscovery.
import app.tasks.ota_tasks  # noqa: F401,E402
import app.tasks.analytics_tasks  # noqa: F401,E402
import app.tasks.report_tasks  # noqa: F401,E402
import app.tasks.notification_tasks  # noqa: F401,E402
