from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.guest import Guest
from app.models.reservation import Reservation, ReservationSourceEnum, ReservationStatusEnum
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.commercial import ProductRoomCompatibility, SellableProduct
from app.services.allocation_policy_service import record_manual_override_feedback
from app.services.allocation_runtime_service import run_persisted_allocation

GEMMA_DEFER_REASON = "Gemma validation is deferred until the final IA configuration phase."


def _override_auth(hotel_id: int, role: str = "owner"):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=1,
            user_email="owner@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _build_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _cleanup_client(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_allocation_policy_api_exposes_active_policy_and_versions():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        active_resp = client.get("/api/allocation/policy")
        assert active_resp.status_code == 200, active_resp.text
        active_body = active_resp.json()
        assert active_body["profile_code"] == "default"
        assert active_body["version"]["weights"]["prefer_exact_match"] == 500.0

        version_resp = client.post(
            "/api/allocation/policy/versions",
            json={
                "constraints": {
                    "no_overlap": True,
                    "respect_locked_assignments": True,
                    "allow_category_fallback": False,
                },
                "weights": {
                    "prefer_exact_match": 900,
                    "stability": 8,
                    "room_usage_penalty": 30,
                    "unassigned_penalty": 15000,
                    "fallback_priority_penalty": 40,
                },
                "prompt_summary": "Version mas estricta para upgrades",
            },
        )
        assert version_resp.status_code == 201, version_resp.text
        version_body = version_resp.json()
        assert version_body["version_number"] == 2
        assert version_body["constraints"]["allow_category_fallback"] is False

        publish_resp = client.post(f"/api/allocation/policy/versions/{version_body['id']}/publish")
        assert publish_resp.status_code == 200, publish_resp.text
        assert publish_resp.json()["is_published"] is True

        active_after_publish = client.get("/api/allocation/policy")
        assert active_after_publish.status_code == 200, active_after_publish.text
        assert active_after_publish.json()["version"]["id"] == version_body["id"]

        versions_list = client.get("/api/allocation/policy/versions")
        assert versions_list.status_code == 200, versions_list.text
        assert [item["version_number"] for item in versions_list.json()] == [2, 1]
    finally:
        _cleanup_client(db, engine)


def test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only():
    client, db, engine = _build_client()
    try:
        db.add_all(
            [
                HotelConfiguration(id=1, owner_email="owner1@test.com", subscription_active=True),
                HotelConfiguration(id=2, owner_email="owner2@test.com", subscription_active=True),
            ]
        )
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
        suggestion_h1 = client.post(
            "/api/allocation/policy/suggestions",
            json={
                "suggestion_type": "questionnaire_ingest",
                "input_summary": "Hotel prioriza evitar huecos de una noche",
                "suggested_policy": {"weights": {"stability": 12}},
                "explanation": "Borrador inicial",
                "source_model": "gemma-4-draft",
            },
        )
        assert suggestion_h1.status_code == 201, suggestion_h1.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        suggestion_h2 = client.post(
            "/api/allocation/policy/suggestions",
            json={
                "suggestion_type": "questionnaire_ingest",
                "input_summary": "Hotel 2 quiere priorizar exact match",
                "suggested_policy": {"weights": {"prefer_exact_match": 800}},
            },
        )
        assert suggestion_h2.status_code == 201, suggestion_h2.text

        list_h2 = client.get("/api/allocation/policy/suggestions")
        assert list_h2.status_code == 200, list_h2.text
        assert [item["input_summary"] for item in list_h2.json()] == ["Hotel 2 quiere priorizar exact match"]

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")
        list_h1 = client.get("/api/allocation/policy/suggestions")
        assert list_h1.status_code == 200, list_h1.text
        assert [item["input_summary"] for item in list_h1.json()] == ["Hotel prioriza evitar huecos de una noche"]

        denied = client.post(
            "/api/allocation/policy/suggestions",
            json={
                "suggestion_type": "manual_test",
                "input_summary": "No deberia poder crear",
                "suggested_policy": {},
            },
        )
        assert denied.status_code == 403, denied.text
    finally:
        _cleanup_client(db, engine)


