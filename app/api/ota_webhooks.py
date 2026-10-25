"""
FastAPI Webhook endpoints for OTA integrations.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.ota_service import (
    OTAIntegrationService,
    OTAError,
    OTAAuthError,
    OTAProcessingError,
    OTA_CONFLICT_ERROR_MESSAGE,
    OTA_PROCESSING_ERROR_MESSAGE,
)
from app.api.webhook_payloads import read_bounded_body
from app.services.external_effects_policy import (
    InboundProviderEventsDisabled,
    require_inbound_provider_events,
)

router = APIRouter(prefix="/api/webhooks", tags=["OTA Webhooks"])
logger = logging.getLogger(__name__)


def _log_ota_processing_failure(provider: str, error: Exception) -> None:
    # Keep diagnostics useful without writing webhook content, credentials, or
    # exception messages that may contain provider or guest data.
    logger.error(
        "OTA webhook processing failed",
        extra={"provider": provider, "exception_type": type(error).__name__},
    )


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
        reservation_id = mapping.reservation_id
        sync_status = mapping.sync_status.value
        db.commit()
        try:
            from app.services.payment_link_service import process_payment_link_revocations

            process_payment_link_revocations(db, hotel_id, reservation_id=reservation_id)
            db.commit()
        except Exception as exc:  # noqa: BLE001 - OTA cancellation is already durable
            db.rollback()
            logger.warning(
                "payment_link.revocation_attempt_unavailable hotel_id=%s reservation_id=%s error_type=%s",
                hotel_id,
                reservation_id,
                type(exc).__name__,
            )
        return {
            "status": "ok",
            "sync_status": sync_status,
            "reservation_id": reservation_id,
        }
    except OTAAuthError as e:
        db.rollback()
        raise HTTPException(status_code=401, detail=str(e))
    except OTAProcessingError as exc:
        db.rollback()
        _log_ota_processing_failure(provider, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=OTA_PROCESSING_ERROR_MESSAGE,
        ) from exc
    except OTAError as exc:
        db.rollback()
        logger.warning(
            "OTA webhook rejected",
            extra={"provider": provider, "exception_type": type(exc).__name__},
        )
        raise HTTPException(status_code=409, detail=OTA_CONFLICT_ERROR_MESSAGE) from exc
    except Exception as exc:
        db.rollback()
        _log_ota_processing_failure(provider, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=OTA_PROCESSING_ERROR_MESSAGE,
        ) from exc


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
