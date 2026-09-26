"""
FastAPI Webhook endpoints for OTA integrations.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ota_service import OTAIntegrationService, OTAError, OTAAuthError
from app.api.webhook_payloads import read_bounded_body
from app.services.external_effects_policy import (
    InboundProviderEventsDisabled,
    require_inbound_provider_events,
)

router = APIRouter(prefix="/api/webhooks", tags=["OTA Webhooks"])


def _handle_ota_webhook(provider: str, hotel_id: int, webhook_secret: str, payload: dict, db: Session):
    try:
        require_inbound_provider_events(provider)
    except InboundProviderEventsDisabled as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    try:
        if provider == "booking":
            mapping = OTAIntegrationService.process_booking_webhook(db, hotel_id, webhook_secret, payload)
        elif provider == "expedia":
            mapping = OTAIntegrationService.process_expedia_webhook(db, hotel_id, webhook_secret, payload)
        elif provider == "despegar":
            mapping = OTAIntegrationService.process_despegar_webhook(db, hotel_id, webhook_secret, payload)
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
async def booking_webhook(hotel_id: int, webhook_secret: str, request: Request, db: Session = Depends(get_db)):
    """Receive reservation notifications from Booking.com."""
    payload = await _guarded_json_payload(
        "booking", request, db=db, hotel_id=hotel_id, webhook_secret=webhook_secret
    )
    return _handle_ota_webhook("booking", hotel_id, webhook_secret, payload, db)


@router.post("/expedia/{hotel_id}/{webhook_secret}")
async def expedia_webhook(hotel_id: int, webhook_secret: str, request: Request, db: Session = Depends(get_db)):
    """Receive reservation notifications from Expedia."""
    payload = await _guarded_json_payload(
        "expedia", request, db=db, hotel_id=hotel_id, webhook_secret=webhook_secret
    )
    return _handle_ota_webhook("expedia", hotel_id, webhook_secret, payload, db)


@router.post("/despegar/{hotel_id}/{webhook_secret}")
async def despegar_webhook(hotel_id: int, webhook_secret: str, request: Request, db: Session = Depends(get_db)):
    """Receive reservation notifications from Despegar."""
    payload = await _guarded_json_payload(
        "despegar", request, db=db, hotel_id=hotel_id, webhook_secret=webhook_secret
    )
    return _handle_ota_webhook("despegar", hotel_id, webhook_secret, payload, db)


async def _guarded_json_payload(
    provider: str,
    request: Request,
    *,
    db: Session | None = None,
    hotel_id: int | None = None,
    webhook_secret: str | None = None,
) -> dict:
    try:
        # Deliberately before request.json(): disabled callbacks do not parse input.
        require_inbound_provider_events(provider)
    except InboundProviderEventsDisabled as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    if db is not None and hotel_id is not None:
        try:
            OTAIntegrationService.validate_webhook_secret(db, hotel_id, provider, webhook_secret or "")
        except OTAAuthError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Webhook OTA no autorizado") from exc
    try:
        raw_body = await read_bounded_body(request, max_bytes=2 * 1024 * 1024)
        return TypeAdapter(dict).validate_json(raw_body)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Payload OTA invalido") from exc


@router.post("/booking")
@router.post("/expedia")
@router.post("/despegar")
def deprecated_webhook():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Los webhooks OTA ahora requieren hotel_id y secret en la URL: /api/webhooks/{provider}/{hotel_id}/{secret}",
    )
