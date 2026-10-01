from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.services.external_effects_policy import (
    external_connections_enabled,
    require_external_connections,
)

logger = logging.getLogger(__name__)

DOLAR_API_BASE = "https://dolarapi.com/v1"
USD_RATE_TYPES: tuple[str, ...] = ("oficial", "blue")
DIRECT_CURRENCY_CODES: tuple[str, ...] = ("EUR", "BRL", "CLP", "UYU")
OTHER_CURRENCIES: list[str] = [currency.lower() for currency in DIRECT_CURRENCY_CODES]
SUPPORTED_CONVERSION_CURRENCIES = frozenset({"ARS", "USD", *DIRECT_CURRENCY_CODES})
# Kept as a compatibility name for API callers, but intentionally excludes
# tarjeta, MEP, CCL, cripto, mayorista and other USD markets.
RATE_TYPES: list[str] = list(USD_RATE_TYPES)
RATE_CACHE_TTL_SECONDS = 300
MAX_PROVIDER_QUOTE_AGE = timedelta(hours=24)
MAX_PROVIDER_FUTURE_SKEW = timedelta(minutes=5)

_cache: dict = {"data": {}, "fetched_at_by_key": {}}


def _cache_key(currency_code: str, rate_type: str = "oficial") -> str:
    currency = currency_code.strip().upper()
    return rate_type if currency == "USD" else f"currency:{currency}"


def _cached_rate(key: str, *, allow_stale: bool = False) -> Optional[dict]:
    quote = (_cache.get("data") or {}).get(key)
    if not isinstance(quote, dict):
        return None
    fetched_at = (_cache.get("fetched_at_by_key") or {}).get(key, 0)
    if allow_stale or (time.monotonic() - fetched_at) < RATE_CACHE_TTL_SECONDS:
        return quote
    return None


def _store_rate(key: str, quote: dict) -> None:
    _cache.setdefault("data", {})[key] = quote
    _cache.setdefault("fetched_at_by_key", {})[key] = time.monotonic()


