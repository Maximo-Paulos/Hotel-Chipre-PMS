"""Tenant-scoped API for fixed post-checkout housekeeping checklists."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.housekeeping_checklist import HousekeepingChecklistItemCodeEnum
from app.schemas.housekeeping_checklist import (
    HousekeepingChecklistListRead,
    HousekeepingChecklistRead,
)
from app.services.housekeeping_checklist_service import (
    HousekeepingChecklistConflict,
    HousekeepingChecklistNotFound,
    complete_checklist_item,
    list_open_checklists,
)
from app.services.permission_service import (
    PERMISSION_HOUSEKEEPING_BOARD_VIEW,
    PERMISSION_ROOM_STATUS_UPDATE,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/housekeeping", tags=["housekeeping"])


@router.get("/checklists", response_model=HousekeepingChecklistListRead)
def get_housekeeping_checklists(
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection
    context: AuthContext = Depends(require_permission(PERMISSION_HOUSEKEEPING_BOARD_VIEW)),  # noqa: B008
) -> HousekeepingChecklistListRead:
    """List open checklists for the caller's hotel without guest data."""
    return list_open_checklists(db, hotel_id=context.hotel_id)


@router.post(
    "/checklists/{checklist_id}/items/{item_code}/complete",
    response_model=HousekeepingChecklistRead,
)
def complete_housekeeping_checklist_item(
    checklist_id: int,
    item_code: HousekeepingChecklistItemCodeEnum,
    db: Session = Depends(get_db),  # noqa: B008 - FastAPI dependency injection
    context: AuthContext = Depends(require_permission(PERMISSION_ROOM_STATUS_UPDATE)),  # noqa: B008
) -> HousekeepingChecklistRead:
    """Complete one fixed item; all PostgreSQL state changes commit together."""
    try:
        response = complete_checklist_item(
            db,
            hotel_id=context.hotel_id,
            checklist_id=checklist_id,
            item_code=item_code,
            actor_user_id=context.user_id,
        )
        db.commit()
    except HousekeepingChecklistNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HousekeepingChecklistConflict as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception(
            "housekeeping.checklist_completion_failed",
            extra={"hotel_id": context.hotel_id, "checklist_id": checklist_id},
        )
        raise HTTPException(status_code=409, detail="No se pudo actualizar el checklist") from exc

    if response.completed_now:
        # PostgreSQL owns the transaction. Historical projection and caches
        # are best-effort side effects after the atomic commit.
        try:
            from app.services.timeseries_projection import project_room_state_event

            project_room_state_event(
                context.hotel_id,
                response.checklist.room.id,
                response.checklist.room.operational_status.value,
                response.checklist.completed_at,
                {
                    "source": "housekeeping.checklist.complete",
                    "housekeeping_status": response.checklist.room.housekeeping_status.value,
                    "checklist_id": response.checklist.checklist_id,
                },
            )
        except Exception as exc:  # noqa: BLE001 - projection is best-effort after commit
            logger.warning(
                "housekeeping.checklist_projection_failed",
                extra={
                    "hotel_id": context.hotel_id,
                    "checklist_id": checklist_id,
                    "error_type": type(exc).__name__,
                },
            )

    if response.changed:
        try:
            from app.services.read_model_cache import (
                invalidate_hotel_operational_caches,
            )

            invalidate_hotel_operational_caches(context.hotel_id)
        except Exception as exc:  # noqa: BLE001 - cache invalidation is best-effort after commit
            logger.warning(
                "housekeeping.checklist_cache_invalidation_failed",
                extra={"hotel_id": context.hotel_id, "error_type": type(exc).__name__},
            )
    return response.checklist
