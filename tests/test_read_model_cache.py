from datetime import date
from concurrent.futures import ThreadPoolExecutor
import json
from threading import Event
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.services import read_model_cache


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl_seconds: int, value: str):
        self.store[key] = value
        self.ttls[key] = ttl_seconds

    def scan_iter(self, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self.store):
            if key.startswith(prefix):
                yield key

    def delete(self, *keys: str):
        for key in keys:
            self.store.pop(key, None)
            self.ttls.pop(key, None)


class BrokenRedis:
    def get(self, key: str):
        raise ConnectionError("redis unavailable")

    def setex(self, key: str, ttl_seconds: int, value: str):
        raise ConnectionError("redis unavailable")


@pytest.fixture(autouse=True)
def isolate_read_model_cache(monkeypatch):
    # Keep tests independent of developer or CI environment cache flags.
    monkeypatch.setattr(read_model_cache, "_settings", lambda: _cache_settings())
    read_model_cache._local_read_model_cache.clear()
    read_model_cache._local_read_model_inflight.clear()
    yield
    read_model_cache._local_read_model_cache.clear()
    read_model_cache._local_read_model_inflight.clear()


def _cache_settings(**overrides):
    values = {
        "READ_MODEL_CACHE_ENABLED": True,
        "READ_MODEL_CACHE_FAILURE_COOLDOWN_SECONDS": 30,
        "REDIS_URL": "redis://cache.test:6379/0",
        "READ_MODEL_AVAILABILITY_TTL_SECONDS": 15,
        "READ_MODEL_ANALYTICS_TTL_SECONDS": 60,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _reset_cache_client_state(monkeypatch):
    monkeypatch.setattr(read_model_cache, "_redis_client", None, raising=False)
    monkeypatch.setattr(read_model_cache, "_redis_client_url", None, raising=False)
    monkeypatch.setattr(read_model_cache, "_redis_unavailable_until", 0.0, raising=False)
    monkeypatch.setattr(read_model_cache, "_redis_was_unavailable", False, raising=False)
    monkeypatch.setattr(read_model_cache, "_redis_availability_known", False, raising=False)


def test_availability_payload_is_cached(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    calls = {"count": 0}

    def producer():
        calls["count"] += 1
        return {"status": "ok", "count": 2, "available_rooms": [101, 102]}

    first = read_model_cache.get_cached_availability_payload(
        hotel_id=1,
        category_id=4,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        producer=producer,
    )
    second = read_model_cache.get_cached_availability_payload(
        hotel_id=1,
        category_id=4,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        producer=producer,
    )

    assert first == {"status": "ok", "count": 2, "available_rooms": [101, 102]}
    assert second == first
    assert calls["count"] == 1


def test_cache_miss_calls_producer(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    calls = {"count": 0}

    def producer():
        calls["count"] += 1
        return {"summary": {"rooms": 12}}

    payload = read_model_cache.get_cached_starter_summary_payload(
        hotel_id=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 3),
        producer=producer,
    )

    assert payload == {"summary": {"rooms": 12}}
    assert calls["count"] == 1
    assert len(fake_redis.store) == 1


def test_redis_down_falls_back_to_producer_without_raising(monkeypatch):
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: BrokenRedis())

    payload = read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=True,
        compare_yoy=False,
        producer=lambda: {"data": {"status": "fresh"}},
    )

    assert payload == {"data": {"status": "fresh"}}


def test_cache_disabled_returns_computed_value_without_constructing_redis(monkeypatch):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.setattr(
        read_model_cache,
        "_settings",
        lambda: _cache_settings(READ_MODEL_CACHE_ENABLED=False),
    )

    def fail_if_constructed(*_args, **_kwargs):
        raise AssertionError("Redis must not be constructed when cache is disabled")

    monkeypatch.setattr(read_model_cache.redis.Redis, "from_url", fail_if_constructed)

    assert read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=lambda: {"data": {"status": "computed"}},
    ) == {"data": {"status": "computed"}}


