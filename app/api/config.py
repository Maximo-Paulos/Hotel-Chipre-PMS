"""
FastAPI routes for Hotel Configuration (Admin Panel).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.hotel_config import HotelConfiguration
from app.schemas.hotel_config import HotelConfigRead, HotelConfigUpdate
from app.services.email_service import mailer
from app.services.payment_service import get_hotel_config
from app.services.permission_service import PERMISSION_CONFIG_MANAGE
from app.services.hotel_configuration_service import apply_configuration_update

router = APIRouter(prefix="/api/config", tags=["Hotel Configuration"])


@router.get("/", response_model=HotelConfigRead)
def get_configuration(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CONFIG_MANAGE)),
):
    config = get_hotel_config(db, context.hotel_id)
    db.commit()
    return config


@router.patch("/", response_model=HotelConfigRead)
def update_configuration(
    data: HotelConfigUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CONFIG_MANAGE)),
):
    config = get_hotel_config(db, context.hotel_id)
    update_data = data.model_dump(exclude_unset=True)
    apply_configuration_update(config, update_data)
    db.commit()
    db.refresh(config)
    return config


@router.get("/email/status")
def email_status(context: AuthContext = Depends(require_permission(PERMISSION_CONFIG_MANAGE))):
    """
    Lightweight status so the frontend can check the active system email provider.
    Returns only whether it is configured — never exposes credentials.
    """
    return {
        "configured": mailer.configured,
        "provider": mailer.provider_name,
    }
