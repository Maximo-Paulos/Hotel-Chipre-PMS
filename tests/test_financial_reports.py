"""
Regression coverage for app/api/reports.py's financial endpoints
(/api/reports/daily, /api/reports/revenue): both accumulated
Transaction.amount (Numeric/Decimal) into a `float` starting value, which
raises `TypeError: unsupported operand type(s) for +=: 'float' and
'decimal.Decimal'` on the very first completed transaction -- a 500 for any
hotel with real payment data. Neither endpoint had any prior test coverage.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import PaymentMethodEnum, Transaction, TransactionStatusEnum
from app.models.user import User


@pytest.fixture
def reports_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, hotel_name="Hotel Uno", subscription_active=True),
            User(
                id=1,
                email="owner@test.com",
                password_hash="test-hash",
                is_active=True,
                is_verified=True,
            ),
        ]
    )
    db.flush()

    # Transaction.reservation_id is a composite (hotel_id, reservation_id) FK
    # (see app/models/transaction.py) -- needs a real reservation to point to.
    category = RoomCategory(
        hotel_id=1, name="Standard", code="STD", base_price_per_night=Decimal("100.00"), max_occupancy=2
    )
    db.add(category)
    db.flush()
    room = Room(hotel_id=1, category_id=category.id, room_number="101", floor=1, status=RoomStatusEnum.AVAILABLE)
    db.add(room)
    db.flush()
    guest = Guest(hotel_id=1, first_name="Test", last_name="Guest", document_number="DOC1", terms_accepted=True)
    db.add(guest)
    db.flush()
    reservation = Reservation(
        hotel_id=1,
        guest_id=guest.id,
        category_id=category.id,
        room_id=room.id,
        confirmation_code="RES-FIN-1",
        check_in_date=date.today(),
        check_out_date=date.today() + timedelta(days=1),
        total_amount=Decimal("15000.50"),
        amount_paid=Decimal("0.00"),
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
    )
    db.add(reservation)
    db.flush()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=1,
            user_email="owner@test.com",
            user_role="owner",
            is_verified=True,
            permissions=set(),
        )

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = override_auth
    client = TestClient(fastapi_app)
    try:
        yield client, db, reservation.id
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def _make_completed_transaction(db, *, reservation_id: int, amount: str) -> Transaction:
    transaction = Transaction(
        hotel_id=1,
        reservation_id=reservation_id,
        amount=Decimal(amount),
        currency="ARS",
        transaction_type="deposit",
        payment_method=PaymentMethodEnum.CASH,
        status=TransactionStatusEnum.COMPLETED,
        created_at=datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_daily_report_totals_a_completed_transaction_without_crashing(reports_client):
    client, db, reservation_id = reports_client
    _make_completed_transaction(db, reservation_id=reservation_id, amount="15000.50")

    report_date = datetime.now(timezone.utc).date()
    response = client.get("/api/reports/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200
    assert response.json()["revenue"]["total"] == 15000.5


def test_revenue_report_totals_multiple_completed_transactions_without_crashing(reports_client):
    client, db, reservation_id = reports_client
    _make_completed_transaction(db, reservation_id=reservation_id, amount="10000.00")
    _make_completed_transaction(db, reservation_id=reservation_id, amount="5000.25")

    report_date = datetime.now(timezone.utc).date()
    response = client.get(
        "/api/reports/revenue",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.json()["collected"]["total"] == 15000.25


def test_occupancy_report_uses_fixed_query_count_for_date_range(reports_client):
    _client, db, _reservation_id = reports_client
    start_date = date.today()
    end_date = start_date + timedelta(days=6)
    query_count = [0]

    from app.api.reports import occupancy_report
    from app.dependencies.auth import AuthContext

    def count_query(*_args, **_kwargs):
        query_count[0] += 1

    event.listen(db.get_bind(), "before_cursor_execute", count_query)
    try:
        payload = occupancy_report(
            start_date=start_date,
            end_date=end_date,
            db=db,
            context=AuthContext(
                hotel_id=1,
                user_id=1,
                user_email="owner@test.com",
                user_role="owner",
                is_verified=True,
                permissions=set(),
            ),
        )
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_query)

    assert payload["daily"][0]["occupied"] == 1
    assert payload["daily"][1]["occupied"] == 0
    assert query_count[0] <= 3, f"occupancy range should use fixed query count, got {query_count[0]}"
