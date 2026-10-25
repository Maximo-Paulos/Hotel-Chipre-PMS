"""
Payment Service — Financial Engine.
Implements the booking cart flow:
  - Deposit payment (e.g. 30%) → status: deposit_paid
  - Full payment → status: fully_paid
  - Balance payment at check-in
  
Coordinates with payment gateway adapters (MercadoPago, PayPal) and cash.
"""
import math
from datetime import datetime, timezone
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.company_night_charge import (
    CompanyNightCharge,
    CompanyNightChargePaymentAllocation,
)
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.operations import BillingAdjustment, ReservationStatusHistory
from app.models.payment_correction import PaymentCorrection
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.reservation import (
    Reservation,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.transaction import (
    PaymentMethodEnum,
    RefundComponentEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services.company_night_charge_service import (
    CompanyNightChargeError,
    prepare_company_night_charge_payment,
    prepare_company_night_charge_refund,
    record_company_night_charge_payment_allocations,
    record_company_night_charge_refund_allocations,
)
from app.services.financial_ledger import (
    completed_paid_amount,
    external_paid_balance_credit,
    operational_balance_due,
    paid_amount_with_legacy_fallback,
    reconciled_paid_amounts_by_reservation,
)
from app.services.fx_service import SUPPORTED_CONVERSION_CURRENCIES
from app.services.pricing_policy_service import PricingPolicyError, _convert_amount
from app.services.quote_token_service import (
    QuoteTokenError,
    issue_quote_token,
    verify_quote_token,
)
from app.services.reservation_service import (
    reservation_has_deferred_company_billing,
    transition_reservation_status,
)
from app.services.timezones import hotel_business_now, utc_naive


class PaymentError(Exception):
    """Custom exception for payment logic errors."""
    pass


class PaymentNotFoundError(PaymentError):
    """A payment target is absent from the caller's tenant scope."""


def _cash_tender_breakdown(
    *,
    gross_amount: Decimal,
    cash_received_amount: Decimal,
    requested_tip_amount: Decimal = Decimal("0.00"),
) -> tuple[Decimal, Decimal]:
    """Return explicit tip and change without altering the billed amount."""
    gross = Decimal(str(gross_amount)).quantize(Decimal("0.01"))
    received = Decimal(str(cash_received_amount)).quantize(Decimal("0.01"))
    tip = Decimal(str(requested_tip_amount or 0)).quantize(Decimal("0.01"))
    if tip < Decimal("0.00"):
        raise PaymentError("El importe de la propina no puede ser negativo.")
    if received < gross:
        raise PaymentError(
            f"El efectivo entregado ({received:.2f}) es menor al importe total del cobro ({gross:.2f})."
        )
    over_tender = (received - gross).quantize(Decimal("0.01"))
    if tip > over_tender:
        raise PaymentError("La propina no puede superar el excedente después de cubrir el importe del cobro.")
    return tip, (over_tender - tip).quantize(Decimal("0.01"))


DEFAULT_DEPOSIT_PERCENTAGE = 30.0
MANUAL_REFERENCE_METHODS = frozenset(
    {PaymentMethodEnum.CREDIT_CARD, PaymentMethodEnum.DEBIT_CARD, PaymentMethodEnum.BANK_TRANSFER}
)


def _same_idempotent_payment(
    db: Session,
    existing: Transaction,
    request: PaymentRequest,
    currency: str,
    hotel_id: int,
) -> bool:
    requested_amount = Decimal(str(request.amount)).quantize(Decimal("0.01"))
    existing_tender_amount = Decimal(
        str(existing.tender_amount if existing.tender_amount is not None else existing.amount)
    ).quantize(Decimal("0.01"))
    requested_cash_received = getattr(request, "cash_received_amount", None)
    requested_cash_tip = Decimal(str(getattr(request, "cash_tip_amount", 0) or 0)).quantize(Decimal("0.01"))
    existing_cash_tip = Decimal(str(getattr(existing, "cash_tip_amount", 0) or 0)).quantize(Decimal("0.01"))
    if request.payment_method == PaymentMethodEnum.CASH and request.transaction_type != TransactionTypeEnum.REFUND:
        existing_expected_gross = Decimal(
            str(existing.gross_amount if existing.gross_amount is not None else existing_tender_amount)
        ).quantize(Decimal("0.01"))
        existing_cash_received = getattr(existing, "cash_received_amount", None)
        if existing_cash_received is None:
            # Legacy cash transactions used the gross amount as both the
            # retained payment and the physical tender.
            existing_cash_received = existing_expected_gross
        else:
            existing_cash_received = Decimal(str(existing_cash_received)).quantize(Decimal("0.01"))
        effective_requested_cash_received = (
            Decimal(str(requested_cash_received)).quantize(Decimal("0.01"))
            if requested_cash_received is not None
            else existing_expected_gross
        )
        cash_receipt_matches = existing_cash_received == effective_requested_cash_received
    else:
        cash_receipt_matches = (
            requested_cash_received is None
            and getattr(existing, "cash_received_amount", None) is None
        )
    cash_tip_matches = existing_cash_tip == requested_cash_tip
    existing_allocations = {
        int(charge_id): Decimal(str(amount)).quantize(Decimal("0.01"))
        for charge_id, amount in db.query(
            CompanyNightChargePaymentAllocation.company_night_charge_id,
            CompanyNightChargePaymentAllocation.amount,
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == hotel_id,
            CompanyNightChargePaymentAllocation.transaction_id == existing.id,
        )
        .all()
    }
    if request.transaction_type == TransactionTypeEnum.REFUND:
        requested_allocations = {
            int(getattr(item, "charge_id", item.get("charge_id") if isinstance(item, dict) else 0)):
            Decimal(str(getattr(item, "amount", item.get("amount") if isinstance(item, dict) else 0))).quantize(
                Decimal("0.01")
            )
            for item in request.company_night_charge_refund_allocations
        }
        allocation_matches = existing_allocations == requested_allocations
    else:
        allocation_matches = set(existing_allocations) == set(request.company_night_charge_ids)
    return (
        existing_tender_amount == requested_amount
        and cash_receipt_matches
        and cash_tip_matches
        and existing.payment_method == request.payment_method
        and existing.transaction_type == request.transaction_type
        and (existing.refund_component or RefundComponentEnum.PAYMENT.value)
        == getattr(request, "refund_component", RefundComponentEnum.PAYMENT.value)
        and (existing.tender_currency or existing.currency) == currency
        and existing.manual_reference == request.manual_reference
        and existing.refund_of_transaction_id == request.refund_of_transaction_id
        and existing.refund_reason == request.refund_reason
        and bool(existing.collected_before) == request.collected_before
        and existing.collected_on == request.collected_on
        and existing.prior_receipt_note == request.prior_receipt_note
        and allocation_matches
    )


def get_hotel_config(db: Session, hotel_id: int) -> HotelConfiguration:
    """
    Get or create the per-hotel configuration.
    No global/singleton fallback â€” requires explicit hotel_id.
    """
    if hotel_id is None:
        raise PaymentError("Se requiere el hotel para operar con pagos.")

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
        raise PaymentError(f"El medio de pago '{method.value}' está deshabilitado.")


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
            "La reserva no pertenece al hotel seleccionado."
        )

    if reservation_hotel_id is not None and existing_tx_hotel_id is not None and reservation_hotel_id != existing_tx_hotel_id:
        raise PaymentError(
            "La reserva ya tiene pagos asociados a otro hotel."
        )

    if existing_tx_hotel_id is not None and hotel_id is not None and hotel_id != existing_tx_hotel_id:
        raise PaymentError("La reserva ya tiene pagos asociados a otro hotel.")

    resolved = reservation_hotel_id or hotel_id or existing_tx_hotel_id

    if resolved is None:
        raise PaymentError("Se requiere el hotel para operar con pagos.")

    return resolved


def _resolve_payment_currency(reservation: Reservation, requested_currency: Optional[str]) -> str:
    """Resolve the tender currency while keeping conversions within supported pairs."""
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    candidate = (requested_currency or reservation_currency).strip().upper()
    if (
        len(reservation_currency) != 3
        or not reservation_currency.isascii()
        or not reservation_currency.isalpha()
        or len(candidate) != 3
        or not candidate.isascii()
        or not candidate.isalpha()
    ):
        raise PaymentError("La moneda de la reserva o del pago no es válida")
    if candidate != reservation_currency and (
        candidate not in SUPPORTED_CONVERSION_CURRENCIES
        or reservation_currency not in SUPPORTED_CONVERSION_CURRENCIES
    ):
        raise PaymentError(
            f"No se admite convertir entre {reservation_currency} y {candidate}; "
            "monedas disponibles: ARS, USD, EUR, BRL, CLP y UYU."
        )
    return candidate


def _rounding_tender_amount(exact_tender_amount: Decimal, policy: str) -> Decimal | None:
    """Return a cash-handling suggestion without changing the exact charge."""
    if policy == "round_up":
        return exact_tender_amount.quantize(Decimal("1"), rounding=ROUND_CEILING)
    if policy == "round_down":
        return exact_tender_amount.quantize(Decimal("1"), rounding=ROUND_DOWN)
    if policy == "nearest_ten":
        return exact_tender_amount.quantize(Decimal("1E1"), rounding=ROUND_HALF_UP)
    return None


def _rounding_policy_for_hotel(db: Session, hotel_id: int) -> str:
    config = get_hotel_config(db, hotel_id)
    policy = str(getattr(config, "fx_rounding_policy", "keep_remainder") or "keep_remainder")
    if policy not in {"exact", "round_up", "round_down", "nearest_ten", "keep_remainder"}:
        raise PaymentError("La política de redondeo cambiario del hotel no es válida.")
    return policy


def _resolve_applied_payment_amount(
    db: Session,
    *,
    hotel_id: int,
    reservation: Reservation,
    tender_amount: Decimal,
    tender_currency: str,
    refund_source: Transaction | None = None,
    payment_fx_rate: Decimal | None = None,
    payment_fx_quote_details: dict | None = None,
) -> tuple[Decimal, float, dict | None]:
    """Convert received tender to reservation currency and freeze its quote."""
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    if tender_currency == reservation_currency:
        return tender_amount.quantize(Decimal("0.01")), 1.0, None

    if refund_source is not None:
        original_tender = Decimal(str(
            refund_source.tender_amount
            if refund_source.tender_amount is not None
            else refund_source.amount or 0
        ))
        principal_tender = max(
            Decimal("0.00"),
            original_tender - Decimal(str(refund_source.rounding_credit_amount or 0)),
        )
        original_credit = Decimal(str(refund_source.amount or 0))
        if principal_tender <= 0 or original_credit <= 0:
            raise PaymentError("No se puede calcular el equivalente de la devolución original")
        # The source FX ratio must map its net principal tender to principal
        # applied amount; issued rounding credit is a separate liability.
        exact_tender_per_credit = principal_tender / original_credit
        tender_per_credit = float(exact_tender_per_credit)
        applied = (tender_amount / exact_tender_per_credit).quantize(Decimal("0.01"))
        details = refund_source.fx_quote_details
        if details:
            details = {**details, "refund_uses_original_quote": True}
        return applied, tender_per_credit, details

    if payment_fx_rate is None:
        direct_rate, details = _payment_conversion_rate(
            db,
            hotel_id=hotel_id,
            from_currency=tender_currency,
            to_currency=reservation_currency,
        )
    else:
        direct_rate = payment_fx_rate
        details = payment_fx_quote_details
    applied = (tender_amount * direct_rate).quantize(Decimal("0.01"))
    if applied <= Decimal("0.00"):
        raise PaymentError("El importe recibido es demasiado bajo para acreditarse a la reserva")
    # Keep the persisted snapshot contract used by receipts: tender currency
    # units per one unit of reservation-currency credit.
    tender_per_credit = float(Decimal("1") / direct_rate)
    return applied, tender_per_credit, details


def _payment_conversion_rate(
    db: Session,
    *,
    hotel_id: int,
    from_currency: str,
    to_currency: str,
) -> tuple[Decimal, dict | None]:
    """Resolve the exact configured payment conversion rate and provenance."""
    try:
        _converted_one, rate, details = _convert_amount(
            db,
            hotel_id=hotel_id,
            amount=1.0,
            from_currency=from_currency,
            to_currency=to_currency,
            fx_policy_id=None,
            provider_code=None,
        )
    except PricingPolicyError as exc:
        raise PaymentError(str(exc)) from exc
    if not math.isfinite(rate) or rate <= 0:
        raise PaymentError("La cotización de conversión no es válida")
    return Decimal(str(rate)), details


def _payment_method_value(method) -> str:
    return method.value if hasattr(method, "value") else str(method)


def _verify_payment_quote_token(
    token: str,
    *,
    hotel_id: int,
    reservation: Reservation,
    payment_method,
    currency_code: str,
    base_amount: Decimal,
) -> tuple[dict, Decimal, dict | None, Decimal]:
    """Verify and bind a short-lived server quote to the submitted collection."""
    try:
        payload = verify_quote_token(token)
    except QuoteTokenError as exc:
        raise PaymentError("La cotización del cobro venció o no es válida. Volvé a cotizar.") from exc

    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    expected_identity = {
        "purpose": "payment_surcharge_quote",
        "hotel_id": hotel_id,
        "reservation_id": reservation.id,
        "payment_method": _payment_method_value(payment_method),
        "currency_code": currency_code,
        "reservation_currency_code": reservation_currency,
    }
    if any(payload.get(key) != value for key, value in expected_identity.items()):
        raise PaymentError("La cotización del cobro no corresponde a esta reserva o forma de pago.")

    try:
        quoted_base_amount = Decimal(str(payload["base_amount"])).quantize(Decimal("0.01"))
        quoted_applied_amount = Decimal(str(payload["applied_amount"])).quantize(Decimal("0.01"))
        payment_fx_rate = Decimal(str(payload["payment_fx_rate"]))
        surcharge_quote_snapshot = payload["surcharge_quote_snapshot"]
    except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentError("La cotización guardada del cobro no es válida.") from exc

    if (
        quoted_base_amount != base_amount
        or quoted_applied_amount <= Decimal("0.00")
        or not payment_fx_rate.is_finite()
        or payment_fx_rate <= Decimal("0.00")
        or not isinstance(surcharge_quote_snapshot, dict)
    ):
        raise PaymentError("La cotización guardada del cobro no coincide con el importe enviado.")
    if currency_code == reservation_currency and payment_fx_rate != Decimal("1"):
        raise PaymentError("La cotización guardada del cobro usa una conversión no válida.")

    payment_fx_quote_details = payload.get("payment_fx_quote_details")
    if payment_fx_quote_details is not None and not isinstance(payment_fx_quote_details, dict):
        raise PaymentError("La procedencia de la cotización guardada no es válida.")
    return (
        surcharge_quote_snapshot,
        payment_fx_rate,
        payment_fx_quote_details,
        quoted_applied_amount,
    )


def calculate_payment_surcharge(
    db: Session,
    *,
    hotel_id: int,
    payment_method,
    base_amount,
    currency_code: str = "ARS",
    surcharge_quote_snapshot: dict | None = None,
) -> dict:
    base = Decimal(str(base_amount or 0)).quantize(Decimal("0.01"))
    target_currency = str(currency_code or "ARS").strip().upper()
    if len(target_currency) != 3 or not target_currency.isascii() or not target_currency.isalpha():
        raise PaymentError("La moneda del cobro no es válida.")
    method_value = _payment_method_value(payment_method)
    surcharge_record = (
        db.query(PaymentSurcharge)
        .filter(
            PaymentSurcharge.hotel_id == hotel_id,
            PaymentSurcharge.payment_method == method_value,
            PaymentSurcharge.is_active.is_(True),
        )
        .first()
    )

    surcharge_type = None
    surcharge_value = None
    surcharge_amount = Decimal("0.00")
    surcharge_currency_code = target_currency
    surcharge_fx_rate = None
    surcharge_fx_quote_details = None

    if surcharge_quote_snapshot is not None:
        if not isinstance(surcharge_quote_snapshot, dict):
            raise PaymentError("La cotización guardada del recargo no es válida.")
        if (
            surcharge_quote_snapshot.get("version") != 1
            or surcharge_quote_snapshot.get("payment_method") != method_value
            or str(surcharge_quote_snapshot.get("currency_code") or "").upper() != target_currency
        ):
            raise PaymentError("La cotización guardada del recargo no corresponde a esta moneda o medio de pago.")
        surcharge_type = surcharge_quote_snapshot.get("surcharge_type")
        surcharge_currency_code = str(
            surcharge_quote_snapshot.get("surcharge_currency_code") or target_currency
        ).upper()
        surcharge_fx_rate = surcharge_quote_snapshot.get("surcharge_fx_rate")
        surcharge_fx_quote_details = surcharge_quote_snapshot.get("surcharge_fx_quote_details")
        if surcharge_type is not None:
            try:
                surcharge_value = Decimal(str(surcharge_quote_snapshot["surcharge_value"]))
                if surcharge_type == PaymentSurchargeTypeEnum.FIXED.value:
                    surcharge_amount = Decimal(str(surcharge_quote_snapshot["surcharge_amount"])).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                elif surcharge_type == PaymentSurchargeTypeEnum.PERCENTAGE.value:
                    if abs(surcharge_value) > 100:
                        raise ValueError("percentage out of range")
                    surcharge_amount = (base * surcharge_value / Decimal("100")).quantize(
                        Decimal("0.01"), rounding=ROUND_HALF_UP
                    )
                else:
                    raise ValueError("unknown surcharge type")
            except (KeyError, InvalidOperation, TypeError, ValueError) as exc:
                raise PaymentError("La cotización guardada del recargo no es válida.") from exc
    elif surcharge_record:
        surcharge_type = (
            surcharge_record.surcharge_type.value
            if hasattr(surcharge_record.surcharge_type, "value")
            else str(surcharge_record.surcharge_type)
        )
        surcharge_value = surcharge_record.amount
        surcharge_currency_code = str(surcharge_record.currency_code or "ARS").strip().upper()
        if surcharge_record.surcharge_type == PaymentSurchargeTypeEnum.FIXED:
            fixed_amount = Decimal(str(surcharge_record.amount))
            if surcharge_currency_code == target_currency:
                surcharge_amount = fixed_amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            else:
                surcharge_fx_rate, surcharge_fx_quote_details = _payment_conversion_rate(
                    db,
                    hotel_id=hotel_id,
                    from_currency=surcharge_currency_code,
                    to_currency=target_currency,
                )
                surcharge_amount = (fixed_amount * surcharge_fx_rate).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
        else:
            surcharge_amount = (
                base * Decimal(str(surcharge_record.amount)) / Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # A discount-shaped adjustment (negative amount) must never push the
    # final amount below 0 -- clamp rather than invent negative money owed.
    final_amount = max(Decimal("0.00"), (base + surcharge_amount)).quantize(Decimal("0.01"))
    snapshot = {
        "version": 1,
        "payment_method": method_value,
        "currency_code": target_currency,
        "base_amount": str(base),
        "final_amount": str(final_amount),
        "surcharge_id": (
            surcharge_quote_snapshot.get("surcharge_id")
            if surcharge_quote_snapshot is not None
            else surcharge_record.id if surcharge_record else None
        ),
        "surcharge_type": surcharge_type,
        "surcharge_value": str(surcharge_value) if surcharge_value is not None else None,
        "surcharge_currency_code": surcharge_currency_code,
        "surcharge_amount": str(surcharge_amount),
        "surcharge_fx_rate": str(surcharge_fx_rate) if surcharge_fx_rate is not None else None,
        "surcharge_fx_quote_details": surcharge_fx_quote_details,
    }
    return {
        "base_amount": base,
        "currency_code": target_currency,
        "surcharge_type": surcharge_type,
        "surcharge_value": surcharge_value,
        "surcharge_currency_code": surcharge_currency_code,
        "surcharge_amount": surcharge_amount,
        "final_amount": final_amount,
        "surcharge_fx_rate": surcharge_fx_rate,
        "surcharge_fx_quote_details": surcharge_fx_quote_details,
        "surcharge_quote_snapshot": snapshot,
    }


def calculate_base_amount_before_surcharge(
    db: Session,
    *,
    hotel_id: int,
    payment_method,
    final_amount,
    currency_code: str = "ARS",
    surcharge_quote_snapshot: dict | None = None,
) -> Decimal:
    final = Decimal(str(final_amount or 0)).quantize(Decimal("0.01"))
    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=payment_method,
        base_amount=Decimal("0.00"),
        currency_code=currency_code,
        surcharge_quote_snapshot=surcharge_quote_snapshot,
    )
    if surcharge_quote_snapshot is not None:
        try:
            quoted_base = Decimal(str(surcharge_quote_snapshot["base_amount"])).quantize(Decimal("0.01"))
            quoted_final = Decimal(str(surcharge_quote_snapshot["final_amount"])).quantize(Decimal("0.01"))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            quoted_base = quoted_final = None
        if quoted_base is not None and final == quoted_final:
            return quoted_base
    if surcharge_info["surcharge_type"] is None:
        return final
    if surcharge_info["surcharge_type"] == PaymentSurchargeTypeEnum.FIXED.value:
        return max(Decimal("0.00"), final - surcharge_info["surcharge_amount"]).quantize(Decimal("0.01"))
    divisor = Decimal("1") + (Decimal(str(surcharge_info["surcharge_value"])) / Decimal("100"))
    if divisor <= 0:
        return final
    return (final / divisor).quantize(Decimal("0.01"))


def quote_reservation_payment_surcharge(
    db: Session,
    *,
    hotel_id: int,
    reservation_id: int,
    payment_method,
    currency_code: str,
    base_amount: Decimal | None = None,
) -> dict:
    """Quote a reservation payment without rounding its ledger principal.

    When ``base_amount`` is omitted, choose the largest tender-currency amount
    whose converted principal does not exceed the current reservation balance.
    This leaves any sub-cent FX remainder in the reservation currency for a
    later mixed-currency payment.
    """
    reservation = (
        db.query(Reservation)
        .filter(Reservation.id == reservation_id, Reservation.hotel_id == hotel_id)
        .first()
    )
    if reservation is None:
        raise PaymentNotFoundError("No se encontró la reserva para cotizar el pago.")

    target_currency = _resolve_payment_currency(reservation, currency_code)
    reservation_currency = (reservation.currency_code or "ARS").strip().upper()
    balance = Decimal(str(operational_balance_due(db, hotel_id=hotel_id, reservation=reservation))).quantize(
        Decimal("0.01")
    )
    if balance <= 0:
        raise PaymentError("La reserva no tiene saldo pendiente para cotizar.")

    payment_fx_rate = Decimal("1")
    payment_fx_quote_details = None
    if target_currency != reservation_currency:
        payment_fx_rate, payment_fx_quote_details = _payment_conversion_rate(
            db,
            hotel_id=hotel_id,
            from_currency=target_currency,
            to_currency=reservation_currency,
        )

    exact_base_amount = base_amount is None
    if base_amount is None:
        if target_currency == reservation_currency:
            resolved_base = balance
        else:
            if payment_fx_rate <= 0:
                raise PaymentError("La cotización de conversión no es válida")
            resolved_base = (balance / payment_fx_rate).quantize(
                Decimal("0.01"), rounding=ROUND_DOWN
            )
    else:
        resolved_base = Decimal(str(base_amount)).quantize(Decimal("0.01"))

    if resolved_base <= 0:
        raise PaymentError("El importe del pago debe ser mayor que cero.")

    try:
        applied_amount, fx_rate_snapshot, fx_quote_details = _resolve_applied_payment_amount(
            db,
            hotel_id=hotel_id,
            reservation=reservation,
            tender_amount=resolved_base,
            tender_currency=target_currency,
            payment_fx_rate=payment_fx_rate,
            payment_fx_quote_details=payment_fx_quote_details,
        )
    except PaymentError:
        raise

    # Guard against rates whose inverse arithmetic lands on a cent above the
    # balance. The quote returns the largest accepted tender unit and leaves
    # the remainder in the reservation currency.
    if exact_base_amount:
        while applied_amount > balance and resolved_base >= Decimal("0.01"):
            resolved_base = (resolved_base - Decimal("0.01")).quantize(Decimal("0.01"))
            if resolved_base <= 0:
                raise PaymentError("El saldo es demasiado bajo para cotizar en esta moneda.")
            applied_amount, fx_rate_snapshot, fx_quote_details = _resolve_applied_payment_amount(
                db,
                hotel_id=hotel_id,
                reservation=reservation,
                tender_amount=resolved_base,
                tender_currency=target_currency,
                payment_fx_rate=payment_fx_rate,
                payment_fx_quote_details=payment_fx_quote_details,
            )
    elif applied_amount > balance:
        raise PaymentError(
            f"El pago convertiría a {applied_amount:.2f} {reservation.currency_code}, "
            f"por encima del saldo pendiente de {balance:.2f} {reservation.currency_code}."
        )

    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=payment_method,
        base_amount=resolved_base,
        currency_code=target_currency,
    )
    policy = _rounding_policy_for_hotel(db, hotel_id) if _payment_method_value(payment_method) == PaymentMethodEnum.CASH.value else None
    cash_suggestion = _rounding_tender_amount(surcharge_info["final_amount"], policy) if policy else None
    try:
        payment_quote_token = issue_quote_token(
            {
                "purpose": "payment_surcharge_quote",
                "hotel_id": hotel_id,
                "reservation_id": reservation.id,
                "payment_method": _payment_method_value(payment_method),
                "currency_code": target_currency,
                "reservation_currency_code": reservation_currency,
                "base_amount": str(resolved_base),
                "applied_amount": str(applied_amount),
                "payment_fx_rate": str(payment_fx_rate),
                "payment_fx_quote_details": payment_fx_quote_details,
                "surcharge_quote_snapshot": surcharge_info["surcharge_quote_snapshot"],
            },
            ttl_seconds=900,
        )
    except (QuoteTokenError, TypeError, ValueError) as exc:
        raise PaymentError("No se pudo asegurar la cotización del cobro. Volvé a cotizar.") from exc
    return {
        **surcharge_info,
        "reservation_id": reservation.id,
        "reservation_currency_code": reservation_currency,
        "reservation_balance": balance,
        "applied_amount": applied_amount,
        "remaining_balance": max(Decimal("0.00"), balance - applied_amount).quantize(Decimal("0.01")),
        "fx_rate_snapshot": fx_rate_snapshot,
        "fx_quote_details": fx_quote_details,
        "cash_tender_rounding_policy": policy,
        "cash_tender_suggestion": cash_suggestion,
        "cash_tender_suggestion_difference": (
            (cash_suggestion - surcharge_info["final_amount"]).quantize(Decimal("0.01"))
            if cash_suggestion is not None
            else Decimal("0.00")
        ),
        "payment_quote_token": payment_quote_token,
    }


