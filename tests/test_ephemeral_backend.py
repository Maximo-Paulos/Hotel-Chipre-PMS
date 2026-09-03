from app.config import Settings, get_settings
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