def parse_provider_updated_at(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def quote_is_fresh(quote: object, *, now: datetime | None = None) -> bool:
    if not isinstance(quote, dict):
        return False
    try:
        buy = float(quote.get("compra"))
        sell = float(quote.get("venta"))
    except (TypeError, ValueError):
        return False
    if buy <= 0 or sell <= 0:
        return False
    updated_at = parse_provider_updated_at(quote.get("fechaActualizacion") or quote.get("fecha"))
    if updated_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    return current - MAX_PROVIDER_QUOTE_AGE <= updated_at <= current + MAX_PROVIDER_FUTURE_SKEW


def _quote_matches_supported_market(
    quote: object,
    *,
    currency: str,
    market: str,
) -> bool:
    if not isinstance(quote, dict):
        return False
    return (
        str(quote.get("moneda") or "").strip().upper() == currency
        and str(quote.get("casa") or "").strip().lower() == market
    )


async def _get_async(url: str) -> Optional[dict | list]:
    # The gate intentionally precedes AsyncClient construction and DNS/network.
    require_external_connections("DolarAPI FX-rate lookup")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("DolarAPI fetch failed error_type=%s", type(exc).__name__)
        return None


def _extract_direct_quotes(payload: object) -> dict[str, dict]:
    if not isinstance(payload, list):
        return {}
    extracted: dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        currency = str(item.get("moneda") or "").strip().upper()
        # DolarAPI publishes the supported non-USD quotes as casa=oficial.
        # Never invent a blue/M.E.P. equivalent for these currencies.
        quote_type = str(item.get("casa") or "").strip().lower()
        if currency in DIRECT_CURRENCY_CODES and quote_type == "oficial":
            extracted[currency] = item
    return extracted


async def _refresh_supported_rates() -> dict[str, dict]:
    import asyncio

    official_task = asyncio.create_task(_get_async(f"{DOLAR_API_BASE}/dolares/oficial"))
    blue_task = asyncio.create_task(_get_async(f"{DOLAR_API_BASE}/dolares/blue"))
    currencies_task = asyncio.create_task(_get_async(f"{DOLAR_API_BASE}/cotizaciones"))
    official, blue, currencies = await asyncio.gather(official_task, blue_task, currencies_task)

    rates: dict[str, dict] = {}
    for key, payload in (("oficial", official), ("blue", blue)):
        if _quote_matches_supported_market(payload, currency="USD", market=key):
            rates[key] = payload
            _store_rate(key, payload)
    for currency, quote in _extract_direct_quotes(currencies).items():
        key = currency.lower()
        rates[key] = quote
        _store_rate(_cache_key(currency), quote)
    return rates


async def fetch_all_rates() -> dict:
    """Fetch only supported USD markets and direct supported-currency quotes."""
    if not external_connections_enabled():
        # The display endpoint may use last-known in-process values, but only
        # for the explicitly supported quote set. Conversions check freshness.
        return await _cached_supported_rates()

    cached = {
        key: _cached_rate(key if key in USD_RATE_TYPES else f"currency:{key.upper()}")
        for key in (*USD_RATE_TYPES, *(code.lower() for code in DIRECT_CURRENCY_CODES))
    }
    if all(_cached_quote_matches(key, quote) for key, quote in cached.items()):
        return {key: quote for key, quote in cached.items() if quote is not None}

    rates = await _refresh_supported_rates()
    if rates:
        return rates
    # Generic rate display may retain cached data. The conversion path below
    # still enforces provider timestamp freshness and exact market selection.
    return await _cached_supported_rates()


async def _cached_supported_rates() -> dict[str, dict]:
    result: dict[str, dict] = {}
    for key in (*USD_RATE_TYPES, *(code.lower() for code in DIRECT_CURRENCY_CODES)):
        cached = _cached_rate(key if key in USD_RATE_TYPES else f"currency:{key.upper()}", allow_stale=True)
        if _cached_quote_matches(key, cached):
            result[key] = cached
    return result


def _cached_quote_matches(rate_type: str, quote: object) -> bool:
    if rate_type in USD_RATE_TYPES:
        return _quote_matches_supported_market(quote, currency="USD", market=rate_type)
    currency = rate_type.upper()
    return (
        currency in DIRECT_CURRENCY_CODES
        and _quote_matches_supported_market(quote, currency=currency, market="oficial")
    )


async def fetch_rate(rate_type: str) -> Optional[dict]:
    """Fetch an allowed USD market or direct-currency row by its short code."""
    normalized = str(rate_type or "").strip().lower()
    if normalized in USD_RATE_TYPES:
        currency = "USD"
        cache_key = normalized
        url = f"{DOLAR_API_BASE}/dolares/{normalized}"
    elif normalized.upper() in DIRECT_CURRENCY_CODES:
        currency = normalized.upper()
        cache_key = _cache_key(currency)
        url = f"{DOLAR_API_BASE}/cotizaciones"
    else:
        return None

    cached = _cached_rate(cache_key)
    if _cached_quote_matches(normalized, cached):
        return cached
    if not external_connections_enabled():
        stale = _cached_rate(cache_key, allow_stale=True)
        return stale if _cached_quote_matches(normalized, stale) else None
    payload = await _get_async(url)
    if currency == "USD":
        quote = payload if _quote_matches_supported_market(payload, currency="USD", market=normalized) else None
    else:
        quote = _extract_direct_quotes(payload).get(currency)
    if quote:
        _store_rate(cache_key, quote)
    return quote


def get_conversion_quote_sync(currency_code: str, rate_type: str = "oficial") -> Optional[dict]:
    """Get a fresh exact-market quote for automatic conversion.

    USD uses only the selected `/dolares/oficial` or `/dolares/blue` endpoint.
    EUR/BRL/CLP/UYU are read only from their matching `/cotizaciones` row.
    """
    currency = str(currency_code or "").strip().upper()
    if currency not in SUPPORTED_CONVERSION_CURRENCIES - {"ARS"}:
        return None
    if currency == "USD" and rate_type not in USD_RATE_TYPES:
        return None

    cache_key = _cache_key(currency, rate_type)
    cached = _cached_rate(cache_key)
    expected_market = rate_type if currency == "USD" else "oficial"
    cache_identifier = rate_type if currency == "USD" else currency.lower()
    if cached and _cached_quote_matches(cache_identifier, cached) and quote_is_fresh(cached):
        return cached
    if not external_connections_enabled():
        return None

    try:
        require_external_connections("DolarAPI FX conversion quote")
        url = (
            f"{DOLAR_API_BASE}/dolares/{rate_type}"
            if currency == "USD"
            else f"{DOLAR_API_BASE}/cotizaciones"
        )
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        quote = (
            payload
            if currency == "USD" and _quote_matches_supported_market(payload, currency="USD", market=rate_type)
            else None
        )
        if currency != "USD":
            quote = _extract_direct_quotes(payload).get(currency)
        if not quote_is_fresh(quote) or (
            currency != "USD"
            and not _quote_matches_supported_market(quote, currency=currency, market=expected_market)
        ):
            return None
        _store_rate(cache_key, quote)
        # One /cotizaciones response is authoritative for all direct currencies.
        if currency != "USD":
            for direct_currency, direct_quote in _extract_direct_quotes(payload).items():
                _store_rate(_cache_key(direct_currency), direct_quote)
        return quote
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "DolarAPI conversion fetch failed currency=%s rate_type=%s error_type=%s",
            currency,
            rate_type,
            type(exc).__name__,
        )
        return None


