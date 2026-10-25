"""Stock count sessions: audited confirmation, recount protection, and tenancy."""

import json
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.audit_log import AuditLog
from app.models.hotel_config import HotelConfiguration
from app.models.stock import StockMovement


def _override_auth(hotel_id: int, role: str, user_id: int):
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
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    db.add(HotelConfiguration(id=1, subscription_active=True))
    db.flush()
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", 10)
    return TestClient(fastapi_app), db, engine


def _teardown(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _create_item(client: TestClient) -> int:
    response = client.post("/api/stock/items", json={"name": "Jabón", "unit": "unidad"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _start_session(client: TestClient) -> int:
    response = client.post(
        "/api/stock/count-sessions", json={"reason": "Conteo mensual"}
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_count_recount_after_movement_and_manager_confirmation_are_atomic_and_idempotent():
    client, db, engine = _client_with_db()
    try:
        item_id = _create_item(client)
        initial = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "in", "quantity": "10.00"},
        )
        assert initial.status_code == 201

        session_id = _start_session(client)
        first_count = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "8.00"},
        )
        assert first_count.status_code == 201
        assert first_count.json()["system_quantity_at_count"] == "10.00"
        assert first_count.json()["recount_required"] is False

        # Normal movements remain available while a count session is open.
        later_movement = client.post(
            "/api/stock/movements",
            json={"item_id": item_id, "movement_type": "in", "quantity": "2.00"},
        )
        assert later_movement.status_code == 201
        detail = client.get(f"/api/stock/count-sessions/{session_id}")
        assert detail.json()["counts"][0]["recount_required"] is True

        stale_confirmation = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Revisión de diferencias"},
        )
        assert stale_confirmation.status_code == 409
        assert stale_confirmation.json()["detail"]["recount_required"] == [
            {"item_id": item_id, "location_id": None}
        ]
        assert (
            db.query(StockMovement).filter_by(hotel_id=1, item_id=item_id).count() == 2
        )

        recounted = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "9.00"},
        )
        assert recounted.status_code == 201
        assert recounted.json()["recount_required"] is False

        # A session has one counter. A different staff member cannot change
        # the observed quantity after the first counter starts recording.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(
            1, "co_owner", 12
        )
        second_counter = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "9.00"},
        )
        assert second_counter.status_code == 409
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(
            1, "owner", 10
        )

        # The counter cannot approve their own adjustment by default.
        self_confirmation = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Intento de autoaprobación"},
        )
        assert self_confirmation.status_code == 409
        assert "different user" in self_confirmation.json()["detail"]
        assert (
            db.query(StockMovement).filter_by(hotel_id=1, item_id=item_id).count() == 2
        )

        # Gerencia has the separate, configurable count-confirm permission by
        # default; it does not widen the existing stock:adjust permission.
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(
            1, "manager", 20
        )
        confirmed = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Verifiqué el recuento físico"},
        )
        assert confirmed.status_code == 200, confirmed.text
        assert confirmed.json()["status"] == "confirmed"
        assert confirmed.json()["counter_user_id"] == 10
        assert confirmed.json()["confirmed_by_user_id"] == 20
        assert confirmed.json()["self_approved"] is False
        assert confirmed.json()["confirmation_reason"] == "Verifiqué el recuento físico"
        assert confirmed.json()["counts"][0]["applied_adjustment"] == "-3.00"
        assert confirmed.json()["counts"][0]["recount_required"] is False

        final_quantity = client.get(f"/api/stock/items/{item_id}/current")
        assert final_quantity.status_code == 200
        assert Decimal(str(final_quantity.json()["quantity"])) == Decimal("9.00")
        movement_count = (
            db.query(StockMovement).filter_by(hotel_id=1, item_id=item_id).count()
        )

        # A lost response followed by retry returns the committed session and
        # never applies a second adjustment.
        retry = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Reintento de la misma operación"},
        )
        assert retry.status_code == 200
        assert (
            db.query(StockMovement).filter_by(hotel_id=1, item_id=item_id).count()
            == movement_count
        )
        assert retry.json()["confirmation_reason"] == "Verifiqué el recuento físico"

        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.hotel_id == 1,
                AuditLog.table_name == "stock_count_sessions",
                AuditLog.record_id == session_id,
                AuditLog.action == "status_change",
            )
            .one()
        )
        audit_payload = json.loads(audit.payload_after)
        assert audit_payload["confirmed_by_user_id"] == 20
        assert audit_payload["counter_user_id"] == 10
        assert audit_payload["self_approved"] is False
        assert audit_payload["confirmation_reason"] == "Verifiqué el recuento físico"
    finally:
        _teardown(db, engine)


