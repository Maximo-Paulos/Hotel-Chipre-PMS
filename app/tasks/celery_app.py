"""
Celery application configuration and async tasks for OTA synchronization.
"""
from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

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

# §15.1 Scheduled operational reports. Times are interpreted in the hotel
# timezone configured above (Celery `timezone`). Morning report at 08:00,
# nightly summary at 23:00.
celery_app.conf.beat_schedule = {
    "operational-morning-reports": {
        "task": "reports.send_morning_reports",
        "schedule": crontab(hour=8, minute=0),
    },
    "operational-nightly-reports": {
        "task": "reports.send_nightly_reports",
        "schedule": crontab(hour=23, minute=0),
    },
}

# Eager imports so Celery registers module-level tasks without autodiscovery.
import app.tasks.ota_tasks  # noqa: F401,E402
import app.tasks.analytics_tasks  # noqa: F401,E402
import app.tasks.report_tasks  # noqa: F401,E402
