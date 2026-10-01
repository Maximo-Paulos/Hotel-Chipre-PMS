"""Create and inspect groups of independently billed hotel reservations."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.reservations import _trigger_reoptimization_bg
from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, require_permission
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.schemas.reservation import ReservationGroupCreate, ReservationGroupRead
from app.services import audit_log_service
from app.services.reservation_group_service import create_reservation_group, list_reservation_groups
from app.services.reservation_service import ReservationError
from app.services.permission_service import PERMISSION_COMPANY_MANAGE, PERMISSION_RESERVATION_CREATE, PERMISSION_RESERVATION_READ


router = APIRouter(prefix="/api/reservation-groups", tags=["Reservation Groups"])


@router.get("", response_model=list[ReservationGroupRead])
def get_reservation_groups(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    return list_reservation_groups(db, hotel_id=context.hotel_id, limit=limit)


@router.post("", response_model=ReservationGroupRead, status_code=status.HTTP_201_CREATED)
def create_reservation_group_route(
    data: ReservationGroupCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_CREATE)),
):
    if any(item.company_id is not None for item in data.reservations):
        authorize_permission(request, db, context, PERMISSION_COMPANY_MANAGE)
    config = db.get(HotelConfiguration, context.hotel_id)
    if config and not config.subscription_active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Suscripción inactiva. Reactivá el plan para crear nuevas reservas.",
        )
    try:
        group, reservations = create_reservation_group(
            db,
            hotel_id=context.hotel_id,
            reservations=data.reservations,
            actor_user_id=context.user_id,
            actor_role=context.user_role,
        )
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="reservation_groups",
            record_id=group.id,
            action=AuditActionEnum.CREATE,
            actor_user_id=context.user_id,
            payload_after={
                **(audit_log_service.model_snapshot(group) or {}),
                "reservation_ids": [reservation.id for reservation in reservations],
            },
        )
        for reservation in reservations:
            audit_log_service.safe_create_audit_log(
                db,
                hotel_id=context.hotel_id,
                table_name="reservations",
                record_id=reservation.id,
                action=AuditActionEnum.CREATE,
                actor_user_id=context.user_id,
                payload_after={
                    **(audit_log_service.model_snapshot(reservation) or {}),
                    "source": "reservation_group_api",
                },
            )
        db.commit()
        background_tasks.add_task(
            _trigger_reoptimization_bg,
            hotel_id=context.hotel_id,
            trigger_type="reservation_group_created",
        )
        summary = list_reservation_groups(db, hotel_id=context.hotel_id, limit=1, group_id=group.id)
        if not summary:
            raise HTTPException(status_code=500, detail="No se pudo leer el grupo recién creado.")
        return summary[0]
    except ReservationError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
