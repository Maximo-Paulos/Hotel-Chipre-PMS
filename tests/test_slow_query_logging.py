from types import SimpleNamespace

from sqlalchemy import text

from app import database


def test_slow_query_logging_is_disabled_by_default(monkeypatch, caplog):
    monkeypatch.setattr(database, "_slow_query_threshold_ms", lambda: 0.0)
    engine = database.get_engine("sqlite:///:memory:")

    with caplog.at_level("WARNING", logger="app.database"):
        with engine.connect() as connection:
            connection.execute(text("SELECT :guest_email"), {"guest_email": "guest@example.com"})

    assert "slow query" not in caplog.text


def test_slow_query_logging_omits_bound_values(monkeypatch, caplog):
    ticks = iter((100.0, 100.010))
    monkeypatch.setattr(
        database,
        "time",
        SimpleNamespace(perf_counter=lambda: next(ticks)),
    )
    monkeypatch.setattr(database, "_slow_query_threshold_ms", lambda: 5.0)
    engine = database.get_engine("sqlite:///:memory:")

    with caplog.at_level("WARNING", logger="app.database"):
        with engine.connect() as connection:
            connection.execute(text("SELECT :guest_email"), {"guest_email": "guest@example.com"})

    assert "slow query" in caplog.text
    assert "SELECT ?" in caplog.text
    assert "guest@example.com" not in caplog.text
