import re
import sqlite3

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.database import (
    _RequestTelemetryQueuePool,
    finish_request_db_metrics,
    get_engine,
    start_request_db_metrics,
)
from app.main import app, request_telemetry


def test_request_timing_and_correlation_id_are_exposed_to_first_party_browser():
    response = TestClient(app).get(
        "/health",
        headers={
            "Origin": "https://app.hotels-pms.com",
            "X-Request-Id": "telemetry-test-123",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == "telemetry-test-123"
    server_timing = response.headers.get("Server-Timing", "")
    assert re.search(r"(?:^|,\s*)app;dur=\d+(?:\.\d+)?(?:,|$)", server_timing)
    exposed_headers = {
        header.strip().lower()
        for header in response.headers.get("Access-Control-Expose-Headers", "").split(",")
    }
    assert {"server-timing", "x-request-id"} <= exposed_headers


def test_request_timing_preserves_existing_server_timing_metrics():
    telemetry_app = FastAPI()
    telemetry_app.middleware("http")(request_telemetry)

    @telemetry_app.get("/upstream-timing")
    async def upstream_timing(response: Response):
        response.headers.append("Server-Timing", "proxy;dur=4.25")
        return {"ok": True}

    response = TestClient(telemetry_app).get("/upstream-timing")

    timing_metrics = response.headers.get_list("Server-Timing")
    assert "proxy;dur=4.25" in timing_metrics
    assert any(re.fullmatch(r"app;dur=\d+(?:\.\d+)?", value) for value in timing_metrics)


def test_request_timing_includes_sql_size_estimate_without_bound_values(caplog):
    telemetry_app = FastAPI()
    telemetry_app.middleware("http")(request_telemetry)
    engine = get_engine("sqlite:///:memory:")

    @telemetry_app.get("/database-query")
    def database_query():
        with engine.connect() as connection:
            connection.execute(text("SELECT :guest_label"), {"guest_label": "Sensitive Guest Name"})
        return {"ok": True}

    try:
        with caplog.at_level("INFO", logger="app.main"):
            response = TestClient(telemetry_app).get("/database-query")
    finally:
        engine.dispose()

    assert response.status_code == 200
    timing_metrics = ",".join(response.headers.get_list("Server-Timing"))
    assert re.search(r"(?:^|,\s*)db;dur=\d+(?:\.\d+)?(?:,|$)", timing_metrics)
    assert re.search(r"(?:^|,\s*)dbmax;dur=\d+(?:\.\d+)?(?:,|$)", timing_metrics)
    assert 'dbq;desc="1 queries"' in timing_metrics
    request_log = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("http.request")
    )
    assert "db_request_bytes_estimate=" in request_log
    assert "db_destination_host=unknown" in request_log
    assert "Sensitive Guest Name" not in request_log


def test_request_pool_checkout_duration_is_recorded():
    pool = _RequestTelemetryQueuePool(
        creator=lambda: sqlite3.connect(":memory:"),
        pool_size=1,
        max_overflow=0,
    )
    token = start_request_db_metrics()
    connection = pool.connect()
    connection.close()
    metrics = finish_request_db_metrics(token)
    pool.dispose()

    assert metrics["pool_checkout_count"] == 1
    assert metrics["pool_checkout_duration_ms"] >= 0
    assert metrics["max_pool_checkout_ms"] >= 0
