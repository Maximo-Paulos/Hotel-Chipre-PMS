"""
FastAPI routes for Payments.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies.auth import AuthContext, authorize_permission, require_all_permissions, require_permission
from app.schemas.reservation_operations import ReservationFinancialSummaryRead
from app.schemas.transaction import (
    PaymentCorrectionRead,
    PaymentCorrectionRequest,
    PaymentReceiptEmailRead,
    PaymentReceiptRead,
    PaymentRequest,
    TransactionRead,
)
from app.models.reservation import Reservation
from app.services.payment_service import (
    process_payment,
    get_reservation_financial_summary,
    get_payment_receipt_data,
    validate_payment_method_enabled,
    PaymentError,
    PaymentNotFoundError,
)
from app.services.payment_receipt_email_service import (
    PaymentReceiptEmailError,
    send_payment_receipt_email,
)
from app.services.payment_receipt_pdf import generate_payment_receipt_pdf
from app.services.payment_correction_service import (
    PaymentCorrectionConflict,
    PaymentCorrectionError,
    PaymentCorrectionNotFound,
    correct_payment,
)
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_RESERVATION_READ,
    PERMISSION_PAYMENT_RECEIPT_EMAIL,
    PERMISSION_CASH_RECORD_PRIOR_RECEIPT,
    PERMISSION_PAYMENT_REFUND,
    PERMISSION_PAYMENT_CORRECT,
    resolve,
)
from app.services.timezones import hotel_today
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum

router = APIRouter(prefix="/api/payments", tags=["Payments"])
EXTERNAL_GATEWAY_METHODS = frozenset(
    {PaymentMethodEnum.MERCADO_PAGO, PaymentMethodEnum.PAYPAL}
)


class PaymentReceiptEmailRequest(BaseModel):
    """A hotel operator explicitly enters the destination for this receipt."""

    recipient_email: str = Field(..., min_length=3, max_length=254)

    @field_validator("recipient_email", mode="before")
    @classmethod
    def trim_recipient_email(cls, value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        allow_reserved_test = normalized.rsplit("@", maxsplit=1)[-1].rstrip(".").lower().endswith(".test")
        try:
            return validate_email(
                normalized,
                check_deliverability=False,
                test_environment=allow_reserved_test,
            ).normalized
        except EmailNotValidError as exc:
            raise ValueError("Ingresá una dirección de correo válida.") from exc


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
                    detail="La fecha del cobro previo no puede ser futura.",
                )
        if not is_refund and data.payment_method in EXTERNAL_GATEWAY_METHODS:
            validate_payment_method_enabled(db, data.payment_method, context.hotel_id)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Los pagos con Mercado Pago y PayPal requieren una respuesta verificada "
                    "del proveedor; usá un link de pago."
                ),
            )
        if is_refund:
            authorize_permission(request, db, context, PERMISSION_PAYMENT_REFUND)
            if data.payment_method != PaymentMethodEnum.CASH:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Las devoluciones manuales de reservas deben registrarse en efectivo.",
                )
            if data.refund_of_transaction_id is None or not data.refund_reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La devolución debe identificar el pago original e incluir un motivo.",
                )
        elif data.refund_of_transaction_id is not None or data.refund_reason is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El pago original y el motivo solo se admiten al registrar una devolución.",
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


@router.post(
    "/transactions/{transaction_id}/correction",
    response_model=PaymentCorrectionRead,
    status_code=status.HTTP_201_CREATED,
)
def correct_payment_transaction(
    transaction_id: int,
    data: PaymentCorrectionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_CASH_OPERATE, PERMISSION_PAYMENT_CORRECT)
    ),
):
    """Reverse a mistaken ledger entry and optionally reassign its payment."""
    target_reservation_id = None
    if data.correction_type == "reassign":
        target_reservation_id = (
            db.query(Reservation.id)
            .filter(
                Reservation.hotel_id == context.hotel_id,
                func.upper(Reservation.confirmation_code) == data.destination_confirmation_code,
            )
            .scalar()
        )
        if target_reservation_id is None:
            raise HTTPException(status_code=404, detail="No se encontró la reserva de destino en este hotel.")

    try:
        outcome = correct_payment(
            db,
            hotel_id=context.hotel_id,
            source_transaction_id=transaction_id,
            correction_type=data.correction_type,
            target_reservation_id=target_reservation_id,
            reason=data.reason,
            idempotency_key=idempotency_key,
            actor_user_id=context.user_id,
        )
        db.commit()
        db.refresh(outcome.correction)
        return PaymentCorrectionRead(
            correction_id=outcome.correction.id,
            correction_type=outcome.correction.correction_type,
            source_transaction_id=outcome.correction.source_transaction_id,
            source_reservation_id=outcome.correction.source_reservation_id,
            target_reservation_id=outcome.correction.target_reservation_id,
            replacement_transaction_id=outcome.correction.replacement_transaction_id,
            reason=outcome.correction.reason,
            actor_user_id=outcome.correction.actor_user_id,
            created_at=outcome.correction.created_at,
            replayed=outcome.replayed,
        )
    except PaymentCorrectionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PaymentCorrectionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except PaymentCorrectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/summary/{reservation_id}", response_model=ReservationFinancialSummaryRead)
def financial_summary(
    reservation_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_RESERVATION_READ)),
):
    try:
        can_read_payment_correction_audit = resolve(
            db,
            context.hotel_id,
            context.user_role,
            PERMISSION_PAYMENT_CORRECT,
            user_id=context.user_id,
        )
        return get_reservation_financial_summary(
            db,
            context.hotel_id,
            reservation_id,
            include_payment_correction_audit=can_read_payment_correction_audit,
        )
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


@router.get("/transactions/{transaction_id}/receipt.pdf", include_in_schema=True)
def download_payment_receipt_pdf(
    transaction_id: int,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(require_permission(PERMISSION_CASH_OPERATE)),
):
    """Download a PDF generated from the persisted, tenant-scoped receipt."""
    try:
        receipt = get_payment_receipt_data(db, context.hotel_id, transaction_id)
        content = generate_payment_receipt_pdf(receipt)
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail="No se encontró el pago confirmado.") from e
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="comprobante-pago-{transaction_id}.pdf"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post(
    "/transactions/{transaction_id}/receipt/email",
    response_model=PaymentReceiptEmailRead,
    status_code=status.HTTP_200_OK,
)
def email_payment_receipt(
    transaction_id: int,
    data: PaymentReceiptEmailRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=100),
    db: Session = Depends(get_db),
    context: AuthContext = Depends(
        require_all_permissions(PERMISSION_CASH_OPERATE, PERMISSION_PAYMENT_RECEIPT_EMAIL)
    ),
):
    """Send or locally capture the persisted receipt for the operator-entered email."""
    try:
        return send_payment_receipt_email(
            db,
            hotel_id=context.hotel_id,
            transaction_id=transaction_id,
            actor_user_id=context.user_id,
            recipient_email=str(data.recipient_email),
            idempotency_key=idempotency_key,
        )
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail="No se encontró el pago confirmado.") from e
    except PaymentReceiptEmailError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
