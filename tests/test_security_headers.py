"""
Every response must carry baseline security headers so the SPA and API are not
missing basic browser-enforced defenses (clickjacking, MIME sniffing, XSS via
inline injection). HSTS is only asserted in production mode since local/dev
HTTP has no TLS to upgrade.
"""
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError
from starlette.requests import Request

from app.database import get_db
from app.main import app, security_headers


def test_health_response_has_baseline_security_headers():
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Content-Security-Policy" in response.headers
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


@pytest.fixture
def _no_real_db():
    """The unmatched-path SPA fallback still depends on get_db; stub it so this
    test never touches the real (unconfigured, unreachable in CI) Postgres."""
    app.dependency_overrides[get_db] = lambda: iter([None])
    yield
    app.dependency_overrides.pop(get_db, None)


def test_api_error_response_still_carries_security_headers(_no_real_db):
    client = TestClient(app)
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_database_pool_timeout_returns_retryable_service_unavailable():
    async def run_middleware():
        request = Request(
            {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": "/api/reservations",
                "raw_path": b"/api/reservations",
                "query_string": b"",
                "headers": [],
                "server": ("testserver", 80),
                "client": ("127.0.0.1", 12345),
                "root_path": "",
            }
        )

        async def raise_pool_timeout(_request):
            raise SQLAlchemyTimeoutError("pool exhausted")

        return await security_headers(request, raise_pool_timeout)

    response = asyncio.run(run_middleware())

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.body == b'{"detail":"Servidor ocupado. Reintent\xc3\xa1 en unos segundos."}'


def test_production_response_includes_hsts(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app.config import get_settings

    get_settings.cache_clear()
    try:
        client = TestClient(app)
        response = client.get("/health")
        assert "Strict-Transport-Security" in response.headers
        assert "max-age=" in response.headers["Strict-Transport-Security"]
    finally:
        get_settings.cache_clear()
