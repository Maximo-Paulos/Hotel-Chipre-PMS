from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.services.distributed_lock as distributed_lock_module
from app.services.distributed_lock import DistributedLockBusy, DistributedLockUnavailable, distributed_lock


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, tuple[str, int | None]] = {}

    def set(self, key: str, value: str, *, nx: bool, ex: int) -> bool:
        if nx and key in self.values:
            return False
        self.values[key] = (value, ex)
        return True

    def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        current = self.values.get(key)
        if current and current[0] == token:
            del self.values[key]
            return 1
        return 0


def _settings(*, required: bool = True):
    return SimpleNamespace(
        DISTRIBUTED_LOCK_ENABLED=True,
        DISTRIBUTED_LOCK_REQUIRED=required,
        DISTRIBUTED_LOCK_DEFAULT_TTL_SECONDS=30,
        REDIS_URL="redis://localhost:6379/0",
    )


def test_lock_is_exclusive_and_releases_only_when_owned(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeRedis()
    monkeypatch.setattr(distributed_lock_module, "_settings", lambda: _settings())
    monkeypatch.setattr(distributed_lock_module, "_get_redis_client", lambda: client)

    with distributed_lock("lock:allocation:1", ttl_seconds=30):
        assert "lock:allocation:1" in client.values
        with pytest.raises(DistributedLockBusy):
            with distributed_lock("lock:allocation:1", ttl_seconds=30):
                pass

    assert "lock:allocation:1" not in client.values


def test_required_lock_fails_closed_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(distributed_lock_module, "_settings", lambda: _settings(required=True))
    monkeypatch.setattr(distributed_lock_module, "_get_redis_client", lambda: None)

    with pytest.raises(DistributedLockUnavailable):
        with distributed_lock("lock:cash_close:1:10", ttl_seconds=30):
            pass


def test_optional_lock_can_degrade_when_redis_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(distributed_lock_module, "_settings", lambda: _settings(required=False))
    monkeypatch.setattr(distributed_lock_module, "_get_redis_client", lambda: None)

    with distributed_lock("lock:cash_close:1:10", ttl_seconds=30):
        pass