def test_count_confirmation_requires_configurable_permission_and_is_tenant_scoped():
    client, db, engine = _client_with_db()
    try:
        item_id = _create_item(client)
        session_id = _start_session(client)
        count_response = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "0"},
        )
        assert count_response.status_code == 201

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(
            1, "receptionist", 11
        )
        denied = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Sin permiso"},
        )
        assert denied.status_code == 403
        assert (
            db.query(StockMovement).filter_by(hotel_id=1, item_id=item_id).count() == 0
        )

        db.add(HotelConfiguration(id=2, subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(
            2, "owner", 22
        )
        cross_tenant = client.get(f"/api/stock/count-sessions/{session_id}")
        assert cross_tenant.status_code == 404
        assert client.get("/api/stock/count-sessions").json() == []
    finally:
        _teardown(db, engine)


def test_count_session_rejects_overlapping_item_and_location_scopes():
    client, _db, engine = _client_with_db()
    try:
        item_id = _create_item(client)
        location = client.post("/api/stock/locations", json={"name": "Depósito"})
        assert location.status_code == 201
        session_id = _start_session(client)

        by_location = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={
                "item_id": item_id,
                "location_id": location.json()["id"],
                "counted_quantity": "4.00",
            },
        )
        assert by_location.status_code == 201
        overlapping_total = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "4.00"},
        )
        assert overlapping_total.status_code == 409
        assert "either hotel-wide or by location" in overlapping_total.json()["detail"]
    finally:
        _teardown(_db, engine)


def test_self_approval_can_be_enabled_by_hotel_configuration_and_is_audited():
    client, db, engine = _client_with_db()
    try:
        item_id = _create_item(client)
        session_id = _start_session(client)
        count_response = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "0"},
        )
        assert count_response.status_code == 201

        config_response = client.patch(
            "/api/config/",
            json={"allow_stock_count_self_approval": True},
        )
        assert config_response.status_code == 200, config_response.text
        assert config_response.json()["allow_stock_count_self_approval"] is True

        approved = client.post(
            f"/api/stock/count-sessions/{session_id}/confirm",
            json={"reason": "Autoaprobación habilitada por el hotel"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["counter_user_id"] == 10
        assert approved.json()["confirmed_by_user_id"] == 10
        assert approved.json()["self_approved"] is True
        audit = (
            db.query(AuditLog)
            .filter(
                AuditLog.hotel_id == 1,
                AuditLog.table_name == "stock_count_sessions",
                AuditLog.record_id == session_id,
                AuditLog.action == "status_change",
            )
            .one()
        )
        assert json.loads(audit.payload_after)["self_approved"] is True
    finally:
        _teardown(db, engine)


def test_count_quantities_and_reasons_are_validated_before_writing():
    client, db, engine = _client_with_db()
    try:
        blank = client.post("/api/stock/count-sessions", json={"reason": "   "})
        assert blank.status_code == 422
        assert (
            db.query(AuditLog)
            .filter_by(hotel_id=1, table_name="stock_count_sessions")
            .count()
            == 0
        )

        item_id = _create_item(client)
        session_id = _start_session(client)
        invalid_precision = client.post(
            f"/api/stock/count-sessions/{session_id}/counts",
            json={"item_id": item_id, "counted_quantity": "1.001"},
        )
        assert invalid_precision.status_code == 422
        assert Decimal("0.00") == Decimal(
            str(client.get(f"/api/stock/items/{item_id}/current").json()["quantity"])
        )
        assert (
            client.get(f"/api/stock/count-sessions/{session_id}").json()["counts"] == []
        )
    finally:
        _teardown(db, engine)
