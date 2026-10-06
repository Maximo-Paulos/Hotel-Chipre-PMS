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
from app.models.company import Company
from app.models.guest import Guest
from app.models.hotel_config import HotelConfiguration
from app.models.reservation import (
    Reservation,
    ReservationChannelCodeEnum,
    ReservationSourceEnum,
    ReservationStatusEnum,
)
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.transaction import (
    PaymentMethodEnum,
    Transaction,
    TransactionStatusEnum,
    TransactionTypeEnum,
)
from app.models.user import User
from app.services.timezones import hotel_today


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


def _make_completed_transaction(
    db,
    *,
    reservation_id: int,
    amount: str,
    currency: str = "ARS",
    payment_method: PaymentMethodEnum = PaymentMethodEnum.CASH,
    transaction_type: TransactionTypeEnum = TransactionTypeEnum.DEPOSIT,
    processed_at: datetime | None = None,
) -> Transaction:
    amount_value = Decimal(amount)
    transaction = Transaction(
        hotel_id=1,
        reservation_id=reservation_id,
        amount=amount_value,
        currency=currency,
        tender_amount=amount_value,
        tender_currency=currency,
        gross_amount=amount_value,
        transaction_type=transaction_type,
        payment_method=payment_method,
        status=TransactionStatusEnum.COMPLETED,
        created_at=processed_at or datetime.now(timezone.utc),
        processed_at=processed_at or datetime.now(timezone.utc),
    )
    db.add(transaction)
    db.flush()
    return transaction


def test_daily_report_totals_a_completed_transaction_without_crashing(reports_client):
    client, db, reservation_id = reports_client
    _make_completed_transaction(db, reservation_id=reservation_id, amount="15000.50")

    report_date = hotel_today(db, 1)
    response = client.get("/api/reports/daily", params={"report_date": report_date.isoformat()})

    assert response.status_code == 200
    assert response.json()["revenue"]["total"] == 15000.5


def test_revenue_report_totals_multiple_completed_transactions_without_crashing(reports_client):
    client, db, reservation_id = reports_client
    _make_completed_transaction(db, reservation_id=reservation_id, amount="10000.00")
    _make_completed_transaction(db, reservation_id=reservation_id, amount="5000.25")

    report_date = hotel_today(db, 1)
    response = client.get(
        "/api/reports/revenue",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["collected"]["total"] == "15000.25"
    assert payload["collected"]["by_method"] == {"cash": "15000.25"}
    assert list(payload["collected"]["by_day"].values()) == ["15000.25"]
    assert payload["expected"]["total"] == "15000.50"
    assert payload["expected"]["pending"] == "0.25"
    assert payload["expected"]["reservations_count"] == 1


def test_revenue_refunds_and_transaction_bounds_use_hotel_local_days(reports_client):
    client, db, reservation_id = reports_client
    hotel = db.get(HotelConfiguration, 1)
    hotel.hotel_timezone = "America/Argentina/Buenos_Aires"
    db.flush()

    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="10.00",
        processed_at=datetime(2026, 4, 1, 2, 59, 59, tzinfo=timezone.utc),
    )  # 2026-03-31 23:59:59 in the hotel.
    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="100.00",
        processed_at=datetime(2026, 4, 1, 3, 0, 0, tzinfo=timezone.utc),
    )  # 2026-04-01 00:00:00 in the hotel.
    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="30.00",
        transaction_type=TransactionTypeEnum.REFUND,
        processed_at=datetime(2026, 4, 2, 2, 59, 59, tzinfo=timezone.utc),
    )  # 2026-04-01 23:59:59 in the hotel.
    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="40.00",
        processed_at=datetime(2026, 4, 2, 3, 0, 0, tzinfo=timezone.utc),
    )  # 2026-04-02 00:00:00 in the hotel.

    response = client.get(
        "/api/reports/revenue",
        params={"start_date": "2026-04-01", "end_date": "2026-04-01"},
    )

    assert response.status_code == 200, response.text
    collected = response.json()["collected"]
    assert collected["by_currency"] == [
        {
            "currency_code": "ARS",
            "gross_collected": "100.00",
            "refunds": "30.00",
            "net_collected": "70.00",
            "transaction_count": 2,
        }
    ]
    assert collected["by_day"] == {"2026-04-01": "70.00"}


