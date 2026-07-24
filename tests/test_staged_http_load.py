from __future__ import annotations

from scripts.scale.staged_http_load import percentile, safe_headers


def test_percentile_is_deterministic_for_empty_and_small_samples():
    assert percentile([], 0.95) == 0.0
    assert percentile([10.0], 0.95) == 10.0
    assert percentile([10.0, 20.0, 30.0, 40.0], 0.95) == 40.0


def test_safe_headers_only_include_non_secret_scope_metadata(monkeypatch):
    monkeypatch.setenv("LOADTEST_BEARER_TOKEN", "secret-token-that-must-not-be-printed")
    monkeypatch.setenv("LOADTEST_HOTEL_ID", "42")
    headers = safe_headers()
    assert headers["X-Hotel-Id"] == "42"
    assert headers["Authorization"] == "Bearer secret-token-that-must-not-be-printed"
    assert "secret-token-that-must-not-be-printed" not in repr({"headers": {key: "[redacted]" for key in headers}})
