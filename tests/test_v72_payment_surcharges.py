from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.payment_surcharge import PaymentSurcharge, PaymentSurchargeTypeEnum
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import RoomCategory
from app.models.transaction import PaymentMethodEnum, TransactionTypeEnum
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.transaction import PaymentGatewayResponse, PaymentRequest
from app.services.payment_link_service import create_link
from app.services.payment_service import process_payment


def _ensure_hotel(db: Session, hotel_id: int) -> HotelConfiguration:
    hotel = db.get(HotelConfiguration, hotel_id)
    if hotel:
        hotel.enable_cash = True
        hotel.enable_mercado_pago = True
        hotel.subscription_active = True
        db.flush()
        return hotel
    hotel = HotelConfiguration(
        id=hotel_id,
        deposit_percentage=30.0,
        enable_cash=True,
        enable_mercado_pago=True,
        subscription_active=True,
    )
    db.add(hotel)
    db.flush()
    return hotel


def _reservation(db: Session, hotel_id: int, total: Decimal = Decimal("200.00")) -> Reservation:
    _ensure_hotel(db, hotel_id)
    guest = Guest(
        first_name="Ada",
        last_name="Surcharge",
        email=f"surcharge-{hotel_id}@example.com",
        hotel_id=hotel_id,
    )
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Surcharge Standard {hotel_id}",
        code=f"SRG{hotel_id}",
        base_price_per_night=Decimal("100.00"),
        max_occupancy=2,
    )
    db.add_all([guest, category])
    db.flush()
    reservation = Reservation(
        hotel_id=hotel_id,
        confirmation_code=f"SRG-{hotel_id}-{guest.id}",
        guest_id=guest.id,
        category_id=category.id,
        check_in_date=date(2026, 8, 1),
        check_out_date=date(2026, 8, 3),
        total_amount=total,
        deposit_amount=Decimal("60.00"),
        currency_code="ARS",
        status=ReservationStatusEnum.PENDING,
    )
    db.add(reservation)
    db.flush()
    return reservation


def _surcharge(
    db: Session,
    hotel_id: int,
    method: str,
    surcharge_type: PaymentSurchargeTypeEnum,
    amount: float,
    *,
    is_active: bool = True,
) -> PaymentSurcharge:
    surcharge = PaymentSurcharge(
        hotel_id=hotel_id,
        payment_method=method,
        surcharge_type=surcharge_type,
        amount=amount,
        currency_code="ARS",
        is_active=is_active,
    )
    db.add(surcharge)
    db.flush()
    return surcharge


def test_fixed_surcharge_applies_to_transaction_gross_and_fee(db: Session):
    reservation = _reservation(db, 1)
    _surcharge(db, 1, "cash", PaymentSurchargeTypeEnum.FIXED, 10.0)

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        ),
        hotel_id=1,
    )
    db.flush()
    db.refresh(reservation)

    assert tx.amount == Decimal("100.00")
    assert tx.fee_amount == Decimal("10.00")
    assert tx.gross_amount == Decimal("110.00")
    assert reservation.amount_paid == Decimal("100.00")


def test_percentage_surcharge_applies_to_transaction_gross_and_fee(db: Session):
    reservation = _reservation(db, 1)
    _surcharge(db, 1, "cash", PaymentSurchargeTypeEnum.PERCENTAGE, 7.5)

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=80.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        ),
        hotel_id=1,
    )
    db.flush()

    assert tx.amount == Decimal("80.00")
    assert tx.fee_amount == Decimal("6.00")
    assert tx.gross_amount == Decimal("86.00")


def test_inactive_surcharge_is_noop(db: Session):
    reservation = _reservation(db, 1)
    _surcharge(db, 1, "cash", PaymentSurchargeTypeEnum.FIXED, 25.0, is_active=False)

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=50.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        ),
        hotel_id=1,
    )
    db.flush()

    assert tx.amount == Decimal("50.00")
    assert tx.fee_amount == Decimal("0.00")
    assert tx.gross_amount == Decimal("50.00")


def test_surcharge_is_scoped_per_hotel(db: Session):
    reservation = _reservation(db, 1)
    _ensure_hotel(db, 2)
    _surcharge(db, 2, "cash", PaymentSurchargeTypeEnum.FIXED, 30.0)

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=70.0,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        ),
        hotel_id=1,
    )
    db.flush()

    assert tx.fee_amount == Decimal("0.00")
    assert tx.gross_amount == Decimal("70.00")


def test_payment_link_requested_amount_includes_surcharge(db: Session):
    reservation = _reservation(db, 1)
    _surcharge(db, 1, "mercado_pago", PaymentSurchargeTypeEnum.PERCENTAGE, 3.0)

    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
        ),
    )

    assert link.requested_amount == Decimal("103.00")


def test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(db: Session):
    reservation = _reservation(db, 1)
    _surcharge(db, 1, "mercado_pago", PaymentSurchargeTypeEnum.PERCENTAGE, 3.0)
    link = create_link(
        db,
        1,
        PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
        ),
    )

    tx = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=100.0,
            payment_method=PaymentMethodEnum.MERCADO_PAGO,
            transaction_type=TransactionTypeEnum.PARTIAL_PAYMENT,
        ),
        hotel_id=1,
        gateway_response=PaymentGatewayResponse(success=True, external_payment_id=link.link_code),
    )
    db.flush()

    assert link.requested_amount == Decimal("103.00")
    assert tx.amount == Decimal("100.00")
    assert tx.fee_amount == Decimal("3.00")
    assert tx.gross_amount == Decimal("103.00")
