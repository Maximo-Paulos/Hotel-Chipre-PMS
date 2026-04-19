"""
FastAPI routes for the onboarding flow used by smoke tests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context, require_roles
from app.schemas.onboarding import (
    CategoriesPayload,
    DepositPolicyPayload,
    HotelIdentityPayload,
    OnboardingStatus,
    OTAChannelsPayload,
    OwnerPayload,
    PaymentMethodsPayload,
    RoomsPayload,
    StaffPayload,
    SubscriptionChoicePayload,
)
from app.services import onboarding_service
from app.services.onboarding_service import OnboardingError
from app.services.subscription_service import ensure_room_within_limit

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/status", response_model=OnboardingStatus)
def onboarding_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    return onboarding_service.get_status(db, hotel_id=context.hotel_id, actor_role=context.user_role)


@router.post("/owner", response_model=OnboardingStatus)
def set_owner(
    payload: OwnerPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.set_owner(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/identity", response_model=OnboardingStatus)
def set_identity(
    payload: HotelIdentityPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.set_hotel_identity(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/categories", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_categories(
    payload: CategoriesPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.upsert_categories(db, payload.categories, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/rooms", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_rooms(
    payload: RoomsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        ensure_room_within_limit(db, context.hotel_id)
        status_data = onboarding_service.upsert_rooms(db, payload.rooms, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/policy", response_model=OnboardingStatus)
def set_policy(
    payload: DepositPolicyPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.set_deposit_policy(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/payments", response_model=OnboardingStatus)
def set_payments(
    payload: PaymentMethodsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.upsert_payment_methods(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/ota", response_model=OnboardingStatus)
def set_ota(
    payload: OTAChannelsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.upsert_ota_channels(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/subscription-choice", response_model=OnboardingStatus)
def set_subscription_choice(
    payload: SubscriptionChoicePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        status_data = onboarding_service.set_subscription_choice(db, payload, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/staff", response_model=OnboardingStatus)
def set_staff(
    payload: StaffPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    status_data = onboarding_service.store_staff(db, payload.staff, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/finish", response_model=OnboardingStatus)
def finish(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        status_data = onboarding_service.finish_onboarding(
            db,
            hotel_id=context.hotel_id,
            actor_role=context.user_role,
        )
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))
