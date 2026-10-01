from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.dependencies.auth import AuthContext, authorize_permission, require_all_permissions, require_permission
from app.schemas.analytics_api import CompanyCreate, CompanyRead, CompanyUpdate
from app.schemas.company_night_charge import (
    CompanyNightlySurchargeRateCreate,
    CompanyNightlySurchargeRateRead,
    CompanyNightlySurchargeRatesRead,
)
from app.services.analytics_service import (
    create_company,
    deactivate_company,
    get_company_or_404,
    list_companies,
    require_analytics_plan,
    reactivate_company,
    update_company,
)
from app.services.company_night_charge_service import (
    CompanyNightChargeError,
    create_company_nightly_surcharge_rate,
    list_company_nightly_surcharge_rates,
)
from app.services.timezones import hotel_today
from app.services.permission_service import (
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_COMPANY_NIGHT_RATE_MANAGE,
    PERMISSION_COMPANY_VIEW,
    PERMISSION_RESERVATION_READ,
)


router = APIRouter(prefix="/api/companies", tags=["Companies"])


class CompanyOptionRead(BaseModel):
    id: int
    display_name: str
    legal_name: str
    is_active: bool
    payment_deferred: bool


@router.get("/options", response_model=list[CompanyOptionRead])
def get_company_options(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    """Return only the names needed to link a reservation to a company."""
    require_analytics_plan(db, context.hotel_id, "pro")
    return [
        {
            "id": row.id,
            "display_name": row.display_name,
            "legal_name": row.legal_name,
            "is_active": row.is_active,
            "payment_deferred": row.payment_deferred,
        }
        for row in db.query(Company)
        .filter(Company.hotel_id == context.hotel_id)
        .order_by(Company.is_active.desc(), Company.display_name.asc(), Company.id.asc())
        .all()
    ]


@router.get("", response_model=list[CompanyRead])
def get_companies(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_VIEW)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return list_companies(db, context.hotel_id)


@router.post("", response_model=CompanyRead, status_code=201)
def create_new_company(
    payload: CompanyCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    if payload.extra_person_nightly_surcharge is not None:
        authorize_permission(request, db, context, PERMISSION_COMPANY_NIGHT_RATE_MANAGE)
    company = create_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, payload=payload)
    if payload.extra_person_nightly_surcharge is not None:
        create_company_nightly_surcharge_rate(
            db,
            hotel_id=context.hotel_id,
            company_id=company.id,
            effective_from=hotel_today(db, context.hotel_id),
            amount=payload.extra_person_nightly_surcharge,
            actor_user_id=context.user_id,
        )
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_VIEW)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return get_company_or_404(db, context.hotel_id, company_id)


@router.get("/{company_id}/nightly-rates", response_model=CompanyNightlySurchargeRatesRead)
def get_company_nightly_rates(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_VIEW)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    try:
        return {
            "hotel_today": hotel_today(db, context.hotel_id),
            "rates": list_company_nightly_surcharge_rates(
                db,
                hotel_id=context.hotel_id,
                company_id=company_id,
            ),
        }
    except CompanyNightChargeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/{company_id}/nightly-rates",
    response_model=CompanyNightlySurchargeRateRead,
    status_code=201,
)
def create_company_nightly_rate(
    company_id: int,
    payload: CompanyNightlySurchargeRateCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_NIGHT_RATE_MANAGE)
    ),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    try:
        rate = create_company_nightly_surcharge_rate(
            db,
            hotel_id=context.hotel_id,
            company_id=company_id,
            effective_from=payload.effective_from,
            amount=payload.amount,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(rate)
        return rate
    except CompanyNightChargeError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{company_id}", response_model=CompanyRead)
def patch_company(
    company_id: int,
    payload: CompanyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company_before = get_company_or_404(db, context.hotel_id, company_id)
    previous_surcharge = company_before.extra_person_nightly_surcharge
    surcharge_was_submitted = "extra_person_nightly_surcharge" in payload.model_fields_set
    next_surcharge = payload.extra_person_nightly_surcharge
    surcharge_changed = surcharge_was_submitted and (
        (previous_surcharge is None) != (next_surcharge is None)
        or (
            previous_surcharge is not None
            and next_surcharge is not None
            and Decimal(str(previous_surcharge)).quantize(Decimal("0.01"))
            != Decimal(str(next_surcharge)).quantize(Decimal("0.01"))
        )
    )
    if surcharge_changed:
        authorize_permission(request, db, context, PERMISSION_COMPANY_NIGHT_RATE_MANAGE)
    company = update_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, company_id=company_id, payload=payload)
    if surcharge_changed:
        create_company_nightly_surcharge_rate(
            db,
            hotel_id=context.hotel_id,
            company_id=company_id,
            effective_from=hotel_today(db, context.hotel_id),
            amount=next_surcharge or Decimal("0.00"),
            actor_user_id=context.user_id,
        )
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/deactivate", response_model=CompanyRead)
def deactivate_company_route(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company = deactivate_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, company_id=company_id)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/reactivate", response_model=CompanyRead)
def reactivate_company_route(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company = reactivate_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, company_id=company_id)
    db.commit()
    db.refresh(company)
    return company
