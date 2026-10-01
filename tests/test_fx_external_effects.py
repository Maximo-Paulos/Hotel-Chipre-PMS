from __future__ import annotations

import time
from datetime import datetime, timezone

import pytest

from app.config import get_settings
from app.services import fx_service


def _supported_official_quote() -> dict[str, object]:
    return {
        "moneda": "USD",
        "casa": "oficial",
        "compra": 1230.0,
        "venta": 1234.5,
        "fechaActualizacion": datetime.now(timezone.utc).isoformat(),
    }


def _store_expired_display_quote() -> dict[str, object]:
    quote = _supported_official_quote()
    fx_service._cache.update(
        {
            "data": {"oficial": quote},
            "fetched_at_by_key": {
                "oficial": time.monotonic() - fx_service.RATE_CACHE_TTL_SECONDS - 1,
            },
        }
    )
    return quote


@pytest.fixture(autouse=True)
def _reset_fx_state():
    original = dict(fx_service._cache)
    fx_service._cache.clear()
    get_settings.cache_clear()
    yield
    fx_service._cache.clear()
    fx_service._cache.update(original)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_disabled_async_fx_uses_cache_without_constructing_client(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("DOLARAPI_RATES_ENABLED", "false")
    get_settings.cache_clear()
    quote = _store_expired_display_quote()

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("AsyncClient must not be constructed")

    monkeypatch.setattr(fx_service.httpx, "AsyncClient", UnexpectedClient)

    assert await fx_service.fetch_rate("oficial") == quote
    assert await fx_service.fetch_all_rates() == {"oficial": quote}


def test_disabled_sync_fx_uses_stale_cache_without_network(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("DOLARAPI_RATES_ENABLED", "false")
    get_settings.cache_clear()
    _store_expired_display_quote()
    monkeypatch.setattr(
        fx_service.httpx,
        "get",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("httpx.get must not be called")
        ),
    )

    assert fx_service.get_rate_sync("oficial") == 1234.5


@pytest.mark.asyncio
async def test_disabled_fx_without_cache_returns_safe_empty_result(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("DOLARAPI_RATES_ENABLED", "false")
    get_settings.cache_clear()

    assert await fx_service.fetch_rate("oficial") is None
    assert await fx_service.fetch_all_rates() == {}
    assert fx_service.get_rate_sync("oficial") is None


def test_production_sandbox_can_read_dolarapi_without_enabling_integrations(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "false")
    monkeypatch.delenv("DOLARAPI_RATES_ENABLED", raising=False)
    get_settings.cache_clear()
    expected_quote = _supported_official_quote()

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return expected_quote

    monkeypatch.setattr(fx_service.httpx, "get", lambda *_args, **_kwargs: FakeResponse())

    assert fx_service.get_conversion_quote_sync("USD", "oficial") == expected_quote


def test_explicitly_disabled_dolarapi_reads_stay_closed_in_production(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DOLARAPI_RATES_ENABLED", "false")
    get_settings.cache_clear()
    monkeypatch.setattr(
        fx_service.httpx,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("disabled DolarAPI rates must not perform a request")
        ),
    )

    assert fx_service.get_conversion_quote_sync("USD", "oficial") is None
