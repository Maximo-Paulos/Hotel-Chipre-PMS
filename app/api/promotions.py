"""
Promotions API (v72 mobile-first pricing/promotions task).

CRUD for versioned, hotel-scoped promotions plus a simulation endpoint that
returns the full canonical price breakdown for a hypothetical booking without
persisting anything -- used by the no-code promotion builder UI.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.promotion import (
    PromotionCreate,
    PromotionRead,
    PromotionSimulateRequest,
    PromotionUpdate,
)
from app.services import promotion_service
from app.services.permission_service import PERMISSION_PROMOTIONS_MANAGE, PERMISSION_PROMOTIONS_READ
from app.services.promotion_pricing_service import CanonicalPricingError, compute_canonical_stay_pricing
from app.services.promotion_service import PromotionError

router = APIRouter(prefix="/api/promotions", tags=["Promotions"])


@router.get("", response_model=list[PromotionRead])
@router.get("/", response_model=list[PromotionRead], include_in_schema=False)
def list_promotions(
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_READ)),
) -> list[PromotionRead]:
    promotions = promotion_service.list_promotions(
        db, hotel_id=context.hotel_id, include_inactive=include_inactive
    )
    return [PromotionRead.from_model(promo) for promo in promotions]


@router.get("/{promotion_id}", response_model=PromotionRead)
def get_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_READ)),
) -> PromotionRead:
    try:
        promo = promotion_service.get_promotion(db, hotel_id=context.hotel_id, promotion_id=promotion_id)
    except PromotionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PromotionRead.from_model(promo)


@router.post("", response_model=PromotionRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PromotionRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_promotion(
    payload: PromotionCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_MANAGE)),
) -> PromotionRead:
    try:
        promo = promotion_service.create_promotion(
            db, hotel_id=context.hotel_id, payload=payload, created_by_user_id=context.user_id
        )
        db.commit()
    except PromotionError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.refresh(promo)
    return PromotionRead.from_model(promo)


@router.patch("/{promotion_id}", response_model=PromotionRead)
def update_promotion(
    promotion_id: int,
    payload: PromotionUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_MANAGE)),
) -> PromotionRead:
    """Creates a new immutable version; the previous version is deactivated.
    Reservations already booked against the previous version are unaffected
    (their pricing_snapshot froze the promotion id/version at booking time)."""
    try:
        promo = promotion_service.update_promotion(
            db, hotel_id=context.hotel_id, promotion_id=promotion_id, payload=payload, actor_user_id=context.user_id
        )
        db.commit()
    except PromotionError as exc:
        db.rollback()
        status_code = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    db.refresh(promo)
    return PromotionRead.from_model(promo)


@router.delete("/{promotion_id}", response_model=PromotionRead)
def deactivate_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_MANAGE)),
) -> PromotionRead:
    try:
        promo = promotion_service.deactivate_promotion(
            db, hotel_id=context.hotel_id, promotion_id=promotion_id, actor_user_id=context.user_id
        )
        db.commit()
    except PromotionError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.refresh(promo)
    return PromotionRead.from_model(promo)


@router.post("/{promotion_id}/reactivate", response_model=PromotionRead)
def reactivate_promotion(
    promotion_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_MANAGE)),
) -> PromotionRead:
    try:
        promo = promotion_service.reactivate_promotion(db, hotel_id=context.hotel_id, promotion_id=promotion_id)
        db.commit()
    except PromotionError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    db.refresh(promo)
    return PromotionRead.from_model(promo)


@router.post("/simulate")
def simulate_promotion_pricing(
    payload: PromotionSimulateRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_PROMOTIONS_READ)),
) -> dict:
    """Return which promotions would apply and the resulting price breakdown
    for a hypothetical booking. Persists nothing."""
    try:
        result = compute_canonical_stay_pricing(
            db,
            hotel_id=context.hotel_id,
            category_id=payload.category_id,
            check_in=payload.check_in_date,
            check_out=payload.check_out_date,
            booking_date=payload.booking_date,
            sales_channel_code=payload.sales_channel_code,
            guest_id=payload.guest_id,
            company_id=payload.company_id,
            payment_method=payload.payment_method,
            target_currency=payload.target_currency,
        )
    except CanonicalPricingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_snapshot_dict()
