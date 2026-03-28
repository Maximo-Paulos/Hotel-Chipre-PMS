"""
FastAPI routes for the onboarding flow used by smoke tests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.schemas.onboarding import (
    OnboardingStatus,
    OwnerPayload,
    CategoriesPayload,
    RoomsPayload,
    StaffPayload,
)
from app.services import onboarding_service
from app.services.onboarding_service import OnboardingError

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/status", response_model=OnboardingStatus)
def onboarding_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    return onboarding_service.get_status(db, hotel_id=context.hotel_id)


@router.post("/owner", response_model=OnboardingStatus)
def set_owner(
    payload: OwnerPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    status_data = onboarding_service.set_owner(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/categories", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_categories(
    payload: CategoriesPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    status_data = onboarding_service.upsert_categories(db, payload.categories, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/rooms", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_rooms(
    payload: RoomsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        status_data = onboarding_service.upsert_rooms(db, payload.rooms, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/staff", response_model=OnboardingStatus)
def set_staff(
    payload: StaffPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    status_data = onboarding_service.store_staff(db, payload.staff, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/finish", response_model=OnboardingStatus)
def finish(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    try:
        status_data = onboarding_service.finish_onboarding(db, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))

