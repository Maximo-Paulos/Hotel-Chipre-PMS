"""
Celery application configuration and async tasks for OTA synchronization.
"""
from celery import Celery
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
