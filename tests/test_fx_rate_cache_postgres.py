from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.fx_rate_cache import FxRateCache
from app.services import pricing_policy_service
from app.services.fx_rate_cache_service import (
    get_fx_rate_cache_quote,
    store_supported_fx_rates,
)
from app.tasks import fx_tasks


def _quote(
    *,
    observed_at: datetime,
    market_updated_at: datetime | None = None,
    sell: float = 1200.0,
) -> dict:
    return {
        "moneda": "USD",
        "casa": "oficial",
        "nombre": "Dólar Oficial",
        "compra": sell - 10,
        "venta": sell,
        "fechaActualizacion": (market_updated_at or observed_at).isoformat(),
        "_observed_at": observed_at.isoformat(),
        "_rate_type": "oficial",
    }


def test_daily_cache_upsert_keeps_one_row_and_never_replaces_newer_observation(
    pg_session,
):
    initial_time = datetime.now(UTC) - timedelta(hours=2)
    newer_time = initial_time + timedelta(minutes=30)
    older_time = initial_time - timedelta(minutes=5)

    assert (
        store_supported_fx_rates(
            pg_session,
            {"oficial": _quote(observed_at=initial_time)},
            cache_source="daily",
        )
        == 1
    )
    assert (
        store_supported_fx_rates(
            pg_session,
            {"oficial": _quote(observed_at=newer_time, sell=1250.0)},
            cache_source="on_demand",
        )
        == 1
    )
    assert (
        store_supported_fx_rates(
            pg_session,
            {"oficial": _quote(observed_at=older_time, sell=900.0)},
            cache_source="daily",
        )
        == 1
    )

    row = (
        pg_session.query(FxRateCache)
        .filter_by(currency="USD", rate_type="oficial")
        .one()
    )
    assert (
        pg_session.query(FxRateCache)
        .filter_by(currency="USD", rate_type="oficial")
        .count()
        == 1
    )
    assert float(row.sell) == 1250.0
    assert row.observed_at.replace(tzinfo=UTC) == newer_time


def test_daily_snapshot_stores_each_supported_currency_and_derived_blue_rate(
    pg_session,
):
    observed_at = datetime.now(UTC)
    rates = {"oficial": _quote(observed_at=observed_at)}
    rates["blue"] = {
        **_quote(observed_at=observed_at, sell=1300.0),
        "casa": "blue",
    }
    for index, currency in enumerate(("EUR", "BRL", "CLP", "UYU"), start=1):
        rates[currency.lower()] = {
            **_quote(observed_at=observed_at, sell=1000.0 + index),
            "moneda": currency,
        }
        rates[f"{currency.lower()}_blue"] = {
            **_quote(observed_at=observed_at, sell=1100.0 + index),
            "moneda": currency,
            "casa": "blue_derivado",
            "_selected_market": "blue",
            "_derived_blue": True,
        }

    assert store_supported_fx_rates(pg_session, rates, cache_source="daily") == 10
    assert pg_session.query(FxRateCache).count() == 10
    euro_blue = get_fx_rate_cache_quote(
        pg_session,
        currency="EUR",
        market="blue",
        max_age=timedelta(hours=24),
        fallback_used=False,
    )
    assert euro_blue is not None
    assert euro_blue["casa"] == "blue_derivado"
    assert euro_blue["_derived_blue"] is True


def test_scheduled_refresh_task_persists_daily_observation(pg_session, monkeypatch):
    observed_at = datetime.now(UTC)

    async def fake_refresh():
        return {"oficial": _quote(observed_at=observed_at)}

    factory = sessionmaker(bind=pg_session.get_bind().engine)
    monkeypatch.setattr(fx_tasks, "dolarapi_rates_enabled", lambda: True)
    monkeypatch.setattr(fx_tasks, "_refresh_supported_rates", fake_refresh)
    monkeypatch.setattr(fx_tasks, "get_session_factory", lambda: factory)

    result = fx_tasks.refresh_daily_rate_cache.run()

    assert result["status"] == "ok"
    assert result["updated"] == 1
    with factory() as verify_db:
        row = (
            verify_db.query(FxRateCache)
            .filter_by(currency="USD", rate_type="oficial")
            .one()
        )
        assert row.cache_source == "daily"
        assert row.observed_at.replace(tzinfo=UTC) == observed_at
        verify_db.delete(row)
        verify_db.commit()


