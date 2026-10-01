"""Manage and inspect per-night extras on corporate reservations."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.company_night_charge import CompanyNightChargeSetRequest, CompanyNightChargesSummaryRead
from app.services.analytics_service import require_analytics_plan
from app.services.company_night_charge_service import (
    CompanyNightChargeError,
    add_company_night_charges,
    get_company_night_charges,
)
from app.services.permission_service import PERMISSION_COMPANY_MANAGE, PERMISSION_RESERVATION_READ


router = APIRouter(prefix="/api/reservations", tags=["Company Night Charges"])


@router.get("/{reservation_id}/company-night-charges", response_model=CompanyNightChargesSummaryRead)
def list_reservation_company_night_charges(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    try:
        return get_company_night_charges(db, hotel_id=context.hotel_id, reservation_id=reservation_id)
    except CompanyNightChargeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/{reservation_id}/company-night-charges", response_model=CompanyNightChargesSummaryRead)
def create_reservation_company_night_charges(
    reservation_id: int,
    payload: CompanyNightChargeSetRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    try:
        result = add_company_night_charges(
            db,
            hotel_id=context.hotel_id,
            reservation_id=reservation_id,
            stay_dates=payload.stay_dates,
            actor_user_id=context.user_id,
        )
        db.commit()
        return result
    except CompanyNightChargeError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
