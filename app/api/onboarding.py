"""
FastAPI routes for the onboarding flow used by smoke tests.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.hotel_config import HotelConfiguration
from app.services.email_service import mailer
from app.services.invitation_email_service import send_staff_invitation_email
from app.schemas.onboarding import (
    CategoriesPayload,
    DepositPolicyPayload,
    HotelIdentityPayload,
    OnboardingStatus,
    OTAChannelsPayload,
    OwnerPayload,
    PaymentMethodsPayload,
    RoomsPayload,
    StaffInvitationDelivery,
    StaffPayload,
    SubscriptionChoicePayload,
)
from app.services import onboarding_service
from app.services.permission_service import PERMISSION_HOTEL_SETTINGS_UPDATE
from app.services.onboarding_service import OnboardingError

router = APIRouter(prefix="/api/onboarding", tags=["Onboarding"])


@router.get("/status", response_model=OnboardingStatus)
def onboarding_status(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    return onboarding_service.get_status(db, hotel_id=context.hotel_id, actor_role=context.user_role)


@router.post("/owner", response_model=OnboardingStatus)
def set_owner(
    payload: OwnerPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    status_data = onboarding_service.set_owner(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/identity", response_model=OnboardingStatus)
def set_identity(
    payload: HotelIdentityPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    status_data = onboarding_service.set_hotel_identity(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/categories", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_categories(
    payload: CategoriesPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    status_data = onboarding_service.upsert_categories(db, payload.categories, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/rooms", response_model=OnboardingStatus, status_code=status.HTTP_201_CREATED)
def set_rooms(
    payload: RoomsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    try:
        status_data = onboarding_service.upsert_rooms(db, payload.rooms, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/policy", response_model=OnboardingStatus)
def set_policy(
    payload: DepositPolicyPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    status_data = onboarding_service.set_deposit_policy(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/payments", response_model=OnboardingStatus)
def set_payments(
    payload: PaymentMethodsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    try:
        status_data = onboarding_service.upsert_payment_methods(db, payload, hotel_id=context.hotel_id)
        db.commit()
        return status_data
    except OnboardingError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/ota", response_model=OnboardingStatus)
def set_ota(
    payload: OTAChannelsPayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    status_data = onboarding_service.upsert_ota_channels(db, payload, hotel_id=context.hotel_id)
    db.commit()
    return status_data


@router.post("/subscription-choice", response_model=OnboardingStatus)
def set_subscription_choice(
    payload: SubscriptionChoicePayload,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
):
    try:
        result = onboarding_service.store_staff(
            db,
            payload.staff,
            hotel_id=context.hotel_id,
            actor_user_id=context.user_id,
            actor_email=context.user_email,
            actor_role=context.user_role,
        )
        db.commit()
        hotel = db.get(HotelConfiguration, context.hotel_id)
        hotel_name = hotel.hotel_name if hotel else f"Hotel {context.hotel_id}"
        settings = get_settings()
        deliveries = []
        for provision in result.invitations:
            _, delivery = send_staff_invitation_email(
                email=provision.invitation.email,
                hotel_name=hotel_name,
                role=provision.invitation.role,
                inviter_email=context.user_email or "",
                token=provision.token,
                frontend_url=settings.FRONTEND_URL,
                sender=mailer,
            )
            deliveries.append(
                StaffInvitationDelivery(
                    invitation_id=provision.invitation.id,
                    email=provision.invitation.email,
                    role=provision.invitation.role,
                    email_delivery=delivery,
                )
            )
        status_data = result.status
        status_data["staff_invitations"] = deliveries
        return status_data
    except OnboardingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/finish", response_model=OnboardingStatus)
def finish(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_UPDATE)),
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