def test_disabled_redis_uses_short_hotel_scoped_analytics_fallback(monkeypatch):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.setattr(
        read_model_cache,
        "_settings",
        lambda: _cache_settings(READ_MODEL_CACHE_ENABLED=False),
    )
    clock = [100.0]
    monkeypatch.setattr(read_model_cache.time, "monotonic", lambda: clock[0])
    calls = {"hotel_one": 0, "hotel_two": 0}

    def first_hotel_payload():
        calls["hotel_one"] += 1
        return {"value": calls["hotel_one"]}

    def second_hotel_payload():
        calls["hotel_two"] += 1
        return {"value": calls["hotel_two"]}

    get_payload = read_model_cache.get_cached_home_payload
    first = get_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=first_hotel_payload,
    )
    repeated = get_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=first_hotel_payload,
    )
    second_hotel = get_payload(
        hotel_id=2,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=second_hotel_payload,
    )

    assert first == repeated == {"value": 1}
    assert second_hotel == {"value": 1}
    assert calls == {"hotel_one": 1, "hotel_two": 1}

    read_model_cache.invalidate_hotel_analytics_cache(1)
    refreshed = get_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=first_hotel_payload,
    )
    assert refreshed == {"value": 2}
    assert calls == {"hotel_one": 2, "hotel_two": 1}

    clock[0] += read_model_cache._LOCAL_READ_MODEL_TTL_SECONDS + 0.01
    expired = get_payload(
        hotel_id=2,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=second_hotel_payload,
    )
    assert expired == {"value": 2}
    assert calls == {"hotel_one": 2, "hotel_two": 2}


def test_concurrent_local_cache_misses_share_one_sql_producer():
    calls = {"count": 0}
    producer_started = Event()
    release_producer = Event()

    def producer():
        calls["count"] += 1
        producer_started.set()
        assert release_producer.wait(timeout=2)
        return {"summary": {"rooms": 12}}

    with ThreadPoolExecutor(max_workers=8) as executor:
        requests = [
            executor.submit(read_model_cache._get_local_cached_or_compute, "hotel:1:summary", producer)
            for _ in range(8)
        ]
        assert producer_started.wait(timeout=2)
        release_producer.set()
        results = [request.result(timeout=2) for request in requests]

    assert calls == {"count": 1}
    assert results == [{"summary": {"rooms": 12}}] * 8


def test_availability_is_not_cached_in_process_when_redis_is_disabled(monkeypatch):
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: None)
    monkeypatch.setattr(
        read_model_cache,
        "_settings",
        lambda: _cache_settings(READ_MODEL_CACHE_ENABLED=False),
    )
    calls = [0]

    def producer():
        calls[0] += 1
        return {"available": calls[0]}

    args = {
        "hotel_id": 1,
        "category_id": 4,
        "check_in": date(2026, 4, 1),
        "check_out": date(2026, 4, 3),
    }
    assert read_model_cache.get_cached_availability_payload(producer=producer, **args) == {"available": 1}
    assert read_model_cache.get_cached_availability_payload(producer=producer, **args) == {"available": 2}
    assert calls[0] == 2


def test_local_fallback_ttl_starts_after_producer_finishes(monkeypatch):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.setattr(
        read_model_cache,
        "_settings",
        lambda: _cache_settings(READ_MODEL_CACHE_ENABLED=False),
    )
    clock = [100.0]
    monkeypatch.setattr(read_model_cache.time, "monotonic", lambda: clock[0])
    calls = [0]

    def producer():
        calls[0] += 1
        clock[0] += 1.5
        return {"value": calls[0]}

    get_payload = read_model_cache.get_cached_home_payload
    args = {
        "hotel_id": 1,
        "date_from": None,
        "date_to": None,
        "currency_display": "ARS",
        "compare_previous": False,
        "compare_yoy": False,
    }
    assert get_payload(producer=producer, **args) == {"value": 1}
    assert get_payload(producer=producer, **args) == {"value": 1}
    assert calls[0] == 1


