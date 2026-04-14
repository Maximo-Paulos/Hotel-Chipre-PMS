"""
FastAPI routes for the commercial configuration domain.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.schemas.commercial import (
    FxPolicyCreate,
    FxPolicyRead,
    FxPolicyUpdate,
    RatePlanCreate,
    RatePlanRead,
    RatePlanUpdate,
    SellableProductCreate,
    SellableProductRead,
    SellableProductUpdate,
    TaxPolicyCreate,
    TaxPolicyRead,
    TaxPolicyUpdate,
)
from app.services.commercial_service import (
    CommercialConfigError,
    create_fx_policy,
    create_rate_plan,
    create_sellable_product,
    create_tax_policy,
    list_fx_policies,
    list_rate_plans,
    list_sellable_products,
    list_tax_policies,
    update_fx_policy,
    update_rate_plan,
    update_sellable_product,
    update_tax_policy,
)

router = APIRouter(prefix="/api/commercial", tags=["Commercial Configuration"])


@router.get("/products", response_model=list[SellableProductRead])
def get_sellable_products(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_sellable_products(db, hotel_id=context.hotel_id)


@router.post("/products", response_model=SellableProductRead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: SellableProductCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        product = create_sellable_product(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        return product
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/products/{product_id}", response_model=SellableProductRead)
def patch_product(
    product_id: int,
    payload: SellableProductUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        product = update_sellable_product(db, hotel_id=context.hotel_id, product_id=product_id, payload=payload)
        db.commit()
        return product
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/rate-plans", response_model=list[RatePlanRead])
def get_rate_plans(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_rate_plans(db, hotel_id=context.hotel_id)


@router.post("/rate-plans", response_model=RatePlanRead, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: RatePlanCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        rate_plan = create_rate_plan(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        return rate_plan
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/rate-plans/{rate_plan_id}", response_model=RatePlanRead)
def patch_rate_plan(
    rate_plan_id: int,
    payload: RatePlanUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        rate_plan = update_rate_plan(db, hotel_id=context.hotel_id, rate_plan_id=rate_plan_id, payload=payload)
        db.commit()
        return rate_plan
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/tax-policies", response_model=list[TaxPolicyRead])
def get_tax_policies(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_tax_policies(db, hotel_id=context.hotel_id)


@router.post("/tax-policies", response_model=TaxPolicyRead, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: TaxPolicyCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        policy = create_tax_policy(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        return policy
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/tax-policies/{policy_id}", response_model=TaxPolicyRead)
def patch_tax_policy(
    policy_id: int,
    payload: TaxPolicyUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        policy = update_tax_policy(db, hotel_id=context.hotel_id, policy_id=policy_id, payload=payload)
        db.commit()
        return policy
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/fx-policies", response_model=list[FxPolicyRead])
def get_fx_policies(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
):
    return list_fx_policies(db, hotel_id=context.hotel_id)


@router.post("/fx-policies", response_model=FxPolicyRead, status_code=status.HTTP_201_CREATED)
def create_fx(
    payload: FxPolicyCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        policy = create_fx_policy(db, hotel_id=context.hotel_id, payload=payload)
        db.commit()
        return policy
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/fx-policies/{policy_id}", response_model=FxPolicyRead)
def patch_fx_policy(
    policy_id: int,
    payload: FxPolicyUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner")),
):
    try:
        policy = update_fx_policy(db, hotel_id=context.hotel_id, policy_id=policy_id, payload=payload)
        db.commit()
        return policy
    except CommercialConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))
