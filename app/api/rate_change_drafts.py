from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.daily_rate import DailyRate
from app.services.permission_service import PERMISSION_RATES_READ, PERMISSION_RATES_UPDATE
from app.services.read_model_cache import invalidate_hotel_operational_caches
from app.services.rate_change_draft_service import (
    MAX_DRAFT_DATES,
    RateDraftError,
    cancel_rate_change_draft,
    confirm_rate_change_draft,
    create_rate_change_draft,
    create_price_period_draft,
    get_rate_change_draft,
    list_rate_change_drafts,
    serialize_draft,
)
from app.services.timeseries_projection import project_daily_rate_change

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rate-change-drafts", tags=["Rate Change Drafts"])


class RateChangeItemIn(BaseModel):
    date: date
    values: dict[str, Any] = Field(..., min_length=1)


class RateChangeDraftIn(BaseModel):
    category_id: int = Field(..., gt=0)
    draft_type: Literal["daily_rates", "price_period"] = "daily_rates"
    changes: list[RateChangeItemIn] | None = Field(default=None, min_length=1, max_length=MAX_DRAFT_DATES)
    period_operation: dict[str, Any] | None = None


class RateChangeDecisionIn(BaseModel):
    expected_version: int = Field(..., ge=1)


class RateChangeDraftOut(BaseModel):
    id: int
    hotel_id: int
    category_id: int
    draft_type: str
    status: str
    version: int
    changes: list[dict[str, Any]]
    period_operation: dict[str, Any] | None = None
    impact: dict[str, Any]
    impact_at_creation: dict[str, Any]
    created_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None = None
    confirmed_by_user_id: int | None = None
    cancelled_at: datetime | None = None
    cancelled_by_user_id: int | None = None


def _raise_draft_http(exc: RateDraftError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _safe_rollback(db: Session) -> None:
    try:
        db.rollback()
    except Exception:
        logger.warning("rate_change_draft.rollback_failed")


@router.post("", response_model=RateChangeDraftOut, status_code=201)
def create_draft(
    payload: RateChangeDraftIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_UPDATE)),
):
    try:
        if payload.draft_type == "daily_rates":
            if payload.changes is None or payload.period_operation is not None:
                raise RateDraftError("El borrador diario debe incluir cambios diarios y no una operación de temporada.")
            draft = create_rate_change_draft(
                db,
                hotel_id=context.hotel_id,
                user_id=context.user_id,
                category_id=payload.category_id,
                changes=[item.model_dump() if hasattr(item, "model_dump") else item.dict() for item in payload.changes],
            )
        else:
            if payload.period_operation is None or payload.changes is not None:
                raise RateDraftError("El borrador de temporada debe incluir una operación y no cambios diarios.")
            draft = create_price_period_draft(
                db,
                hotel_id=context.hotel_id,
                user_id=context.user_id,
                category_id=payload.category_id,
                action=payload.period_operation.get("action", ""),
                period_id=payload.period_operation.get("period_id"),
                values=payload.period_operation.get("values"),
            )
        db.commit()
        db.refresh(draft)
        return serialize_draft(db, draft)
    except RateDraftError as exc:
        _safe_rollback(db)
        _raise_draft_http(exc)
    except IntegrityError as exc:
        _safe_rollback(db)
        logger.warning("rate_change_draft.create_conflict", extra={"hotel_id": context.hotel_id})
        raise HTTPException(status_code=409, detail="No se pudo crear el borrador porque la tarifa cambió. Reintentá.") from exc
    except Exception:
        _safe_rollback(db)
        raise


@router.get("", response_model=list[RateChangeDraftOut])
def list_drafts(
    category_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_READ)),
):
    try:
        drafts = list_rate_change_drafts(db, hotel_id=context.hotel_id, category_id=category_id, limit=limit)
        return [serialize_draft(db, draft) for draft in drafts]
    except Exception:
        raise


@router.get("/{draft_id}", response_model=RateChangeDraftOut)
def get_draft(
    draft_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_READ)),
):
    try:
        draft = get_rate_change_draft(db, hotel_id=context.hotel_id, draft_id=draft_id)
        return serialize_draft(db, draft)
    except RateDraftError as exc:
        _raise_draft_http(exc)


@router.post("/{draft_id}/confirm", response_model=RateChangeDraftOut)
def confirm_draft(
    draft_id: int,
    payload: RateChangeDecisionIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_UPDATE)),
):
    try:
        draft, touched = confirm_rate_change_draft(
            db,
            hotel_id=context.hotel_id,
            draft_id=draft_id,
            expected_version=payload.expected_version,
            user_id=context.user_id,
        )
        db.commit()
        db.refresh(draft)
    except RateDraftError as exc:
        _safe_rollback(db)
        _raise_draft_http(exc)
    except IntegrityError as exc:
        _safe_rollback(db)
        logger.warning("rate_change_draft.confirm_conflict", extra={"hotel_id": context.hotel_id, "draft_id": draft_id})
        raise HTTPException(status_code=409, detail="La tarifa cambió mientras se confirmaba. Actualizá y revisá el borrador.") from exc
    except Exception:
        _safe_rollback(db)
        raise
    changed_at = datetime.now().astimezone()
    if draft.draft_type == "price_period":
        for change in (draft.period_operation or {}).get("effective_changes", []):
            project_daily_rate_change(
                context.hotel_id,
                draft.category_id,
                date.fromisoformat(change["date"]),
                float(change["after"].get("price", 0)),
                changed_at,
            )
    else:
        for row in touched:
            project_daily_rate_change(context.hotel_id, draft.category_id, row.date, float(row.price), changed_at)
    invalidate_hotel_operational_caches(context.hotel_id)
    return serialize_draft(db, draft)


@router.post("/{draft_id}/cancel", response_model=RateChangeDraftOut)
def cancel_draft(
    draft_id: int,
    payload: RateChangeDecisionIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RATES_UPDATE)),
):
    try:
        draft = cancel_rate_change_draft(
            db,
            hotel_id=context.hotel_id,
            draft_id=draft_id,
            expected_version=payload.expected_version,
            user_id=context.user_id,
        )
        db.commit()
        db.refresh(draft)
        return serialize_draft(db, draft)
    except RateDraftError as exc:
        _safe_rollback(db)
        _raise_draft_http(exc)
    except Exception:
        _safe_rollback(db)
        raise
