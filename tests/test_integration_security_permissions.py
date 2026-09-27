from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import integrations
from app.database import get_db
from app.dependencies import auth as auth_dependencies
from app.dependencies.auth import AuthContext, get_auth_context
from app.schemas.integration import IntegrationConnectRequest
from app.services import permission_service
from app.services import action_step_up_service
from app.services.action_step_up_service import create_action_step_up_ticket
from app.services.permission_service import PERMISSION_HOTEL_SECURITY_MANAGE


class _DB:
    pass


def _client(role: str):
    app = FastAPI()
    app.include_router(integrations.router)

    def override_db():
        yield _DB()

    def override_auth():
        return AuthContext(
            hotel_id=1,
            user_id=10,
            user_email=f"{role}@example.test",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_auth_context] = override_auth
    return TestClient(app, raise_server_exceptions=False)


def test_owner_can_enter_secret_connection_mutations_but_co_owner_is_denied(monkeypatch):
    calls = []
    resolved = []

    def marker(*_args, **_kwargs):
        calls.append("entered")
        raise RuntimeError("handler entered")

    monkeypatch.setattr(integrations, "_ensure_enabled", marker)
    monkeypatch.setattr(
        permission_service,
        "resolve",
        lambda _db, _hotel_id, role, code, user_id=None: resolved.append((role, code)) or role == "owner",
    )
    monkeypatch.setattr(permission_service, "audit_permission_denied", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(auth_dependencies, "_require_action_step_up", lambda *_args, **_kwargs: None)
    mutating_requests = (
        ("post", "/api/integrations/1/connect", {"json": {"payload": {}}}),
        ("get", "/api/integrations/1/callback?code=synthetic", {}),
        ("post", "/api/integrations/1/revoke", {}),
    )

    co_owner = _client("co_owner")
    for method, path, kwargs in mutating_requests:
        response = getattr(co_owner, method)(path, **kwargs)
        assert response.status_code == 403
    assert calls == []
    assert all(code == PERMISSION_HOTEL_SECURITY_MANAGE for _role, code in resolved)

    owner = _client("owner")
    path = "/api/integrations/1/revoke"
    ticket = create_action_step_up_ticket(
        user_id=10,
        hotel_id=1,
        token_version=0,
        permission_code=PERMISSION_HOTEL_SECURITY_MANAGE,
        method="POST",
        path=path,
    )
    owner_response = owner.post(path, headers={"X-Action-Step-Up-Ticket": ticket})
    assert owner_response.status_code == 500
    assert calls == ["entered"]


@pytest.mark.parametrize("payload", [{}, {"token": "synthetic-not-a-credential"}])
def test_generic_whatsapp_connection_mutations_are_rejected_before_writing(monkeypatch, payload):
    mutation_calls = []
    integration = SimpleNamespace(id=1, provider="whatsapp", auth_type="bearer_token")
    context = AuthContext(
        hotel_id=1,
        user_id=10,
        user_email="owner@example.test",
        user_role="owner",
        is_verified=True,
        permissions=set(),
    )

    monkeypatch.setattr(integrations, "_ensure_enabled", lambda: None)
    monkeypatch.setattr(integrations, "_find_integration", lambda *_args, **_kwargs: (integration, []))
    monkeypatch.setattr(
        integrations,
        "decode_signed_token",
        lambda _state: {
            "type": "integration_oauth",
            "integration_id": 1,
            "provider": "whatsapp",
            "hotel_id": 1,
            "user_id": 10,
            "web_origin": "https://app.example.test",
        },
    )
    monkeypatch.setattr(integrations, "_authorize_oauth_state_actor", lambda *_args, **_kwargs: None)
    for name in ("upsert_connection", "record_event", "_store_oauth_code", "revoke_connection", "verify_connection_health"):
        monkeypatch.setattr(
            integrations,
            name,
            lambda *_args, _name=name, **_kwargs: mutation_calls.append(_name),
        )

    db = _DB()
    request = SimpleNamespace(query_params={"code": "synthetic-code", "state": "synthetic-state"})
    operations = (
        lambda: integrations.connect_integration(
            1, IntegrationConnectRequest(payload=payload), None, db, context
        ),
        lambda: integrations.oauth_provider_callback("whatsapp", request, db),
        lambda: integrations.oauth_callback_manual(1, request, db, context),
        lambda: integrations.revoke(1, db, context),
        lambda: integrations.refresh(1, db, context),
    )

    for operation in operations:
        with pytest.raises(HTTPException) as error:
            operation()
        assert error.value.status_code == 409

    assert mutation_calls == []
