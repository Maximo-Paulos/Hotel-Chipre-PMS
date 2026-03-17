"""
FastAPI Webhook endpoints for OTA integrations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ota_service import OTAIntegrationService, OTAError

router = APIRouter(prefix="/api/webhooks", tags=["OTA Webhooks"])


@router.post("/booking")
def booking_webhook(payload: dict, db: Session = Depends(get_db)):
    """Receive reservation notifications from Booking.com."""
    try:
        mapping = OTAIntegrationService.process_booking_webhook(db, payload)
        db.commit()
        return {
            "status": "ok",
            "sync_status": mapping.sync_status.value,
            "reservation_id": mapping.reservation_id,
        }
    except OTAError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/expedia")
def expedia_webhook(payload: dict, db: Session = Depends(get_db)):
    """Receive reservation notifications from Expedia."""
    try:
        mapping = OTAIntegrationService.process_expedia_webhook(db, payload)
        db.commit()
        return {
            "status": "ok",
            "sync_status": mapping.sync_status.value,
            "reservation_id": mapping.reservation_id,
        }
    except OTAError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