def test_reservation_conversion_checks_provider_before_using_recent_global_cache(
    pg_session, monkeypatch
):
    observed_at = datetime.now(UTC) - timedelta(hours=2)
    store_supported_fx_rates(
        pg_session,
        {
            "oficial": _quote(
                observed_at=observed_at,
                market_updated_at=observed_at - timedelta(days=2),
            )
        },
        cache_source="daily",
    )
    live_observed_at = datetime.now(UTC)
    live_quote = _quote(
        observed_at=live_observed_at,
        market_updated_at=observed_at - timedelta(days=2),
        sell=1230.0,
    )
    provider_calls = []

    def fake_provider(currency, market="oficial"):
        provider_calls.append((currency, market))
        return live_quote

    monkeypatch.setattr(pricing_policy_service, "get_conversion_quote_sync", fake_provider)

    quote = pricing_policy_service._resolve_conversion_quote(
        pg_session,
        hotel_id=1,
        currency="USD",
        market="oficial",
    )

    cached_row = (
        pg_session.query(FxRateCache)
        .filter_by(currency="USD", rate_type="oficial")
        .one()
    )
    assert provider_calls == [("USD", "oficial")]
    assert quote["_cache_fallback"] is False
    assert quote["_quote_source"] == "live_api"
    assert quote["_observed_at"] == live_observed_at.isoformat()
    assert float(cached_row.sell) == 1230.0
    assert cached_row.observed_at.replace(tzinfo=UTC) == live_observed_at


def test_provider_outage_uses_last_saved_quote_up_to_24_hours(pg_session, monkeypatch):
    observed_at = datetime.now(UTC) - timedelta(hours=4)
    store_supported_fx_rates(
        pg_session,
        {
            "oficial": _quote(
                observed_at=observed_at,
                market_updated_at=observed_at - timedelta(days=2),
            )
        },
        cache_source="daily",
    )
    monkeypatch.setattr(
        pricing_policy_service, "get_conversion_quote_sync", lambda *_args: None
    )

    quote = pricing_policy_service._resolve_conversion_quote(
        pg_session,
        hotel_id=1,
        currency="USD",
        market="oficial",
    )

    assert quote["_cache_fallback"] is True
    assert quote["_fallback_reason"] == "provider_unavailable"
    assert quote["_observed_at"] == observed_at.isoformat()


def test_successful_provider_response_with_friday_timestamp_becomes_current_cache(
    pg_session, monkeypatch
):
    market_updated_at = datetime.now(UTC) - timedelta(days=2)
    response = _quote(
        observed_at=datetime.now(UTC), market_updated_at=market_updated_at
    )
    response.pop("_observed_at")
    monkeypatch.setattr(
        pricing_policy_service, "get_conversion_quote_sync", lambda *_args: response
    )

    quote = pricing_policy_service._resolve_conversion_quote(
        pg_session,
        hotel_id=1,
        currency="USD",
        market="oficial",
    )

    row = (
        pg_session.query(FxRateCache)
        .filter_by(currency="USD", rate_type="oficial")
        .one()
    )
    assert quote.get("_cache_fallback", False) is False
    assert quote["_provider_updated_at"] == market_updated_at.isoformat()
    assert row.observed_at.replace(tzinfo=UTC) > market_updated_at


def test_missing_or_expired_cache_blocks_automatic_conversion(pg_session, monkeypatch):
    expired_at = datetime.now(UTC) - timedelta(hours=24, minutes=1)
    pg_session.add(
        FxRateCache(
            currency="USD",
            rate_type="oficial",
            provider_market="oficial",
            buy=1190,
            sell=1200,
            provider_updated_at=expired_at,
            observed_at=expired_at,
            cache_source="daily",
        )
    )
    pg_session.flush()
    monkeypatch.setattr(
        pricing_policy_service, "get_conversion_quote_sync", lambda *_args: None
    )

    with pytest.raises(
        pricing_policy_service.PricingPolicyError, match="respaldo de menos de 24 horas"
    ):
        pricing_policy_service._resolve_conversion_quote(
            pg_session,
            hotel_id=1,
            currency="USD",
            market="oficial",
        )
