from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.config import get_settings
from app.services import fx_service


@pytest.fixture(autouse=True)
def _isolate_fx_provider_state():
    previous = {
        "data": dict(fx_service._cache.get("data") or {}),
        "fetched_at_by_key": dict(fx_service._cache.get("fetched_at_by_key") or {}),
    }
    fx_service._cache.clear()
    fx_service._cache.update({"data": {}, "fetched_at_by_key": {}})
    get_settings.cache_clear()
    yield
    fx_service._cache.clear()
    fx_service._cache.update(previous)
    get_settings.cache_clear()


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def _quote(currency: str, *, updated_at: datetime | None = None):
    return {
        "moneda": currency,
        "casa": "oficial",
        "compra": 100.0,
        "venta": 110.0,
        "fechaActualizacion": (updated_at or datetime.now(timezone.utc)).isoformat(),
    }


def test_conversion_provider_uses_only_selected_usd_market_and_exact_direct_currency(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()
    fx_service._cache.clear()
    fx_service._cache.update({"data": {}, "fetched_at_by_key": {}})
    requested_urls = []

    def fake_get(url, **_kwargs):
        requested_urls.append(url)
        if url.endswith("/dolares/blue"):
            quote = _quote("USD")
            quote["casa"] = "blue"
            return _FakeResponse(quote)
        if url.endswith("/cotizaciones"):
            return _FakeResponse(
                [
                    _quote("USD"),
                    _quote("EUR"),
                    {**_quote("EUR"), "casa": "blue", "compra": 999.0, "venta": 999.0},
                    _quote("BRL"),
                    _quote("CLP"),
                    _quote("UYU"),
                    _quote("BTC"),
                ]
            )
        raise AssertionError(f"unexpected endpoint requested: {url}")

    monkeypatch.setattr(fx_service.httpx, "get", fake_get)

    blue = fx_service.get_conversion_quote_sync("USD", "blue")
    euro = fx_service.get_conversion_quote_sync("EUR", "blue")

    assert blue["moneda"] == "USD"
    assert euro["moneda"] == "EUR"
    assert euro["casa"] == "oficial"
    assert euro["compra"] == 100.0
    assert requested_urls == [
        "https://dolarapi.com/v1/dolares/blue",
        "https://dolarapi.com/v1/cotizaciones",
    ]
    assert fx_service.get_conversion_quote_sync("USD", "tarjeta") is None


def test_stale_selected_usd_quote_fails_closed_without_requesting_official_fallback(monkeypatch):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()
    fx_service._cache.clear()
    fx_service._cache.update({"data": {}, "fetched_at_by_key": {}})
    requested_urls = []
    stale = _quote("USD", updated_at=datetime.now(timezone.utc) - timedelta(days=3))

    def fake_get(url, **_kwargs):
        requested_urls.append(url)
        return _FakeResponse(stale)

    monkeypatch.setattr(fx_service.httpx, "get", fake_get)

    assert fx_service.get_conversion_quote_sync("USD", "blue") is None
    assert requested_urls == ["https://dolarapi.com/v1/dolares/blue"]


@pytest.mark.parametrize(
    ("rate_type", "payload"),
    [
        ("oficial", {**_quote("USD"), "casa": "blue"}),
        ("blue", {**_quote("USD"), "casa": "tarjeta"}),
        ("oficial", _quote("EUR")),
    ],
)
def test_usd_conversion_rejects_provider_quote_for_wrong_currency_or_market(
    monkeypatch, rate_type, payload
):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(fx_service.httpx, "get", lambda *_args, **_kwargs: _FakeResponse(payload))

    assert fx_service.get_conversion_quote_sync("USD", rate_type) is None
    assert fx_service._cache["data"] == {}


def test_display_refresh_does_not_cache_usd_payloads_with_wrong_market_or_currency(
    monkeypatch,
):
    monkeypatch.setenv("EXTERNAL_EFFECTS_ENABLED", "true")
    monkeypatch.setenv("CONNECTIONS_ENABLED", "true")
    get_settings.cache_clear()

    async def fake_get(url):
        if url.endswith("/dolares/oficial"):
            return {**_quote("USD"), "casa": "blue"}
        if url.endswith("/dolares/blue"):
            return _quote("EUR")
        return [_quote("EUR"), _quote("BRL"), _quote("CLP"), _quote("UYU")]

    monkeypatch.setattr(fx_service, "_get_async", fake_get)
    rates = asyncio.run(fx_service.fetch_all_rates())

    assert "oficial" not in rates
    assert "blue" not in rates
    assert set(rates) == {"eur", "brl", "clp", "uyu"}
    assert "oficial" not in fx_service._cache["data"]
    assert "blue" not in fx_service._cache["data"]
