"""
V72 §8.5 — Daily rate management API.

  GET  /api/rates/category/{category_id}
  POST /api/rates/category/{category_id}/daily
  POST /api/rates/category/{category_id}/bulk

  GET    /api/rates/periods
  POST   /api/rates/periods
  PATCH  /api/rates/periods/{period_id}
  DELETE /api/rates/periods/{period_id}
  POST   /api/rates/periods/{period_id}/apply
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.audit_log import AuditActionEnum
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.room import RoomCategory
from app.services import audit_log_service
from app.services.pricing_service import (
    apply_price_period,
    get_price_for_date,
    resolve_rate_calendar,
)
from app.services.timeseries_projection import project_daily_rate_change

router = APIRouter(prefix="/api/rates", tags=["Daily Rates"])

_WRITE_ROLES = ("owner", "co_owner", "manager")
_READ_ROLES = ("owner", "co_owner", "manager")

# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class DailyRateOut(BaseModel):
    id: int
    hotel_id: int
    category_id: int
    date: date
    price: float
    price_cash: Optional[float] = None
    price_transfer: Optional[float] = None
    price_mercadopago: Optional[float] = None
    price_paypal: Optional[float] = None
    price_credit_card: Optional[float] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DailyRateFallbackOut(BaseModel):
    """Row returned for GET range — may be a real DailyRate or a synthesised fallback."""

    date: date
    price: float
    price_cash: Optional[float] = None
    price_transfer: Optional[float] = None
    price_mercadopago: Optional[float] = None
    price_paypal: Optional[float] = None
    price_credit_card: Optional[float] = None
    source: str  # "daily_rate" | "price_period" | "category_pricing" | "none"
    daily_rate_id: Optional[int] = None


class DailyRateIn(BaseModel):
    date: date
    price: float = Field(..., ge=0)
    price_cash: Optional[float] = Field(None, ge=0)
    price_transfer: Optional[float] = Field(None, ge=0)
    price_mercadopago: Optional[float] = Field(None, ge=0)
    price_paypal: Optional[float] = Field(None, ge=0)
    price_credit_card: Optional[float] = Field(None, ge=0)


class BulkRateIn(BaseModel):
    from_date: date
    to_date: date
    price: float = Field(..., ge=0)
    price_cash: Optional[float] = Field(None, ge=0)
    price_transfer: Optional[float] = Field(None, ge=0)
    price_mercadopago: Optional[float] = Field(None, ge=0)
    price_paypal: Optional[float] = Field(None, ge=0)
    price_credit_card: Optional[float] = Field(None, ge=0)
    exclude_dates: List[date] = Field(default_factory=list)


class BulkFieldRateIn(BaseModel):
    from_date: date
    to_date: date
    field: str = Field(..., pattern="^(price|price_cash|price_transfer|price_mercadopago|price_paypal|price_credit_card)$")
    mode: str = Field(..., pattern="^(set|amount_delta|percent_delta)$")
    value: float
    exclude_dates: List[date] = Field(default_factory=list)


class BulkRateOut(BaseModel):
    created: int
    updated: int


class PricePeriodIn(BaseModel):
    category_id: int
    name: str = Field(..., max_length=100)
    start_date: date
    end_date: date
    price_per_night: float = Field(..., ge=0)
    priority: int = Field(0, ge=0)
    is_active: bool = True


class PricePeriodPatch(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    price_per_night: Optional[float] = Field(None, ge=0)
    priority: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class PricePeriodOut(BaseModel):
    id: int
    hotel_id: int
    category_id: int
    name: str
    start_date: date
    end_date: date
    price_per_night: float
    priority: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApplyPeriodOut(BaseModel):
    applied_dates: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_category_or_404(db: Session, hotel_id: int, category_id: int) -> RoomCategory:
    cat = (
        db.query(RoomCategory)
        .filter(RoomCategory.id == category_id, RoomCategory.hotel_id == hotel_id)
        .first()
    )
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return cat


def _resolve_source(
    db: Session,
    hotel_id: int,
    category_id: int,
    target_date: date,
) -> str:
    from app.models.daily_rate import DailyRate, PricePeriod
    from app.models.pricing import CategoryPricing
    from app.models.room import RoomCategory

    if db.query(DailyRate).filter(
        DailyRate.hotel_id == hotel_id,
        DailyRate.category_id == category_id,
        DailyRate.date == target_date,
    ).first():
        return "daily_rate"
    if db.query(PricePeriod).filter(
        PricePeriod.hotel_id == hotel_id,
        PricePeriod.category_id == category_id,
        PricePeriod.deleted_at.is_(None),
        PricePeriod.is_active == True,
        PricePeriod.start_date <= target_date,
        PricePeriod.end_date >= target_date,
    ).first():
        return "price_period"
    if db.query(CategoryPricing).join(
        RoomCategory, RoomCategory.id == CategoryPricing.category_id
    ).filter(
        CategoryPricing.category_id == category_id,
        RoomCategory.hotel_id == hotel_id,
    ).first():
        return "category_pricing"
    return "none"


# ---------------------------------------------------------------------------
# GET /api/rates/category/{category_id}
# ---------------------------------------------------------------------------


@router.get(
    "/category/{category_id}",
    response_model=List[DailyRateFallbackOut],
    summary="Get daily rates for a category in a date range (with fallback)",
)
def get_category_rates(
    category_id: int,
    from_date: date = Query(...),
    to_date: date = Query(...),
    payment_method: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_READ_ROLES)),
):
    if to_date < from_date:
        raise HTTPException(status_code=422, detail="to_date must be >= from_date")
    if (to_date - from_date).days > 366:
        raise HTTPException(status_code=422, detail="Date range cannot exceed 366 days")

    _get_category_or_404(db, context.hotel_id, category_id)

    # Batched resolution: a fixed number of queries for the whole range instead of
    # ~6 queries per date (previously up to ~2000 queries for a one-year calendar).
    resolved = resolve_rate_calendar(
        db,
        context.hotel_id,
        category_id,
        from_date,
        to_date,
        payment_method=payment_method,
    )
    return [DailyRateFallbackOut(**row) for row in resolved]


# ---------------------------------------------------------------------------
# POST /api/rates/category/{category_id}/daily  — upsert single date
# ---------------------------------------------------------------------------


@router.post(
    "/category/{category_id}/daily",
    response_model=DailyRateOut,
    status_code=200,
    summary="Upsert a single daily rate",
)
def upsert_daily_rate(
    category_id: int,
    payload: DailyRateIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    _get_category_or_404(db, context.hotel_id, category_id)

    existing = (
        db.query(DailyRate)
        .filter(
            DailyRate.hotel_id == context.hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date == payload.date,
        )
        .first()
    )
    if existing is None:
        before = None
        row = DailyRate(
            hotel_id=context.hotel_id,
            category_id=category_id,
            date=payload.date,
            price=payload.price,
            price_cash=payload.price_cash,
            price_transfer=payload.price_transfer,
            price_mercadopago=payload.price_mercadopago,
            price_paypal=payload.price_paypal,
            price_credit_card=payload.price_credit_card,
            created_by_user_id=context.user_id,
        )
        db.add(row)
    else:
        before = audit_log_service.model_snapshot(existing)
        existing.price = payload.price
        existing.price_cash = payload.price_cash
        existing.price_transfer = payload.price_transfer
        existing.price_mercadopago = payload.price_mercadopago
        existing.price_paypal = payload.price_paypal
        existing.price_credit_card = payload.price_credit_card
        existing.updated_at = datetime.now(timezone.utc)
        row = existing

    db.commit()
    db.refresh(row)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="daily_rates",
        record_id=row.id,
        action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(row),
    )
    project_daily_rate_change(
        context.hotel_id,
        category_id,
        row.date,
        row.price,
        row.updated_at,
    )
    return row


# ---------------------------------------------------------------------------
# POST /api/rates/category/{category_id}/bulk
# ---------------------------------------------------------------------------


@router.post(
    "/category/{category_id}/bulk",
    response_model=BulkRateOut,
    status_code=200,
    summary="Bulk-upsert daily rates for a date range",
)
def bulk_upsert_daily_rates(
    category_id: int,
    payload: BulkRateIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    if payload.to_date < payload.from_date:
        raise HTTPException(status_code=422, detail="to_date must be >= from_date")
    if (payload.to_date - payload.from_date).days > 730:
        raise HTTPException(status_code=422, detail="Bulk range cannot exceed 730 days")

    _get_category_or_404(db, context.hotel_id, category_id)
    exclude = set(payload.exclude_dates)

    # Pre-fetch existing rows in range
    existing_map: dict[date, DailyRate] = {
        r.date: r
        for r in db.query(DailyRate).filter(
            DailyRate.hotel_id == context.hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date >= payload.from_date,
            DailyRate.date <= payload.to_date,
        )
    }

    created = updated = 0
    touched_dates: list[date] = []
    touched_rows: list[tuple[DailyRate, dict | None]] = []
    current = payload.from_date
    while current <= payload.to_date:
        if current not in exclude:
            touched_dates.append(current)
            if current in existing_map:
                r = existing_map[current]
                before = audit_log_service.model_snapshot(r)
                r.price = payload.price
                r.price_cash = payload.price_cash
                r.price_transfer = payload.price_transfer
                r.price_mercadopago = payload.price_mercadopago
                r.price_paypal = payload.price_paypal
                r.price_credit_card = payload.price_credit_card
                r.updated_at = datetime.now(timezone.utc)
                touched_rows.append((r, before))
                updated += 1
            else:
                r = DailyRate(
                    hotel_id=context.hotel_id,
                    category_id=category_id,
                    date=current,
                    price=payload.price,
                    price_cash=payload.price_cash,
                    price_transfer=payload.price_transfer,
                    price_mercadopago=payload.price_mercadopago,
                    price_paypal=payload.price_paypal,
                    price_credit_card=payload.price_credit_card,
                    created_by_user_id=context.user_id,
                )
                db.add(r)
                touched_rows.append((r, None))
                created += 1
        current += timedelta(days=1)

    db.commit()
    for row, before in touched_rows:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="daily_rates",
            record_id=row.id,
            action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(row),
        )
    changed_at = datetime.now(timezone.utc)
    for touched_date in touched_dates:
        project_daily_rate_change(
            context.hotel_id,
            category_id,
            touched_date,
            payload.price,
            changed_at,
        )
    return BulkRateOut(created=created, updated=updated)


# ---------------------------------------------------------------------------
# POST /api/rates/category/{category_id}/bulk-field
# ---------------------------------------------------------------------------


def _bulk_field_value(base_price: float, current_value: float | None, payload: BulkFieldRateIn) -> float:
    reference = base_price if payload.field != "price" else (current_value if current_value is not None else base_price)
    if payload.mode == "set":
        result = payload.value
    elif payload.mode == "amount_delta":
        result = reference + payload.value
    else:
        result = reference * (1 + (payload.value / 100.0))
    if result < 0:
        raise HTTPException(status_code=422, detail="Resulting rate value cannot be negative")
    return round(float(result), 2)


@router.post(
    "/category/{category_id}/bulk-field",
    response_model=BulkRateOut,
    status_code=200,
    summary="Bulk-update one daily rate field without overwriting other prices",
)
def bulk_update_daily_rate_field(
    category_id: int,
    payload: BulkFieldRateIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    if payload.to_date < payload.from_date:
        raise HTTPException(status_code=422, detail="to_date must be >= from_date")
    if (payload.to_date - payload.from_date).days > 730:
        raise HTTPException(status_code=422, detail="Bulk range cannot exceed 730 days")

    category = _get_category_or_404(db, context.hotel_id, category_id)
    exclude = set(payload.exclude_dates)

    existing_map: dict[date, DailyRate] = {
        r.date: r
        for r in db.query(DailyRate).filter(
            DailyRate.hotel_id == context.hotel_id,
            DailyRate.category_id == category_id,
            DailyRate.date >= payload.from_date,
            DailyRate.date <= payload.to_date,
        )
    }

    created = updated = 0
    touched_dates: list[date] = []
    touched_rows: list[tuple[DailyRate, dict | None]] = []
    current = payload.from_date
    while current <= payload.to_date:
        if current in exclude:
            current += timedelta(days=1)
            continue

        touched_dates.append(current)
        existing = existing_map.get(current)
        if existing is None:
            fallback_price = get_price_for_date(db, context.hotel_id, category_id, current)
            source = _resolve_source(db, context.hotel_id, category_id, current)
            base_price = fallback_price if source != "none" else float(category.base_price_per_night or 0.0)
            row = DailyRate(
                hotel_id=context.hotel_id,
                category_id=category_id,
                date=current,
                price=round(float(base_price), 2),
                created_by_user_id=context.user_id,
            )
            before = None
            created += 1
            db.add(row)
        else:
            row = existing
            before = audit_log_service.model_snapshot(row)
            updated += 1

        base_price = round(float(row.price), 2)
        current_value = getattr(row, payload.field)
        setattr(row, payload.field, _bulk_field_value(base_price, current_value, payload))
        row.updated_at = datetime.now(timezone.utc)
        touched_rows.append((row, before))
        current += timedelta(days=1)

    db.commit()
    for row, before in touched_rows:
        audit_log_service.safe_create_audit_log(
            db,
            hotel_id=context.hotel_id,
            table_name="daily_rates",
            record_id=row.id,
            action=AuditActionEnum.CREATE if before is None else AuditActionEnum.UPDATE,
            actor_user_id=context.user_id,
            payload_before=before,
            payload_after=audit_log_service.model_snapshot(row),
        )
    changed_at = datetime.now(timezone.utc)
    for touched_date in touched_dates:
        row = existing_map.get(touched_date)
        projected_price = row.price if row is not None else get_price_for_date(db, context.hotel_id, category_id, touched_date)
        project_daily_rate_change(
            context.hotel_id,
            category_id,
            touched_date,
            projected_price,
            changed_at,
        )
    return BulkRateOut(created=created, updated=updated)


# ---------------------------------------------------------------------------
# Price Periods CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/periods",
    response_model=List[PricePeriodOut],
    summary="List price periods for the active hotel",
)
def list_price_periods(
    category_id: Optional[int] = Query(None),
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_READ_ROLES)),
):
    q = db.query(PricePeriod).filter(
        PricePeriod.hotel_id == context.hotel_id,
        PricePeriod.deleted_at.is_(None),
    )
    if category_id is not None:
        q = q.filter(PricePeriod.category_id == category_id)
    if active_only:
        q = q.filter(PricePeriod.is_active == True)
    return q.order_by(PricePeriod.start_date.asc(), PricePeriod.priority.desc()).all()


@router.post(
    "/periods",
    response_model=PricePeriodOut,
    status_code=201,
    summary="Create a price period",
)
def create_price_period(
    payload: PricePeriodIn,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=422, detail="end_date must be >= start_date")
    _get_category_or_404(db, context.hotel_id, payload.category_id)

    period = PricePeriod(
        hotel_id=context.hotel_id,
        category_id=payload.category_id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        price_per_night=payload.price_per_night,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(period)
    db.commit()
    db.refresh(period)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="price_periods",
        record_id=period.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=context.user_id,
        payload_after=audit_log_service.model_snapshot(period),
    )
    return period


@router.patch(
    "/periods/{period_id}",
    response_model=PricePeriodOut,
    summary="Update a price period",
)
def update_price_period(
    period_id: int,
    payload: PricePeriodPatch,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    period = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.id == period_id,
            PricePeriod.hotel_id == context.hotel_id,
            PricePeriod.deleted_at.is_(None),
        )
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Price period not found")

    before = audit_log_service.model_snapshot(period)
    if payload.name is not None:
        period.name = payload.name
    if payload.start_date is not None:
        period.start_date = payload.start_date
    if payload.end_date is not None:
        period.end_date = payload.end_date
    if payload.price_per_night is not None:
        period.price_per_night = payload.price_per_night
    if payload.priority is not None:
        period.priority = payload.priority
    if payload.is_active is not None:
        period.is_active = payload.is_active

    # Validate after update
    if period.end_date < period.start_date:
        db.rollback()
        raise HTTPException(status_code=422, detail="end_date must be >= start_date")

    db.commit()
    db.refresh(period)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="price_periods",
        record_id=period.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(period),
    )
    return period


@router.delete(
    "/periods/{period_id}",
    status_code=204,
    summary="Delete a price period",
)
def delete_price_period(
    period_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    period = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.id == period_id,
            PricePeriod.hotel_id == context.hotel_id,
            PricePeriod.deleted_at.is_(None),
        )
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Price period not found")
    before = audit_log_service.model_snapshot(period)
    period.deleted_at = datetime.now(timezone.utc)
    period.deleted_by_user_id = context.user_id
    db.commit()
    db.refresh(period)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="price_periods",
        record_id=period.id,
        action=AuditActionEnum.DELETE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(period),
    )


@router.post(
    "/periods/{period_id}/apply",
    response_model=ApplyPeriodOut,
    summary="Materialise a price period into daily_rates rows",
)
def apply_period_to_daily_rates(
    period_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles(*_WRITE_ROLES)),
):
    period = (
        db.query(PricePeriod)
        .filter(
            PricePeriod.id == period_id,
            PricePeriod.hotel_id == context.hotel_id,
            PricePeriod.deleted_at.is_(None),
        )
        .first()
    )
    if not period:
        raise HTTPException(status_code=404, detail="Price period not found")

    try:
        count = apply_price_period(
            db,
            hotel_id=context.hotel_id,
            category_id=period.category_id,
            period_id=period_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    db.commit()
    current = period.start_date
    changed_at = datetime.now(timezone.utc)
    while current <= period.end_date:
        project_daily_rate_change(
            context.hotel_id,
            period.category_id,
            current,
            period.price_per_night,
            changed_at,
        )
        current += timedelta(days=1)
    return ApplyPeriodOut(applied_dates=count)
