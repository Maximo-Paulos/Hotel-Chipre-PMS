from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import integrations
from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.services import permission_service
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
    owner_response = owner.post("/api/integrations/1/revoke")
    assert owner_response.status_code == 500
    assert calls == ["entered"]
