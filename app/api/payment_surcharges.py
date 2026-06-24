"""
Payment surcharges API - v72 section 12.3.

GET    /api/payment-surcharges          - list active surcharges for hotel
POST   /api/payment-surcharges          - create a surcharge
PATCH  /api/payment-surcharges/{id}     - update amount/type/active flag
DELETE /api/payment-surcharges/{id}     - deactivate a surcharge
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_roles
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum

router = APIRouter(prefix="/api/payment-surcharges", tags=["Payment Surcharges"])


class PaymentSurchargeRead(BaseModel):
    id: int
    hotel_id: int
    payment_method: str
    surcharge_type: PaymentSurchargeTypeEnum
    amount: float
    currency_code: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentSurchargeCreate(BaseModel):
    payment_method: str = Field(..., max_length=50)
    surcharge_type: PaymentSurchargeTypeEnum
    amount: float = Field(..., ge=0)
    currency_code: str = Field(default="ARS", max_length=3)


class PaymentSurchargeUpdate(BaseModel):
    payment_method: Optional[str] = Field(default=None, max_length=50)
    surcharge_type: Optional[PaymentSurchargeTypeEnum] = None
    amount: Optional[float] = Field(default=None, ge=0)
    currency_code: Optional[str] = Field(default=None, max_length=3)
    is_active: Optional[bool] = None


def _get_surcharge_or_404(db: Session, surcharge_id: int, hotel_id: int) -> PaymentSurcharge:
    surcharge = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.id == surcharge_id,
            PaymentSurcharge.hotel_id == hotel_id,
        )
        .first()
    )
    if not surcharge:
        raise HTTPException(status_code=404, detail="Surcharge not found")
    return surcharge


@router.get("", response_model=list[PaymentSurchargeRead])
@router.get("/", response_model=list[PaymentSurchargeRead], include_in_schema=False)
def list_payment_surcharges(
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager", "receptionist")),
) -> list[PaymentSurchargeRead]:
    surcharges = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.hotel_id == context.hotel_id,
            PaymentSurcharge.is_active.is_(True),
        )
        .order_by(PaymentSurcharge.payment_method.asc())
        .all()
    )
    return [PaymentSurchargeRead.model_validate(surcharge) for surcharge in surcharges]


@router.post("", response_model=PaymentSurchargeRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=PaymentSurchargeRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
def create_payment_surcharge(
    payload: PaymentSurchargeCreate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
) -> PaymentSurchargeRead:
    existing = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.hotel_id == context.hotel_id,
            PaymentSurcharge.payment_method == payload.payment_method,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Ya existe un recargo para el metodo '{payload.payment_method}'. "
                "Use PATCH para actualizar o reactivar."
            ),
        )

    surcharge = PaymentSurcharge(
        hotel_id=context.hotel_id,
        payment_method=payload.payment_method,
        surcharge_type=payload.surcharge_type,
        amount=payload.amount,
        currency_code=payload.currency_code.upper(),
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(surcharge)
    db.commit()
    db.refresh(surcharge)
    return PaymentSurchargeRead.model_validate(surcharge)


@router.patch("/{surcharge_id}", response_model=PaymentSurchargeRead)
def update_payment_surcharge(
    surcharge_id: int,
    payload: PaymentSurchargeUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
) -> PaymentSurchargeRead:
    surcharge = _get_surcharge_or_404(db, surcharge_id, context.hotel_id)

    if payload.payment_method is not None:
        surcharge.payment_method = payload.payment_method
    if payload.surcharge_type is not None:
        surcharge.surcharge_type = payload.surcharge_type
    if payload.amount is not None:
        surcharge.amount = payload.amount
    if payload.currency_code is not None:
        surcharge.currency_code = payload.currency_code.upper()
    if payload.is_active is not None:
        surcharge.is_active = payload.is_active

    db.commit()
    db.refresh(surcharge)
    return PaymentSurchargeRead.model_validate(surcharge)


@router.delete("/{surcharge_id}", response_model=PaymentSurchargeRead)
def deactivate_payment_surcharge(
    surcharge_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_roles("owner", "co_owner", "manager")),
) -> PaymentSurchargeRead:
    surcharge = _get_surcharge_or_404(db, surcharge_id, context.hotel_id)
    surcharge.is_active = False
    db.commit()
    db.refresh(surcharge)
    return PaymentSurchargeRead.model_validate(surcharge)