def test_booked_value_includes_and_prorates_stays_overlapping_the_report_window(reports_client):
    client, db, base_reservation_id = reports_client
    base_reservation = db.get(Reservation, base_reservation_id)
    _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-FIN-MONTH-CROSSING",
        check_in_date=date(2026, 4, 30),
        amount="300.01",
        currency="ARS",
    )
    crossing = db.query(Reservation).filter_by(confirmation_code="RES-FIN-MONTH-CROSSING").one()
    crossing.check_out_date = date(2026, 5, 3)
    db.flush()

    response = client.get(
        "/api/reports/revenue",
        params={"start_date": "2026-05-01", "end_date": "2026-05-01"},
    )

    assert response.status_code == 200, response.text
    booked = response.json()["booked_value"]["by_currency"]
    assert booked == [
        {
            "currency_code": "ARS",
            "amount": "100.00",
            "reservation_count": 1,
            "booked_night_count": 1,
        }
    ]


def test_booked_value_endpoint_matches_full_report_with_bounded_query_count(reports_client):
    client, db, base_reservation_id = reports_client
    base_reservation = db.get(Reservation, base_reservation_id)
    company = Company(
        hotel_id=1,
        legal_name="Deferred Company",
        display_name="Deferred Company",
        payment_deferred=True,
    )
    db.add(company)
    db.flush()

    crossing = _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-BOOKED-CROSSING",
        check_in_date=date(2026, 4, 30),
        amount="300.01",
        currency="ARS",
    )
    crossing.check_out_date = date(2026, 5, 3)
    _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-BOOKED-USD",
        check_in_date=date(2026, 5, 1),
        amount="80.00",
        currency="USD",
    )
    deferred = _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-BOOKED-DEFERRED",
        check_in_date=date(2026, 5, 1),
        amount="900.00",
        currency="ARS",
    )
    deferred.company_id = company.id
    cancelled = _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-BOOKED-CANCELLED",
        check_in_date=date(2026, 5, 1),
        amount="500.00",
        currency="ARS",
    )
    cancelled.status = ReservationStatusEnum.CANCELLED
    db.flush()

    statements = []

    def capture_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = db.get_bind()
    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        narrow_response = client.get(
            "/api/reports/booked-value",
            params={"start_date": "2026-05-01", "end_date": "2026-05-01"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert narrow_response.status_code == 200, narrow_response.text
    booked_value_selects = [
        statement.lower()
        for statement in statements
        if " from reservations" in statement.lower() or " from companies" in statement.lower()
    ]
    assert len(booked_value_selects) <= 2
    assert narrow_response.json() == {
        "total": None,
        "currency_code": None,
        "by_currency": [
            {
                "currency_code": "ARS",
                "amount": "100.00",
                "reservation_count": 1,
                "booked_night_count": 1,
            },
            {
                "currency_code": "USD",
                "amount": "80.00",
                "reservation_count": 1,
                "booked_night_count": 1,
            },
        ],
    }

    full_statements = []

    def capture_full_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            full_statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture_full_select)
    try:
        full_response = client.get(
            "/api/reports/revenue",
            params={"start_date": "2026-05-01", "end_date": "2026-05-01"},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture_full_select)
    assert full_response.status_code == 200, full_response.text
    assert narrow_response.json() == full_response.json()["booked_value"]
    assert len(statements) < len(full_statements)


def _reservation_for_report(
    db,
    *,
    base_reservation: Reservation,
    confirmation_code: str,
    check_in_date: date,
    amount: str,
    currency: str,
    channel: ReservationChannelCodeEnum = ReservationChannelCodeEnum.OTHER_DIRECT,
    source: ReservationSourceEnum = ReservationSourceEnum.DIRECT,
) -> Reservation:
    reservation = Reservation(
        hotel_id=1,
        guest_id=base_reservation.guest_id,
        category_id=base_reservation.category_id,
        room_id=None,
        confirmation_code=confirmation_code,
        check_in_date=check_in_date,
        check_out_date=check_in_date + timedelta(days=1),
        total_amount=Decimal(amount),
        amount_paid=Decimal("0.00"),
        currency_code=currency,
        status=ReservationStatusEnum.PENDING,
        num_adults=1,
        channel_code=channel,
        source=source,
    )
    db.add(reservation)
    db.flush()
    return reservation


def test_revenue_keeps_currencies_separate_and_uses_reportable_channel(reports_client):
    client, db, reservation_id = reports_client
    base_reservation = db.get(Reservation, reservation_id)
    base_reservation.channel_code = ReservationChannelCodeEnum.BOOKING
    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="100.00",
        currency="ARS",
    )
    usd_reservation = _reservation_for_report(
        db,
        base_reservation=base_reservation,
        confirmation_code="RES-FIN-USD",
        check_in_date=date.today(),
        amount="50.00",
        currency="USD",
        channel=ReservationChannelCodeEnum.EXPEDIA,
        source=ReservationSourceEnum.EXPEDIA,
    )
    _make_completed_transaction(
        db,
        reservation_id=usd_reservation.id,
        amount="50.00",
        currency="USD",
        payment_method=PaymentMethodEnum.BANK_TRANSFER,
    )

    report_date = hotel_today(db, 1)
    response = client.get(
        "/api/reports/revenue",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["collected"]["total"] is None
    assert payload["collected"]["currency_code"] is None
    assert {
        (row["currency_code"], row["net_collected"])
        for row in payload["collected"]["by_currency"]
    } == {("ARS", "100.00"), ("USD", "50.00")}
    assert {
        (row["channel_code"], row["currency_code"])
        for row in payload["collected"]["by_channel"]
    } == {("booking_manual", "ARS"), ("expedia_manual", "USD")}


def test_confirmed_external_ota_amount_is_not_reported_as_pms_collection(reports_client):
    client, db, reservation_id = reports_client
    reservation = db.get(Reservation, reservation_id)
    reservation.source = ReservationSourceEnum.EXPEDIA
    reservation.channel_code = ReservationChannelCodeEnum.EXPEDIA
    reservation.external_id = "OTA-TEST-1"
    reservation.external_paid_amount = Decimal("40.00")
    reservation.external_paid_confirmed = True
    reservation.external_paid_confirmed_at = datetime.now(timezone.utc)
    reservation.currency_code = "USD"
    report_date = hotel_today(db, 1)

    response = client.get(
        "/api/reports/revenue",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["collected"]["by_currency"] == []
    assert payload["external_ota_collected"]["by_channel"] == [
        {"channel_code": "expedia_manual", "currency_code": "USD", "amount": "40.00"}
    ]


def test_empty_collections_have_no_currency_or_synthetic_multicurrency_total(reports_client):
    client, db, reservation_id = reports_client
    db.get(Reservation, reservation_id).deleted_at = datetime.now(timezone.utc)
    db.flush()
    report_date = hotel_today(db, 1)

    response = client.get(
        "/api/reports/revenue",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    collected = response.json()["collected"]
    assert collected["currency_code"] is None
    assert collected["total"] == "0.00"
    assert collected["by_currency"] == []
    assert response.json()["booked_value"]["by_currency"] == []


def test_revenue_reports_current_receivables_by_currency_and_due_bucket(reports_client):
    client, db, reservation_id = reports_client
    today = date.today()
    overdue = db.get(Reservation, reservation_id)
    overdue.check_in_date = today - timedelta(days=1)
    overdue.check_out_date = today
    overdue.total_amount = Decimal("100.00")
    _make_completed_transaction(
        db,
        reservation_id=overdue.id,
        amount="20.00",
        processed_at=datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc),
    )
    check_in_today = _reservation_for_report(
        db,
        base_reservation=overdue,
        confirmation_code="RES-DUE-TODAY",
        check_in_date=today,
        amount="200.00",
        currency="USD",
    )
    future = _reservation_for_report(
        db,
        base_reservation=overdue,
        confirmation_code="RES-DUE-FUTURE",
        check_in_date=today + timedelta(days=2),
        amount="300.00",
        currency="USD",
    )
    db.flush()

    response = client.get(
        "/api/reports/revenue",
        params={"start_date": today.isoformat(), "end_date": today.isoformat()},
    )

    assert response.status_code == 200
    rows = {row["currency_code"]: row for row in response.json()["receivables"]["by_currency"]}
    assert rows["ARS"]["overdue"] == "80.00"
    assert rows["ARS"]["due_at_check_in"] == "0.00"
    assert rows["USD"]["due_at_check_in"] == "200.00"
    assert rows["USD"]["future"] == "300.00"
    assert rows["USD"]["total"] == "500.00"


def test_revenue_csv_groups_by_method_category_channel_and_currency(reports_client):
    client, db, reservation_id = reports_client
    reservation = db.get(Reservation, reservation_id)
    reservation.channel_code = ReservationChannelCodeEnum.BOOKING
    _make_completed_transaction(
        db,
        reservation_id=reservation_id,
        amount="100.00",
        currency="ARS",
        payment_method=PaymentMethodEnum.BANK_TRANSFER,
    )
    report_date = hotel_today(db, 1)

    response = client.get(
        "/api/reports/revenue/export.csv",
        params={"start_date": report_date.isoformat(), "end_date": report_date.isoformat()},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "cobro_en_hotel,bank_transfer,Standard,booking_manual,ARS,100.00,0.00,100.00,1" in response.text
    assert "Test Guest" not in response.text


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