def test_default_setting_skips_redis_for_read_and_invalidation(monkeypatch):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.delenv("READ_MODEL_CACHE_ENABLED", raising=False)
    monkeypatch.setattr(read_model_cache, "_settings", lambda: Settings(_env_file=None))

    def fail_if_constructed(*_args, **_kwargs):
        raise AssertionError("Redis must stay unused while read caching is disabled")

    monkeypatch.setattr(read_model_cache.redis.Redis, "from_url", fail_if_constructed)
    assert read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=lambda: {"data": {"status": "computed"}},
    ) == {"data": {"status": "computed"}}

    read_model_cache.invalidate_hotel_operational_caches(1)


def test_redis_client_uses_configured_bounded_timeouts(monkeypatch):
    _reset_cache_client_state(monkeypatch)
    settings = _cache_settings(
        REDIS_CONNECT_TIMEOUT_SECONDS=0.4,
        REDIS_SOCKET_TIMEOUT_SECONDS=0.7,
    )
    monkeypatch.setattr(read_model_cache, "_settings", lambda: settings)
    fake_redis = FakeRedis()
    constructor_calls = []

    def build_client(*args, **kwargs):
        constructor_calls.append((args, kwargs))
        return fake_redis

    monkeypatch.setattr(read_model_cache.redis.Redis, "from_url", build_client)

    assert read_model_cache._get_redis_client() is fake_redis
    assert constructor_calls == [
        (
            (settings.REDIS_URL,),
            {
                "decode_responses": True,
                "socket_connect_timeout": 0.4,
                "socket_timeout": 0.7,
            },
        )
    ]


def test_unreachable_redis_opens_circuit_and_retries_only_after_cooldown(monkeypatch, caplog):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.setattr(read_model_cache, "_settings", lambda: _cache_settings())
    clock = [100.0]
    redis_client = BrokenRedis()
    constructor_calls = []
    get_calls = [0]
    original_get = redis_client.get

    def get_with_count(key):
        get_calls[0] += 1
        return original_get(key)

    redis_client.get = get_with_count
    monkeypatch.setattr(read_model_cache.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        read_model_cache.redis.Redis,
        "from_url",
        lambda *args, **kwargs: constructor_calls.append((args, kwargs)) or redis_client,
    )

    with caplog.at_level("WARNING", logger="app.services.read_model_cache"):
        first = read_model_cache.get_cached_home_payload(
            hotel_id=1,
            date_from=None,
            date_to=None,
            currency_display="ARS",
            compare_previous=False,
            compare_yoy=False,
            producer=lambda: {"value": 1},
        )
        second = read_model_cache.get_cached_home_payload(
            hotel_id=1,
            date_from=None,
            date_to=None,
            currency_display="ARS",
            compare_previous=False,
            compare_yoy=False,
            producer=lambda: {"value": 2},
        )

    assert first == {"value": 1}
    assert second == {"value": 1}
    assert len(constructor_calls) == 1
    assert constructor_calls[0][1]["socket_connect_timeout"] == 1.0
    assert constructor_calls[0][1]["socket_timeout"] == 1.0
    assert get_calls[0] == 1
    assert [record.message for record in caplog.records].count("read_model_cache.redis_unavailable") == 1

    clock[0] += 31
    third = read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=None,
        date_to=None,
        currency_display="ARS",
        compare_previous=False,
        compare_yoy=False,
        producer=lambda: {"value": 3},
    )

    assert third == {"value": 3}
    assert len(constructor_calls) == 1
    assert get_calls[0] == 2


