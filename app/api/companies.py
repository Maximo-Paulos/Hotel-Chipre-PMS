from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.analytics_api import CompanyCreate, CompanyRead, CompanyUpdate
from app.services.analytics_service import (
    create_company,
    deactivate_company,
    get_company_or_404,
    list_companies,
    require_analytics_plan,
    reactivate_company,
    update_company,
)


router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.get("", response_model=list[CompanyRead])
def get_companies(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return list_companies(db, context.hotel_id)


@router.post("", response_model=CompanyRead, status_code=201)
def create_new_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company = create_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, payload=payload)
    db.commit()
    db.refresh(company)
    return company


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return get_company_or_404(db, context.hotel_id, company_id)


@router.patch("/{company_id}", response_model=CompanyRead)
def patch_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company = update_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, company_id=company_id, payload=payload)
    db.commit()
    db.refresh(company)
    return company


@router.post("/{company_id}/deactivate", response_model=CompanyRead)
def deactivate_company_route(
    company_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
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
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    company = reactivate_company(db, hotel_id=context.hotel_id, user_id=context.user_id or 0, company_id=company_id)
    db.commit()
    db.refresh(company)
    return company
