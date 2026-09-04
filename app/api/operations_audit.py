"""Read-only integral operations audit endpoint."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.operational_audit import OperationalAuditRead
from app.services.operational_audit_service import list_operational_audit
from app.services.permission_service import PERMISSION_OPERATIONS_AUDIT_VIEW


router = APIRouter(tags=["Operations Audit"])


@router.get("/api/operations/audit", response_model=OperationalAuditRead)
@router.get("/operations/audit", response_model=OperationalAuditRead)
def operations_audit(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100_000),
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    actor_user_id: int | None = Query(default=None, ge=1),
    category: str | None = Query(default=None, min_length=1, max_length=60),
    reservation_id: int | None = Query(default=None, ge=1),
    room_id: int | None = Query(default=None, ge=1),
    action: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_OPERATIONS_AUDIT_VIEW)),
):
    if from_date is not None and to_date is not None and to_date < from_date:
        raise HTTPException(status_code=422, detail="to debe ser mayor o igual que from")
    try:
        items, total = list_operational_audit(
            db,
            hotel_id=context.hotel_id,
            limit=limit,
            offset=offset,
            from_date=from_date,
            to_date=to_date,
            actor_user_id=actor_user_id,
            category=category,
            reservation_id=reservation_id,
            room_id=room_id,
            action=action,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="La zona horaria del hotel no es valida") from exc
    return OperationalAuditRead(
        hotel_id=context.hotel_id,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(items) < total,
    )
