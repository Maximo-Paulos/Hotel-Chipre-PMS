from datetime import datetime, timedelta, timezone

import pytest

from app.services.fx_service import _as_cached_fallback_quote


@pytest.mark.parametrize(
    ("age", "expected_status"),
    [
        (timedelta(hours=23), "outage_fallback_24h"),
        (timedelta(hours=24, minutes=1), "stale"),
        (None, "stale"),
    ],
)
def test_cached_display_quote_reports_24_hour_fallback_window(age, expected_status):
    observed_at = datetime.now(timezone.utc) - age if age is not None else None
    quote = {
        "moneda": "USD",
        "compra": 1000,
        "venta": 1010,
        "_observed_at": observed_at.isoformat() if observed_at else None,
    }

    result = _as_cached_fallback_quote(quote)

    assert result["quote_status"] == expected_status
    assert result["_cache_fallback"] is True
    assert "quote_status" not in quote
