"""
Payment surcharges API - v72 section 12.3.

GET    /api/payment-surcharges          - list active surcharges for hotel
POST   /api/payment-surcharges          - create a surcharge
PATCH  /api/payment-surcharges/{id}     - update amount/type/active flag
DELETE /api/payment-surcharges/{id}     - deactivate a surcharge
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.models.audit_log import AuditActionEnum
from app.models.daily_rate import DailyRate, PricePeriod
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.services import audit_log_service
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_REPORTS_FINANCIAL_VIEW,
)

router = APIRouter(prefix="/api/payment-surcharges", tags=["Payment Surcharges"])

# Payment method -> per-method nightly-price override column, mirrors
# app.services.pricing_service._METHOD_COLS. A hotel must configure either a
# payment-method-specific nightly rate OR a payment-method surcharge for a
# given payment method -- never both (no double-adjustment on the same
# concept).
_METHOD_PRICE_COLS: dict[str, str] = {
    "cash": "price_cash",
    "transfer": "price_transfer",
    "mercadopago": "price_mercadopago",
    "paypal": "price_paypal",
    "credit_card": "price_credit_card",
}


def _has_per_method_nightly_price(db: Session, *, hotel_id: int, payment_method: str) -> bool:
    column_name = _METHOD_PRICE_COLS.get(payment_method)
    if column_name is None:
        return False
    daily_column = getattr(DailyRate, column_name)
    if (
        db.query(DailyRate.id)
        .filter(DailyRate.hotel_id == hotel_id, daily_column.is_not(None))
        .first()
        is not None
    ):
        return True
    return (
        db.query(PricePeriod.id)
        .filter(PricePeriod.hotel_id == hotel_id, PricePeriod.deleted_at.is_(None), getattr(PricePeriod, column_name).is_not(None))
        .first()
        is not None
    )


class PaymentSurchargeRead(BaseModel):
    id: int
    hotel_id: int
    payment_method: str
    surcharge_type: PaymentSurchargeTypeEnum
    amount: Decimal
    currency_code: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PaymentSurchargeCreate(BaseModel):
    payment_method: str = Field(..., max_length=50)
    surcharge_type: PaymentSurchargeTypeEnum
    # Negative values represent a discount (e.g. cash pays less than card).
    # The *computed* final amount is always clamped at 0 by
    # app.services.payment_service.calculate_payment_surcharge.
    amount: Decimal = Field(..., ge=-1_000_000, le=1_000_000)
    currency_code: str = Field(default="ARS", max_length=3)

    @model_validator(mode="after")
    def _validate_amount_range(self) -> "PaymentSurchargeCreate":
        if self.surcharge_type == PaymentSurchargeTypeEnum.PERCENTAGE and abs(self.amount) > 100:
            raise ValueError("Percentage amount must be between -100 and 100")
        return self


class PaymentSurchargeUpdate(BaseModel):
    payment_method: Optional[str] = Field(default=None, max_length=50)
    surcharge_type: Optional[PaymentSurchargeTypeEnum] = None
    amount: Optional[Decimal] = Field(default=None, ge=-1_000_000, le=1_000_000)
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
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
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
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
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
    if _has_per_method_nightly_price(db, hotel_id=context.hotel_id, payment_method=payload.payment_method):
        raise HTTPException(
            status_code=409,
            detail=(
                f"El hotel ya tiene una tarifa nocturna especifica para el metodo "
                f"'{payload.payment_method}' (DailyRate/PricePeriod). No se puede "
                "configurar tambien un recargo para el mismo metodo (doble ajuste)."
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
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="payment_surcharges",
        record_id=surcharge.id,
        action=AuditActionEnum.CREATE,
        actor_user_id=context.user_id,
        payload_after=audit_log_service.model_snapshot(surcharge),
    )
    return PaymentSurchargeRead.model_validate(surcharge)


@router.patch("/{surcharge_id}", response_model=PaymentSurchargeRead)
def update_payment_surcharge(
    surcharge_id: int,
    payload: PaymentSurchargeUpdate,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
) -> PaymentSurchargeRead:
    surcharge = _get_surcharge_or_404(db, surcharge_id, context.hotel_id)
    before = audit_log_service.model_snapshot(surcharge)

    new_payment_method = payload.payment_method if payload.payment_method is not None else surcharge.payment_method
    new_surcharge_type = payload.surcharge_type if payload.surcharge_type is not None else surcharge.surcharge_type
    new_amount = payload.amount if payload.amount is not None else surcharge.amount
    if new_surcharge_type == PaymentSurchargeTypeEnum.PERCENTAGE and abs(new_amount) > 100:
        raise HTTPException(status_code=422, detail="Percentage amount must be between -100 and 100")
    if (
        payload.payment_method is not None
        and payload.payment_method != surcharge.payment_method
        and _has_per_method_nightly_price(db, hotel_id=context.hotel_id, payment_method=new_payment_method)
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"El hotel ya tiene una tarifa nocturna especifica para el metodo "
                f"'{new_payment_method}'. No se puede configurar tambien un recargo "
                "para el mismo metodo (doble ajuste)."
            ),
        )

    surcharge.payment_method = new_payment_method
    surcharge.surcharge_type = new_surcharge_type
    surcharge.amount = new_amount
    if payload.currency_code is not None:
        surcharge.currency_code = payload.currency_code.upper()
    if payload.is_active is not None:
        surcharge.is_active = payload.is_active

    db.commit()
    db.refresh(surcharge)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="payment_surcharges",
        record_id=surcharge.id,
        action=AuditActionEnum.UPDATE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(surcharge),
    )
    return PaymentSurchargeRead.model_validate(surcharge)


@router.delete("/{surcharge_id}", response_model=PaymentSurchargeRead)
def deactivate_payment_surcharge(
    surcharge_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_REPORTS_FINANCIAL_VIEW)),
) -> PaymentSurchargeRead:
    surcharge = _get_surcharge_or_404(db, surcharge_id, context.hotel_id)
    before = audit_log_service.model_snapshot(surcharge)
    surcharge.is_active = False
    db.commit()
    db.refresh(surcharge)
    audit_log_service.safe_create_audit_log(
        db,
        hotel_id=context.hotel_id,
        table_name="payment_surcharges",
        record_id=surcharge.id,
        action=AuditActionEnum.STATUS_CHANGE,
        actor_user_id=context.user_id,
        payload_before=before,
        payload_after=audit_log_service.model_snapshot(surcharge),
    )
    return PaymentSurchargeRead.model_validate(surcharge)
