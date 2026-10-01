from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from app.services.external_effects_policy import (
    dolarapi_rates_enabled,
    require_dolarapi_rates,
)

logger = logging.getLogger(__name__)

DOLAR_API_BASE = "https://dolarapi.com/v1"
USD_RATE_TYPES: tuple[str, ...] = ("oficial", "blue")
DIRECT_CURRENCY_CODES: tuple[str, ...] = ("EUR", "BRL", "CLP", "UYU")
OTHER_CURRENCIES: list[str] = [currency.lower() for currency in DIRECT_CURRENCY_CODES]
SUPPORTED_CONVERSION_CURRENCIES = frozenset({"ARS", "USD", *DIRECT_CURRENCY_CODES})
DERIVED_BLUE_MARKET = "blue_derivado"
DIRECT_CURRENCY_BLUE_RATE_TYPES: tuple[str, ...] = tuple(
    f"{currency.lower()}_blue" for currency in DIRECT_CURRENCY_CODES
)
SUPPORTED_DISPLAY_RATE_TYPES: tuple[str, ...] = (
    *USD_RATE_TYPES,
    *(currency.lower() for currency in DIRECT_CURRENCY_CODES),
    *DIRECT_CURRENCY_BLUE_RATE_TYPES,
)
# Kept as a compatibility name for API callers, but intentionally excludes
# tarjeta, MEP, CCL, cripto, mayorista and other USD markets.
RATE_TYPES: list[str] = list(USD_RATE_TYPES)
RATE_CACHE_TTL_SECONDS = 300
MAX_PROVIDER_QUOTE_AGE = timedelta(hours=24)
MAX_PROVIDER_FUTURE_SKEW = timedelta(minutes=5)

_cache: dict = {"data": {}, "fetched_at_by_key": {}}


def _cache_key(currency_code: str, rate_type: str = "oficial") -> str:
    currency = currency_code.strip().upper()
    if currency == "USD":
        return rate_type
    if rate_type == "oficial":
        # Preserve the original direct-quote cache key for compatibility.
        return f"currency:{currency}"
    return f"currency:{currency}:{rate_type}"


def _cache_key_for_display_rate(rate_type: str) -> str:
    normalized = rate_type.strip().lower()
    if normalized in USD_RATE_TYPES:
        return normalized
    if normalized.endswith("_blue"):
        return _cache_key(normalized[:-5], "blue")
    return _cache_key(normalized.upper(), "oficial")


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
    if not math.isfinite(buy) or not math.isfinite(sell) or buy <= 0 or sell <= 0:
        return False
    updated_at = parse_provider_updated_at(quote.get("fechaActualizacion") or quote.get("fecha"))
    if updated_at is None:
        return False
    current = now or datetime.now(timezone.utc)
    return (
        buy <= sell
        and current - MAX_PROVIDER_QUOTE_AGE <= updated_at <= current + MAX_PROVIDER_FUTURE_SKEW
    )


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


def _quote_matches_conversion_market(
    quote: object,
    *,
    currency: str,
    market: str,
) -> bool:
    if currency == "USD":
        return _quote_matches_supported_market(quote, currency="USD", market=market)
    if market == "oficial":
        return _quote_matches_supported_market(quote, currency=currency, market="oficial")
    return (
        isinstance(quote, dict)
        and str(quote.get("moneda") or "").strip().upper() == currency
        and str(quote.get("casa") or "").strip().lower() == DERIVED_BLUE_MARKET
        and str(quote.get("_selected_market") or "blue").strip().lower() == "blue"
    )


