"""
FastAPI routes for Payments.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.transaction import PaymentRequest, TransactionRead
from app.services.payment_service import (
    process_payment,
    get_reservation_financial_summary,
    PaymentError,
)

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def make_payment(data: PaymentRequest, db: Session = Depends(get_db)):
    try:
        transaction = process_payment(db, data)
        db.commit()
        db.refresh(transaction)
        return transaction
    except PaymentError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summary/{reservation_id}")
def financial_summary(reservation_id: int, db: Session = Depends(get_db)):
    try:
        return get_reservation_financial_summary(db, reservation_id)
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))
