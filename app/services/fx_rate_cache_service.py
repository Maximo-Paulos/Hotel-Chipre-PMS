"""Persistence helpers for the public DolarAPI quote cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.fx_rate_cache import FxRateCache
from app.services.fx_service import (
    DERIVED_BLUE_MARKET,
    DIRECT_CURRENCY_CODES,
    USD_RATE_TYPES,
    parse_provider_updated_at,
    quote_is_fresh,
)

FRESH_FX_CACHE_AGE = timedelta(hours=3)
MAX_FX_CACHE_AGE = timedelta(hours=24)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _cache_identity(rate_key: str) -> tuple[str, str] | None:
    normalized = str(rate_key or "").strip().lower()
    if normalized in USD_RATE_TYPES:
        return "USD", normalized
    if normalized.endswith("_blue"):
        currency = normalized[:-5].upper()
        if currency in DIRECT_CURRENCY_CODES:
            return currency, normalized
        return None
    currency = normalized.upper()
    if currency in DIRECT_CURRENCY_CODES:
        return currency, f"{normalized}_oficial"
    return None


def _expected_market(currency: str, market: str) -> str:
    return market if currency == "USD" or market == "oficial" else DERIVED_BLUE_MARKET


def _quote_for_cache_row(row: FxRateCache, *, fallback_used: bool) -> dict:
    observed_at = _as_utc(row.observed_at)
    provider_updated_at = _as_utc(row.provider_updated_at)
    market = str(row.provider_market or "").strip().lower()
    rate_type = str(row.rate_type or "").strip().lower()
    currency = str(row.currency or "").strip().upper()
    quote = {
        "moneda": currency,
        "casa": market,
        "nombre": row.name,
        "compra": float(row.buy),
        "venta": float(row.sell),
        "fechaActualizacion": provider_updated_at.isoformat()
        if provider_updated_at
        else None,
        "_observed_at": observed_at.isoformat() if observed_at else None,
        "_rate_type": rate_type,
        "_derived_blue": bool(row.is_derived),
        "_source_quotes": row.source_quotes,
        "_quote_source": "daily_cache"
        if row.cache_source == "daily"
        else "persisted_cache",
        "_cache_fallback": fallback_used,
    }
    if rate_type.endswith("_blue") and currency != "USD":
        quote["_selected_market"] = "blue"
    return quote


def get_fx_rate_cache_quote(
    db: Session,
    *,
    currency: str,
    market: str,
    max_age: timedelta,
    fallback_used: bool,
    now: datetime | None = None,
) -> dict | None:
    """Return the exact market quote if its response-observed age is allowed."""
    normalized_currency = str(currency or "").strip().upper()
    normalized_market = str(market or "").strip().lower()
    if normalized_currency == "ARS" or normalized_market not in USD_RATE_TYPES:
        return None
    rate_type = (
        normalized_market
        if normalized_currency == "USD"
        else f"{normalized_currency.lower()}_{normalized_market}"
    )
    row = (
        db.query(FxRateCache)
        .filter(
            FxRateCache.currency == normalized_currency,
            FxRateCache.rate_type == rate_type,
        )
        .one_or_none()
    )
    if row is None:
        return None
    observed_at = _as_utc(row.observed_at)
    current = _as_utc(now) or datetime.now(UTC)
    if observed_at is None or current - observed_at > max_age:
        return None
    quote = _quote_for_cache_row(row, fallback_used=fallback_used)
    if not quote_is_fresh(quote, now=current) or quote["casa"] != _expected_market(
        normalized_currency, normalized_market
    ):
        return None
    return quote


def _row_values(
    *,
    currency: str,
    rate_type: str,
    quote: dict,
    observed_at: datetime,
    cache_source: str,
) -> dict | None:
    if not isinstance(quote, dict):
        return None
    provider_market = str(quote.get("casa") or "").strip().lower()
    expected = _expected_market(currency, rate_type.rsplit("_", 1)[-1])
    # USD rate types are plain market names; non-USD rate types end in the
    # selected market (`eur_oficial` or `eur_blue`).
    if currency == "USD":
        expected = rate_type
    if provider_market != expected:
        return None
    stamped = dict(quote)
    stamped.setdefault("_observed_at", observed_at.isoformat())
    if not quote_is_fresh(stamped, now=observed_at):
        return None
    try:
        buy = Decimal(str(quote.get("compra")))
        sell = Decimal(str(quote.get("venta")))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if (
        not buy.is_finite()
        or not sell.is_finite()
        or buy <= 0
        or sell <= 0
        or buy > sell
    ):
        return None
    provider_updated_at = parse_provider_updated_at(
        quote.get("fechaActualizacion") or quote.get("fecha")
    )
    return {
        "currency": currency,
        "rate_type": rate_type,
        "provider_market": provider_market,
        "name": str(quote.get("nombre") or "")[:120] or None,
        "buy": buy,
        "sell": sell,
        "provider_updated_at": provider_updated_at,
        "observed_at": observed_at,
        "is_derived": bool(quote.get("_derived_blue"))
        or provider_market == DERIVED_BLUE_MARKET,
        "source_quotes": quote.get("_source_quotes"),
        "cache_source": cache_source,
    }


def store_supported_fx_rates(
    db: Session,
    rates: dict[str, dict],
    *,
    cache_source: str,
    observed_at: datetime | None = None,
) -> int:
    """Upsert exact supported rates without replacing a newer observation."""
    default_observed_at = _as_utc(observed_at) or datetime.now(UTC)
    stored = 0
    for rate_key, quote in rates.items():
        identity = _cache_identity(rate_key)
        if identity is None:
            continue
        currency, rate_type = identity
        quote_observed_at = (
            parse_provider_updated_at(
                quote.get("_observed_at") if isinstance(quote, dict) else None
            )
            or default_observed_at
        )
        values = _row_values(
            currency=currency,
            rate_type=rate_type,
            quote=quote,
            observed_at=quote_observed_at,
            cache_source=cache_source,
        )
        if values is None:
            continue

        if db.get_bind().dialect.name == "postgresql":
            statement = pg_insert(FxRateCache).values(**values)
            statement = statement.on_conflict_do_update(
                index_elements=[FxRateCache.currency, FxRateCache.rate_type],
                set_={
                    column: getattr(statement.excluded, column)
                    for column in values
                    if column not in {"currency", "rate_type"}
                },
                where=FxRateCache.observed_at <= statement.excluded.observed_at,
            )
            db.execute(statement)
        else:
            # Keep the application adapter-compatible for legacy callers; all
            # database-backed validation and deployments use PostgreSQL.
            row = (
                db.query(FxRateCache)
                .filter(
                    FxRateCache.currency == currency,
                    FxRateCache.rate_type == rate_type,
                )
                .one_or_none()
            )
            if row is None:
                db.add(FxRateCache(**values))
            elif _as_utc(row.observed_at) <= quote_observed_at:
                for column, value in values.items():
                    setattr(row, column, value)
        stored += 1
    return stored