def _derive_blue_equivalent(
    currency: str,
    *,
    direct_quote: object,
    usd_official_quote: object,
    usd_blue_quote: object,
) -> dict | None:
    """Scale a direct DolarAPI quote by the USD blue/official relationship.

    DolarAPI provides blue-market rows only for USD. Other supported currencies
    therefore keep their direct official quote as the source and expose a
    separately labeled blue equivalent derived from the same provider's USD
    official and blue rows.
    """
    if (
        not _quote_matches_supported_market(direct_quote, currency=currency, market="oficial")
        or not _quote_matches_supported_market(usd_official_quote, currency="USD", market="oficial")
        or not _quote_matches_supported_market(usd_blue_quote, currency="USD", market="blue")
        or not quote_is_fresh(direct_quote)
        or not quote_is_fresh(usd_official_quote)
        or not quote_is_fresh(usd_blue_quote)
    ):
        return None
    try:
        direct_buy = float(direct_quote["compra"])
        direct_sell = float(direct_quote["venta"])
        official_buy = float(usd_official_quote["compra"])
        official_sell = float(usd_official_quote["venta"])
        blue_buy = float(usd_blue_quote["compra"])
        blue_sell = float(usd_blue_quote["venta"])
    except (KeyError, TypeError, ValueError):
        return None
    inputs = (direct_buy, direct_sell, official_buy, official_sell, blue_buy, blue_sell)
    if any(not math.isfinite(value) or value <= 0 for value in inputs):
        return None

    update_times = [
        parse_provider_updated_at(item.get("fechaActualizacion") or item.get("fecha"))
        for item in (direct_quote, usd_official_quote, usd_blue_quote)
    ]
    if any(item is None for item in update_times):
        return None
    # A derived quote is only as current as its oldest input.
    effective_update = min(item for item in update_times if item is not None)
    derived_buy = direct_buy * blue_buy / official_buy
    derived_sell = direct_sell * blue_sell / official_sell
    if not math.isfinite(derived_buy) or not math.isfinite(derived_sell) or derived_buy <= 0 or derived_sell <= 0:
        return None
    if derived_buy > derived_sell:
        return None
    return {
        "moneda": currency,
        "casa": DERIVED_BLUE_MARKET,
        "nombre": f"{direct_quote.get('nombre') or currency} (equivalente blue derivado)",
        "compra": derived_buy,
        "venta": derived_sell,
        "fechaActualizacion": effective_update.isoformat(),
        "_selected_market": "blue",
        "_rate_type": f"{currency.lower()}_blue",
        "_derived_blue": True,
        "_source_quotes": {
            "formula_version": "1",
            "formula": "currency_official * usd_blue / usd_official",
            "currency_official": {
                "compra": direct_buy,
                "venta": direct_sell,
                "updated_at": update_times[0].isoformat(),
            },
            "usd_official": {
                "compra": official_buy,
                "venta": official_sell,
                "updated_at": update_times[1].isoformat(),
            },
            "usd_blue": {
                "compra": blue_buy,
                "venta": blue_sell,
                "updated_at": update_times[2].isoformat(),
            },
        },
    }


async def _get_async(url: str) -> Optional[dict | list]:
    # The dedicated public-market-data gate precedes DNS/network. It does not
    # open the general provider-connection lane used by payments or OTA calls.
    require_dolarapi_rates("DolarAPI FX-rate lookup")
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
        # DolarAPI publishes supported non-USD source quotes as casa=oficial.
        # A blue equivalent is derived separately from exact USD official/blue
        # inputs and is never presented as a direct provider quote.
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
    direct_quotes = _extract_direct_quotes(currencies)
    for currency, quote in direct_quotes.items():
        key = currency.lower()
        rates[key] = quote
        _store_rate(_cache_key(currency), quote)
        derived_blue = _derive_blue_equivalent(
            currency,
            direct_quote=quote,
            usd_official_quote=rates.get("oficial"),
            usd_blue_quote=rates.get("blue"),
        )
        if derived_blue is not None:
            blue_key = f"{key}_blue"
            rates[blue_key] = derived_blue
            _store_rate(_cache_key(currency, "blue"), derived_blue)
    return rates


async def fetch_all_rates() -> dict:
    """Fetch USD official/blue quotes and direct/derived supported currencies."""
    if not dolarapi_rates_enabled():
        # The display endpoint may use last-known in-process values, but only
        # for the explicitly supported quote set. Conversions check freshness.
        return await _cached_supported_rates()

    cached = {key: _cached_rate(_cache_key_for_display_rate(key)) for key in SUPPORTED_DISPLAY_RATE_TYPES}
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
    for key in SUPPORTED_DISPLAY_RATE_TYPES:
        cached = _cached_rate(_cache_key_for_display_rate(key), allow_stale=True)
        if _cached_quote_matches(key, cached):
            result[key] = cached
    return result


