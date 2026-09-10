from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.reservation_communication import (
    ReservationEmailDeliveryRead,
    ReservationEmailSendRequest,
    ReservationEmailSendResponse,
)
from app.services.permission_service import PERMISSION_RESERVATION_READ, PERMISSION_RESERVATION_UPDATE
from app.services.reservation_communication_service import (
    ReservationCommunicationError,
    list_reservation_email_deliveries,
    send_reservation_email,
)


router = APIRouter(prefix="/api/reservations", tags=["Reservation communications"])


@router.get(
    "/{reservation_id}/communications",
    response_model=list[ReservationEmailDeliveryRead],
)
def list_reservation_communications(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    return list_reservation_email_deliveries(
        db,
        hotel_id=context.hotel_id,
        reservation_id=reservation_id,
    )


@router.post(
    "/{reservation_id}/communications",
    response_model=ReservationEmailSendResponse,
    status_code=status.HTTP_200_OK,
)
def send_reservation_communication(
    reservation_id: int,
    payload: ReservationEmailSendRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_UPDATE)),
):
    try:
        outcome = send_reservation_email(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
            kind=payload.kind.value,
            requested_by_user_id=context.user_id,
            recipient_email=str(payload.recipient_email) if payload.recipient_email else None,
            resend=payload.resend,
        )
        db.commit()
        db.refresh(outcome.delivery)
        return ReservationEmailSendResponse(
            delivery=outcome.delivery,
            deduplicated=outcome.deduplicated,
        )
    except ReservationCommunicationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
