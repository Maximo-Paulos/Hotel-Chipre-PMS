from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.rate_calendar import RateCalendarResponse
from app.services.rate_calendar_service import get_daily_calendar


router = APIRouter(prefix="/api/rate-calendar", tags=["Rate Calendar"])


@router.get("/daily", response_model=RateCalendarResponse)
def get_daily_rate_calendar(
    category_id: int = Query(...),
    date_from: date = Query(...),
    date_to: date = Query(...),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to must be greater than or equal to date_from")
    if (date_to - date_from).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days")

    try:
        return get_daily_calendar(
            db,
            hotel_id=context.hotel_id,
            category_id=category_id,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as exc:
        if str(exc) == "Category not found":
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        raise HTTPException(status_code=422, detail=str(exc)) from exc
