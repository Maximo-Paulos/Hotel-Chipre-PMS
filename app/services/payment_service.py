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

from app.models.operations import BillingAdjustment, ReservationStatusHistory
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
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


def _resolve_payment_currency(reservation: Reservation, requested_currency: Optional[str]) -> str:
    """
    Prefer an explicit payment currency, otherwise inherit the reservation currency.
    This avoids recording ARS by default for reservations quoted in another currency.
    """
    candidate = (requested_currency or reservation.currency_code or "ARS").strip().upper()
    return candidate[:3] if candidate else "ARS"


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
        .enable_eagerloads(False)
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

    is_refund = request.transaction_type == TransactionTypeEnum.REFUND
    if not is_refund and reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
    ):
        raise PaymentError(
            f"Cannot process payment for reservation in status '{reservation.status.value}'"
        )

    # 2. Validate payment method
    validate_payment_method_enabled(db, request.payment_method, resolved_hotel_id)
    transaction_currency = _resolve_payment_currency(reservation, request.currency)

    # 3. Validate amount
    if is_refund:
        if request.amount > reservation.amount_paid + 0.01:
            raise PaymentError(
                f"Refund amount ${request.amount:.2f} exceeds paid amount ${reservation.amount_paid:.2f}"
            )
    else:
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
        currency=transaction_currency,
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
    signed_amount = -amount if tx_type == TransactionTypeEnum.REFUND else amount
    reservation.amount_paid = max(0.0, round(reservation.amount_paid + signed_amount, 2))
    _sync_reservation_financial_status(db, reservation, hotel_id=hotel_id, reason_code=tx_type.value)
    db.flush()


def _sync_reservation_financial_status(
    db: Session,
    reservation: Reservation,
    *,
    hotel_id: int,
    reason_code: str,
) -> None:
    if reservation.status in (ReservationStatusEnum.CANCELLED, ReservationStatusEnum.CHECKED_OUT):
        return

    if reservation.amount_paid >= reservation.total_amount - 0.01:
        target_status = ReservationStatusEnum.FULLY_PAID
    elif reservation.amount_paid >= reservation.deposit_amount - 0.01 and reservation.amount_paid > 0:
        target_status = ReservationStatusEnum.DEPOSIT_PAID
    else:
        target_status = ReservationStatusEnum.PENDING

    if reservation.status == target_status:
        return

    if reservation.can_transition_to(target_status):
        transition_reservation_status(db, reservation, target_status, hotel_id, reason_code=reason_code)
        return

    previous_status = reservation.status
    reservation.status = target_status
    db.add(
        ReservationStatusHistory(
            hotel_id=hotel_id,
            reservation_id=reservation.id,
            from_status=previous_status.value if previous_status else None,
            to_status=target_status.value,
            reason_code=reason_code,
            notes="Financial reconciliation adjusted reservation status outside the forward-only state machine",
        )
    )


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
    billing_adjustments = (
        db.query(BillingAdjustment)
        .filter(
            BillingAdjustment.reservation_id == reservation_id,
            BillingAdjustment.hotel_id == resolved_hotel_id,
        )
        .order_by(BillingAdjustment.effective_at, BillingAdjustment.id)
        .all()
    )
    billing_adjustment_total = round(sum(adj.total_amount for adj in billing_adjustments), 2)
    completed_payment_total = round(
        sum(_signed_transaction_amount(t.transaction_type, t.amount) for t in completed_transactions),
        2,
    )
    operational_total = round(reservation.total_amount + billing_adjustment_total, 2)
    operational_balance_due = round(max(0.0, operational_total - reservation.amount_paid), 2)
    reconciliation_gap = round(reservation.amount_paid - completed_payment_total, 2)

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "currency_code": reservation.currency_code or "ARS",
        "total_amount": reservation.total_amount,
        "deposit_required": reservation.deposit_amount,
        "amount_paid": reservation.amount_paid,
        "balance_due": reservation.balance_due,
        "operational_total_amount": operational_total,
        "operational_balance_due": operational_balance_due,
        "billing_adjustment_total": billing_adjustment_total,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "has_financial_reconciliation_gap": abs(reconciliation_gap) > 0.01,
        "financial_reconciliation_gap": reconciliation_gap,
        "recommended_next_action": _recommended_financial_action(
            reservation=reservation,
            operational_balance_due=operational_balance_due,
        ),
        "transactions": [
            {
                "id": t.id,
                "amount": t.amount,
                "currency": t.currency,
                "method": t.payment_method.value,
                "type": t.transaction_type.value,
                "status": t.status.value,
                "created_at": str(t.created_at),
            }
            for t in transactions
        ],
        "billing_adjustments": [
            {
                "id": adj.id,
                "type": adj.adjustment_type.value if hasattr(adj.adjustment_type, "value") else str(adj.adjustment_type),
                "amount": adj.amount,
                "tax_amount": adj.tax_amount,
                "total_amount": adj.total_amount,
                "currency_code": adj.currency_code,
                "notes": adj.notes,
            }
            for adj in billing_adjustments
        ],
        "completed_payments": completed_payment_total,
    }


def _signed_transaction_amount(transaction_type: TransactionTypeEnum, amount: float) -> float:
    if transaction_type == TransactionTypeEnum.REFUND:
        return -amount
    return amount


def _recommended_financial_action(*, reservation: Reservation, operational_balance_due: float) -> str | None:
    if reservation.requires_manual_review:
        return "manual_review_required"
    if reservation.status == ReservationStatusEnum.CANCELLED and reservation.source != ReservationSourceEnum.DIRECT:
        return "review_cancellation_settlement"
    if reservation.settlement_status in {"manual_resolution_required", "pending_hotel_action"}:
        return "resolve_external_channel"
    if operational_balance_due > 0.01 and reservation.payment_collection_model == "hotel_collect":
        return "collect_from_guest"
    if reservation.payment_collection_model == "ota_prepaid" and reservation.settlement_status in {"pending", "unknown"}:
        return "await_channel_settlement"
    return None
