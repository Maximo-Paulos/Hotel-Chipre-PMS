"""Celery entry point for the internal no-show reconciliation."""
from app.services.no_show_sweep_service import run_no_show_sweep, sweep_no_shows
from app.tasks.celery_app import celery_app


@celery_app.task(name="reservations.sweep_no_shows")
def sweep_no_shows_task(database_url: str | None = None) -> dict:
    """Run the internal sweep per hotel without invoking providers."""
    return run_no_show_sweep(database_url)
