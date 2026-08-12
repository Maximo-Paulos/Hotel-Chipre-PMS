from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.services.external_effects_policy import (
    external_connections_enabled,
    require_external_connections,
)

logger = logging.getLogger(__name__)

DOLAR_API_BASE = "https://dolarapi.com"

RATE_TYPES: list[str] = [
    "oficial",
    "blue",
    "bolsa",
    "contadoconliqui",
    "tarjeta",
    "mayorista",
    "cripto",
]

OTHER_CURRENCIES: list[str] = ["eur", "brl", "clp", "uyu"]
RATE_CACHE_TTL_SECONDS = 300

_cache: dict = {}


def _is_cache_fresh() -> bool:
    if not _cache:
        return False
    return (time.monotonic() - _cache.get("fetched_at", 0)) < RATE_CACHE_TTL_SECONDS


async def _get_async(url: str) -> Optional[dict | list]:
    # The gate intentionally precedes AsyncClient construction and DNS/network.
    require_external_connections("DolarAPI FX-rate lookup")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DolarAPI fetch failed for %s: %s", url, exc)
        return None


async def fetch_all_rates() -> dict:
    import asyncio

    if not external_connections_enabled():
        # A closed sandbox may use an already-populated in-process cache, but it
        # never refreshes it and never treats stale data as newly fetched.
        return dict(_cache.get("data") or {})

    dollar_task = asyncio.create_task(_get_async(f"{DOLAR_API_BASE}/d%C3%B3lares"))
    other_task = asyncio.create_task(_get_async(f"{DOLAR_API_BASE}/cotizaciones"))
    dollar_data, other_data = await asyncio.gather(dollar_task, other_task)

    rates: dict = {}

    if isinstance(dollar_data, list):
        for item in dollar_data:
            key = (item.get("casa") or item.get("nombre") or "").lower().replace(" ", "_")
            if key:
                rates[key] = item
    elif isinstance(dollar_data, dict):
        key = (dollar_data.get("casa") or dollar_data.get("nombre") or "usd").lower()
        rates[key] = dollar_data

    if isinstance(other_data, list):
        for item in other_data:
            key = (item.get("moneda") or item.get("nombre") or "").lower()
            if key:
                rates[key] = item
    elif isinstance(other_data, dict):
        key = (other_data.get("moneda") or other_data.get("nombre") or "other").lower()
        rates[key] = other_data

    if rates:
        _cache["data"] = rates
        _cache["fetched_at"] = time.monotonic()
    elif _cache.get("data"):
        logger.warning("DolarAPI returned no data; serving stale cache.")
        rates = _cache["data"]

    return rates


async def fetch_rate(rate_type: str) -> Optional[dict]:
    if rate_type not in RATE_TYPES:
        logger.warning("Unknown rate_type '%s'; must be one of %s", rate_type, RATE_TYPES)
        return None
    if not external_connections_enabled():
        cached = (_cache.get("data") or {}).get(rate_type)
        return cached if isinstance(cached, dict) else None
    return await _get_async(f"{DOLAR_API_BASE}/d%C3%B3lar/{rate_type}")  # type: ignore[return-value]


async def get_usd_official_rate() -> float:
    return await get_usd_rate_for_type("oficial") or 0.0


async def get_usd_rate_for_type(rate_type: str) -> Optional[float]:
    if _is_cache_fresh():
        cached = _cache["data"].get(rate_type)
        if cached:
            return cached.get("venta")

    data = await fetch_rate(rate_type)
    if data:
        if not _cache.get("data"):
            _cache["data"] = {}
        _cache["data"][rate_type] = data
        _cache.setdefault("fetched_at", time.monotonic())
        return data.get("venta")
    return None


async def get_all_rates_snapshot() -> dict:
    all_rates = await fetch_all_rates()
    snapshot: dict = {}
    for key, item in all_rates.items():
        snapshot[key] = {
            "compra": item.get("compra"),
            "venta": item.get("venta"),
            "fecha": item.get("fechaActualizacion"),
            "nombre": item.get("nombre"),
            "moneda": item.get("moneda"),
        }
    return snapshot


def get_cached_rates() -> Optional[dict]:
    if _is_cache_fresh():
        return _cache.get("data")
    return None


def get_rate_sync(rate_type: str = "oficial") -> Optional[float]:
    if rate_type not in RATE_TYPES:
        logger.warning("Unknown rate_type '%s'", rate_type)
        return None

    if _is_cache_fresh():
        cached = _cache["data"].get(rate_type)
        if cached:
            return cached.get("venta")

    if not external_connections_enabled():
        # Stale cache is the only permitted fallback while the lane is closed.
        cached = (_cache.get("data") or {}).get(rate_type)
        return cached.get("venta") if isinstance(cached, dict) else None

    try:
        require_external_connections("DolarAPI FX-rate lookup")
        response = httpx.get(f"{DOLAR_API_BASE}/d%C3%B3lar/{rate_type}", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if not _cache.get("data"):
            _cache["data"] = {}
        _cache["data"][rate_type] = data
        _cache.setdefault("fetched_at", time.monotonic())
        return data.get("venta")
    except Exception as exc:  # noqa: BLE001
        logger.warning("DolarAPI sync fetch failed for %s: %s", rate_type, exc)
        return None
