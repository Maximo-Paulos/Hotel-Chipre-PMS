"""
FastAPI routes for Hotel Configuration (Admin Panel).
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, get_auth_context, require_permission
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.schemas.hotel_config import HotelConfigRead, HotelConfigUpdate, HotelInterfaceLanguageRead
from app.services.email_service import mailer
from app.services.payment_service import get_hotel_config
from app.services.permission_service import (
    PERMISSION_CONFIG_MANAGE,
    PERMISSION_HOTEL_SETTINGS_READ,
    PERMISSION_SETTINGS_FX_MANAGE,
)
from app.services.hotel_configuration_service import apply_configuration_update
from app.services import audit_log_service
from app.services.permission_service import PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE

router = APIRouter(prefix="/api/config", tags=["Hotel Configuration"])


@router.get("/interface-language", response_model=HotelInterfaceLanguageRead)
def get_interface_language(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    """Expose only the selected UI language to authenticated hotel members."""
    language = (
        db.query(HotelConfiguration.interface_language)
        .filter(HotelConfiguration.id == context.hotel_id)
        .scalar()
    )
    return {"interface_language": "en" if language == "en" else "es"}


@router.get("/", response_model=HotelConfigRead)
def get_configuration(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_HOTEL_SETTINGS_READ)),
):
    config = get_hotel_config(db, context.hotel_id)
    db.commit()
    return config


@router.patch("/", response_model=HotelConfigRead)
def update_configuration(
    data: HotelConfigUpdate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CONFIG_MANAGE)),
):
    config = get_hotel_config(db, context.hotel_id)
    update_data = data.model_dump(exclude_unset=True)
    manual_rate_fields = (
        "manual_rate_min_adjustment_pct",
        "manual_rate_max_adjustment_pct",
    )
    changed_manual_rate_fields = {
        field: update_data[field]
        for field in manual_rate_fields
        if field in update_data and update_data[field] != getattr(config, field)
    }
    fx_fields = ("fx_conversion_rate_type", "fx_display_rate_types")
    fx_before = {field: getattr(config, field) for field in fx_fields}
    changed_fx_fields = {
        field: update_data[field]
        for field in fx_fields
        if field in update_data and update_data[field] != fx_before[field]
    }
    if changed_manual_rate_fields:
        # A combined pricing-policy save already requires the stronger owner-only
        # manual-rate permission and its action-bound step-up ticket. For an FX-only
        # change, use the shared Owner/Co-owner FX permission below.
        authorize_permission(
            request,
            db,
            context,
            PERMISSION_RESERVATION_MANUAL_RATE_POLICY_MANAGE,
        )
    elif changed_fx_fields:
        authorize_permission(
            request,
            db,
            context,
            PERMISSION_SETTINGS_FX_MANAGE,
        )

    manual_rate_min = update_data.get(
        "manual_rate_min_adjustment_pct",
        config.manual_rate_min_adjustment_pct,
    )
    manual_rate_max = update_data.get(
        "manual_rate_max_adjustment_pct",
        config.manual_rate_max_adjustment_pct,
    )
    if (manual_rate_min is None) != (manual_rate_max is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Configurá o limpiá juntos los dos límites de tarifa manual.",
        )
    if manual_rate_min is not None:
        if manual_rate_min < Decimal("-100") or manual_rate_min > manual_rate_max:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El límite inferior debe ser mayor o igual a -100% y no puede superar al superior.",
            )

    manual_rate_before = {
        field: getattr(config, field)
        for field in manual_rate_fields
    }
    apply_configuration_update(config, update_data)
    if changed_manual_rate_fields:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="hotel_configuration",
            record_id=config.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=manual_rate_before,
            payload_after={field: getattr(config, field) for field in manual_rate_fields},
        )
    if changed_fx_fields:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="hotel_configuration",
            record_id=config.id,
            action=AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before={field: fx_before[field] for field in changed_fx_fields},
            payload_after={field: getattr(config, field) for field in changed_fx_fields},
        )
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
