from datetime import date
import json

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


def test_operational_invalidation_clears_availability_and_analytics(monkeypatch):
    fake_redis = FakeRedis()
    monkeypatch.setattr(read_model_cache, "_get_redis_client", lambda: fake_redis)

    fake_redis.store["hotel:1:availability:category:4:checkin:2026-04-01:checkout:2026-04-03"] = '{"ok": true}'
    fake_redis.store["hotel:1:analytics:starter:from:2026-04-01:to:2026-04-03"] = '{"ok": true}'
    fake_redis.store["hotel:2:availability:category:4:checkin:2026-04-01:checkout:2026-04-03"] = '{"ok": true}'

    read_model_cache.invalidate_hotel_operational_caches(1)

    assert "hotel:1:availability:category:4:checkin:2026-04-01:checkout:2026-04-03" not in fake_redis.store
    assert "hotel:1:analytics:starter:from:2026-04-01:to:2026-04-03" not in fake_redis.store
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
