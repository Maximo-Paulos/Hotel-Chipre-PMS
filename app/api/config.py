"""
FastAPI routes for Hotel Configuration (Admin Panel).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.hotel_config import HotelConfiguration
from app.schemas.hotel_config import HotelConfigRead, HotelConfigUpdate
from app.services.payment_service import get_hotel_config

router = APIRouter(prefix="/api/config", tags=["Hotel Configuration"])


@router.get("/", response_model=HotelConfigRead)
def get_configuration(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission("config:manage")),
):
    config = get_hotel_config(db, context.hotel_id)
    db.commit()
    return config


@router.patch("/", response_model=HotelConfigRead)
def update_configuration(
    data: HotelConfigUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission("config:manage")),
):
    config = get_hotel_config(db, context.hotel_id)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)
    db.commit()
    db.refresh(config)
    return config