def process_payment(
    db: Session,
    request: PaymentRequest,
    hotel_id: Optional[int] = None,
    gateway_response: Optional[PaymentGatewayResponse] = None,
    idempotency_key: Optional[str] = None,
    actor_user_id: Optional[int] = None,
    manual_confirmation: bool = False,
    apply_surcharge: bool = True,
    allow_verified_cancelled_settlement: bool = False,
    capture_cash_receipt: bool = True,
    surcharge_quote_snapshot: dict | None = None,
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

    ``apply_surcharge`` (default True) adds any active PaymentSurcharge on top
    of ``request.amount`` and records it as gross_amount/fee_amount. This is
    correct when the caller represents a live collection point (cash handed
    over now, or a gateway/link amount that already asked the guest for the
    grossed-up figure before it arrived). It is WRONG when ``request.amount``
    is itself a historical fact -- e.g. a bank-transfer proof, where the guest
    already sent an exact, already-capped-at-balance amount and there is no
    additional money to invent on top. Callers reconciling such a fact must
    pass ``apply_surcharge=False`` so fee_amount/gross_amount are not
    fabricated for money nobody actually collected.
    """
    # 1. Validate reservation
    reservation_query = db.query(Reservation).filter(Reservation.id == request.reservation_id)
    if hotel_id is not None:
        reservation_query = reservation_query.filter(Reservation.hotel_id == hotel_id)
    reservation = (
        reservation_query
        .enable_eagerloads(False)
        .with_for_update()
        .first()
    )

    if not reservation:
        raise PaymentNotFoundError("No se encontró la reserva.")

    existing_tx_query = db.query(Transaction.hotel_id).filter(Transaction.reservation_id == request.reservation_id)
    if hotel_id is not None:
        existing_tx_query = existing_tx_query.filter(Transaction.hotel_id == hotel_id)
    existing_tx = existing_tx_query.first()
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError("La reserva no pertenece al hotel seleccionado.")

    is_refund = request.transaction_type == TransactionTypeEnum.REFUND
    refund_component = getattr(request, "refund_component", RefundComponentEnum.PAYMENT.value)
    if refund_component not in {
        RefundComponentEnum.PAYMENT.value,
        RefundComponentEnum.ROUNDING_CREDIT.value,
    } or (not is_refund and refund_component != RefundComponentEnum.PAYMENT.value):
        raise PaymentError("El componente de devolución no es válido para esta transacción.")
    is_credit_refund = is_refund and refund_component == RefundComponentEnum.ROUNDING_CREDIT.value
    transaction_currency = _resolve_payment_currency(reservation, request.currency)
    tender_amount = Decimal(str(request.amount)).quantize(Decimal("0.01"))
    if tender_amount <= Decimal("0.00"):
        raise PaymentError("El importe del cobro debe ser mayor a cero")
    payment_fx_rate = None
    payment_fx_quote_details = None
    quoted_applied_amount = None
    if request.payment_quote_token:
        if is_refund or request.collected_before or not apply_surcharge:
            raise PaymentError("La cotización solo se admite para un cobro nuevo.")
        if surcharge_quote_snapshot is not None:
            raise PaymentError("No se pueden combinar dos cotizaciones para el mismo cobro.")
        (
            surcharge_quote_snapshot,
            payment_fx_rate,
            payment_fx_quote_details,
            quoted_applied_amount,
        ) = _verify_payment_quote_token(
            request.payment_quote_token,
            hotel_id=resolved_hotel_id,
            reservation=reservation,
            payment_method=request.payment_method,
            currency_code=transaction_currency,
            base_amount=tender_amount,
        )
    requested_cash_received = getattr(request, "cash_received_amount", None)
    requested_cash_tip = getattr(request, "cash_tip_amount", Decimal("0.00"))
    normalized_cash_received = None
    normalized_cash_tip = Decimal("0.00")
    if requested_cash_received is not None:
        if request.payment_method != PaymentMethodEnum.CASH or is_refund:
            raise PaymentError("El efectivo entregado solo se admite en pagos en efectivo, no en devoluciones.")
        try:
            normalized_cash_received = Decimal(str(requested_cash_received)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise PaymentError("El efectivo entregado no es válido.") from exc
        if normalized_cash_received <= Decimal("0.00"):
            raise PaymentError("El efectivo entregado debe ser mayor a cero.")
    try:
        normalized_cash_tip = Decimal(str(requested_cash_tip or 0)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PaymentError("El importe de la propina no es válido.") from exc
    if normalized_cash_tip < Decimal("0.00"):
        raise PaymentError("El importe de la propina no puede ser negativo.")
    if normalized_cash_tip > 0:
        if request.payment_method != PaymentMethodEnum.CASH or is_refund:
            raise PaymentError("La propina solo se admite en cobros en efectivo.")
        if normalized_cash_received is None:
            raise PaymentError("Para dejar propina se debe registrar el efectivo entregado.")
        if not capture_cash_receipt:
            raise PaymentError("La propina se registra una sola vez en el cobro grupal.")
    if not capture_cash_receipt and normalized_cash_received is not None:
        raise PaymentError("El efectivo entregado se registra una sola vez en el cobro grupal.")
    allocation_plan = None
    refund_allocation_plan = None
    rounding_credit_amount = Decimal("0.00")
    credit_refund_amount = Decimal("0.00")
    if idempotency_key is not None:
        existing_by_key = (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.reservation_id == request.reservation_id,
                Transaction.idempotency_key == idempotency_key,
            )
            .first()
        )
        if existing_by_key is not None:
            if not _same_idempotent_payment(
                db,
                existing_by_key,
                request,
                transaction_currency,
                resolved_hotel_id,
            ):
                raise PaymentError("La clave de idempotencia ya se usó para una solicitud de pago diferente.")
            return existing_by_key

    if request.manual_reference and (is_refund or request.payment_method not in MANUAL_REFERENCE_METHODS):
        raise PaymentError("Las referencias manuales solo se admiten para pagos presenciales con tarjeta o débito, y para transferencias bancarias.")
    if not is_refund and (request.refund_of_transaction_id is not None or request.refund_reason is not None):
        raise PaymentError("El pago original y el motivo solo se admiten al registrar una devolución.")
    refund_source = None
    if is_refund:
        if request.payment_method != PaymentMethodEnum.CASH:
            raise PaymentError("Las devoluciones manuales de reservas deben registrarse en efectivo.")
        if request.refund_of_transaction_id is None or not request.refund_reason:
            raise PaymentError("La devolución debe identificar el pago original e incluir un motivo.")
        refund_source = (
            db.query(Transaction)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.reservation_id == request.reservation_id,
                Transaction.id == request.refund_of_transaction_id,
                Transaction.status == TransactionStatusEnum.COMPLETED,
                Transaction.transaction_type != TransactionTypeEnum.REFUND,
            )
            .with_for_update()
            .first()
        )
        if refund_source is None:
            raise PaymentError("No se encontró el pago original como un cobro completado de esta reserva.")
        if (refund_source.tender_currency or refund_source.currency) != transaction_currency:
            raise PaymentError("La devolución debe usar la misma moneda del pago original.")
        if is_credit_refund:
            issued_credit = Decimal(str(refund_source.rounding_credit_amount or 0)).quantize(Decimal("0.01"))
            already_refunded_credit = (
                db.query(func.coalesce(func.sum(Transaction.credit_refund_amount), 0))
                .filter(
                    Transaction.hotel_id == resolved_hotel_id,
                    Transaction.reservation_id == request.reservation_id,
                    Transaction.refund_of_transaction_id == refund_source.id,
                    Transaction.transaction_type == TransactionTypeEnum.REFUND,
                    Transaction.refund_component == RefundComponentEnum.ROUNDING_CREDIT.value,
                    Transaction.status == TransactionStatusEnum.COMPLETED,
                )
                .scalar()
            )
            refundable_credit = max(
                Decimal("0.00"),
                issued_credit - Decimal(str(already_refunded_credit or 0)),
            ).quantize(Decimal("0.01"))
            if issued_credit <= 0 or tender_amount > refundable_credit:
                raise PaymentError(
                    f"El importe de la devolución ({tender_amount:.2f} {transaction_currency}) supera "
                    f"el crédito cambiario disponible ({refundable_credit:.2f} {transaction_currency})."
                )
            credit_refund_amount = tender_amount
        else:
            already_refunded_tender = (
                db.query(func.coalesce(func.sum(func.coalesce(Transaction.tender_amount, Transaction.amount)), 0))
                .filter(
                    Transaction.hotel_id == resolved_hotel_id,
                    Transaction.reservation_id == request.reservation_id,
                    Transaction.refund_of_transaction_id == refund_source.id,
                    Transaction.transaction_type == TransactionTypeEnum.REFUND,
                    Transaction.refund_component == RefundComponentEnum.PAYMENT.value,
                    Transaction.status == TransactionStatusEnum.COMPLETED,
                )
                .scalar()
            )
            original_tender_amount = Decimal(str(
                refund_source.tender_amount if refund_source.tender_amount is not None else refund_source.amount
            ))
            # The issued credit is a separate liability and cannot also be
            # returned as part of the source payment's principal refund.
            principal_tender_amount = max(
                Decimal("0.00"),
                original_tender_amount - Decimal(str(refund_source.rounding_credit_amount or 0)),
            )
            refundable_remaining = principal_tender_amount - Decimal(str(already_refunded_tender or 0))
            if tender_amount > refundable_remaining:
                raise PaymentError(
                    f"El importe de la devolución ({tender_amount:.2f} {transaction_currency}) supera "
                    f"el saldo reembolsable restante ({max(refundable_remaining, Decimal('0.00')):.2f} "
                    f"{transaction_currency}) del pago original."
                )

    if request.collected_before and transaction_currency != (reservation.currency_code or "ARS").strip().upper():
        raise PaymentError(
            "Un cobro previo en otra moneda requiere la cotización vigente en la fecha original. "
            "Registralo en la moneda de la reserva hasta contar con esa cotización histórica."
        )
    if is_credit_refund and refund_source is not None:
        applied_amount = Decimal("0.00")
        fx_rate_snapshot = refund_source.fx_rate_snapshot
        fx_quote_details = dict(refund_source.fx_quote_details or {})
        fx_quote_details["refund_uses_rounding_credit"] = True
    else:
        applied_amount, fx_rate_snapshot, fx_quote_details = _resolve_applied_payment_amount(
            db,
            hotel_id=resolved_hotel_id,
            reservation=reservation,
            tender_amount=tender_amount,
            tender_currency=transaction_currency,
            refund_source=refund_source,
            payment_fx_rate=payment_fx_rate,
            payment_fx_quote_details=payment_fx_quote_details,
        )
    if quoted_applied_amount is not None and applied_amount != quoted_applied_amount:
        raise PaymentError("La cotización guardada ya no coincide con el importe aplicado. Volvé a cotizar.")
    if is_refund and refund_source is not None and not is_credit_refund:
        try:
            refund_allocation_plan = prepare_company_night_charge_refund(
                db,
                hotel_id=resolved_hotel_id,
                reservation_id=request.reservation_id,
                source_transaction=refund_source,
                amount=applied_amount,
                refund_allocations=request.company_night_charge_refund_allocations,
            )
            if refund_allocation_plan:
                selected_night_refund_total = sum(
                    (Decimal(str(item["amount"])) for item in refund_allocation_plan),
                    Decimal("0.00"),
                ).quantize(Decimal("0.01"))
                # Tender is rounded to its currency's minor unit. If the frozen
                # FX conversion differs from the selected company-night amount
                # by at most one cent, preserve the operator's explicit night
                # allocation and record that applied amount in the ledger.
                if abs(selected_night_refund_total - applied_amount) <= Decimal("0.01"):
                    applied_amount = selected_night_refund_total
        except CompanyNightChargeError as exc:
            raise PaymentError(str(exc)) from exc
    if not is_refund:
        try:
            allocation_plan = prepare_company_night_charge_payment(
                db,
                hotel_id=resolved_hotel_id,
                reservation_id=request.reservation_id,
                amount=applied_amount,
                payment_currency=transaction_currency,
                charge_ids=request.company_night_charge_ids,
                idempotency_key=idempotency_key,
            )
        except CompanyNightChargeError as exc:
            raise PaymentError(str(exc)) from exc

    # Deferred company invoices are recorded outside the PMS. A new payment
    # against that reservation may only collect explicitly selected nightly
    # extras; prepare_company_night_charge_payment above verifies ownership,
    # outstanding status, and the exact amount for those extras. Keep refunds
    # on their existing source-payment validation path so earlier valid
    # collections can still be returned.
    if not is_refund:
        company_uses_deferred_settlement = False
        if reservation.company_id is not None:
            company = (
                db.query(Company)
                .filter(
                    Company.hotel_id == resolved_hotel_id,
                    Company.id == reservation.company_id,
                )
                .with_for_update()
                .one_or_none()
            )
            company_uses_deferred_settlement = bool(company and company.payment_deferred)
        if reservation.settlement_status == "deferred" or company_uses_deferred_settlement:
            if not request.company_night_charge_ids or not allocation_plan:
                raise PaymentError(
                    "La factura diferida de la empresa se registra fuera del PMS; "
                    "solo se pueden cobrar adicionales por noche seleccionados."
                )

    if manual_confirmation and request.manual_reference:
        duplicate_reference = (
            db.query(Transaction.id)
            .filter(
                Transaction.hotel_id == resolved_hotel_id,
                Transaction.payment_method == request.payment_method,
                func.lower(Transaction.manual_reference) == request.manual_reference.strip().lower(),
                Transaction.status != TransactionStatusEnum.CANCELLED,
            )
            .first()
        )
        if duplicate_reference is not None:
            raise PaymentError("Esta referencia de pago manual ya está registrada para esta reserva.")

    verified_late_settlement = (
        allow_verified_cancelled_settlement
        and reservation.status == ReservationStatusEnum.CANCELLED
        and gateway_response is not None
        and gateway_response.success
        and bool(gateway_response.external_payment_id)
    )
    if not is_refund and reservation.status in (
        ReservationStatusEnum.CHECKED_OUT,
        ReservationStatusEnum.CANCELLED,
    ) and not verified_late_settlement:
        raise PaymentError(
            f"No se puede registrar un pago para una reserva en estado «{reservation.status.value}»."
        )

    # 2. Validate payment method
    validate_payment_method_enabled(db, request.payment_method, resolved_hotel_id)
    if apply_surcharge and not is_refund and not request.collected_before:
        surcharge_info = calculate_payment_surcharge(
            db,
            hotel_id=resolved_hotel_id,
            payment_method=request.payment_method,
            base_amount=request.amount,
            currency_code=transaction_currency,
            surcharge_quote_snapshot=surcharge_quote_snapshot,
        )
        surcharge_amount = surcharge_info["surcharge_amount"]
    else:
        surcharge_amount = Decimal("0.00")
        surcharge_info = None
    gross_amount = (tender_amount + surcharge_amount).quantize(Decimal("0.01"))

    # 3. Validate against the confirmed transaction ledger; amount_paid is only
    #    a materialized compatibility cache and must not authorize overpayment.
    ledger_paid = paid_amount_with_legacy_fallback(db, resolved_hotel_id, reservation)
    if is_refund:
        if applied_amount > ledger_paid:
            raise PaymentError(
                f"El importe de la devolución (${applied_amount:.2f}) supera el total pagado (${ledger_paid:.2f})."
            )
    else:
        balance = operational_balance_due(
            db,
            hotel_id=resolved_hotel_id,
            reservation=reservation,
            paid_amount=ledger_paid,
        )
        balance = Decimal(str(balance)).quantize(Decimal("0.01"))
        if applied_amount > balance:
            raise PaymentError(
                f"El importe del pago (${applied_amount:.2f}) supera el saldo pendiente (${balance:.2f})."
            )
        if (
            request.transaction_type == TransactionTypeEnum.FULL_PAYMENT
            and balance - applied_amount > Decimal("0.00")
        ):
            raise PaymentError(
                f"El pago total debe cubrir el saldo pendiente (${Decimal(str(balance)):.2f})."
            )

    if request.payment_method == PaymentMethodEnum.CASH and not request.collected_before:
        from app.services import cash_register_service

        try:
            cash_register_service.require_open_session_for_currency(
                db,
                hotel_id=resolved_hotel_id,
                currency_code=transaction_currency,
            )
        except cash_register_service.CashRegisterError as exc:
            raise PaymentError(str(exc)) from exc

    # 4. Create transaction
    tx_status = TransactionStatusEnum.PENDING
    external_payment_id = None
    external_status = None
    raw_response = None
    processed_at = None

    # Cash and an explicitly approved manual proof are completed immediately.
    # Bank transfers submitted without proof intentionally remain pending.
    if request.payment_method == PaymentMethodEnum.CASH or manual_confirmation:
        tx_status = TransactionStatusEnum.COMPLETED
        processed_at = utc_naive(hotel_business_now(db, resolved_hotel_id))

    # For gateway payments, use the provided response
    if gateway_response:
        if gateway_response.success:
            tx_status = TransactionStatusEnum.COMPLETED
            processed_at = utc_naive(hotel_business_now(db, resolved_hotel_id))
        else:
            tx_status = TransactionStatusEnum.FAILED

        external_payment_id = gateway_response.external_payment_id
        external_status = gateway_response.external_status
        raw_response = gateway_response.gateway_response

    cash_received_amount = None
    cash_change_amount = None
    cash_tip_amount = Decimal("0.00")
    if normalized_cash_received is not None and tx_status != TransactionStatusEnum.COMPLETED:
        raise PaymentError("El efectivo entregado solo se registra para cobros completados.")
    if (
        request.payment_method == PaymentMethodEnum.CASH
        and not is_refund
        and capture_cash_receipt
        and tx_status == TransactionStatusEnum.COMPLETED
    ):
        cash_received_amount = normalized_cash_received if normalized_cash_received is not None else gross_amount
        cash_tip_amount, cash_change_amount = _cash_tender_breakdown(
            gross_amount=gross_amount,
            cash_received_amount=cash_received_amount,
            requested_tip_amount=normalized_cash_tip,
        )

    # idempotency_key is set AT CONSTRUCTION (before the INSERT) so a concurrent
    # duplicate delivery collides on the partial unique index
    # (hotel_id, reservation_id, idempotency_key) during the flush itself, rather
    # than leaving a race window where the key is assigned after the row is visible.
    transaction = Transaction(
        hotel_id=resolved_hotel_id,
        reservation_id=request.reservation_id,
        amount=applied_amount,
        tender_amount=tender_amount,
        tender_currency=transaction_currency,
        rounding_credit_amount=(
            rounding_credit_amount
            if tx_status == TransactionStatusEnum.COMPLETED
            else Decimal("0.00")
        ),
        credit_refund_amount=credit_refund_amount,
        refund_component=refund_component,
        gross_amount=gross_amount,
        cash_received_amount=cash_received_amount,
        cash_change_amount=cash_change_amount,
        cash_tip_amount=cash_tip_amount,
        fee_amount=surcharge_amount,
        currency=(reservation.currency_code or "ARS").strip().upper(),
        fx_rate_snapshot=fx_rate_snapshot,
        fx_quote_details=(
            {
                **(fx_quote_details or {}),
                **(
                    {"payment_surcharge_conversion": surcharge_info["surcharge_fx_quote_details"]}
                    if surcharge_info and surcharge_info.get("surcharge_fx_quote_details")
                    else {}
                ),
                **(
                    {"payment_surcharge_quote": surcharge_quote_snapshot["surcharge_fx_quote_details"]}
                    if surcharge_quote_snapshot
                    and surcharge_quote_snapshot.get("surcharge_fx_quote_details")
                    and not (surcharge_info and surcharge_info.get("surcharge_fx_quote_details"))
                    else {}
                ),
            }
            or None
        ),
        transaction_type=request.transaction_type,
        payment_method=request.payment_method,
        status=tx_status,
        external_payment_id=external_payment_id,
        external_status=external_status,
        manual_reference=request.manual_reference,
        refund_of_transaction_id=request.refund_of_transaction_id,
        refund_reason=request.refund_reason,
        collected_before=request.collected_before,
        collected_on=request.collected_on,
        prior_receipt_note=request.prior_receipt_note,
        gateway_response=raw_response,
        description=request.description,
        processed_at=processed_at,
        idempotency_key=idempotency_key,
        created_by_user_id=actor_user_id,
    )
    if idempotency_key is not None:
        # Savepoint: if a concurrent delivery already inserted this key, the unique
        # index raises IntegrityError here; roll back ONLY this insert and replay the
        # existing transaction (idempotent), never poisoning the outer transaction.
        try:
            with db.begin_nested():
                db.add(transaction)
                db.flush()
        except IntegrityError:
            existing = (
                db.query(Transaction)
                .filter(
                    Transaction.hotel_id == resolved_hotel_id,
                    Transaction.reservation_id == request.reservation_id,
                    Transaction.idempotency_key == idempotency_key,
                )
                .first()
            )
            if existing is not None:
                if _same_idempotent_payment(
                    db,
                    existing,
                    request,
                    transaction_currency,
                    resolved_hotel_id,
                ):
                    return existing
                raise PaymentError("La clave de idempotencia ya se usó para una solicitud de pago diferente.")
            if manual_confirmation and request.manual_reference:
                duplicate_reference = (
                    db.query(Transaction.id)
                    .filter(
                        Transaction.hotel_id == resolved_hotel_id,
                        Transaction.payment_method == request.payment_method,
                        func.lower(Transaction.manual_reference) == request.manual_reference.strip().lower(),
                        Transaction.status != TransactionStatusEnum.CANCELLED,
                    )
                    .first()
                )
                if duplicate_reference is not None:
                    raise PaymentError("Esta referencia de pago manual ya está registrada para esta reserva.")
            raise
    else:
        db.add(transaction)
        db.flush()

    if allocation_plan is not None:
        try:
            record_company_night_charge_payment_allocations(
                db,
                hotel_id=resolved_hotel_id,
                transaction=transaction,
                allocation_plan=allocation_plan,
            )
        except CompanyNightChargeError as exc:
            raise PaymentError(str(exc)) from exc

    if refund_allocation_plan:
        record_company_night_charge_refund_allocations(
            db,
            hotel_id=resolved_hotel_id,
            transaction=transaction,
            allocation_plan=refund_allocation_plan,
        )

    # 5. If completed, update reservation financial state
    if tx_status == TransactionStatusEnum.COMPLETED:
        _update_reservation_financials(
            db,
            reservation,
            request.amount,
            request.transaction_type,
            resolved_hotel_id,
        )
        if verified_late_settlement:
            reservation.requires_manual_review = True
            reservation.settlement_status = "review_cancellation"
        # 6. Physical cash must land in an explicitly opened caja so the
        #    arqueo reconciles. The cash-register service rejects the payment
        #    if there is no open session.
        if request.payment_method == PaymentMethodEnum.CASH and not request.collected_before:
            from app.services import cash_register_service

            try:
                cash_register_service.record_cash_payment_movement(
                    db,
                    transaction=transaction,
                    recorded_by_user_id=actor_user_id,
                )
            except cash_register_service.CashRegisterError as exc:
                # Every process_payment caller (direct payment route, webhook
                # processing, reservation extension, transfer-proof approval)
                # already catches PaymentError with a clean 4xx response.
                # Without this translation a cash charge with no open caja
                # crashed as an unhandled 500 instead of blocking clearly.
                raise PaymentError(str(exc)) from exc

    return transaction


def get_payment_link_with_surcharge(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    payment_method: str,
    amount: Optional[float] = None,
) -> dict:
    """
    Calculate surcharge for a payment link and return a guest-facing breakdown.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise PaymentError(f"No se encontró la reserva {reservation_id}.")
    if reservation.hotel_id and reservation.hotel_id != hotel_id:
        raise PaymentError(f"La reserva {reservation_id} no pertenece al hotel {hotel_id}.")

    if amount is None:
        amount = operational_balance_due(db, hotel_id=hotel_id, reservation=reservation)
    base_amount = Decimal(str(amount)).quantize(Decimal("0.01"))
    if base_amount <= 0:
        raise PaymentError("El importe del pago debe ser mayor que cero.")

    surcharge_info = calculate_payment_surcharge(
        db,
        hotel_id=hotel_id,
        payment_method=payment_method,
        base_amount=base_amount,
        currency_code=(reservation.currency_code or "ARS").strip().upper(),
    )
    final_amount = surcharge_info["final_amount"]
    payment_url = f"/api/pay/{payment_method}/{reservation_id}?amount={final_amount}"
    shareable_link = f"/pay/{reservation.confirmation_code}/{payment_method}"

    return {
        "base_amount": float(surcharge_info["base_amount"]),
        "currency_code": surcharge_info["currency_code"],
        "surcharge_type": surcharge_info["surcharge_type"],
        "surcharge_value": surcharge_info["surcharge_value"],
        "surcharge_currency_code": surcharge_info["surcharge_currency_code"],
        "surcharge_amount": float(surcharge_info["surcharge_amount"]),
        "final_amount": float(final_amount),
        "fx_quote_details": surcharge_info["surcharge_fx_quote_details"],
        "payment_url": payment_url,
        "shareable_link": shareable_link,
    }


def _update_reservation_financials(
    db: Session,
    reservation: Reservation,
    amount: float,
    tx_type: TransactionTypeEnum,
    hotel_id: int,
) -> None:
    """
    Refresh the materialized amount_paid cache from confirmed OTA credits and
    the in-house completed ledger, then transition status from that total.

    State machine:
    - If deposit paid (amount >= deposit_amount) and status is PENDING → deposit_paid
    - If fully paid (balance_due == 0) → fully_paid
    """
    was_no_show = reservation.status == ReservationStatusEnum.NO_SHOW
    reservation.amount_paid = paid_amount_with_legacy_fallback(db, hotel_id, reservation)
    sync_reservation_financial_status(db, reservation, hotel_id=hotel_id, reason_code=tx_type.value)
    if was_no_show and reservation.status == ReservationStatusEnum.NO_SHOW:
        # Partial no-show revenue is derived from amount_paid. Keep its fact row
        # current in the same transaction without reopening the terminal state.
        from app.services.analytics_facts import touch_reservation_fact_window

        touch_reservation_fact_window(
            db,
            hotel_id=hotel_id,
            date_from=reservation.check_in_date,
            date_to=reservation.check_out_date,
            reservation_id=reservation.id,
        )
    db.flush()


def sync_reservation_financial_status(
    db: Session,
    reservation: Reservation,
    *,
    hotel_id: int,
    reason_code: str,
) -> None:
    if reservation.status in (
        ReservationStatusEnum.CANCELLED,
        ReservationStatusEnum.NO_SHOW,
        ReservationStatusEnum.PRE_CHECK_IN,
        ReservationStatusEnum.PARTIAL_CHECK_IN,
        ReservationStatusEnum.CHECKED_IN,
        ReservationStatusEnum.CHECKED_OUT,
    ):
        return

    _TOL = Decimal("0.01")
    d_paid = Decimal(str(reservation.amount_paid or 0))
    adjustment_total = (
        db.query(func.coalesce(func.sum(BillingAdjustment.total_amount), 0))
        .filter(
            BillingAdjustment.hotel_id == hotel_id,
            BillingAdjustment.reservation_id == reservation.id,
        )
        .scalar()
    )
    d_total = Decimal(str(reservation.total_amount or 0)) + Decimal(str(adjustment_total or 0))
    d_deposit = Decimal(str(reservation.deposit_amount or 0))
    if d_paid >= d_total - _TOL:
        target_status = ReservationStatusEnum.FULLY_PAID
    elif d_paid >= d_deposit - _TOL and d_paid > 0:
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


def _company_night_charge_refund_options(
    *,
    transactions: list[Transaction],
    night_charges: list[CompanyNightCharge],
    allocations: list[tuple[CompanyNightChargePaymentAllocation, Transaction]],
) -> dict[int, list[dict[str, object]]]:
    """Return still-refundable source allocations in reservation currency.

    New refunds carry explicit per-night allocations. Historical refunds with no
    allocation rows retain their former proportional treatment for compatibility.
    """
    if not allocations or not night_charges:
        return {}
    charges_by_id = {row.id: row for row in night_charges}
    allocation_rows_by_transaction: dict[int, list[CompanyNightChargePaymentAllocation]] = {}
    for allocation, _transaction in allocations:
        allocation_rows_by_transaction.setdefault(allocation.transaction_id, []).append(allocation)

    legacy_refunds_by_source: dict[int, Decimal] = {}
    explicit_refunds_by_source_charge: dict[tuple[int, int], Decimal] = {}
    for refund in transactions:
        if (
            refund.status != TransactionStatusEnum.COMPLETED
            or refund.transaction_type != TransactionTypeEnum.REFUND
            or refund.refund_of_transaction_id is None
        ):
            continue
        refund_allocations = allocation_rows_by_transaction.get(refund.id, [])
        if refund_allocations:
            for allocation in refund_allocations:
                key = (refund.refund_of_transaction_id, allocation.company_night_charge_id)
                explicit_refunds_by_source_charge[key] = (
                    explicit_refunds_by_source_charge.get(key, Decimal("0.00"))
                    + Decimal(str(allocation.amount or 0))
                )
        else:
            source_id = refund.refund_of_transaction_id
            legacy_refunds_by_source[source_id] = (
                legacy_refunds_by_source.get(source_id, Decimal("0.00"))
                + Decimal(str(refund.amount or 0))
            )

    options: dict[int, list[dict[str, object]]] = {}
    transaction_by_id = {row.id: row for row in transactions}
    for source_id, source_allocations in allocation_rows_by_transaction.items():
        source = transaction_by_id.get(source_id)
        if (
            source is None
            or source.status != TransactionStatusEnum.COMPLETED
            or source.transaction_type == TransactionTypeEnum.REFUND
        ):
            continue
        source_amount = Decimal(str(source.amount or 0)).quantize(Decimal("0.01"))
        allocated_total = sum(
            (Decimal(str(row.amount or 0)) for row in source_allocations),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        if source_amount <= 0 or allocated_total != source_amount:
            continue
        legacy_fraction = min(
            Decimal("1"),
            legacy_refunds_by_source.get(source.id, Decimal("0.00")) / source_amount,
        )
        source_options: list[dict[str, object]] = []
        for allocation in source_allocations:
            charge = charges_by_id.get(allocation.company_night_charge_id)
            if charge is None:
                continue
            original_amount = Decimal(str(allocation.amount or 0)).quantize(Decimal("0.01"))
            legacy_refund_amount = (original_amount * legacy_fraction).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            explicit_refund_amount = explicit_refunds_by_source_charge.get(
                (source.id, charge.id), Decimal("0.00")
            )
            remaining = max(
                Decimal("0.00"),
                original_amount - legacy_refund_amount - explicit_refund_amount,
            ).quantize(Decimal("0.01"))
            if remaining > 0:
                source_options.append(
                    {
                        "charge_id": charge.id,
                        "stay_date": charge.stay_date,
                        "remaining_amount": remaining,
                    }
                )
        if source_options:
            options[source.id] = sorted(source_options, key=lambda item: (item["stay_date"], item["charge_id"]))
    return options


def get_reservation_financial_summary(
    db: Session,
    hotel_id: Optional[int],
    reservation_id: int,
    *,
    include_payment_correction_audit: bool = False,
) -> dict:
    """
    Get a full financial summary for a reservation.
    Returns total, paid, balance, deposit required, and all transactions.
    """
    reservation_query = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_query = reservation_query.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_query.first()
    if not reservation:
        raise PaymentNotFoundError("No se encontró la reserva.")

    existing_tx_query = db.query(Transaction.hotel_id).filter(Transaction.reservation_id == reservation_id)
    if hotel_id is not None:
        existing_tx_query = existing_tx_query.filter(Transaction.hotel_id == hotel_id)
    existing_tx = existing_tx_query.first()
    existing_tx_hotel_id = existing_tx[0] if existing_tx else None

    resolved_hotel_id = _resolve_reservation_hotel(
        reservation,
        hotel_id,
        existing_tx_hotel_id=existing_tx_hotel_id,
    )
    if reservation.hotel_id and reservation.hotel_id != resolved_hotel_id:
        raise PaymentError(f"La reserva {reservation_id} no pertenece al hotel {resolved_hotel_id}.")

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.reservation_id == reservation_id,
            Transaction.hotel_id == resolved_hotel_id,
        )
        .order_by(Transaction.created_at)
        .all()
    )
    payment_corrections = []
    if include_payment_correction_audit:
        correction_rows = (
            db.query(PaymentCorrection)
            .filter(
                PaymentCorrection.hotel_id == resolved_hotel_id,
                (PaymentCorrection.source_reservation_id == reservation.id)
                | (PaymentCorrection.target_reservation_id == reservation.id),
            )
            .order_by(PaymentCorrection.created_at.desc(), PaymentCorrection.id.desc())
            .all()
        )
        payment_corrections = [
            {
                "correction_id": correction.id,
                "correction_type": correction.correction_type,
                "source_transaction_id": correction.source_transaction_id,
                "source_reservation_id": correction.source_reservation_id,
                "target_reservation_id": correction.target_reservation_id,
                "replacement_transaction_id": correction.replacement_transaction_id,
                "reason": correction.reason,
                "actor_user_id": correction.actor_user_id,
                "created_at": str(correction.created_at),
            }
            for correction in correction_rows
        ]

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
    deferred_company_billing = reservation_has_deferred_company_billing(
        db,
        reservation,
        hotel_id=resolved_hotel_id,
    )
    visible_transactions = transactions
    visible_adjustments = billing_adjustments
    night_charges = (
        db.query(CompanyNightCharge)
        .filter(
            CompanyNightCharge.hotel_id == resolved_hotel_id,
            CompanyNightCharge.reservation_id == reservation.id,
        )
        .all()
    )
    night_charge_ids = {row.id for row in night_charges}
    allocations = (
        db.query(CompanyNightChargePaymentAllocation, Transaction)
        .join(
            Transaction,
            (Transaction.id == CompanyNightChargePaymentAllocation.transaction_id)
            & (Transaction.hotel_id == CompanyNightChargePaymentAllocation.hotel_id),
        )
        .filter(
            CompanyNightChargePaymentAllocation.hotel_id == resolved_hotel_id,
            CompanyNightChargePaymentAllocation.company_night_charge_id.in_(night_charge_ids),
        )
        .all()
        if night_charge_ids
        else []
    )
    charge_refund_options = _company_night_charge_refund_options(
        transactions=transactions,
        night_charges=night_charges,
        allocations=allocations,
    )
    if deferred_company_billing:
        # Only specifically selected company-night extras are collectible
        # through the PMS. Keep their ledger evidence, while hiding any legacy
        # lodging receipts/amounts from this reservation summary.
        adjustment_ids = {row.billing_adjustment_id for row in night_charges}
        visible_adjustments = [row for row in billing_adjustments if row.id in adjustment_ids]
        allocations_by_transaction: dict[int, Decimal] = {}
        for allocation, _transaction in allocations:
            allocations_by_transaction[allocation.transaction_id] = (
                allocations_by_transaction.get(allocation.transaction_id, Decimal("0.00"))
                + Decimal(str(allocation.amount or 0))
            )
        transaction_by_id = {row.id: row for row in transactions}
        valid_extra_payment_ids = {
            transaction_id
            for transaction_id, allocated_amount in allocations_by_transaction.items()
            if transaction_id in transaction_by_id
            and allocated_amount.quantize(Decimal("0.01"))
            == Decimal(str(transaction_by_id[transaction_id].amount or 0)).quantize(Decimal("0.01"))
        }
        visible_transactions = [
            transaction
            for transaction in transactions
            if transaction.id in valid_extra_payment_ids
            or (
                transaction.transaction_type == TransactionTypeEnum.REFUND
                and transaction.refund_of_transaction_id in valid_extra_payment_ids
            )
        ]
        charge_totals = {
            row.id: Decimal(str(row.amount or 0)).quantize(Decimal("0.01"))
            for row in night_charges
        }
        paid_by_charge: dict[int, Decimal] = {}
        legacy_refunds_by_source: dict[int, Decimal] = {}
        explicitly_allocated_refund_ids = {
            transaction.id
            for allocation, transaction in allocations
            if transaction.transaction_type == TransactionTypeEnum.REFUND
        }
        for transaction in visible_transactions:
            if (
                transaction.status == TransactionStatusEnum.COMPLETED
                and transaction.transaction_type == TransactionTypeEnum.REFUND
                and transaction.id not in explicitly_allocated_refund_ids
                and transaction.refund_of_transaction_id is not None
            ):
                legacy_refunds_by_source[transaction.refund_of_transaction_id] = (
                    legacy_refunds_by_source.get(transaction.refund_of_transaction_id, Decimal("0.00"))
                    + Decimal(str(transaction.amount or 0))
                )
        completed_extra_payment_total = Decimal("0.00")
        for transaction in visible_transactions:
            if transaction.status != TransactionStatusEnum.COMPLETED:
                continue
            signed_amount = Decimal(str(_signed_transaction_amount(transaction.transaction_type, transaction.amount)))
            completed_extra_payment_total += signed_amount
            if transaction.transaction_type == TransactionTypeEnum.REFUND:
                # New refunds have an explicit charge allocation row; legacy
                # refunds are applied proportionally below for compatibility.
                for allocation, _row in allocations:
                    if allocation.transaction_id == transaction.id:
                        paid_by_charge[allocation.company_night_charge_id] = (
                            paid_by_charge.get(allocation.company_night_charge_id, Decimal("0.00"))
                            - Decimal(str(allocation.amount or 0))
                        )
                continue
            tx_amount = Decimal(str(transaction.amount or 0))
            allocated_amount = allocations_by_transaction.get(transaction.id, Decimal("0.00"))
            if tx_amount <= 0 or allocated_amount.quantize(Decimal("0.01")) != tx_amount.quantize(Decimal("0.01")):
                continue
            legacy_refund = min(
                legacy_refunds_by_source.get(transaction.id, Decimal("0.00")),
                tx_amount,
            )
            legacy_fraction = legacy_refund / tx_amount if tx_amount > 0 else Decimal("0")
            for allocation, _row in allocations:
                if allocation.transaction_id == transaction.id:
                    net_allocation = Decimal(str(allocation.amount or 0)) * (Decimal("1") - legacy_fraction)
                    paid_by_charge[allocation.company_night_charge_id] = (
                        paid_by_charge.get(allocation.company_night_charge_id, Decimal("0.00"))
                        + net_allocation
                    )
        extra_total = sum(charge_totals.values(), Decimal("0.00"))
        billing_adjustment_total = extra_total
        completed_payment_total = completed_extra_payment_total.quantize(Decimal("0.01"))
        operational_total = extra_total
        operational_balance_due = sum(
            (
                max(Decimal("0.00"), amount - paid_by_charge.get(charge_id, Decimal("0.00")))
                for charge_id, amount in charge_totals.items()
            ),
            Decimal("0.00"),
        ).quantize(Decimal("0.01"))
        d_total = Decimal("0.00")
        d_paid = Decimal("0.00")
        reconciliation_gap = None
    else:
        billing_adjustment_total = Decimal(str(round(sum(adj.total_amount for adj in billing_adjustments), 2)))
        completed_payment_total = Decimal(str(round(
            sum(_signed_transaction_amount(t.transaction_type, t.amount) for t in completed_transactions),
            2,
        )))
        d_total = Decimal(str(reservation.total_amount or 0))
        materialized_paid = Decimal(str(reservation.amount_paid or 0))
        d_paid = paid_amount_with_legacy_fallback(db, resolved_hotel_id, reservation)
        operational_total = d_total + billing_adjustment_total
        operational_balance_due = max(Decimal("0"), operational_total - d_paid)
        evidenced_paid = reconciled_paid_amounts_by_reservation(
            db,
            resolved_hotel_id,
            [reservation.id],
        ).get(reservation.id, Decimal("0.00"))
        reconciliation_gap = materialized_paid - evidenced_paid

    credit_sources: dict[int, dict[str, Decimal | str]] = {}
    for transaction in visible_transactions:
        if transaction.status != TransactionStatusEnum.COMPLETED:
            continue
        currency_code = str(transaction.tender_currency or transaction.currency or "ARS").strip().upper()
        if (
            transaction.transaction_type != TransactionTypeEnum.REFUND
            and Decimal(str(transaction.rounding_credit_amount or 0)) > 0
        ):
            credit_sources[transaction.id] = {
                "currency_code": currency_code,
                "issued_amount": Decimal(str(transaction.rounding_credit_amount or 0)).quantize(Decimal("0.01")),
                "refunded_amount": Decimal("0.00"),
            }
    for transaction in visible_transactions:
        if (
            transaction.status != TransactionStatusEnum.COMPLETED
            or transaction.transaction_type != TransactionTypeEnum.REFUND
            or transaction.refund_component != RefundComponentEnum.ROUNDING_CREDIT.value
            or transaction.refund_of_transaction_id not in credit_sources
        ):
            continue
        source = credit_sources[transaction.refund_of_transaction_id]
        source["refunded_amount"] = (
            Decimal(str(source["refunded_amount"]))
            + Decimal(str(transaction.credit_refund_amount or 0))
        ).quantize(Decimal("0.01"))

    credit_by_currency: dict[str, dict[str, Decimal]] = {}
    credit_source_summaries = []
    for source_id, credit in sorted(credit_sources.items()):
        currency_code = str(credit["currency_code"])
        issued_amount = Decimal(str(credit["issued_amount"]))
        refunded_amount = Decimal(str(credit["refunded_amount"]))
        open_amount = max(Decimal("0.00"), issued_amount - refunded_amount).quantize(Decimal("0.01"))
        currency_totals = credit_by_currency.setdefault(
            currency_code,
            {
                "issued_amount": Decimal("0.00"),
                "refunded_amount": Decimal("0.00"),
                "open_amount": Decimal("0.00"),
            },
        )
        currency_totals["issued_amount"] += issued_amount
        currency_totals["refunded_amount"] += refunded_amount
        currency_totals["open_amount"] += open_amount
        credit_source_summaries.append(
            {
                "source_transaction_id": source_id,
                "currency_code": currency_code,
                "issued_amount": issued_amount,
                "refunded_amount": refunded_amount,
                "open_amount": open_amount,
            }
        )

    return {
        "reservation_id": reservation.id,
        "confirmation_code": reservation.confirmation_code,
        "status": reservation.status.value,
        "currency_code": reservation.currency_code or "ARS",
        "total_amount": None if deferred_company_billing else reservation.total_amount,
        "deposit_required": None if deferred_company_billing else reservation.deposit_amount,
        "amount_paid": None if deferred_company_billing else d_paid,
        "hotel_received_amount": None if deferred_company_billing else completed_payment_total,
        "ota_prepaid_amount": None if deferred_company_billing else external_paid_balance_credit(reservation),
        "balance_due": None if deferred_company_billing else max(Decimal("0"), d_total - d_paid),
        "operational_total_amount": operational_total,
        "operational_balance_due": operational_balance_due,
        "billing_adjustment_total": billing_adjustment_total,
        "company_billing_deferred": deferred_company_billing,
        "payment_collection_model": reservation.payment_collection_model,
        "settlement_status": reservation.settlement_status,
        "has_financial_reconciliation_gap": (
            abs(reconciliation_gap) > 0.01 if reconciliation_gap is not None else False
        ),
        "financial_reconciliation_gap": reconciliation_gap,
        "recommended_next_action": None if deferred_company_billing else _recommended_financial_action(
            reservation=reservation,
            operational_balance_due=operational_balance_due,
        ),
        "rounding_credit_by_currency": [
            {"currency_code": currency, **amounts}
            for currency, amounts in sorted(credit_by_currency.items())
        ],
        "rounding_credit_sources": credit_source_summaries,
        "payment_corrections": payment_corrections,
        "transactions": [
            {
                "id": t.id,
                "group_payment_batch_id": t.group_payment_batch_id,
                "amount": t.tender_amount if t.tender_amount is not None else t.amount,
                "applied_amount": t.amount,
                "applied_currency": t.currency,
                "fx_rate_snapshot": t.fx_rate_snapshot,
                "gross_amount": t.gross_amount if t.gross_amount is not None else t.amount,
                "cash_received_amount": t.cash_received_amount,
                "cash_change_amount": t.cash_change_amount,
                "cash_tip_amount": t.cash_tip_amount,
                "fee_amount": t.fee_amount or 0,
                "currency": t.tender_currency or t.currency,
                "method": t.payment_method.value,
                "type": t.transaction_type.value,
                "status": t.status.value,
                "manual_reference": t.manual_reference,
                "refund_of_transaction_id": t.refund_of_transaction_id,
                "rounding_credit_amount": t.rounding_credit_amount or Decimal("0.00"),
                "credit_refund_amount": t.credit_refund_amount or Decimal("0.00"),
                "refund_component": t.refund_component or RefundComponentEnum.PAYMENT.value,
                "collected_before": bool(t.collected_before),
                "collected_on": t.collected_on,
                "prior_receipt_note": t.prior_receipt_note,
                "company_night_charge_refundable_allocations": charge_refund_options.get(t.id, []),
                "created_at": str(t.created_at),
            }
            for t in visible_transactions
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
            for adj in visible_adjustments
        ],
        "completed_payments": completed_payment_total,
    }


