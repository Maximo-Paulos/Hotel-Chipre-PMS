"""Experimental tariff suggestions and hotel-owned recommendation policy."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.audit_log import AuditActionEnum
from app.models.hotel_config import HotelConfiguration
from app.services import audit_log_service
from app.services.permission_service import (
    PERMISSION_CONFIG_MANAGE,
    PERMISSION_RATES_READ,
    PERMISSION_RATES_UPDATE,
)
from app.services.rate_change_draft_service import RateDraftError, serialize_draft
from app.services.tariff_recommendation_service import (
    generate_category_rate_recommendations,
)

router = APIRouter(prefix="/api/tariff-recommendations", tags=["Tariff Recommendations"])


class TariffRecommendationSettings(BaseModel):
    enabled: bool
    high_occupancy_pct: Decimal = Field(ge=Decimal(0), le=Decimal(100))
    low_occupancy_pct: Decimal = Field(ge=Decimal(0), le=Decimal(100))
    pickup_change_pct: Decimal = Field(gt=Decimal(0), le=Decimal(500))
    max_step_pct: Decimal = Field(gt=Decimal(0), le=Decimal(5))

    @model_validator(mode="after")
    def validate_occupancy_order(self):
        if self.low_occupancy_pct >= self.high_occupancy_pct:
            raise ValueError("El umbral de ocupación baja debe ser menor al umbral de ocupación alta.")
        return self


class TariffRecommendationSettingsOut(TariffRecommendationSettings):
    hotel_id: int


class TariffRecommendationRunIn(BaseModel):
    category_id: int = Field(gt=0)
    date_from: date
    date_to: date


class TariffRecommendationRunOut(BaseModel):
    created: bool
    reason: str | None = None
    draft_id: int | None = None
    suggestions: list[dict]
    skipped: dict[str, int] = Field(default_factory=dict)
    draft: dict | None = None


def _settings_out(config: HotelConfiguration) -> TariffRecommendationSettingsOut:
    return TariffRecommendationSettingsOut(
        hotel_id=config.id,
        enabled=bool(config.tariff_recommendations_enabled),
        high_occupancy_pct=config.tariff_high_occupancy_pct,
        low_occupancy_pct=config.tariff_low_occupancy_pct,
        pickup_change_pct=config.tariff_pickup_change_pct,
        max_step_pct=config.tariff_max_step_pct,
    )


@router.get("/settings", response_model=TariffRecommendationSettingsOut)
def read_settings(
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_permission(PERMISSION_RATES_READ))],
):
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == context.hotel_id).one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="No se encontró la configuración del hotel.")
    return _settings_out(config)


@router.put("/settings", response_model=TariffRecommendationSettingsOut)
def update_settings(
    payload: TariffRecommendationSettings,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_permission(PERMISSION_CONFIG_MANAGE))],
):
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == context.hotel_id).one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="No se encontró la configuración del hotel.")
    before = audit_log_service.model_snapshot(config)
    config.tariff_recommendations_enabled = payload.enabled
    config.tariff_high_occupancy_pct = payload.high_occupancy_pct
    config.tariff_low_occupancy_pct = payload.low_occupancy_pct
    config.tariff_pickup_change_pct = payload.pickup_change_pct
    config.tariff_max_step_pct = payload.max_step_pct
    db.flush()
    audit_log_service.create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="hotel_configuration",
        record_id=context.hotel_id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(config),
    )
    db.commit()
    db.refresh(config)
    return _settings_out(config)


@router.post("/generate", response_model=TariffRecommendationRunOut)
def generate_recommendation(
    payload: TariffRecommendationRunIn,
    db: Annotated[Session, Depends(get_db)],
    context: Annotated[AuthContext, Depends(require_permission(PERMISSION_RATES_UPDATE))],
):
    try:
        result = generate_category_rate_recommendations(
            db,
            hotel_id=context.hotel_id,
            category_id=payload.category_id,
            date_from=payload.date_from,
            date_to=payload.date_to,
            user_id=context.user_id,
            trigger="operator_requested",
            now=datetime.now().astimezone(),
        )
        draft = result.get("draft")
        if draft is not None:
            db.commit()
            db.refresh(draft)
        return TariffRecommendationRunOut(
            created=bool(result.get("created")),
            reason=result.get("reason"),
            draft_id=draft.id if draft is not None else None,
            suggestions=result.get("suggestions", []),
            skipped=result.get("skipped", {}),
            draft=serialize_draft(db, draft) if draft is not None else None,
        )
    except (ValueError, RateDraftError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise
