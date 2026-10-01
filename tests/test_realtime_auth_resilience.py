from sqlalchemy.exc import TimeoutError as SQLAlchemyTimeoutError

from app.api import events


def test_realtime_auth_uses_recent_positive_check_during_pool_timeout(monkeypatch):
    now = [100.0]
    monkeypatch.setattr(events.time, "monotonic", lambda: now[0])

    def unavailable_session():
        raise SQLAlchemyTimeoutError("pool exhausted")

    monkeypatch.setattr(events, "get_session_factory", lambda: unavailable_session)
    check_authorization = events._build_authorization_check(hotel_id=12, user_id=34)

    assert check_authorization() is True
    now[0] += 60
    assert check_authorization() is True
    now[0] += 0.1
    assert check_authorization() is False


def test_realtime_auth_still_closes_stream_for_explicitly_inactive_member(monkeypatch):
    class Query:
        def filter(self, *_conditions):
            return self

        def one_or_none(self):
            return None

    class Session:
        closed = False

        def query(self, _model):
            return Query()

        def close(self):
            self.closed = True

    db = Session()
    monkeypatch.setattr(events, "get_session_factory", lambda: lambda: db)
    monkeypatch.setattr(events, "set_tenant_user_context", lambda *_args: None)
    check_authorization = events._build_authorization_check(hotel_id=12, user_id=34)

    assert check_authorization() is False
    assert db.closed
