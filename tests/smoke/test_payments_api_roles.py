from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from tests.smoke.helpers import register_owner, seed_operational_reservation
from app.models.reservation import ReservationStatusEnum
from app.models.user import User
from app.dependencies.auth import AuthContext, get_auth_context
import app.main as main_module


def _receptionist_context(hotel_id: int, user_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email="receptionist-smoke@example.com",
            user_role="receptionist",
            is_verified=True,
        )

    return dependency


def _open_cash_session(engine, hotel_id: int) -> None:
    from app.services.cash_register_service import open_session

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as db:
        open_session(db, hotel_id=hotel_id, opened_by_user_id=None, opening_balance=Decimal("0"))
        db.commit()


def _create_receptionist_user(engine) -> int:
    # cash_movements.recorded_by_user_id is a real FK; a fake in-memory user id
    # (unbacked by a users row) trips the constraint on cash payments.
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with SessionLocal() as db:
        user = User(
            email="receptionist-smoke@example.com",
            password_hash="not-a-real-hash",
            is_active=True,
            is_verified=True,
            role="receptionist",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id


def test_receptionist_can_view_and_make_reservation_payments(client, engine):
    """POST /api/payments and GET /api/payments/summary/{id} only allowed
    owner/co_owner/manager (a role list never migrated to the permission
    matrix that already grants receptionist cash:operate and
    reservation:charge). The Reservations page "Pagos y balance" panel --
    reachable by receptionist since /reservas has no per-role gate -- calls
    both endpoints for every "Cobro parcial"/"Pago total"/"Seña" action, so
    front-desk staff got a permanently-loading summary and could not record
    any guest payment through the UI.
    """
    headers, hotel_id = register_owner(client, "payments-ops-owner@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.PENDING,
        total_amount=150.0,
        amount_paid=0.0,
    )
    _open_cash_session(engine, hotel_id)
    receptionist_user_id = _create_receptionist_user(engine)

    main_module.app.dependency_overrides[get_auth_context] = _receptionist_context(hotel_id, receptionist_user_id)
    try:
        summary = client.get(f"/api/payments/summary/{seeded['reservation_id']}")
        assert summary.status_code == 200, summary.text

        payment = client.post(
            "/api/payments",
            json={
                "reservation_id": seeded["reservation_id"],
                "amount": 150.0,
                "payment_method": "cash",
                "transaction_type": "full_payment",
            },
            headers={"Idempotency-Key": "qa-receptionist-full-payment-0001"},
        )
        assert payment.status_code == 201, payment.text
    finally:
        del main_module.app.dependency_overrides[get_auth_context]
