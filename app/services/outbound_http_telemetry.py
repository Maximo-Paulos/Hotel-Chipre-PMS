"""Privacy-safe size and latency telemetry for outbound HTTP calls."""
from __future__ import annotations

import logging
import re
import time
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit


logger = logging.getLogger(__name__)
_OPERATION_RE = re.compile(r"[a-z0-9_.-]{1,64}")


def _json_size_estimate(value) -> int:
    """Estimate JSON bytes without serializing or retaining payload contents."""
    if value is None:
        return 4
    if isinstance(value, bool):
        return 4 if value else 5
    if isinstance(value, (int, float)):
        return len(str(value))
    if isinstance(value, str):
        # Quotes are counted; uncommon JSON escaping is intentionally an estimate.
        return len(value.encode("utf-8")) + 2
    if isinstance(value, Mapping):
        if not value:
            return 2
        return 2 + sum(
            _json_size_estimate(str(key)) + 1 + _json_size_estimate(item) + 1
            for key, item in value.items()
        ) - 1
    if isinstance(value, Sequence):
        if not value:
            return 2
        return 2 + sum(_json_size_estimate(item) + 1 for item in value) - 1
    return _json_size_estimate(str(value))


def _body_size_estimate(kwargs: Mapping[str, object]) -> int | str:
    for name in ("content", "data", "json"):
        value = kwargs.get(name)
        if value is None:
            continue
        if isinstance(value, (bytes, bytearray, memoryview)):
            return len(value)
        if isinstance(value, str):
            return len(value.encode("utf-8"))
        if name == "json":
            return _json_size_estimate(value)
        if isinstance(value, Mapping):
            return sum(
                len(str(key).encode("utf-8")) + len(str(item).encode("utf-8")) + 2
                for key, item in value.items()
            )
        if isinstance(value, Sequence):
            sizes = [
                _body_size_estimate({"data": item}) if item is not None else 0
                for item in value
            ]
            if any(size == "unknown" for size in sizes):
                return "unknown"
            return sum(int(size) for size in sizes)
        return "unknown"
    if kwargs.get("files"):
        return "unknown"
    return 0


def _request_details(response, fallback_url: str, kwargs: Mapping[str, object]) -> tuple[str, int | str]:
    request = getattr(response, "request", None) if response is not None else None
    request_url = getattr(request, "url", None) or fallback_url
    try:
        host = urlsplit(str(request_url)).hostname or "unknown"
    except ValueError:
        host = "unknown"

    request_bytes: int | str = "unknown"
    if request is not None:
        headers = getattr(request, "headers", {}) or {}
        content_length = headers.get("content-length") if hasattr(headers, "get") else None
        try:
            body_bytes = int(content_length) if content_length is not None else None
        except (TypeError, ValueError):
            body_bytes = None
        if body_bytes is None:
            body = getattr(request, "body", None)
            if isinstance(body, (bytes, bytearray, memoryview)):
                body_bytes = len(body)
            elif isinstance(body, str):
                body_bytes = len(body.encode("utf-8"))
        if body_bytes is not None:
            request_bytes = len(str(request_url).encode("utf-8")) + body_bytes
    if request_bytes == "unknown":
        body_bytes = _body_size_estimate(kwargs)
        if body_bytes != "unknown":
            request_bytes = len(fallback_url.encode("utf-8")) + body_bytes
    return host, request_bytes


def _response_body_size(response) -> int | str:
    try:
        content = getattr(response, "content", None)
        if isinstance(content, (bytes, bytearray, memoryview)):
            return len(content)
    except Exception:  # response streams may not expose a buffered body
        pass
    return "unknown"


def _safe_operation(operation: str) -> str:
    return operation if _OPERATION_RE.fullmatch(operation or "") else "external"


def _fallback_url(args, kwargs) -> str:
    if len(args) > 1 and str(args[0]).upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
        return str(args[1])
    return str(args[0] if args else kwargs.get("url") or "")


def observed_http_call(operation: str, sender, *args, **kwargs):
    """Call an HTTP client and log only destination, byte counts, time and status."""
    started = time.perf_counter()
    fallback_url = _fallback_url(args, kwargs)
    operation_code = _safe_operation(operation)
    try:
        response = sender(*args, **kwargs)
    except Exception as exc:
        host, request_bytes = _request_details(None, fallback_url, kwargs)
        logger.warning(
            "outbound.http operation=%s host=%s request_bytes_estimate=%s response_body_bytes=unknown duration_ms=%.2f status=failed error_type=%s",
            operation_code,
            host,
            request_bytes,
            (time.perf_counter() - started) * 1000.0,
            type(exc).__name__,
        )
        raise

    host, request_bytes = _request_details(response, fallback_url, kwargs)
    logger.info(
        "outbound.http operation=%s host=%s request_bytes_estimate=%s response_body_bytes=%s duration_ms=%.2f status=%s",
        operation_code,
        host,
        request_bytes,
        _response_body_size(response),
        (time.perf_counter() - started) * 1000.0,
        getattr(response, "status_code", "unknown"),
    )
    return response


async def observed_async_http_call(operation: str, sender, *args, **kwargs):
    """Async equivalent of :func:`observed_http_call`."""
    started = time.perf_counter()
    fallback_url = _fallback_url(args, kwargs)
    operation_code = _safe_operation(operation)
    try:
        response = await sender(*args, **kwargs)
    except Exception as exc:
        host, request_bytes = _request_details(None, fallback_url, kwargs)
        logger.warning(
            "outbound.http operation=%s host=%s request_bytes_estimate=%s response_body_bytes=unknown duration_ms=%.2f status=failed error_type=%s",
            operation_code,
            host,
            request_bytes,
            (time.perf_counter() - started) * 1000.0,
            type(exc).__name__,
        )
        raise

    host, request_bytes = _request_details(response, fallback_url, kwargs)
    logger.info(
        "outbound.http operation=%s host=%s request_bytes_estimate=%s response_body_bytes=%s duration_ms=%.2f status=%s",
        operation_code,
        host,
        request_bytes,
        _response_body_size(response),
        (time.perf_counter() - started) * 1000.0,
        getattr(response, "status_code", "unknown"),
    )
    return response