def test_cache_resumes_and_logs_recovery_after_redis_returns(monkeypatch, caplog):
    _reset_cache_client_state(monkeypatch)
    monkeypatch.setattr(read_model_cache, "_settings", lambda: _cache_settings())
    clock = [100.0]

    class RecoveringRedis:
        def __init__(self):
            self.fail_first_get = True
            self.get_calls = 0
            self.store = {}

        def get(self, key):
            self.get_calls += 1
            if self.fail_first_get:
                self.fail_first_get = False
                raise ConnectionError("redis unavailable")
            return self.store.get(key)

        def setex(self, key, _ttl_seconds, value):
            self.store[key] = value

    redis_client = RecoveringRedis()
    monkeypatch.setattr(read_model_cache.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(read_model_cache.redis.Redis, "from_url", lambda *args, **kwargs: redis_client)
    calls = [0]

    def producer():
        calls[0] += 1
        return {"value": calls[0]}

    with caplog.at_level("INFO", logger="app.services.read_model_cache"):
        first = read_model_cache.get_cached_home_payload(
            hotel_id=1,
            date_from=None,
            date_to=None,
            currency_display="ARS",
            compare_previous=False,
            compare_yoy=False,
            producer=producer,
        )
        clock[0] += 31
        second = read_model_cache.get_cached_home_payload(
            hotel_id=1,
            date_from=None,
            date_to=None,
            currency_display="ARS",
            compare_previous=False,
            compare_yoy=False,
            producer=producer,
        )
        third = read_model_cache.get_cached_home_payload(
            hotel_id=1,
            date_from=None,
            date_to=None,
            currency_display="ARS",
            compare_previous=False,
            compare_yoy=False,
            producer=producer,
        )

    assert first == {"value": 1}
    assert second == {"value": 2}
    assert third == {"value": 2}
    assert calls[0] == 2
    assert redis_client.get_calls == 3
    assert [record.message for record in caplog.records].count("read_model_cache.redis_unavailable") == 1
    assert [record.message for record in caplog.records].count("read_model_cache.redis_available") == 1


def test_ttl_and_serialization_round_trip(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    payload = read_model_cache.get_cached_availability_payload(
        hotel_id=1,
        category_id=4,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        producer=lambda: {"generated_on": date(2026, 4, 1), "rooms": [101]},
    )

    key, raw_value = next(iter(fake_redis.store.items()))

    assert payload == {"generated_on": date(2026, 4, 1), "rooms": [101]}
    assert fake_redis.ttls[key] == read_model_cache._settings().READ_MODEL_AVAILABILITY_TTL_SECONDS
    assert json.loads(raw_value) == {"generated_on": "2026-04-01", "rooms": [101]}

    cached = read_model_cache.get_cached_availability_payload(
        hotel_id=1,
        category_id=4,
        check_in=date(2026, 4, 1),
        check_out=date(2026, 4, 3),
        producer=lambda: {"generated_on": date(2026, 4, 2), "rooms": []},
    )

    assert cached == {"generated_on": "2026-04-01", "rooms": [101]}


def test_operational_payloads_use_distinct_keys_and_ttls(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    calls = {"rate": 0, "report": 0, "grid": 0}

    def rate_producer():
        calls["rate"] += 1
        return {"days": []}

    def report_producer():
        calls["report"] += 1
        return {"report_date": "2026-04-01"}

    def grid_producer():
        calls["grid"] += 1
        return {"rooms": []}

    rate_args = dict(
        hotel_id=1, category_id=4,
        date_from=date(2026, 4, 1), date_to=date(2026, 4, 3),
    )
    grid_args = dict(
        hotel_id=1, date_from=date(2026, 4, 1), date_to=date(2026, 4, 3), role="front_desk",
    )
    assert read_model_cache.get_cached_rate_calendar_payload(producer=rate_producer, **rate_args) == {"days": []}
    assert read_model_cache.get_cached_rate_calendar_payload(producer=rate_producer, **rate_args) == {"days": []}
    assert read_model_cache.get_cached_daily_report_payload(
        hotel_id=1, report_date=date(2026, 4, 1), producer=report_producer,
    ) == {"report_date": "2026-04-01"}
    assert read_model_cache.get_cached_daily_report_payload(
        hotel_id=1,
        report_date=date(2026, 4, 1),
        pending_page=2,
        pending_page_size=50,
        producer=lambda: {"report_date": "2026-04-01", "pending_page": 2},
    ) == {"report_date": "2026-04-01", "pending_page": 2}
    assert read_model_cache.get_cached_daily_report_payload(
        hotel_id=1, report_date=date(2026, 4, 1), producer=report_producer,
    ) == {"report_date": "2026-04-01"}
    assert read_model_cache.get_cached_occupancy_grid_payload(producer=grid_producer, **grid_args) == {"rooms": []}
    assert read_model_cache.get_cached_occupancy_grid_payload(producer=grid_producer, **grid_args) == {"rooms": []}

    assert calls == {"rate": 1, "report": 1, "grid": 1}
    assert set(fake_redis.store) == {
        "hotel:1:rate_calendar:category:4:from:2026-04-01:to:2026-04-03",
        "hotel:1:daily_report:date:2026-04-01:pending_page:1:page_size:50",
        "hotel:1:daily_report:date:2026-04-01:pending_page:2:page_size:50",
        "hotel:1:occupancy_grid:from:2026-04-01:to:2026-04-03:role:front_desk",
    }
    assert fake_redis.ttls["hotel:1:rate_calendar:category:4:from:2026-04-01:to:2026-04-03"] == read_model_cache._settings().READ_MODEL_AVAILABILITY_TTL_SECONDS
    assert fake_redis.ttls[
        "hotel:1:daily_report:date:2026-04-01:pending_page:1:page_size:50"
    ] == read_model_cache._settings().READ_MODEL_ANALYTICS_TTL_SECONDS


def test_operational_invalidation_clears_availability_and_analytics(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    fake_redis.store["hotel:1:availability:category:4:checkin:2026-04-01:checkout:2026-04-03"] = '{"ok": true}'
    fake_redis.store["hotel:1:analytics:starter:from:2026-04-01:to:2026-04-03"] = '{"ok": true}'
    fake_redis.store["hotel:1:rate_calendar:category:4:from:2026-04-01:to:2026-04-03"] = '{"ok": true}'
    fake_redis.store["hotel:1:daily_report:date:2026-04-01"] = '{"ok": true}'
    fake_redis.store["hotel:1:occupancy_grid:from:2026-04-01:to:2026-04-03:role:front_desk"] = '{"ok": true}'
    fake_redis.store["hotel:2:availability:category:4:checkin:2026-04-01:checkout:2026-04-03"] = '{"ok": true}'

    read_model_cache.invalidate_hotel_operational_caches(1)

    assert "hotel:1:availability:category:4:checkin:2026-04-01:checkout:2026-04-03" not in fake_redis.store
    assert "hotel:1:analytics:starter:from:2026-04-01:to:2026-04-03" not in fake_redis.store
    assert "hotel:1:rate_calendar:category:4:from:2026-04-01:to:2026-04-03" not in fake_redis.store
    assert "hotel:1:daily_report:date:2026-04-01" not in fake_redis.store
    assert "hotel:1:occupancy_grid:from:2026-04-01:to:2026-04-03:role:front_desk" not in fake_redis.store
    assert "hotel:2:availability:category:4:checkin:2026-04-01:checkout:2026-04-03" in fake_redis.store


def test_analytics_home_cache_key_varies_by_filter(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    calls = {"count": 0}

    def producer():
        calls["count"] += 1
        return {"data": {"cards": []}, "comparison": {"previous": {"requested": True}}}

    first = read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 5),
        currency_display="ARS",
        compare_previous=True,
        compare_yoy=False,
        producer=producer,
    )
    second = read_model_cache.get_cached_home_payload(
        hotel_id=1,
        date_from=date(2026, 4, 1),
        date_to=date(2026, 4, 5),
        currency_display="USD",
        compare_previous=True,
        compare_yoy=False,
        producer=producer,
    )

    assert first["data"]["cards"] == []
    assert second["data"]["cards"] == []
    assert calls["count"] == 2
