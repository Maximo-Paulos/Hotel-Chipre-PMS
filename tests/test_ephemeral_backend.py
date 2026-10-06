from app.config import get_settings
from app.infrastructure import redis_backend


def test_namespaced_key_is_opt_in_for_legacy_local_doubles(monkeypatch):
    monkeypatch.setenv("REDIS_NAMESPACE", "hotel-pms:test")
    get_settings.cache_clear()
    assert redis_backend.namespaced_key("hotel:1:events") == "hotel-pms:test:hotel:1:events"
    get_settings.cache_clear()


def test_shared_sync_client_reuses_pool(monkeypatch):
    clients = []

    class FakeRedis:
        pass

    monkeypatch.setattr(
        redis_backend.redis.Redis,
        "from_url",
        lambda *args, **kwargs: clients.append(FakeRedis()) or clients[-1],
    )
    monkeypatch.setattr(redis_backend, "_sync_client", None)
    monkeypatch.setattr(redis_backend, "_sync_signature", None)
    monkeypatch.setenv("REDIS_URL", "redis://shared.test/0")
    get_settings.cache_clear()
    first = redis_backend.get_sync_redis_client(capability="cache")
    second = redis_backend.get_sync_redis_client(capability="events")
    assert first is second
    assert len(clients) == 1
    get_settings.cache_clear()


def test_realtime_fast_fail_client_isolated_from_general_redis_timeouts(monkeypatch):
    constructor_kwargs = []

    class FakeRedis:
        pass

    def build_client(*_args, **kwargs):
        constructor_kwargs.append(kwargs)
        return FakeRedis()

    monkeypatch.setattr(redis_backend.redis.Redis, "from_url", build_client)
    monkeypatch.setattr(redis_backend, "_sync_client", None)
    monkeypatch.setattr(redis_backend, "_sync_signature", None)
    monkeypatch.setattr(redis_backend, "_sync_realtime_fast_fail_client", None)
    monkeypatch.setattr(redis_backend, "_sync_realtime_fast_fail_signature", None)
    monkeypatch.setenv("REDIS_URL", "redis://profile.test/0")
    monkeypatch.setenv("REDIS_CONNECT_TIMEOUT_SECONDS", "0.8")
    monkeypatch.setenv("REDIS_SOCKET_TIMEOUT_SECONDS", "0.6")
    get_settings.cache_clear()

    try:
        general_client = redis_backend.get_sync_redis_client(capability="general")
        realtime_client = redis_backend.get_sync_redis_client(capability="realtime")
        fast_fail_client = redis_backend.get_sync_redis_client(capability="realtime_fast_fail")

        assert general_client is realtime_client
        assert fast_fail_client is not general_client
        assert fast_fail_client is redis_backend.get_sync_redis_client(capability="realtime_fast_fail")
        assert len(constructor_kwargs) == 2
        assert constructor_kwargs[0]["socket_connect_timeout"] == 0.8
        assert constructor_kwargs[0]["socket_timeout"] == 0.6
        assert constructor_kwargs[1]["socket_connect_timeout"] == 0.25
        assert constructor_kwargs[1]["socket_timeout"] == 0.25
    finally:
        get_settings.cache_clear()
        redis_backend.reset_clients()
