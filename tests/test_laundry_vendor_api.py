"""
API-level coverage for outsourced laundry vendors/remitos (D1) and the linen
item/location catalog that backs them (post-split): permission gating
(manage_vendors vs operate_remitos) and cross-hotel isolation, following the
same harness pattern as tests/test_permissions_api.py.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.services.linen_service import create_linen_item, create_location, register_movement


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
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
        ]
    )
    db.flush()

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


def test_owner_can_manage_vendors_and_receptionist_cannot():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        response = client.post("/api/laundry/vendors", json={"name": "Lavadero API"})
        assert response.status_code == 201
        vendor_id = response.json()["id"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        forbidden = client.post("/api/laundry/vendors", json={"name": "Lavadero denegado"})
        assert forbidden.status_code == 403

        item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unit", min_quantity=None, active=True)
        db.commit()

        forbidden_price = client.post(
            f"/api/laundry/vendors/{vendor_id}/prices",
            json={"linen_item_id": item.id, "unit_price": "100.00"},
        )
        assert forbidden_price.status_code == 403
    finally:
        _teardown(db, engine)


def test_owner_can_manage_linen_items_and_receptionist_cannot():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        created = client.post("/api/laundry/items", json={"name": "Sabanas", "unit": "unidad"})
        assert created.status_code == 201
        item_id = created.json()["id"]

        listed = client.get("/api/laundry/items")
        assert listed.status_code == 200
        assert item_id in [row["id"] for row in listed.json()]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        denied_create = client.post("/api/laundry/items", json={"name": "No deberia poder", "unit": "unidad"})
        assert denied_create.status_code == 403
        denied_delete = client.delete(f"/api/laundry/items/{item_id}")
        assert denied_delete.status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        deleted = client.delete(f"/api/laundry/items/{item_id}")
        assert deleted.status_code == 204
        listed_after = client.get("/api/laundry/items")
        assert item_id not in [row["id"] for row in listed_after.json()]
    finally:
        _teardown(db, engine)


def test_owner_can_register_a_linen_movement_and_load_an_opening_balance():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        item_id = client.post("/api/laundry/items", json={"name": "Sabanas", "unit": "unidad"}).json()["id"]
        location_id = client.post("/api/laundry/locations", json={"name": "Deposito casa"}).json()["id"]

        movement = client.post(
            "/api/laundry/movements",
            json={"linen_item_id": item_id, "location_id": location_id, "movement_type": "in", "quantity": "8.00"},
        )
        assert movement.status_code == 201

        current = client.get(f"/api/laundry/items/{item_id}/current", params={"location_id": location_id})
        assert current.status_code == 200
        assert Decimal(str(current.json()["quantity"])) == Decimal("8.00")

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        denied = client.post(
            "/api/laundry/movements",
            json={"linen_item_id": item_id, "location_id": location_id, "movement_type": "in", "quantity": "1.00"},
        )
        assert denied.status_code == 403
    finally:
        _teardown(db, engine)


def test_housekeeping_can_operate_remitos_but_not_manage_vendors():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=1)
        vendor_resp = client.post(
            "/api/laundry/vendors",
            json={
                "name": "Lavadero HK",
                "contact_phone": "+54 11 5555 0101",
                "contact_email": "private@laundry.example",
            },
        )
        vendor_id = vendor_resp.json()["id"]

        item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unit", min_quantity=None, active=True)
        house = create_location(db, hotel_id=1, name="Deposito casa")
        db.flush()
        register_movement(
            db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
            quantity=Decimal("10.00"), reason="opening balance", reservation_id=None, created_by_user_id=None,
        )
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "housekeeping", user_id=2)

        denied_vendor_create = client.post("/api/laundry/vendors", json={"name": "No deberia poder"})
        assert denied_vendor_create.status_code == 403

        vendors_read = client.get("/api/laundry/vendors")
        assert vendors_read.status_code == 200
        assert vendors_read.json()[0]["id"] == vendor_id
        assert vendors_read.json()[0]["contact_phone"] is None
        assert vendors_read.json()[0]["contact_email"] is None
        assert "private@laundry.example" not in vendors_read.text

        # D2 (now D: linen split): housekeeping has to pick a house
        # LinenLocation on the remito form, so GET /api/laundry/locations
        # must accept laundry:operate_remitos even without
        # laundry:manage_vendors -- see require_any_permission in
        # app/api/laundry_vendor.py.
        locations_read = client.get("/api/laundry/locations")
        assert locations_read.status_code == 200
        # The vendor's own auto-created LinenLocation ("Lavadero HK") is also
        # listed here -- listing itself is not remito-specific, only this
        # test's assertion cares that the house location is reachable too.
        assert house.id in [loc["id"] for loc in locations_read.json()]
        # Write endpoints on the same router stay manage_vendors-only.
        denied_location_create = client.post("/api/laundry/locations", json={"name": "No deberia poder"})
        assert denied_location_create.status_code == 403

        # Same reasoning for GET /api/laundry/items (choosing the remito
        # line's item).
        items_read = client.get("/api/laundry/items")
        assert items_read.status_code == 200
        assert item.id in [i["id"] for i in items_read.json()]
        denied_item_create = client.post("/api/laundry/items", json={"name": "No deberia poder", "unit": "unit"})
        assert denied_item_create.status_code == 403

        remito_payload = {
            "vendor_id": vendor_id,
            "direction": "outbound",
            "remito_number": "R-HK-1",
            "remito_date": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
            "house_location_id": house.id,
            "lines": [{"linen_item_id": item.id, "quantity": "4.00"}],
        }
        created = client.post("/api/laundry/remitos", json=remito_payload)
        assert created.status_code == 201
        body = created.json()
        assert body["remito"]["direction"] == "outbound"
        assert "No hay precio configurado" in body["warnings"][0]

        balance = client.get(f"/api/laundry/vendors/{vendor_id}/balance")
        assert balance.status_code == 200
        assert balance.json()[0]["quantity"] == "4.00"

        # Spend is a financial report gated by manage_vendors, not operate_remitos.
        spend_denied = client.get(f"/api/laundry/vendors/{vendor_id}/spend")
        assert spend_denied.status_code == 403

        # "limpio disponible en el hotel" narrows GET .../current by
        # location_id -- gated the same as the item/location lists above, so
        # housekeeping itself can already reach it (switch back to owner only
        # to keep this assertion about the numbers, not permissions). The 10
        # units moved in at the house dropped to 6 there (4 went "out" to the
        # vendor via the remito above), while the hotel-wide total (no
        # location_id) still shows the unmoved 10 -- a transfer nets to zero
        # hotel-wide.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=1)
        house_current = client.get(f"/api/laundry/items/{item.id}/current?location_id={house.id}")
        assert house_current.status_code == 200
        assert Decimal(str(house_current.json()["quantity"])) == Decimal("6.00")
        hotel_wide_current = client.get(f"/api/laundry/items/{item.id}/current")
        assert Decimal(str(hotel_wide_current.json()["quantity"])) == Decimal("10.00")
    finally:
        _teardown(db, engine)


def test_remito_rejects_insufficient_house_stock_via_api():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        vendor_id = client.post("/api/laundry/vendors", json={"name": "Lavadero Insuf"}).json()["id"]

        item = create_linen_item(db, hotel_id=1, name="Toallas", unit="unit", min_quantity=None, active=True)
        house = create_location(db, hotel_id=1, name="Deposito casa")
        db.flush()
        db.commit()

        response = client.post(
            "/api/laundry/remitos",
            json={
                "vendor_id": vendor_id,
                "direction": "outbound",
                "remito_number": "R-FAIL",
                "remito_date": datetime(2026, 7, 1, tzinfo=timezone.utc).isoformat(),
                "house_location_id": house.id,
                "lines": [{"linen_item_id": item.id, "quantity": "5.00"}],
            },
        )
        assert response.status_code == 400
        assert "Not enough" in response.json()["detail"]

        history = client.get("/api/laundry/remitos")
        assert history.json() == []
    finally:
        _teardown(db, engine)


def test_settlements_default_unpaid_and_can_be_marked_paid_with_notes():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        vendor_id = client.post("/api/laundry/vendors", json={"name": "Lavadero Liquidacion"}).json()["id"]

        item = create_linen_item(db, hotel_id=1, name="Sabanas", unit="unit", min_quantity=None, active=True)
        house = create_location(db, hotel_id=1, name="Deposito casa")
        db.flush()
        register_movement(
            db, hotel_id=1, item_id=item.id, location_id=house.id, movement_type="in",
            quantity=Decimal("20.00"), reason="opening balance", reservation_id=None, created_by_user_id=None,
        )
        db.commit()
        client.post(
            f"/api/laundry/vendors/{vendor_id}/prices",
            json={"linen_item_id": item.id, "unit_price": "100.00"},
        )
        client.post(
            "/api/laundry/remitos",
            json={
                "vendor_id": vendor_id,
                "direction": "outbound",
                "remito_number": "R-SETTLE-1",
                "remito_date": datetime(2026, 7, 5, tzinfo=timezone.utc).isoformat(),
                "house_location_id": house.id,
                "lines": [{"linen_item_id": item.id, "quantity": "10.00"}],
            },
        )

        # Receptionist cannot see the financial settlement report.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        forbidden = client.get(f"/api/laundry/vendors/{vendor_id}/settlements?year=2026")
        assert forbidden.status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        quarters = client.get(f"/api/laundry/vendors/{vendor_id}/settlements?year=2026").json()
        assert len(quarters) == 4
        q3 = next(q for q in quarters if q["period_start"] == "2026-07-01")
        assert q3["total_amount"] == "1000.00"
        assert q3["paid"] is False

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
        assert client.post(
            f"/api/laundry/vendors/{vendor_id}/settlements/2026-07-01/mark-paid", json={"paid": True}
        ).status_code == 403

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        marked = client.post(
            f"/api/laundry/vendors/{vendor_id}/settlements/2026-07-01/mark-paid",
            json={"paid": True, "notes": "Coincide con factura"},
        )
        assert marked.status_code == 200
        assert marked.json()["paid"] is True
        assert marked.json()["notes"] == "Coincide con factura"
        assert marked.json()["total_amount"] == "1000.00"

        invalid = client.post(
            f"/api/laundry/vendors/{vendor_id}/settlements/2026-07-15/mark-paid", json={"paid": True}
        )
        assert invalid.status_code == 400
    finally:
        _teardown(db, engine)


def test_settlements_are_hotel_scoped_across_the_api():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        vendor_h2 = client.post("/api/laundry/vendors", json={"name": "Lavadero H2 Liquidacion"}).json()["id"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        cross_read = client.get(f"/api/laundry/vendors/{vendor_h2}/settlements?year=2026")
        assert cross_read.status_code == 404

        cross_mark = client.post(
            f"/api/laundry/vendors/{vendor_h2}/settlements/2026-01-01/mark-paid", json={"paid": True}
        )
        assert cross_mark.status_code == 400
    finally:
        _teardown(db, engine)


def test_vendors_and_balance_are_hotel_scoped_across_the_api():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        vendor_h2 = client.post("/api/laundry/vendors", json={"name": "Lavadero H2"}).json()["id"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        vendor_h1 = client.post("/api/laundry/vendors", json={"name": "Lavadero H1"}).json()["id"]

        # Hotel 1's owner cannot see hotel 2's vendor in the list...
        listed = client.get("/api/laundry/vendors").json()
        assert [v["id"] for v in listed] == [vendor_h1]

        # ...nor query its balance directly by id.
        cross_balance = client.get(f"/api/laundry/vendors/{vendor_h2}/balance")
        assert cross_balance.status_code == 404

        cross_update = client.patch(f"/api/laundry/vendors/{vendor_h2}", json={"name": "Hijack"})
        assert cross_update.status_code == 404
    finally:
        _teardown(db, engine)


def test_linen_items_and_locations_are_hotel_scoped():
    client, db, engine = _client_with_db()
    try:
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        item_h2 = create_linen_item(db, hotel_id=2, name="Sabanas H2", unit="unit")
        location_h2 = create_location(db, hotel_id=2, name="Deposito H2")
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        items = client.get("/api/laundry/items").json()
        assert item_h2.id not in [row["id"] for row in items]
        locations = client.get("/api/laundry/locations").json()
        assert location_h2.id not in [row["id"] for row in locations]

        cross_delete = client.delete(f"/api/laundry/items/{item_h2.id}")
        assert cross_delete.status_code == 404
    finally:
        _teardown(db, engine)
