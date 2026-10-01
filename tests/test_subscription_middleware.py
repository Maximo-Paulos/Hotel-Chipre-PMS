import asyncio
from types import SimpleNamespace

import pytest

from app.middleware import subscription
from app.middleware.subscription import SubscriptionEnforcementMiddleware


class _Session:
    def __init__(self):
        self.closed = False

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        self.closed = True


@pytest.mark.parametrize("can_write", [True, False])
def test_subscription_session_closes_before_asgi_work(monkeypatch, can_write):
    db = _Session()
    inner_calls = []
    sent_messages = []
    monkeypatch.setattr(
        subscription,
        "get_settings",
        lambda: SimpleNamespace(SUBSCRIPTION_ENFORCEMENT=True, SUBSCRIPTION_ENFORCEMENT_ENABLED=False),
    )
    monkeypatch.setattr(subscription, "get_session_factory", lambda: lambda: db)
    monkeypatch.setattr(subscription, "set_tenant_hotel_context", lambda *_args: None)
    monkeypatch.setattr(
        subscription,
        "get_subscription_snapshot",
        lambda *_args: {"dirty": False, "plan": "pro", "status": "active"},
    )
    monkeypatch.setattr(
        subscription,
        "evaluate_hotel_write_access",
        lambda *_args, **_kwargs: SimpleNamespace(can_write=can_write, reason="test"),
    )

    async def app(_scope, _receive, _send):
        inner_calls.append(db.closed)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        assert db.closed
        sent_messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/api/reservations",
        "raw_path": b"/api/reservations",
        "query_string": b"",
        "headers": [(b"x-hotel-id", b"12")],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }

    asyncio.run(SubscriptionEnforcementMiddleware(app)(scope, receive, send))

    assert db.closed
    if can_write:
        assert inner_calls == [True]
        assert sent_messages == []
    else:
        assert inner_calls == []
        assert sent_messages[0]["status"] == 402
