"""
D5 (Via D): GET /api/stock/consumption-report -- per-item stock consumption
(out + adjustment_out) for a period, plus the same-length period immediately
before for a variation %.

Service-level coverage (aggregation math) plus API-level coverage
(permission gating and tenant isolation), following the same harness pattern
as tests/test_laundry_vendor_api.py.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.stock import StockMovement
from app.services.stock_service import StockError, consumption_report, create_stock_item


def _seed_hotels(db):
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
        ]
    )
    db.flush()


def _movement(db, *, hotel_id, item_id, movement_type, quantity, created_at):
    movement = StockMovement(
        hotel_id=hotel_id,
        item_id=item_id,
        location_id=None,
        movement_type=movement_type,
        quantity=Decimal(quantity),
        created_at=created_at,
    )
    db.add(movement)
    db.flush()
    return movement


# --- Service-level: aggregation and variation math ---------------------


def test_consumption_report_totals_and_variation_between_periods(db):
    _seed_hotels(db)
    item = create_stock_item(
        db, hotel_id=1, name="Papel higienico", sku=None, unit="paquete", min_quantity=None, active=True
    )
    db.flush()

    current_from = date(2026, 7, 20)
    current_to = date(2026, 7, 26)

    # Previous week (immediately before, same length): 2 units consumed.
    _movement(
        db, hotel_id=1, item_id=item.id, movement_type="out", quantity="2.00",
        created_at=datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc),
    )
    # Current week: 4 units consumed -- doubled with, per the plan's example,
    # flat occupancy elsewhere -- this is exactly the anomaly signal D5 exists for.
    _movement(
        db, hotel_id=1, item_id=item.id, movement_type="out", quantity="4.00",
        created_at=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )
    db.commit()

    report = consumption_report(db, hotel_id=1, date_from=current_from, date_to=current_to, group_by="week")

    assert report["date_from"] == current_from
    assert report["date_to"] == current_to
    # Same length (7 days), immediately before -- 2026-07-13..2026-07-19.
    assert report["previous_date_from"] == date(2026, 7, 13)
    assert report["previous_date_to"] == date(2026, 7, 19)
    assert len(report["items"]) == 1
    entry = report["items"][0]
    assert entry["stock_item_id"] == item.id
    assert entry["stock_item_name"] == "Papel higienico"
    assert entry["current_quantity"] == Decimal("4.00")
    assert entry["previous_quantity"] == Decimal("2.00")
    assert entry["variation_pct"] == Decimal("100.0")


def test_consumption_report_only_counts_out_and_adjustment_out(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Jabon", sku=None, unit="unidad", min_quantity=None, active=True)
    db.flush()

    within = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
    _movement(db, hotel_id=1, item_id=item.id, movement_type="in", quantity="50.00", created_at=within)
    _movement(db, hotel_id=1, item_id=item.id, movement_type="adjustment", quantity="10.00", created_at=within)
    _movement(db, hotel_id=1, item_id=item.id, movement_type="out", quantity="3.00", created_at=within)
    _movement(db, hotel_id=1, item_id=item.id, movement_type="adjustment_out", quantity="1.00", created_at=within)
    db.commit()

    report = consumption_report(
        db, hotel_id=1, date_from=date(2026, 7, 20), date_to=date(2026, 7, 26), group_by="week"
    )
    entry = report["items"][0]
    # 3 (out) + 1 (adjustment_out) = 4 -- the 50 (in) and 10 (adjustment) that
    # raised stock must not count as "consumption".
    assert entry["current_quantity"] == Decimal("4.00")


def test_consumption_report_is_hotel_scoped(db):
    _seed_hotels(db)
    item_h1 = create_stock_item(
        db, hotel_id=1, name="Bolsas chicas", sku=None, unit="paquete", min_quantity=None, active=True
    )
    item_h2 = create_stock_item(
        db, hotel_id=2, name="Bolsas chicas", sku=None, unit="paquete", min_quantity=None, active=True
    )
    db.flush()

    within = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
    _movement(db, hotel_id=1, item_id=item_h1.id, movement_type="out", quantity="5.00", created_at=within)
    _movement(db, hotel_id=2, item_id=item_h2.id, movement_type="out", quantity="9.00", created_at=within)
    db.commit()

    report_h1 = consumption_report(
        db, hotel_id=1, date_from=date(2026, 7, 20), date_to=date(2026, 7, 26), group_by="week"
    )
    assert len(report_h1["items"]) == 1
    assert report_h1["items"][0]["current_quantity"] == Decimal("5.00")

    report_h2 = consumption_report(
        db, hotel_id=2, date_from=date(2026, 7, 20), date_to=date(2026, 7, 26), group_by="week"
    )
    assert len(report_h2["items"]) == 1
    assert report_h2["items"][0]["current_quantity"] == Decimal("9.00")


def test_consumption_report_variation_is_none_without_a_previous_baseline(db):
    _seed_hotels(db)
    item = create_stock_item(db, hotel_id=1, name="Colchas", sku=None, unit="unidad", min_quantity=None, active=True)
    db.flush()
    _movement(
        db, hotel_id=1, item_id=item.id, movement_type="out", quantity="1.00",
        created_at=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    )
    db.commit()

    report = consumption_report(
        db, hotel_id=1, date_from=date(2026, 7, 20), date_to=date(2026, 7, 26), group_by="week"
    )
    entry = report["items"][0]
    assert entry["previous_quantity"] == Decimal("0.00")
    assert entry["variation_pct"] is None


def test_consumption_report_rejects_invalid_group_by(db):
    _seed_hotels(db)
    with pytest.raises(StockError):
        consumption_report(db, hotel_id=1, date_from=date(2026, 7, 20), date_to=date(2026, 7, 26), group_by="day")


def test_consumption_report_rejects_inverted_range(db):
    _seed_hotels(db)
    with pytest.raises(StockError):
        consumption_report(db, hotel_id=1, date_from=date(2026, 7, 26), date_to=date(2026, 7, 20), group_by="week")


# --- API-level: permission gating and tenant isolation ------------------


def _override_auth(hotel_id: int, role: str, user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    _seed_hotels(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _teardown(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_consumption_report_api_requires_stock_permission():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        item = create_stock_item(db, hotel_id=1, name="Toallas", sku=None, unit="unidad", min_quantity=None, active=True)
        db.commit()
        _movement(
            db, hotel_id=1, item_id=item.id, movement_type="out", quantity="2.00",
            created_at=datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
        )
        db.commit()

        owner_response = client.get(
            "/api/stock/consumption-report",
            params={"date_from": "2026-07-20", "date_to": "2026-07-26", "group_by": "week"},
        )
        assert owner_response.status_code == 200
        assert owner_response.json()["items"][0]["current_quantity"] == "2.00"

        # housekeeping has laundry:operate_remitos but not stock:operate
        # (same reasoning as the other stock reads in app/api/stock.py).
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping")
        denied = client.get(
            "/api/stock/consumption-report",
            params={"date_from": "2026-07-20", "date_to": "2026-07-26", "group_by": "week"},
        )
        assert denied.status_code == 403
    finally:
        _teardown(db, engine)


def test_consumption_report_api_is_hotel_isolated():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        item_h1 = create_stock_item(db, hotel_id=1, name="Jabon H1", sku=None, unit="unidad", min_quantity=None, active=True)
        item_h2 = create_stock_item(db, hotel_id=2, name="Jabon H2", sku=None, unit="unidad", min_quantity=None, active=True)
        db.commit()
        within = datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc)
        _movement(db, hotel_id=1, item_id=item_h1.id, movement_type="out", quantity="3.00", created_at=within)
        _movement(db, hotel_id=2, item_id=item_h2.id, movement_type="out", quantity="7.00", created_at=within)
        db.commit()

        response = client.get(
            "/api/stock/consumption-report",
            params={"date_from": "2026-07-20", "date_to": "2026-07-26", "group_by": "week"},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["stock_item_name"] == "Jabon H1"
        assert body["items"][0]["current_quantity"] == "3.00"
    finally:
        _teardown(db, engine)
