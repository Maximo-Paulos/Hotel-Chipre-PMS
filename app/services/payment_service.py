"""
Payment Service — Financial Engine.
Implements the booking cart flow:
  - Deposit payment (e.g. 30%) → status: deposit_paid
  - Full payment → status: fully_paid
  - Balance payment at check-in
  
Coordinates with payment gateway adapters (MercadoPago, PayPal) and cash.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.transaction import (
    Transaction, PaymentMethodEnum, TransactionStatusEnum, TransactionTypeEnum
)
from app.models.hotel_config import HotelConfiguration
from app.schemas.transaction import PaymentRequest, PaymentGatewayResponse
from app.services.reservation_service import transition_reservation_status, ReservationError


class PaymentError(Exception):
    """Custom exception for payment logic errors."""
    pass


DEFAULT_DEPOSIT_PERCENTAGE = 30.0


def get_hotel_config(db: Session, hotel_id: int) -> HotelConfiguration:
    """
    Get or create the per-hotel configuration.
    No global/singleton fallback â€” requires explicit hotel_id.
    """
    if hotel_id is None:
        raise PaymentError("hotel_id is required for finance operations")

    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    if not config:
        config = HotelConfiguration(id=hotel_id)
        db.add(config)
        db.flush()

    # Defensive defaults (transitional only, not hardcoded product behavior)
    if config.deposit_percentage is None:
        config.deposit_percentage = DEFAULT_DEPOSIT_PERCENTAGE
    if config.enable_cash is None:
        config.enable_cash = True
    if config.enable_mercado_pago is None:
        config.enable_mercado_pago = True
    if config.enable_paypal is None:
        config.enable_paypal = True
    if config.enable_credit_card is None:
        config.enable_credit_card = True
    if config.enable_debit_card is None:
        config.enable_debit_card = True
    if config.enable_bank_transfer is None:
        config.enable_bank_transfer = False

    return config


def validate_payment_method_enabled(db: Session, method: PaymentMethodEnum, hotel_id: int) -> None:
    """Check that the requested payment method is enabled in hotel config."""
    config = get_hotel_config(db, hotel_id)
    if not config.is_payment_method_enabled(method.value):
        raise PaymentError(f"Payment method '{method.value}' is currently disabled")


def _resolve_reservation_hotel(
    reservation: Reservation,
    hotel_id: Optional[int],
    existing_tx_hotel_id: Optional[int] = None,
) -> int:
    """
    Resolve hotel scope using caller input or existing transactions.
    """
    reservation_hotel_id = getattr(reservation, "hotel_id", None)

    if reservation_hotel_id is not None and hotel_id is not None and reservation_hotel_id != hotel_id:
        raise PaymentError(
            f"Reservation {reservation.id} does not belong to hotel {hotel_id} (belongs to {reservation_hotel_id})"
        )

    if reservation_hotel_id is not None and existing_tx_hotel_id is not None and reservation_hotel_id != existing_tx_hotel_id:
        raise PaymentError(
            f"Reservation {reservation.id} already has payments for hotel {existing_tx_hotel_id}"
        )

    if existing_tx_hotel_id is not None and hotel_id is not None and hotel_id != existing_tx_hotel_id:
        raise PaymentError(f"Reservation {reservation.id} already has payments for hotel {existing_tx_hotel_id}")

    resolved = reservation_hotel_id or hotel_id or existing_tx_hotel_id

    if resolved is None:
        raise PaymentError("hotel_id is required for finance operations")

    return resolved


def process_payment(
    db: Session,
    request: PaymentRequest,
    hotel_id: Optional[int] = None,
    gateway_response: Optional[PaymentGatewayResponse] = None,
) -> Transaction:
    """
    Process a payment for a reservation.
    
    This is the core financial engine:
    1. Validate reservation exists and is in a payable state
    2. Validate payment method is enabled
    3. Validate amount does not exceed balance due
    4. Create Transaction record
    5. If gateway involved (MP/PayPal), record external IDs
    6. Update reservation.amount_paid
    7. Transition reservation status based on financial state

    For cash payments, the transaction is completed immediately.
    For gateway payments, the caller provides the gateway_response.
    """
    # 1. Validate reservation
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == request.reservation_id)
        .with_for_update()
        .first()
    )

    if not reservation:
        raise PaymentError(f"Reservation {request.reservation_id} not found")

    existing_tx = (
        db.query(Transaction.hotel_id)
        .filter(Transaction.reservation_id == request.reservation_id)
        .first()
    )
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError("Reservation does not belong to selected hotel")

    if reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
    ):
        raise PaymentError(
            f"Cannot process payment for reservation in status '{reservation.status.value}'"
        )

    # 2. Validate payment method
    validate_payment_method_enabled(db, request.payment_method, resolved_hotel_id)

    # 2.5 Dynamic Pricing Override
    from app.models.pricing import CategoryPricing
    pricing = db.query(CategoryPricing).filter(CategoryPricing.category_id == reservation.category_id).first()
    if pricing and request.transaction_type != TransactionTypeEnum.REFUND:
        method_key = request.payment_method.value
        if method_key == "bank_transfer": method_key = "transfer"
        elif method_key == "mercado_pago": method_key = "mercadopago"
        
        method_price = getattr(pricing, f"price_{method_key}", None)
        if method_price is not None and method_price > 0:
            reservation.total_amount = round(method_price * reservation.nights, 2)
            config = get_hotel_config(db, resolved_hotel_id)
            dep_pct = config.deposit_percentage if config else DEFAULT_DEPOSIT_PERCENTAGE
            reservation.deposit_amount = round(reservation.total_amount * (dep_pct / 100.0), 2)
            db.flush()

    # 3. Validate amount
    balance = reservation.balance_due
    if request.amount > balance + 0.01:  # Small tolerance for float arithmetic
        raise PaymentError(
            f"Payment amount ${request.amount:.2f} exceeds balance due ${balance:.2f}"
        )

    # 4. Create transaction
    tx_status = TransactionStatusEnum.PENDING
    external_payment_id = None
    external_status = None
    raw_response = None
    processed_at = None

    # For cash, mark completed immediately
    if request.payment_method == PaymentMethodEnum.CASH:
        tx_status = TransactionStatusEnum.COMPLETED
        processed_at = datetime.now(timezone.utc)

    # For gateway payments, use the provided response
    if gateway_response:
        if gateway_response.success:
            tx_status = TransactionStatusEnum.COMPLETED
            processed_at = datetime.now(timezone.utc)
        else:
            tx_status = TransactionStatusEnum.FAILED

        external_payment_id = gateway_response.external_payment_id
        external_status = gateway_response.external_status
        raw_response = gateway_response.gateway_response

    transaction = Transaction(
        hotel_id=resolved_hotel_id,
        reservation_id=request.reservation_id,
        amount=request.amount,
        currency=request.currency,
        transaction_type=request.transaction_type,
        payment_method=request.payment_method,
        status=tx_status,
        external_payment_id=external_payment_id,
        external_status=external_status,
        gateway_response=raw_response,
        description=request.description,
        processed_at=processed_at,
    )
    db.add(transaction)
    db.flush()

    # 5. If completed, update reservation financial state
    if tx_status == TransactionStatusEnum.COMPLETED:
        _update_reservation_financials(
            db,
            reservation,
            request.amount,
            request.transaction_type,
            resolved_hotel_id,
        )

    return transaction


def _update_reservation_financials(
    db: Session,
    reservation: Reservation,
    amount: float,
    tx_type: TransactionTypeEnum,
    hotel_id: int,
) -> None:
    """
    Update reservation.amount_paid and transition status based on payment.

    State machine:
    - If deposit paid (amount >= deposit_amount) and status is PENDING → deposit_paid
    - If fully paid (balance_due == 0) → fully_paid
    """
    reservation.amount_paid = round(reservation.amount_paid + amount, 2)

    new_balance = reservation.balance_due  # Computed property

    if reservation.status == ReservationStatusEnum.PENDING:
        if new_balance <= 0.01:
            # Fully paid in one shot
            transition_reservation_status(db, reservation, ReservationStatusEnum.FULLY_PAID, hotel_id)
        elif reservation.amount_paid >= reservation.deposit_amount - 0.01:
            # Deposit threshold reached
            transition_reservation_status(db, reservation, ReservationStatusEnum.DEPOSIT_PAID, hotel_id)

    elif reservation.status == ReservationStatusEnum.DEPOSIT_PAID:
        if new_balance <= 0.01:
            transition_reservation_status(db, reservation, ReservationStatusEnum.FULLY_PAID, hotel_id)

    db.flush()


def get_reservation_financial_summary(db: Session, hotel_id: Optional[int], reservation_id: int) -> dict:
    """
    Get a full financial summary for a reservation.
    Returns total, paid, balance, deposit required, and all transactions.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise PaymentError(f"Reservation {reservation_id} not found")

    existing_tx = (
        db.query(Transaction.hotel_id)
        .filter(Transaction.reservation_id == reservation_id)
        .first()
    )
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError(f"Reservation {reservation_id} does not belong to hotel {resolved_hotel_id}")

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.reservation_id == reservation_id,
            Transaction.hotel_id == resolved_hotel_id,
        )
        .order_by(Transaction.created_at)
        .all()
    )

    completed_transactions = [
        t for t in transactions if t.status == TransactionStatusEnum.COMPLETED
    ]

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "total_amount": reservation.total_amount,
        "deposit_required": reservation.deposit_amount,
        "amount_paid": reservation.amount_paid,
        "balance_due": reservation.balance_due,
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "method": t.payment_method.value,
                "type": t.transaction_type.value,
                "status": t.status.value,
                "created_at": str(t.created_at),
            }
            for t in transactions
        ],
        "completed_payments": sum(t.amount for t in completed_transactions),
    }