async def get_usd_official_rate() -> float:
    return await get_usd_rate_for_type("oficial") or 0.0


async def get_usd_rate_for_type(rate_type: str) -> Optional[float]:
    if rate_type not in USD_RATE_TYPES:
        return None
    data = await fetch_rate(rate_type)
    if data:
        return data.get("venta")
    return None


async def get_all_rates_snapshot() -> dict:
    all_rates = await fetch_all_rates()
    snapshot: dict = {}
    for key, item in all_rates.items():
        if not isinstance(item, dict):
            continue
        snapshot[key] = {
            "compra": item.get("compra"),
            "venta": item.get("venta"),
            "fecha": item.get("fechaActualizacion"),
            "fechaActualizacion": item.get("fechaActualizacion"),
            "casa": item.get("casa"),
            "nombre": item.get("nombre"),
            "moneda": item.get("moneda"),
        }
    return snapshot


def get_cached_rates() -> Optional[dict]:
    if all(
        _cached_rate(key)
        for key in (*USD_RATE_TYPES, *(f"currency:{code}" for code in DIRECT_CURRENCY_CODES))
    ):
        return _cache.get("data")
    return None


def get_rate_sync(rate_type: str = "oficial") -> Optional[float]:
    """Legacy display helper restricted to supported USD markets."""
    normalized = str(rate_type or "").strip().lower()
    if normalized not in USD_RATE_TYPES:
        return None
    cached = _cached_rate(normalized)
    if _cached_quote_matches(normalized, cached):
        return cached.get("venta")
    if not external_connections_enabled():
        cached = _cached_rate(normalized, allow_stale=True)
        return cached.get("venta") if _cached_quote_matches(normalized, cached) else None
    try:
        require_external_connections("DolarAPI FX-rate lookup")
        response = httpx.get(f"{DOLAR_API_BASE}/dolares/{normalized}", timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if not _quote_matches_supported_market(data, currency="USD", market=normalized):
            return None
        _store_rate(normalized, data)
        return data.get("venta")
    except Exception as exc:  # noqa: BLE001
        logger.warning("DolarAPI sync fetch failed rate_type=%s error_type=%s", normalized, type(exc).__name__)
        return None
