from __future__ import annotations

from datetime import date

import pytest

from app.config import Settings
from app.services import analytics_warehouse


class FakeWarehouseClient:
    def __init__(self, warehouse_count: int = 0):
        self.warehouse_count = warehouse_count
        self.queries: list[tuple[str, dict]] = []
        self.inserted: list[dict] = []

    def execute(self, query: str, params: dict | None = None):
        self.queries.append((query, params or {}))
        if "count()" in query.lower():
            return [[self.warehouse_count]]
        return []

    def insert_json_each_row(self, table: str, rows: list[dict], *, version: str):
        self.inserted.extend(rows)
        self.queries.append((f"INSERT {table}", {"version": version}))


def _settings(**overrides) -> Settings:
    values = {
        "CLICKHOUSE_ENABLED": True,
        "CLICKHOUSE_REQUIRED": True,
        "CLICKHOUSE_URL": "https://clickhouse.qa.example.test:8443",
        "CLICKHOUSE_DATABASE": "hotel_analytics",
        "CLICKHOUSE_USER": "qa_user",
        "CLICKHOUSE_PASSWORD": "qa_password",
    }
    values.update(overrides)
    return Settings(**values)


def test_clickhouse_schema_is_derived_and_tenant_partitioned(monkeypatch: pytest.MonkeyPatch):
    fake = FakeWarehouseClient()
    monkeypatch.setattr(analytics_warehouse, "_settings", lambda: _settings())

    analytics_warehouse.ensure_schema(fake)

    joined = "\n".join(query for query, _ in fake.queries)
    assert "ReplacingMergeTree" in joined
    assert "hotel_id" in joined
    assert "guest" not in joined.lower()
    assert "password" not in joined.lower()


def test_build_reservation_fact_row_is_pii_free_and_stable():
    row = analytics_warehouse.build_reservation_fact_row(
        {
            "hotel_id": 7,
            "reservation_id": 11,
            "stay_date": date(2026, 7, 24),
            "room_id": 3,
            "category_id": 2,
            "revenue_gross_ars": 1000,
            "status": "confirmed",
            "guest_name": "must not be copied",
            "email": "guest@example.test",
        }
    )

    assert row == {
        "hotel_id": 7,
        "reservation_id": 11,
        "stay_date": "2026-07-24",
        "room_id": 3,
        "category_id": 2,
        "revenue_gross_ars": 1000,
        "status": "confirmed",
    }
    assert "guest_name" not in row
    assert "email" not in row


def test_reconcile_compares_source_and_derived_counts():
    fake = FakeWarehouseClient(warehouse_count=2)
    result = analytics_warehouse.reconcile_reservation_fact_counts(
        fake,
        hotel_id=7,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
        source_count=2,
    )
    assert result.ok is True
    assert result.source_count == result.warehouse_count == 2

    mismatch = analytics_warehouse.reconcile_reservation_fact_counts(
        FakeWarehouseClient(warehouse_count=1),
        hotel_id=7,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
        source_count=2,
    )
    assert mismatch.ok is False
    assert mismatch.difference == 1


def test_required_warehouse_configuration_fails_closed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(analytics_warehouse, "_settings", lambda: _settings(CLICKHOUSE_URL=""))
    with pytest.raises(analytics_warehouse.AnalyticsWarehouseUnavailable):
        analytics_warehouse.get_clickhouse_client()
