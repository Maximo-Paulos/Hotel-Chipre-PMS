"""
FastAPI Webhook endpoints for OTA integrations.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ota_service import OTAIntegrationService, OTAError, OTAAuthError

router = APIRouter(prefix="/api/webhooks", tags=["OTA Webhooks"])


def _handle_ota_webhook(provider: str, hotel_id: int, webhook_secret: str, payload: dict, db: Session):
    try:
        if provider == "booking":
            mapping = OTAIntegrationService.process_booking_webhook(db, hotel_id, webhook_secret, payload)
        elif provider == "expedia":
            mapping = OTAIntegrationService.process_expedia_webhook(db, hotel_id, webhook_secret, payload)
        else:
            raise OTAError(f"Unsupported OTA provider: {provider}")
        db.commit()
        return {
            "status": "ok",
            "sync_status": mapping.sync_status.value,
            "reservation_id": mapping.reservation_id,
        }
    except OTAAuthError as e:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(e))
    except OTAError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/booking/{hotel_id}/{webhook_secret}")
def booking_webhook(hotel_id: int, webhook_secret: str, payload: dict, db: Session = Depends(get_db)):
    """Receive reservation notifications from Booking.com."""
    return _handle_ota_webhook("booking", hotel_id, webhook_secret, payload, db)


@router.post("/expedia/{hotel_id}/{webhook_secret}")
def expedia_webhook(hotel_id: int, webhook_secret: str, payload: dict, db: Session = Depends(get_db)):
    """Receive reservation notifications from Expedia."""
    return _handle_ota_webhook("expedia", hotel_id, webhook_secret, payload, db)


@router.post("/booking")
@router.post("/expedia")
def deprecated_webhook():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Los webhooks OTA ahora requieren hotel_id y secret en la URL: /api/webhooks/{provider}/{hotel_id}/{secret}",
    )