def get_payment_receipt_data(db: Session, hotel_id: Optional[int], transaction_id: int) -> dict:
    """Return only confirmed, tenant-scoped transaction data for receipt rendering."""
    if hotel_id is None:
        raise PaymentNotFoundError("No se encontró el pago.")

    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id, Transaction.hotel_id == hotel_id)
        .first()
    )
    if transaction is None or transaction.status not in {
        TransactionStatusEnum.COMPLETED,
        TransactionStatusEnum.REFUNDED,
    }:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")

    reservation_row = (
        db.query(
            Reservation.confirmation_code,
            Reservation.currency_code,
            Guest.first_name,
            Guest.last_name,
        )
        .join(Guest, Guest.id == Reservation.guest_id)
        .filter(
            Reservation.id == transaction.reservation_id,
            Reservation.hotel_id == hotel_id,
            Guest.hotel_id == hotel_id,
        )
        .first()
    )
    if reservation_row is None:
        raise PaymentNotFoundError("No se encontró el pago confirmado.")
    reservation_code, reservation_currency, guest_first_name, guest_last_name = reservation_row
    guest_name = " ".join(
        part.strip()
        for part in (str(guest_first_name or ""), str(guest_last_name or ""))
        if part.strip()
    ) or "Huésped"

    hotel = db.get(HotelConfiguration, hotel_id)
    created_at = transaction.created_at
    if created_at.tzinfo is None:
        # Legacy DateTime columns are stored as naive UTC values.
        created_at = created_at.replace(tzinfo=timezone.utc)
    else:
        created_at = created_at.astimezone(timezone.utc)
    return {
        "id": transaction.id,
        "reservation_id": transaction.reservation_id,
        "confirmation_code": reservation_code,
        "guest_name": guest_name,
        "hotel_name": hotel.hotel_name if hotel and hotel.hotel_name else "Mi Hotel",
        "hotel_timezone": hotel.hotel_timezone if hotel and hotel.hotel_timezone else "America/Argentina/Buenos_Aires",
        "amount": transaction.tender_amount if transaction.tender_amount is not None else transaction.amount,
        "applied_amount": transaction.amount,
        "applied_currency": transaction.currency or reservation_currency,
        "fx_rate_snapshot": transaction.fx_rate_snapshot,
        "gross_amount": transaction.gross_amount if transaction.gross_amount is not None else transaction.amount,
        "cash_received_amount": transaction.cash_received_amount,
        "cash_change_amount": transaction.cash_change_amount,
        "cash_tip_amount": transaction.cash_tip_amount,
        "fee_amount": transaction.fee_amount or Decimal("0.00"),
        "currency": transaction.tender_currency or transaction.currency,
        "method": transaction.payment_method,
        "type": transaction.transaction_type,
        "status": transaction.status,
        "manual_reference": transaction.manual_reference,
        "refund_of_transaction_id": transaction.refund_of_transaction_id,
        "created_at": created_at,
    }


def _signed_transaction_amount(transaction_type: TransactionTypeEnum, amount) -> Decimal:
    d = Decimal(str(amount))
    return -d if transaction_type == TransactionTypeEnum.REFUND else d


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
