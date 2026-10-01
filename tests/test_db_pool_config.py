import re
from pathlib import Path
from types import SimpleNamespace

from app import database
from app.config import Settings


def test_settings_default_to_bounded_api_pool_capacity():
    assert Settings.model_fields["DB_POOL_SIZE"].default == 8
    assert Settings.model_fields["DB_MAX_OVERFLOW"].default == 4
    assert Settings.model_fields["DB_POOL_TIMEOUT_SECONDS"].default == 15.0


def test_postgres_engine_uses_configured_bounded_pool(monkeypatch):
    monkeypatch.setattr(
        database,
        "get_settings",
        lambda: SimpleNamespace(DB_POOL_SIZE=8, DB_MAX_OVERFLOW=4, DB_POOL_TIMEOUT_SECONDS=15.0),
    )
    engine = database.get_engine("postgresql+psycopg2://pms:test@127.0.0.1/hotel_chipre_test")
    try:
        assert engine.pool.size() == 8
        assert engine.pool._max_overflow == 4
        assert engine.pool._timeout == 15.0
    finally:
        engine.dispose()


def _render_service_block(render_yaml: str, service_name: str) -> str:
    blocks = re.split(r"(?m)^  - type:\s*", render_yaml)[1:]
    for block in blocks:
        if re.search(rf"(?m)^    name:\s*{re.escape(service_name)}\s*$", block):
            return block
    raise AssertionError(f"Render service {service_name} is missing")


def _env_value(service_block: str, key: str) -> str:
    match = re.search(
        rf"(?m)^      - key: {re.escape(key)}\s*\n        value: [\"']?([^\"'\n]+)",
        service_block,
    )
    assert match, f"{key} is missing from Render service configuration"
    return match.group(1)


def test_render_pool_budgets_keep_worker_and_beat_reservations():
    render_yaml = Path("render.yaml").read_text(encoding="utf-8")
    services = {
        name: _render_service_block(render_yaml, name)
        for name in ("hotel-chipre-pms-api", "hotel-chipre-pms-worker", "hotel-chipre-pms-beat")
    }

    assert {
        key: _env_value(services["hotel-chipre-pms-api"], key)
        for key in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT_SECONDS")
    } == {"DB_POOL_SIZE": "8", "DB_MAX_OVERFLOW": "4", "DB_POOL_TIMEOUT_SECONDS": "15"}
    worker_pool = {
        key: _env_value(services["hotel-chipre-pms-worker"], key)
        for key in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT_SECONDS")
    }
    assert worker_pool == {"DB_POOL_SIZE": "2", "DB_MAX_OVERFLOW": "0", "DB_POOL_TIMEOUT_SECONDS": "15"}
    assert re.search(r"(?m)^    startCommand: .*--concurrency=4(?:\s|$)", services["hotel-chipre-pms-worker"])

    for name in ("hotel-chipre-pms-beat",):
        assert {
            key: _env_value(services[name], key)
            for key in ("DB_POOL_SIZE", "DB_MAX_OVERFLOW", "DB_POOL_TIMEOUT_SECONDS")
        } == {"DB_POOL_SIZE": "2", "DB_MAX_OVERFLOW": "0", "DB_POOL_TIMEOUT_SECONDS": "15"}

    total_connections = 3 * (8 + 4) + 4 * (2 + 0) + (2 + 0)
    assert total_connections == 46
    assert total_connections < 60
