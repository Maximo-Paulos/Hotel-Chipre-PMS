from datetime import datetime, timedelta, timezone

from app.services.analytics_freshness import annotate_analytics_payload


def test_live_postgres_payload_exposes_data_as_of_and_zero_source_lag():
    generated_at = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)

    payload = annotate_analytics_payload(
        {
            "hotel_id": 1,
            "generated_at": generated_at,
            "data": {"cards": []},
        },
        now=generated_at,
    )

    assert payload["data_as_of"] == generated_at
    assert payload["source_lag_seconds"] == 0.0
    assert payload["data_source"] == "postgresql"


def test_cached_payload_calculates_lag_without_masking_explicit_warehouse_metadata():
    generated_at = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    now = generated_at + timedelta(seconds=42)

    cached = annotate_analytics_payload(
        {
            "hotel_id": 1,
            "generated_at": generated_at.isoformat(),
            "data": {"cards": []},
        },
        now=now,
    )
    assert cached["data_as_of"] == generated_at
    assert cached["source_lag_seconds"] == 42.0

    warehouse = annotate_analytics_payload(
        {
            "hotel_id": 1,
            "generated_at": generated_at.isoformat(),
            "data_as_of": "2026-07-24T11:58:00+00:00",
            "source_lag_seconds": 120,
            "data_source": "clickhouse",
            "data": {"cards": []},
        },
        now=now,
    )
    assert warehouse["data_as_of"] == datetime(2026, 7, 24, 11, 58, tzinfo=timezone.utc)
    assert warehouse["source_lag_seconds"] == 120.0
    assert warehouse["data_source"] == "clickhouse"


def test_non_finite_explicit_lag_is_recomputed_from_data_as_of():
    generated_at = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
    payload = annotate_analytics_payload(
        {
            "generated_at": generated_at,
            "data_as_of": generated_at,
            "source_lag_seconds": float("nan"),
            "data": {},
        },
        now=generated_at + timedelta(seconds=18),
    )

    assert payload["source_lag_seconds"] == 18.0
