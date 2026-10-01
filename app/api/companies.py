from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.dependencies.auth import AuthContext, require_all_permissions, require_permission
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
from app.services.permission_service import (
    PERMISSION_COMPANY_MANAGE,
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
    context: AuthContext = Depends(require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return list_companies(db, context.hotel_id)


@router.post("", response_model=CompanyRead, status_code=201)
def create_new_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
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
    context: AuthContext = Depends(require_all_permissions(PERMISSION_COMPANY_MANAGE, PERMISSION_COMPANY_VIEW)),
):
    require_analytics_plan(db, context.hotel_id, "pro")
    return get_company_or_404(db, context.hotel_id, company_id)


@router.patch("/{company_id}", response_model=CompanyRead)
def patch_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_COMPANY_MANAGE)),
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