def _cached_quote_matches(rate_type: str, quote: object) -> bool:
    if rate_type in USD_RATE_TYPES:
        return _quote_matches_supported_market(quote, currency="USD", market=rate_type)
    if rate_type.endswith("_blue"):
        currency = rate_type[:-5].upper()
        return (
            currency in DIRECT_CURRENCY_CODES
            and _quote_matches_conversion_market(quote, currency=currency, market="blue")
        )
    currency = rate_type.upper()
    return (
        currency in DIRECT_CURRENCY_CODES
        and _quote_matches_supported_market(quote, currency=currency, market="oficial")
    )


async def fetch_rate(rate_type: str) -> Optional[dict]:
    """Fetch a USD market, direct official quote, or derived blue equivalent."""
    normalized = str(rate_type or "").strip().lower()
    if normalized in USD_RATE_TYPES:
        currency = "USD"
        cache_key = normalized
        url = f"{DOLAR_API_BASE}/dolares/{normalized}"
    elif normalized.upper() in DIRECT_CURRENCY_CODES:
        currency = normalized.upper()
        cache_key = _cache_key(currency)
        url = f"{DOLAR_API_BASE}/cotizaciones"
    elif normalized.endswith("_blue") and normalized[:-5].upper() in DIRECT_CURRENCY_CODES:
        currency = normalized[:-5].upper()
        cache_key = _cache_key(currency, "blue")
        cached = _cached_rate(cache_key)
        if cached and _cached_quote_matches(normalized, cached):
            return cached
        if not dolarapi_rates_enabled():
            stale = _cached_rate(cache_key, allow_stale=True)
            return stale if _cached_quote_matches(normalized, stale) else None
        return (await _refresh_supported_rates()).get(normalized)
    else:
        return None

    cached = _cached_rate(cache_key)
    if _cached_quote_matches(normalized, cached):
        return cached
    if not dolarapi_rates_enabled():
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
    EUR/BRL/CLP/UYU use their direct official row or a clearly labeled blue
    equivalent derived from that row and the USD blue/official ratio.
    """
    currency = str(currency_code or "").strip().upper()
    market = str(rate_type or "").strip().lower()
    if currency not in SUPPORTED_CONVERSION_CURRENCIES - {"ARS"}:
        return None
    if market not in USD_RATE_TYPES:
        return None

    cache_key = _cache_key(currency, market)
    cached = _cached_rate(cache_key)
    expected_market = market if currency == "USD" or market == "oficial" else DERIVED_BLUE_MARKET
    if (
        cached
        and _quote_matches_conversion_market(cached, currency=currency, market=market)
        and quote_is_fresh(cached)
    ):
        return cached

    if currency != "USD" and market == "blue":
        if not dolarapi_rates_enabled():
            return None
        direct_quote = get_conversion_quote_sync(currency, "oficial")
        official_usd = get_conversion_quote_sync("USD", "oficial")
        blue_usd = get_conversion_quote_sync("USD", "blue")
        derived = _derive_blue_equivalent(
            currency,
            direct_quote=direct_quote,
            usd_official_quote=official_usd,
            usd_blue_quote=blue_usd,
        )
        if derived is not None:
            _store_rate(cache_key, derived)
        return derived

    if not dolarapi_rates_enabled():
        return None

    try:
        require_dolarapi_rates("DolarAPI FX conversion quote")
        url = (
            f"{DOLAR_API_BASE}/dolares/{market}"
            if currency == "USD"
            else f"{DOLAR_API_BASE}/cotizaciones"
        )
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        payload = response.json()
        quote = (
            payload
            if currency == "USD" and _quote_matches_supported_market(payload, currency="USD", market=market)
            else None
        )
        if currency != "USD":
            quote = _extract_direct_quotes(payload).get(currency)
        if not quote_is_fresh(quote) or (
            not _quote_matches_supported_market(quote, currency=currency, market=expected_market)
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
            market,
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
        _cached_rate(_cache_key_for_display_rate(key))
        for key in SUPPORTED_DISPLAY_RATE_TYPES
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
    if not dolarapi_rates_enabled():
        cached = _cached_rate(normalized, allow_stale=True)
        return cached.get("venta") if _cached_quote_matches(normalized, cached) else None
    try:
        require_dolarapi_rates("DolarAPI FX-rate lookup")
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
