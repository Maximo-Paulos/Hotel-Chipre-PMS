from __future__ import annotations

from fastapi.testclient import TestClient
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.hotel_config import HotelConfiguration
from app.models.user import User
from app.services.gemma_orchestrator import GemmaOrchestrator


def _override_auth(hotel_id: int, role: str = "owner", user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email="owner@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _build_client(orchestrator: GemmaOrchestrator | None = None):
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
    if orchestrator is not None:
        from app.api.gemma_chat import _get_orchestrator

        fastapi_app.dependency_overrides[_get_orchestrator] = lambda: orchestrator
    client = TestClient(fastapi_app)
    return client, db, engine


def _cleanup_client(db, engine):
    fastapi_app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_gemma_chat_creates_session_and_persists_messages_with_fallback():
    client, db, engine = _build_client()
    try:
        db.add(User(id=55, email="owner55@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Gemma", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=55)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero entender como viene el hotel este mes y si Booking bajo."},
        )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["mode"] == "analysis"
        assert body["session"]["message_count"] == 2
        assert body["messages"][-1]["role"] == "assistant"
        assert body["metadata"]["intent_type"] == "analyze_channel_drop"

        history = client.get("/api/gemma/chat/history")
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1

        session_id = body["session"]["id"]
        detail = client.get(f"/api/gemma/chat/session/{session_id}")
        assert detail.status_code == 200, detail.text
        assert [item["role"] for item in detail.json()["messages"]] == ["user", "assistant"]
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_scopes_history_by_user_and_hotel():
    client, db, engine = _build_client()
    try:
        db.add_all(
            [
                User(id=7, email="owner7@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"),
                User(id=8, email="owner8@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"),
                HotelConfiguration(id=1, hotel_name="Hotel Uno", subscription_active=True),
                HotelConfiguration(id=2, hotel_name="Hotel Dos", subscription_active=True),
            ]
        )
        db.commit()

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=7)
        first = client.post("/api/gemma/chat/message", json={"message": "Quiero revisar ocupacion"})
        assert first.status_code == 201, first.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=8)
        second = client.post("/api/gemma/chat/message", json={"message": "Quiero revisar restricciones"})
        assert second.status_code == 201, second.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner", user_id=7)
        third = client.post("/api/gemma/chat/message", json={"message": "Quiero revisar Booking"})
        assert third.status_code == 201, third.text

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=7)
        history = client.get("/api/gemma/chat/history")
        assert history.status_code == 200, history.text
        assert len(history.json()) == 1
        assert history.json()[0]["id"] == first.json()["session"]["id"]
        assert history.json()[0]["id"] != second.json()["session"]["id"]
        assert history.json()[0]["id"] != third.json()["session"]["id"]
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_can_archive_session_and_hide_it_from_history():
    client, db, engine = _build_client()
    try:
        db.add(User(id=56, email="owner56@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Archive", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=56)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero revisar ocupacion del hotel."},
        )
        assert response.status_code == 201, response.text
        session_id = response.json()["session"]["id"]

        archive_response = client.post(f"/api/gemma/chat/session/{session_id}/archive")
        assert archive_response.status_code == 200, archive_response.text
        assert archive_response.json()["status"] == "archived"

        history_response = client.get("/api/gemma/chat/history")
        assert history_response.status_code == 200, history_response.text
        assert history_response.json() == []
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_persists_and_lists_insights():
    client, db, engine = _build_client()
    try:
        db.add(User(id=57, email="owner57@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Insights", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=57)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero entender como viene el hotel este mes y si Booking bajo."},
        )
        assert response.status_code == 201, response.text

        insights_response = client.get("/api/gemma/chat/insights")
        assert insights_response.status_code == 200, insights_response.text
        body = insights_response.json()
        assert len(body) == 1
        assert body[0]["insight_type"] == "analysis"
        assert body[0]["summary"] == "Snapshot operativo del hotel."
        assert body[0]["details"]["intent_type"] == "analyze_channel_drop"
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_returns_controlled_preview_for_policy_change_requests():
    client, db, engine = _build_client()
    try:
        db.add(User(id=90, email="owner90@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Preview", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=90)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero reducir noches sueltas y proteger estadias largas."},
        )
        assert response.status_code == 201, response.text
        body = response.json()

        assert body["mode"] == "proposal"
        assert body["requires_confirmation"] is True
        assert body["actions"]
        assert body["actions"][0]["action_type"] == "allocation_policy.update_preview"
        assert body["preview"]["title"] == "Preview de politica de asignacion"
        changed_weight_keys = {item["key"] for item in body["preview"]["changed_weights"]}
        assert "room_usage_penalty" in changed_weight_keys
        assert "fallback_priority_penalty" in changed_weight_keys
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft():
    client, db, engine = _build_client()
    try:
        db.add(User(id=91, email="owner91@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Confirm", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=91)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero reducir noches sueltas y proteger estadias largas."},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        action_run_id = body["actions"][0]["action_run_id"]
        session_id = body["session"]["id"]

        approve_response = client.post(
            f"/api/gemma/chat/actions/{action_run_id}/approve",
            json={"session_id": session_id},
        )
        assert approve_response.status_code == 200, approve_response.text
        approve_body = approve_response.json()
        assert approve_body["status"] == "executed"
        assert approve_body["created_suggestion_id"] > 0

        session_response = client.get(f"/api/gemma/chat/session/{session_id}")
        assert session_response.status_code == 200, session_response.text
        session_body = session_response.json()
        assert session_body["actions"][0]["status"] == "executed"
        assert session_body["actions"][0]["result"]["created_suggestion_id"] == approve_body["created_suggestion_id"]
        assert session_body["messages"][-1]["role"] == "system"
        assert "borrador de politica" in session_body["messages"][-1]["text"].lower()
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_can_reject_pending_action():
    client, db, engine = _build_client()
    try:
        db.add(User(id=92, email="owner92@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Reject", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=92)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero reducir noches sueltas y proteger estadias largas."},
        )
        assert response.status_code == 201, response.text
        body = response.json()

        reject_response = client.post(
            f"/api/gemma/chat/actions/{body['actions'][0]['action_run_id']}/reject",
            json={"session_id": body["session"]["id"]},
        )
        assert reject_response.status_code == 200, reject_response.text
        assert reject_response.json()["status"] == "rejected"

        session_response = client.get(f"/api/gemma/chat/session/{body['session']['id']}")
        assert session_response.status_code == 200, session_response.text
        session_body = session_response.json()
        assert session_body["actions"][0]["status"] == "rejected"
        assert session_body["messages"][-1]["role"] == "system"
        assert "rechazada" in session_body["messages"][-1]["text"].lower()
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_can_review_and_apply_created_draft():
    client, db, engine = _build_client()
    try:
        db.add(User(id=93, email="owner93@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Apply", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=93)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero reducir noches sueltas y proteger estadias largas."},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        action_run_id = body["actions"][0]["action_run_id"]
        session_id = body["session"]["id"]

        approve_response = client.post(
            f"/api/gemma/chat/actions/{action_run_id}/approve",
            json={"session_id": session_id},
        )
        assert approve_response.status_code == 200, approve_response.text

        review_response = client.post(
            f"/api/gemma/chat/actions/{action_run_id}/review-draft",
            json={"session_id": session_id},
        )
        assert review_response.status_code == 200, review_response.text
        assert review_response.json()["status"] == "reviewed"
        assert review_response.json()["suggestion_status"] == "reviewed"

        apply_response = client.post(
            f"/api/gemma/chat/actions/{action_run_id}/apply-draft",
            json={"session_id": session_id, "publish": False},
        )
        assert apply_response.status_code == 200, apply_response.text
        apply_body = apply_response.json()
        assert apply_body["status"] == "applied"
        assert apply_body["suggestion_status"] == "accepted"
        assert apply_body["created_version_id"] > 0
        assert apply_body["is_published"] is False

        session_response = client.get(f"/api/gemma/chat/session/{session_id}")
        assert session_response.status_code == 200, session_response.text
        session_body = session_response.json()
        assert session_body["actions"][0]["status"] == "applied"
        assert session_body["actions"][0]["result"]["created_version_id"] == apply_body["created_version_id"]
        system_messages = [item for item in session_body["messages"] if item["role"] == "system"]
        assert len(system_messages) >= 3
        assert "version" in system_messages[-1]["text"].lower()
    finally:
        _cleanup_client(db, engine)


class _StubGemmaOrchestrator(GemmaOrchestrator):
    def _local_runtime_enabled(self) -> bool:
        return True

    def _call_local_runtime(self, **kwargs):
        return {
            "mode": "analysis",
            "summary": "Respuesta del modelo local",
            "answer": "Modelo local activo y respondiendo.",
            "warnings": [],
            "missing_information": [],
            "confidence": 0.91,
            "suggested_follow_up": ["Seguir con politica de asignacion."],
        }

    def get_runtime_status(self):
        return {
            "enabled": True,
            "configured": True,
            "provider": "openai_compatible",
            "model": "gemma-local-test",
            "endpoint_url": "http://127.0.0.1:11434/v1/chat/completions",
            "status": "ready",
            "reachable": True,
            "strict_json": True,
            "timeout_seconds": 20.0,
            "max_conversation_messages": 6,
            "max_input_chars": 4000,
            "fallback_reason": None,
            "probe_error": None,
        }


class _TimeoutGemmaOrchestrator(GemmaOrchestrator):
    def _local_runtime_enabled(self) -> bool:
        return True

    def _call_local_runtime(self, **kwargs):
        raise httpx.TimeoutException("simulated timeout")


def test_gemma_chat_uses_local_runtime_when_available():
    orchestrator = _StubGemmaOrchestrator()
    client, db, engine = _build_client(orchestrator=orchestrator)
    try:
        db.add(User(id=22, email="manager22@test.com", password_hash="hash", is_active=True, is_verified=True, role="manager"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Runtime", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=22)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Decime como rindio el hotel y que deberia mirar."},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["messages"][-1]["text"] == "Modelo local activo y respondiendo."
        assert body["metadata"]["used_model"] == orchestrator.settings.GEMMA_MODEL
    finally:
        _cleanup_client(db, engine)


def test_gemma_runtime_status_endpoint_uses_orchestrator_probe():
    orchestrator = _StubGemmaOrchestrator()
    client, db, engine = _build_client(orchestrator=orchestrator)
    try:
        db.add(User(id=24, email="manager24@test.com", password_hash="hash", is_active=True, is_verified=True, role="manager"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Runtime Status", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=24)

        response = client.get("/api/gemma/chat/runtime-status")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "ready"
        assert body["reachable"] is True
        assert body["provider"] == "openai_compatible"
        assert body["model"] == "gemma-local-test"
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_falls_back_cleanly_when_local_runtime_times_out():
    orchestrator = _TimeoutGemmaOrchestrator()
    client, db, engine = _build_client(orchestrator=orchestrator)
    try:
        db.add(User(id=23, email="manager23@test.com", password_hash="hash", is_active=True, is_verified=True, role="manager"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Runtime Timeout", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=23)

        response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Decime como rindio el hotel y que deberia mirar."},
        )
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["mode"] == "analysis"
        assert body["metadata"]["fallback_used"] is True
        assert body["metadata"]["runtime_status"] == "timeout"
        assert body["metadata"]["runtime_error_code"] == "timeout"
        assert any("tiempo limite" in item.lower() for item in body["warnings"])
    finally:
        _cleanup_client(db, engine)


def test_gemma_chat_enforces_rate_limit_per_user_and_hotel():
    settings = Settings(GEMMA_RATE_LIMIT_MAX_MESSAGES=1, GEMMA_RATE_LIMIT_WINDOW_SECONDS=3600)
    orchestrator = GemmaOrchestrator(settings=settings)
    client, db, engine = _build_client(orchestrator=orchestrator)
    try:
        db.add(User(id=25, email="owner25@test.com", password_hash="hash", is_active=True, is_verified=True, role="owner"))
        db.add(HotelConfiguration(id=1, hotel_name="Hotel Rate Limit", subscription_active=True))
        db.commit()
        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner", user_id=25)

        first_response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero revisar ocupacion."},
        )
        assert first_response.status_code == 201, first_response.text

        second_response = client.post(
            "/api/gemma/chat/message",
            json={"message": "Quiero revisar Booking."},
        )
        assert second_response.status_code == 429, second_response.text
        assert "limite temporal" in second_response.json()["detail"].lower()
    finally:
        _cleanup_client(db, engine)
