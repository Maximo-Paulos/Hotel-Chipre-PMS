"""
Celery tasks for OTA synchronization.
Sends inventory/availability updates to Booking.com and Expedia
whenever internal state changes (new reservation, allocation move, etc.).
"""
import json
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from app.tasks.celery_app import celery_app
from app.config import get_settings

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="ota.push_availability_update",
    max_retries=3,
    default_retry_delay=60,
)
def push_availability_update(
    self,
    category_id: int,
    start_date_str: str,
    end_date_str: str,
    database_url: Optional[str] = None,
):
    """
    Push availability updates to all enabled OTAs for a given category and date range.
    This task is triggered after:
    - A new reservation is created
    - The AllocationEngine moves rooms
    - A reservation is cancelled
    
    Args:
        category_id: Room category to update availability for.
        start_date_str: Start of the date range (ISO format).
        end_date_str: End of the date range (ISO format).
        database_url: Optional DB URL override for testing.
    """
    try:
        from app.database import get_engine, Base
        from sqlalchemy.orm import sessionmaker
        from app.services.ota_service import OTAIntegrationService
        from app.models.hotel_config import HotelConfiguration

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            start_date = date.fromisoformat(start_date_str)
            end_date = date.fromisoformat(end_date_str)
            from app.models.room import RoomCategory

            # Build availability data
            availability = OTAIntegrationService.build_availability_update(
                db, category_id, start_date, end_date
            )

            category = db.query(RoomCategory).filter(RoomCategory.id == category_id).first()
            if not category:
                return {"status": "skipped", "reason": "category not found"}

            config = db.query(HotelConfiguration).filter(
                HotelConfiguration.id == category.hotel_id
            ).first()
            if not config:
                return {"status": "skipped", "reason": "hotel configuration not found"}

            results = {}

            if config.enable_booking_sync:
                try:
                    results["booking"] = _push_to_booking(availability, category_id)
                except Exception as e:
                    logger.error(f"Failed to push to Booking.com: {e}")
                    results["booking"] = {"error": str(e)}

            if config.enable_expedia_sync:
                try:
                    results["expedia"] = _push_to_expedia(availability, category_id)
                except Exception as e:
                    logger.error(f"Failed to push to Expedia: {e}")
                    results["expedia"] = {"error": str(e)}

            return results

        finally:
            db.close()

    except Exception as exc:
        logger.error(f"push_availability_update failed: {exc}")
        raise self.retry(exc=exc)


def _push_to_booking(availability: list[dict], category_id: int) -> dict:
    """
    Send availability update to Booking.com OC API.
    
    In production, this would use the Booking.com XML/JSON API.
    This implementation shows the complete request structure.
    """
    settings = get_settings()

    # Build Booking.com availability XML/JSON payload
    payload = {
        "hotel_id": settings.BOOKING_USERNAME,
        "room_type_id": str(category_id),
        "availability": [
            {
                "date": entry["date"],
                "rooms_to_sell": entry["available"],
            }
            for entry in availability
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{settings.BOOKING_API_URL}/availability",
                json=payload,
                auth=(settings.BOOKING_USERNAME, settings.BOOKING_PASSWORD),
            )
            return {
                "status_code": response.status_code,
                "response": response.text[:500],  # Truncate for logging
            }
    except httpx.ConnectError:
        logger.warning("Booking.com API unreachable (expected in development)")
        return {"status": "skipped", "reason": "API unreachable"}


def _push_to_expedia(availability: list[dict], category_id: int) -> dict:
    """
    Send availability update to Expedia EQC API.
    
    In production, this would use the Expedia Product API.
    This implementation shows the complete request structure.
    """
    settings = get_settings()

    payload = {
        "property_id": settings.EXPEDIA_HOTEL_ID,
        "room_type_id": str(category_id),
        "inventory": [
            {
                "date": entry["date"],
                "totalInventoryAvailable": entry["available"],
            }
            for entry in availability
        ],
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.put(
                f"{settings.EXPEDIA_API_URL}/v3/properties/{settings.EXPEDIA_HOTEL_ID}/availability",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.EXPEDIA_API_KEY}",
                    "Content-Type": "application/json",
                },
            )
            return {
                "status_code": response.status_code,
                "response": response.text[:500],
            }
    except httpx.ConnectError:
        logger.warning("Expedia API unreachable (expected in development)")
        return {"status": "skipped", "reason": "API unreachable"}


@celery_app.task(
    bind=True,
    name="ota.sync_all_availability",
    max_retries=2,
    default_retry_delay=120,
)
def sync_all_availability(self, days_ahead: int = 90, database_url: Optional[str] = None):
    """
    Full sync: push availability for ALL categories for the next N days.
    Typically run as a periodic task (e.g., every 15 minutes).
    """
    try:
        from app.database import get_engine
        from sqlalchemy.orm import sessionmaker
        from app.models.room import RoomCategory

        settings = get_settings()
        url = database_url or settings.DATABASE_URL
        engine = get_engine(url)
        SessionLocal = sessionmaker(bind=engine)
        db = SessionLocal()

        try:
            today = date.today()
            end = today + timedelta(days=days_ahead)

            categories = db.query(RoomCategory).all()
            results = {}

            for cat in categories:
                task_result = push_availability_update.delay(
                    category_id=cat.id,
                    start_date_str=today.isoformat(),
                    end_date_str=end.isoformat(),
                    database_url=url,
                )
                results[cat.code] = task_result.id

            return results

        finally:
            db.close()

    except Exception as exc:
        logger.error(f"sync_all_availability failed: {exc}")
        raise self.retry(exc=exc)
