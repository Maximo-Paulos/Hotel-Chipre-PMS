from __future__ import annotations

import time

import pytest

from app.config import get_settings
from app.services import fx_service


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
    get_settings.cache_clear()
    fx_service._cache.update(
        {
            "data": {"oficial": {"venta": 1234.5}},
            "fetched_at": time.monotonic() - fx_service.RATE_CACHE_TTL_SECONDS - 1,
        }
    )

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("AsyncClient must not be constructed")

    monkeypatch.setattr(fx_service.httpx, "AsyncClient", UnexpectedClient)

    assert await fx_service.fetch_rate("oficial") == {"venta": 1234.5}
    assert await fx_service.fetch_all_rates() == {"oficial": {"venta": 1234.5}}


def test_disabled_sync_fx_uses_stale_cache_without_network(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "false")
    get_settings.cache_clear()
    fx_service._cache.update(
        {
            "data": {"oficial": {"venta": 1234.5}},
            "fetched_at": time.monotonic() - fx_service.RATE_CACHE_TTL_SECONDS - 1,
        }
    )
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
    get_settings.cache_clear()

    assert await fx_service.fetch_rate("oficial") is None
    assert await fx_service.fetch_all_rates() == {}
    assert fx_service.get_rate_sync("oficial") is None
