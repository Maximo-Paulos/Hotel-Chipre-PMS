"""
FastAPI routes for Payments.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, require_permission
from app.schemas.reservation_operations import ReservationFinancialSummaryRead
from app.schemas.transaction import PaymentRequest, TransactionRead
from app.services.payment_service import (
    process_payment,
    get_reservation_financial_summary,
    PaymentError,
)
from app.services.permission_service import PERMISSION_CASH_OPERATE

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def make_payment(
    data: PaymentRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        transaction = process_payment(
            db,
            data,
            hotel_id=context.hotel_id,
            actor_user_id=context.user_id,
            idempotency_key=idempotency_key,
        )
        db.commit()
        db.refresh(transaction)
        return transaction
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary/{reservation_id}", response_model=ReservationFinancialSummaryRead)
def financial_summary(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        return get_reservation_financial_summary(db, context.hotel_id, reservation_id)
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))
