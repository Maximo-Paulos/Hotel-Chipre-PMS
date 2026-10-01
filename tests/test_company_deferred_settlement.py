"""v72 §3.5 corporate deferred billing flow (R5b ITEM C).

A company reservation with payment_deferred is created with settlement_status
'deferred' and a settlement_due_date = check_out + deferred_days. Registering the
collection transitions it to 'settled'.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api import payments as payments_api
from app.api import reservations as reservations_api
from app.dependencies.auth import AuthContext
from app.models.cash_register import CashMovement
from app.models.company import Company
from app.models.hotel_config import HotelConfiguration
from app.models.payment import PaymentLink
from app.models.reservation import ReservationStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum, TransactionTypeEnum
from app.schemas.transaction import PaymentRequest
from app.schemas.payment_link import PaymentLinkCreate
from app.schemas.reservation import ReservationCreate, ReservationExtensionRequest
from app.services.company_night_charge_service import add_company_night_charges
from app.services import reservation_operations_service
from app.services.payment_service import PaymentError, process_payment
from app.services.permission_service import (
    PERMISSION_CASH_OPERATE,
    PERMISSION_COMPANY_MANAGE,
    PERMISSION_RESERVATION_CHARGE,
)
from app.services.reservation_operations_service import ReservationOperationsError, extend_reservation_stay
from app.services.reservation_service import (
    ReservationError,
    create_reservation,
    register_company_settlement,
)


def _deferred_company(
    db,
    *,
    hotel_id: int = 1,
    deferred_days: int = 30,
    base_price: Decimal | None = None,
    nightly_extra: Decimal | None = None,
) -> Company:
    company = Company(
        hotel_id=hotel_id,
        legal_name="UOCRA SA",
        display_name="UOCRA",
        payment_deferred=True,
        deferred_days=deferred_days,
        base_price=base_price,
        extra_person_nightly_surcharge=nightly_extra,
    )
    db.add(company)
    db.flush()
    return company


def test_deferred_company_reservation_sets_settlement(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    company = _deferred_company(db, deferred_days=30)
    check_out = date(2026, 4, 5)
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 4, 1),
        check_out_date=check_out,
        company_id=company.id,
    )
    reservation = create_reservation(db, data)

    assert reservation.settlement_status == "deferred"
    assert reservation.settlement_due_date == check_out + timedelta(days=30)
    assert reservation.total_amount == 0
    assert reservation.deposit_amount == 0
    assert reservation.subtotal_amount == 0
    assert reservation.tax_amount == 0
    assert reservation.fee_amount == 0
    assert reservation.commission_amount == 0
    assert reservation.net_amount == 0
    assert '"amount_recorded_in_pms": false' in reservation.pricing_snapshot
    assert "525" not in reservation.pricing_snapshot


def test_register_settlement_marks_settled(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    company = _deferred_company(db, deferred_days=15)
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 5, 1),
        check_out_date=date(2026, 5, 3),
        company_id=company.id,
    )
    reservation = create_reservation(db, data)
    assert reservation.settlement_status == "deferred"

    register_company_settlement(db, reservation, hotel_id=1)
    assert reservation.settlement_status == "settled"

    # Idempotent: a second call does not raise and stays settled.
    register_company_settlement(db, reservation, hotel_id=1)
    assert reservation.settlement_status == "settled"


def test_register_settlement_rejects_non_company(db, sample_guest, sample_rooms, sample_categories, hotel_config):
    data = ReservationCreate(
        guest_id=sample_guest.id,
        category_id=sample_categories[0].id,
        room_id=sample_rooms[0].id,
        check_in_date=date(2026, 6, 1),
        check_out_date=date(2026, 6, 3),
    )
    reservation = create_reservation(db, data)
    with pytest.raises(ReservationError):
        register_company_settlement(db, reservation, hotel_id=1)


def _company_reservation(db, sample_guest, sample_rooms, sample_categories, company, *, start_offset=10):
    check_in = date.today() + timedelta(days=start_offset)
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=check_in,
            check_out_date=check_in + timedelta(days=2),
            company_id=company.id,
        ),
        hotel_id=1,
    )
    reservation.status = ReservationStatusEnum.CHECKED_IN
    reservation.company_extension_request_pending = True
    reservation.company_extension_request_note = "La empresa solicitó una extensión"
    db.flush()
    return reservation


def test_deferred_company_extension_does_not_calculate_or_record_base_price(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    company = _deferred_company(db, deferred_days=14, base_price=Decimal("100.00"))
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    # The company rate changed after the original stay was booked; the new
    # nights must use today's company rate rather than the old reservation total.
    company.base_price = Decimal("150.00")
    db.flush()
    original_checkout = reservation.check_out_date
    original_version = reservation.version
    original_amounts = (
        reservation.total_amount,
        reservation.subtotal_amount,
        reservation.net_amount,
    )
    original_snapshot = reservation.pricing_snapshot
    new_checkout = original_checkout + timedelta(days=2)
    monkeypatch.setattr(
        reservation_operations_service,
        "_extension_amount",
        lambda *args, **kwargs: pytest.fail("deferred company extension must not calculate base price"),
    )

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=1,
        new_checkout_date=new_checkout,
        client_version=original_version,
        pricing_mode="current_rate",
        payment_action="company_account",
    )

    assert result.success is True
    assert result.extension_amount == Decimal("0.00")
    assert result.transaction is None
    assert result.payment_link is None
    assert reservation.status == ReservationStatusEnum.CHECKED_IN
    assert reservation.check_out_date == new_checkout
    assert (
        reservation.total_amount,
        reservation.subtotal_amount,
        reservation.net_amount,
    ) == original_amounts
    assert reservation.settlement_status == "deferred"
    assert reservation.settlement_due_date == new_checkout + timedelta(days=14)
    assert reservation.amount_paid == Decimal("0.00")
    assert reservation.company_extension_request_pending is False
    assert reservation.company_extension_request_note == "La empresa solicitó una extensión"
    assert reservation.pricing_snapshot == original_snapshot
    assert "last_extension_amount" not in (reservation.pricing_snapshot or "")
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(PaymentLink).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(CashMovement).filter_by(reservation_id=reservation.id).count() == 0

def test_company_account_extension_rejects_payment_payload_and_average_pricing():
    with pytest.raises(ValidationError, match="no admite datos de cobro"):
        ReservationExtensionRequest(
            new_checkout_date=date.today() + timedelta(days=1),
            client_version=0,
            payment_action="company_account",
            payment_link={
                "reservation_id": 1,
                "requested_amount": "10.00",
                "recipient_email": "guest@example.com",
            },
        )
    with pytest.raises(ValidationError, match="usa la tarifa vigente"):
        ReservationExtensionRequest(
            new_checkout_date=date.today() + timedelta(days=1),
            client_version=0,
            pricing_mode="original_average",
            payment_action="company_account",
        )


def test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    company = _deferred_company(db)
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    original_checkout = reservation.check_out_date
    original_total = reservation.total_amount
    monkeypatch.setattr(
        reservation_operations_service,
        "resolve_extension_conflict",
        lambda *args, **kwargs: {"resolved": False, "conflicts": [{"reason": "occupied"}], "actions": []},
    )

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=1,
        new_checkout_date=original_checkout + timedelta(days=1),
        client_version=reservation.version,
        pricing_mode="current_rate",
        payment_action="company_account",
    )

    assert result.success is False
    assert reservation.check_out_date == original_checkout
    assert reservation.total_amount == original_total
    assert reservation.company_extension_request_pending is True
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0


def test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    check_in = date.today() + timedelta(days=10)
    tourist = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[0].id,
            check_in_date=check_in,
            check_out_date=check_in + timedelta(days=2),
        ),
        hotel_id=1,
    )
    tourist.status = ReservationStatusEnum.CHECKED_IN
    with pytest.raises(ReservationOperationsError, match="reservas de empresa"):
        extend_reservation_stay(
            db,
            reservation=tourist,
            hotel_id=1,
            new_checkout_date=tourist.check_out_date + timedelta(days=1),
            client_version=tourist.version,
            pricing_mode="current_rate",
            payment_action="company_account",
        )

    disabled_company = _deferred_company(db, deferred_days=10)
    disabled_company.payment_deferred = False
    disabled_reservation = _company_reservation(
        db, sample_guest, sample_rooms, sample_categories, disabled_company, start_offset=20
    )
    with pytest.raises(ReservationOperationsError, match="cuenta diferida"):
        extend_reservation_stay(
            db,
            reservation=disabled_reservation,
            hotel_id=1,
            new_checkout_date=disabled_reservation.check_out_date + timedelta(days=1),
            client_version=disabled_reservation.version,
            pricing_mode="current_rate",
            payment_action="company_account",
        )

    db.add(HotelConfiguration(id=2, hotel_name="Other hotel", subscription_active=True))
    db.flush()
    foreign_company = _deferred_company(db, hotel_id=2, deferred_days=10)
    tenant_reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=sample_guest.id,
            category_id=sample_categories[0].id,
            room_id=sample_rooms[1].id,
            check_in_date=check_in + timedelta(days=30),
            check_out_date=check_in + timedelta(days=32),
        ),
        hotel_id=1,
    )
    tenant_reservation.status = ReservationStatusEnum.CHECKED_IN
    # Simulate a legacy/corrupt cross-tenant link without flushing it through
    # the composite hotel/company foreign key.
    tenant_reservation.company_id = foreign_company.id
    with pytest.raises(ReservationOperationsError, match="cuenta diferida"):
        extend_reservation_stay(
            db,
            reservation=tenant_reservation,
            hotel_id=1,
            new_checkout_date=tenant_reservation.check_out_date + timedelta(days=1),
            client_version=tenant_reservation.version,
            pricing_mode="current_rate",
            payment_action="company_account",
        )


@pytest.mark.parametrize("payment_action", ["immediate_payment", "payment_link"])
def test_deferred_company_extension_cannot_collect_base_rate_in_pms(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, payment_action
):
    company = _deferred_company(db, base_price=Decimal("150.00"))
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    original = {
        "checkout": reservation.check_out_date,
        "amounts": (reservation.total_amount, reservation.subtotal_amount, reservation.net_amount),
        "settlement": reservation.settlement_status,
        "snapshot": reservation.pricing_snapshot,
        "version": reservation.version,
        "request_pending": reservation.company_extension_request_pending,
    }

    with pytest.raises(ReservationOperationsError, match="registrarse fuera del PMS"):
        extend_reservation_stay(
            db,
            reservation=reservation,
            hotel_id=1,
            new_checkout_date=reservation.check_out_date + timedelta(days=1),
            client_version=reservation.version,
            pricing_mode="current_rate",
            payment_action=payment_action,
        )

    assert reservation.check_out_date == original["checkout"]
    assert (reservation.total_amount, reservation.subtotal_amount, reservation.net_amount) == original["amounts"]
    assert reservation.settlement_status == original["settlement"]
    assert reservation.pricing_snapshot == original["snapshot"]
    assert reservation.version == original["version"]
    assert reservation.company_extension_request_pending == original["request_pending"]
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(PaymentLink).filter_by(reservation_id=reservation.id).count() == 0


@pytest.mark.parametrize(
    ("settlement_status", "company_payment_deferred"),
    [("deferred", False), ("not_applicable", True)],
)
def test_extension_route_checks_company_permission_and_conditional_payment_permissions(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch,
    settlement_status, company_payment_deferred,
):
    company = _deferred_company(db, deferred_days=14, base_price=Decimal("150.00"))
    company.payment_deferred = company_payment_deferred
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    reservation.settlement_status = settlement_status
    db.flush()
    context = AuthContext(hotel_id=1, user_id=20, user_role="owner", is_verified=True, permissions=set())
    path = f"/api/reservations/{reservation.id}/extend"
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("testclient", 123),
            "server": ("testserver", 80),
        }
    )
    required_checks = []
    denied_permission = PERMISSION_COMPANY_MANAGE

    def all_permissions_factory(*permission_codes):
        def check_all(_request, _db, _context):
            required_checks.extend(permission_codes)
            if denied_permission in permission_codes:
                raise HTTPException(status_code=403, detail="No tenes permisos para esta accion")

        return check_all

    monkeypatch.setattr(reservations_api, "require_all_permissions", all_permissions_factory)
    original_checkout = reservation.check_out_date
    original_total = reservation.total_amount
    original_version = reservation.version
    original_settlement = reservation.settlement_status

    with pytest.raises(HTTPException) as company_error:
        reservations_api.extend_stay(
            reservation_id=reservation.id,
            payload=ReservationExtensionRequest(
                new_checkout_date=original_checkout + timedelta(days=1),
                client_version=reservation.version,
                pricing_mode="current_rate",
                payment_action="payment_link",
                payment_link={
                    "reservation_id": reservation.id,
                    "requested_amount": "1000.00",
                    "recipient_email": "guest@example.com",
                },
            ),
            background_tasks=BackgroundTasks(),
            request=request,
            db=db,
            context=context,
        )
    assert company_error.value.status_code == 403
    assert required_checks == [PERMISSION_COMPANY_MANAGE]
    assert reservation.check_out_date == original_checkout
    assert reservation.total_amount == original_total
    assert reservation.version == original_version
    assert reservation.settlement_status == original_settlement
    assert reservation.company_extension_request_pending is True
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(PaymentLink).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(CashMovement).filter_by(reservation_id=reservation.id).count() == 0

    denied_permission = PERMISSION_CASH_OPERATE
    required_checks.clear()
    with pytest.raises(HTTPException) as cash_error:
        reservations_api.extend_stay(
            reservation_id=reservation.id,
            payload=ReservationExtensionRequest(
                new_checkout_date=original_checkout + timedelta(days=1),
                client_version=reservation.version,
                pricing_mode="current_rate",
                payment_action="payment_link",
                payment_link={
                    "reservation_id": reservation.id,
                    "requested_amount": "1000.00",
                    "recipient_email": "guest@example.com",
                },
            ),
            background_tasks=BackgroundTasks(),
            request=request,
            db=db,
            context=context,
        )
    assert cash_error.value.status_code == 403
    assert required_checks == [
        PERMISSION_COMPANY_MANAGE,
        PERMISSION_RESERVATION_CHARGE,
        PERMISSION_CASH_OPERATE,
    ]
    assert reservation.check_out_date == original_checkout
    assert reservation.total_amount == original_total
    assert reservation.version == original_version
    assert reservation.settlement_status == original_settlement
    assert reservation.company_extension_request_pending is True
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(PaymentLink).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(CashMovement).filter_by(reservation_id=reservation.id).count() == 0


def test_deferred_company_payment_api_rejects_base_balance_without_writes(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company = _deferred_company(db)
    company.payment_deferred = False
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    reservation.settlement_status = "deferred"
    assert reservation.settlement_status == "deferred"
    original_paid = reservation.amount_paid
    original_total = reservation.total_amount
    original_version = reservation.version
    original_status = reservation.status
    request = Request({"type": "http", "method": "POST", "headers": []})
    context = AuthContext(hotel_id=1, user_id=20, user_role="owner", is_verified=True, permissions=set())
    payment = PaymentRequest(
        reservation_id=reservation.id,
        amount=25.00,
        payment_method=PaymentMethodEnum.CASH,
        transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
    )

    with pytest.raises(HTTPException) as error:
        payments_api.make_payment(
            data=payment,
            request=request,
            idempotency_key="deferred-base-001",
            db=db,
            context=context,
        )

    assert error.value.status_code == 400
    assert "adicionales por noche seleccionados" in error.value.detail
    assert reservation.amount_paid == original_paid
    assert reservation.total_amount == original_total
    assert reservation.version == original_version
    assert reservation.status == original_status
    assert reservation.settlement_status == "deferred"
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(CashMovement).filter_by(reservation_id=reservation.id).count() == 0


@pytest.mark.parametrize(
    ("settlement_status", "company_payment_deferred"),
    [("deferred", False), ("not_applicable", True)],
)
def test_payment_service_rejects_base_balance_when_either_company_deferred_flag_is_set(
    db, sample_guest, sample_rooms, sample_categories, hotel_config,
    settlement_status, company_payment_deferred,
):
    company = _deferred_company(db)
    company.payment_deferred = company_payment_deferred
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    reservation.settlement_status = settlement_status
    original_total = reservation.total_amount
    original_paid = reservation.amount_paid

    with pytest.raises(PaymentError, match="se registra fuera del PMS"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=25.00,
                payment_method=PaymentMethodEnum.CASH,
                transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
            ),
            hotel_id=1,
            idempotency_key="deferred-service-001",
        )

    assert reservation.total_amount == original_total
    assert reservation.amount_paid == original_paid
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0
    assert db.query(CashMovement).filter_by(reservation_id=reservation.id).count() == 0


def test_deferred_company_selected_nightly_extra_remains_collectible(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    hotel_config.enable_bank_transfer = True
    company = _deferred_company(db, nightly_extra=Decimal("75.00"))
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    summary = add_company_night_charges(
        db,
        hotel_id=1,
        reservation_id=reservation.id,
        stay_dates=[reservation.check_in_date],
        actor_user_id=None,
    )
    charge = summary.charges[0]

    with pytest.raises(PaymentError, match="importe debe coincidir con las noches seleccionadas"):
        process_payment(
            db,
            PaymentRequest(
                reservation_id=reservation.id,
                amount=float(charge.amount + Decimal("0.01")),
                payment_method=PaymentMethodEnum.BANK_TRANSFER,
                transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
                manual_reference="transfer-extra-wrong-001",
                company_night_charge_ids=[charge.id],
            ),
            hotel_id=1,
            idempotency_key="night-charge-wrong-001",
            manual_confirmation=True,
        )

    assert reservation.amount_paid == Decimal("0.00")
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 0

    transaction = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=float(charge.amount),
            payment_method=PaymentMethodEnum.BANK_TRANSFER,
            transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
            manual_reference="transfer-extra-001",
            company_night_charge_ids=[charge.id],
        ),
        hotel_id=1,
        idempotency_key="night-charge-001",
        manual_confirmation=True,
    )

    db.flush()
    assert transaction.status == TransactionStatusEnum.COMPLETED
    assert transaction.amount == charge.amount
    assert reservation.amount_paid == charge.amount
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 1


def test_valid_refund_of_payment_collected_before_company_became_deferred(
    db, sample_guest, sample_rooms, sample_categories, hotel_config, monkeypatch
):
    from app.services import cash_register_service

    monkeypatch.setattr(cash_register_service, "require_open_session_for_currency", lambda *args, **kwargs: None)
    monkeypatch.setattr(cash_register_service, "record_cash_payment_movement", lambda *args, **kwargs: None)
    company = _deferred_company(db)
    company.payment_deferred = False
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    reservation.total_amount = Decimal("100.00")
    reservation.amount_paid = Decimal("0.00")
    reservation.settlement_status = "not_applicable"
    db.flush()

    original_payment = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=100.00,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.BALANCE_PAYMENT,
        ),
        hotel_id=1,
        idempotency_key="prior-payment-001",
    )
    assert original_payment.status == TransactionStatusEnum.COMPLETED

    company.payment_deferred = True
    reservation.settlement_status = "deferred"
    db.flush()
    refund = process_payment(
        db,
        PaymentRequest(
            reservation_id=reservation.id,
            amount=100.00,
            payment_method=PaymentMethodEnum.CASH,
            transaction_type=TransactionTypeEnum.REFUND,
            refund_of_transaction_id=original_payment.id,
            refund_reason="Devolución aprobada",
        ),
        hotel_id=1,
        idempotency_key="refund-payment-001",
    )

    assert refund.status == TransactionStatusEnum.COMPLETED
    assert refund.transaction_type == TransactionTypeEnum.REFUND
    assert reservation.amount_paid == Decimal("0.00")
    assert db.query(Transaction).filter_by(reservation_id=reservation.id).count() == 2


def test_non_deferred_company_extension_still_creates_payment_link(
    db, sample_guest, sample_rooms, sample_categories, hotel_config
):
    company = Company(
        hotel_id=1,
        legal_name="UOCRA Standard SA",
        display_name="UOCRA Standard",
        payment_deferred=False,
    )
    db.add(company)
    db.flush()
    reservation = _company_reservation(db, sample_guest, sample_rooms, sample_categories, company)
    new_checkout = reservation.check_out_date + timedelta(days=1)

    result = extend_reservation_stay(
        db,
        reservation=reservation,
        hotel_id=1,
        new_checkout_date=new_checkout,
        client_version=reservation.version,
        pricing_mode="current_rate",
        payment_action="payment_link",
        payment_link=PaymentLinkCreate(
            reservation_id=reservation.id,
            requested_amount=Decimal("100.00"),
            recipient_email="guest@example.com",
        ),
    )

    assert result.success is True
    assert result.transaction is None
    assert result.payment_link is not None
    assert result.payment_link.reservation_id == reservation.id
    assert reservation.check_out_date == new_checkout
    assert reservation.settlement_status != "deferred"