@pytest.mark.skip(reason=GEMMA_DEFER_REASON)
def test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        resp = client.post(
            "/api/allocation/policy/questionnaire-draft",
            json={
                "business_summary": "Queremos minimizar huecos, evitar mover huespedes y priorizar la misma categoria.",
                "prioritize_exact_match": 5,
                "minimize_one_night_gaps": 5,
                "minimize_moves": 4,
                "preserve_future_availability": 4,
                "allow_category_fallback": True,
                "notes": "Hotel con alta rotacion de fines de semana",
            },
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["suggestion_type"] == "questionnaire_ingest"
        assert body["source_model"] == "questionnaire_heuristic_seed"
        assert body["suggested_policy"]["weights"]["prefer_exact_match"] >= 950.0
        assert body["suggested_policy"]["questionnaire_summary"]["notes"] == "Hotel con alta rotacion de fines de semana"
    finally:
        _cleanup_client(db, engine)


def test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion():
    client, db, engine = _build_client()
    try:
        hotel = HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True)
        db.add(hotel)
        db.flush()
        guest = Guest(first_name="Ana", last_name="Test", hotel_id=1)
        category = RoomCategory(
            hotel_id=1,
            name="Standard",
            code="STD",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        reservation = Reservation(
            confirmation_code="API-FEEDBACK-1",
            hotel_id=1,
            guest_id=guest.id,
            room_id=None,
            category_id=category.id,
            check_in_date=date(2026, 4, 11),
            check_out_date=date(2026, 4, 12),
            total_amount=100.0,
            subtotal_amount=100.0,
            net_amount=100.0,
            amount_paid=0.0,
            deposit_amount=30.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            source=ReservationSourceEnum.DIRECT,
            num_adults=2,
            num_children=0,
        )
        db.add(reservation)
        db.flush()
        record_manual_override_feedback(
            db,
            hotel_id=1,
            reservation_id=reservation.id,
            override_type="room_move",
            reason_code="keep_group_together",
            notes="Mover para priorizar grupo",
            created_by_user_id=None,
        )
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        resp = client.post(
            "/api/allocation/policy/feedback-draft",
            json={"max_events": 10, "notes": "Aprender de room moves recientes"},
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["suggestion_type"] == "feedback_learning"
        assert body["source_model"] in {
            "feedback_heuristic_seed",
            "questionnaire_heuristic_seed",
        } or body["source_model"].startswith("gemma")
        assert "feedback" in body["input_summary"].lower()
    finally:
        _cleanup_client(db, engine)


def test_allocation_policy_api_can_review_and_apply_suggestion():
    client, db, engine = _build_client()
    try:
        db.add(HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")

        create_resp = client.post(
            "/api/allocation/policy/suggestions",
            json={
                "suggestion_type": "feedback_learning",
                "input_summary": "Tighten exact-match preference",
                "suggested_policy": {
                    "constraints": {
                        "no_overlap": True,
                        "respect_locked_assignments": True,
                        "allow_category_fallback": False,
                    },
                    "weights": {
                        "prefer_exact_match": 950,
                        "stability": 7,
                        "room_usage_penalty": 40,
                        "unassigned_penalty": 12000,
                        "fallback_priority_penalty": 10,
                    },
                },
                "explanation": "Based on recent manual overrides",
                "source_model": "gemma-feedback",
            },
        )
        assert create_resp.status_code == 201, create_resp.text
        suggestion_id = create_resp.json()["id"]

        review_resp = client.post(
            f"/api/allocation/policy/suggestions/{suggestion_id}/review",
            json={"action": "review"},
        )
        assert review_resp.status_code == 200, review_resp.text
        assert review_resp.json()["status"] == "reviewed"

        apply_resp = client.post(
            f"/api/allocation/policy/suggestions/{suggestion_id}/apply",
            json={"publish": True, "prompt_summary": "Apply feedback draft"},
        )
        assert apply_resp.status_code == 200, apply_resp.text
        body = apply_resp.json()
        assert body["suggestion"]["status"] == "accepted"
        assert body["version"]["is_published"] is True
        assert body["version"]["constraints"]["allow_category_fallback"] is False

        active_resp = client.get("/api/allocation/policy")
        assert active_resp.status_code == 200, active_resp.text
        assert active_resp.json()["version"]["id"] == body["version"]["id"]
    finally:
        _cleanup_client(db, engine)


def test_allocation_policy_api_exposes_latest_run_details():
    client, db, engine = _build_client()
    try:
        hotel = HotelConfiguration(id=1, owner_email="owner@test.com", subscription_active=True)
        db.add(hotel)
        db.flush()
        guest = Guest(first_name="Ana", last_name="Run", hotel_id=1)
        category = RoomCategory(
            hotel_id=1,
            name="Standard",
            code="STD",
            base_price_per_night=100.0,
            max_occupancy=2,
        )
        db.add_all([guest, category])
        db.flush()
        product = SellableProduct(
            hotel_id=1,
            primary_room_category_id=category.id,
            code="STD_PRODUCT",
            name="Producto standard",
            min_occupancy=1,
            max_occupancy=2,
        )
        db.add(product)
        db.flush()
        db.add(
            ProductRoomCompatibility(
                hotel_id=1,
                sellable_product_id=product.id,
                room_category_id=category.id,
                compatibility_kind="exact",
                priority=1,
            )
        )
        room = Room(
            room_number="101",
            floor=1,
            category_id=category.id,
            status=RoomStatusEnum.AVAILABLE,
            hotel_id=1,
        )
        db.add(room)
        reservation = Reservation(
            confirmation_code="API-RUN-1",
            hotel_id=1,
            guest_id=guest.id,
            room_id=None,
            category_id=category.id,
            sellable_product_id=product.id,
            check_in_date=date(2026, 4, 20),
            check_out_date=date(2026, 4, 22),
            total_amount=100.0,
            subtotal_amount=100.0,
            net_amount=100.0,
            amount_paid=0.0,
            deposit_amount=30.0,
            currency_code="ARS",
            status=ReservationStatusEnum.PENDING,
            source=ReservationSourceEnum.DIRECT,
            num_adults=2,
            num_children=0,
        )
        db.add(reservation)
        db.commit()

        run = run_persisted_allocation(
            db,
            hotel_id=1,
            trigger_type="api_run_details_test",
            apply=True,
            horizon_start=date(2026, 4, 20),
            horizon_end=date(2026, 4, 25),
        )
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager")

        latest_resp = client.get("/api/allocation/policy/runs/latest")
        assert latest_resp.status_code == 200, latest_resp.text
        latest_body = latest_resp.json()
        assert latest_body["run_id"] == run.run.id
        assert any(item["explanation_type"] == "assignment" for item in latest_body["explanations"])
        assert any(item["metric_key"] == "assigned_reservations" for item in latest_body["metrics"])

        detail_resp = client.get(f"/api/allocation/policy/runs/{run.run.id}")
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["run_id"] == run.run.id
    finally:
        _cleanup_client(db, engine)
