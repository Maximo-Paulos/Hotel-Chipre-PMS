"""Freshness metadata for analytics responses and derived read models."""

from __future__ import annotations

from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


def _as_utc_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def annotate_analytics_payload(
    payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Add honest source freshness without changing the analytics data.

    PostgreSQL-backed responses use their calculation timestamp as ``data_as_of``.
    Cached or warehouse-backed responses may provide an older ``data_as_of`` and
    explicit lag; those values are preserved so consumers never mistake a derived
    read model for current transactional truth.
    """

    observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    generated_at = _as_utc_datetime(payload.get("generated_at")) or observed_at
    data_as_of = _as_utc_datetime(payload.get("data_as_of")) or generated_at

    explicit_lag = payload.get("source_lag_seconds")
    try:
        source_lag = float(explicit_lag) if explicit_lag is not None else None
    except (TypeError, ValueError):
        source_lag = None
    if source_lag is None or not isfinite(source_lag) or source_lag < 0:
        source_lag = max(0.0, (observed_at - data_as_of).total_seconds())

    data_source = payload.get("data_source") or "postgresql"
    if not isinstance(data_source, str) or not data_source.strip():
        data_source = "postgresql"

    return {
        **payload,
        "data_as_of": data_as_of,
        "source_lag_seconds": source_lag,
        "data_source": data_source.strip().lower(),
    }
