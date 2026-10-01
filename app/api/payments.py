"""
FastAPI routes for Payments.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, require_permission
from app.schemas.reservation_operations import ReservationFinancialSummaryRead
from app.schemas.transaction import PaymentReceiptRead, PaymentRequest, TransactionRead
from app.services.payment_service import (
    process_payment,
    get_reservation_financial_summary,
    get_payment_receipt_data,
    PaymentError,
    PaymentNotFoundError,
)
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_CASH_RECORD_PRIOR_RECEIPT,
    PERMISSION_PAYMENT_REFUND,
)
from app.services.timezones import hotel_today
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("", response_model=TransactionRead, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=TransactionRead, status_code=status.HTTP_201_CREATED)
def make_payment(
    data: PaymentRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    try:
        is_refund = data.transaction_type == TransactionTypeEnum.REFUND
        if data.collected_before:
            authorize_permission(request, db, context, PERMISSION_CASH_RECORD_PRIOR_RECEIPT)
            if data.collected_on is not None and data.collected_on > hotel_today(db, context.hotel_id):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The prior receipt date cannot be in the future.",
                )
        if is_refund:
            authorize_permission(request, db, context, PERMISSION_PAYMENT_REFUND)
            if data.payment_method != PaymentMethodEnum.CASH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Manual reservation refunds must be returned through cash.",
                )
            if data.refund_of_transaction_id is None or not data.refund_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="A refund must identify the original payment and include a reason.",
                )
        elif data.refund_of_transaction_id is not None or data.refund_reason is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Refund source and reason are only accepted for refund transactions.",
            )

        manual_methods = {
            PaymentMethodEnum.CREDIT_CARD,
            PaymentMethodEnum.DEBIT_CARD,
            PaymentMethodEnum.BANK_TRANSFER,
        }
        manual_confirmation = not is_refund and data.payment_method in manual_methods
        if manual_confirmation and not data.manual_reference:
            reference_label = (
                "número de operación bancaria"
                if data.payment_method == PaymentMethodEnum.BANK_TRANSFER
                else "cupón verificado del posnet"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ingresá el {reference_label} antes de registrar el pago.",
            )
        if not manual_confirmation and data.manual_reference:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El comprobante solo se acepta para cobros presenciales con verificación manual.",
            )
        transaction = process_payment(
            db,
            data,
            hotel_id=context.hotel_id,
            actor_user_id=context.user_id,
            idempotency_key=idempotency_key,
            manual_confirmation=manual_confirmation,
        )
        db.commit()
        db.refresh(transaction)
        return transaction
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except HTTPException:
        raise
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
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/transactions/{transaction_id}/receipt", response_model=PaymentReceiptRead)
def payment_receipt_data(
    transaction_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    """Re-authorize and fetch the persisted source data before local receipt rendering."""
    try:
        return get_payment_receipt_data(db, context.hotel_id, transaction_id)
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
