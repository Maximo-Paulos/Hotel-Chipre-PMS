#!/usr/bin/env python3
"""Bounded SSE/recovery load for an isolated preview.

This script performs GETs only. It never creates reservations, payments or
other business writes, and rejects the shared production hosts by default.
Provide a staging/preview bearer token through LOADTEST_BEARER_TOKEN.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
import json
import os
import time
from urllib.parse import urlsplit

import httpx


PRODUCTION_HOSTS = {"api.hotels-pms.com", "app.hotels-pms.com", "hotels-pms.com"}


@dataclass
class RealtimeMetrics:
    sessions: int
    duration_seconds: float
    recovery_latencies_ms: list[float] = field(default_factory=list)
    recovery_statuses: dict[str, int] = field(default_factory=dict)
    sse_ready: int = 0
    heartbeats: int = 0
    events: int = 0
    errors: int = 0

    def payload(self) -> dict[str, object]:
        latencies = sorted(self.recovery_latencies_ms)
        p95 = latencies[min(len(latencies) - 1, int(round((len(latencies) - 1) * 0.95)))] if latencies else 0.0
        return {
            "sessions": self.sessions,
            "duration_seconds": self.duration_seconds,
            "recovery_statuses": dict(sorted(self.recovery_statuses.items())),
            "sse_ready": self.sse_ready,
            "heartbeats": self.heartbeats,
            "events": self.events,
            "errors": self.errors,
            "recovery_latency_ms": {"p95": round(p95, 2)},
        }


def validate_target(base_url: str) -> None:
    parsed = urlsplit(base_url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("--base-url must be an HTTP(S) origin")
    if host in PRODUCTION_HOSTS:
        raise ValueError("refusing shared production host; use an isolated preview")


async def run_load(*, base_url: str, hotel_id: int, sessions: int, duration_seconds: float, timeout_seconds: float) -> RealtimeMetrics:
    if sessions <= 0 or duration_seconds <= 0:
        raise ValueError("sessions and duration must be positive")
    token = os.getenv("LOADTEST_BEARER_TOKEN", "").strip()
    if not token:
        raise ValueError("LOADTEST_BEARER_TOKEN is required for the authenticated SSE stream")
    headers = {"Authorization": f"Bearer {token}", "X-Hotel-Id": str(hotel_id), "Accept": "text/event-stream"}
    metrics = RealtimeMetrics(sessions=sessions, duration_seconds=duration_seconds)
    deadline = time.monotonic() + duration_seconds
    limits = httpx.Limits(max_connections=sessions + 5, max_keepalive_connections=sessions)
    timeout = httpx.Timeout(timeout_seconds, connect=5.0)
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), headers=headers, limits=limits, timeout=timeout) as client:
        async def one_session() -> None:
            if time.monotonic() >= deadline:
                return
            started = time.perf_counter()
            try:
                recovery = await client.get(f"/api/events/recovery?after_cursor=0")
                metrics.recovery_latencies_ms.append((time.perf_counter() - started) * 1000)
                metrics.recovery_statuses[str(recovery.status_code)] = metrics.recovery_statuses.get(str(recovery.status_code), 0) + 1
                if recovery.status_code >= 400:
                    metrics.errors += 1
                    return
                async with client.stream("GET", "/api/events/stream") as stream:
                    async for line in stream.aiter_lines():
                        if time.monotonic() >= deadline:
                            break
                        if line.startswith("event: ready"):
                            metrics.sse_ready += 1
                        elif line.startswith(": heartbeat"):
                            metrics.heartbeats += 1
                        elif line.startswith("data:"):
                            metrics.events += 1
            except (httpx.HTTPError, OSError, asyncio.TimeoutError):
                metrics.errors += 1

        await asyncio.gather(*(one_session() for _ in range(sessions)))
    return metrics


async def _run(args: argparse.Namespace) -> int:
    validate_target(args.base_url)
    metrics = await run_load(
        base_url=args.base_url,
        hotel_id=args.hotel_id,
        sessions=args.sessions,
        duration_seconds=args.duration,
        timeout_seconds=args.timeout,
    )
    payload = metrics.payload()
    payload["base_url"] = args.base_url
    payload["hotel_id"] = args.hotel_id
    print(json.dumps(payload, sort_keys=True))
    error_rate = metrics.errors / max(metrics.sessions, 1)
    return 1 if error_rate > args.max_error_rate else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--hotel-id", type=int, required=True)
    parser.add_argument("--sessions", type=int, default=10)
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-error-rate", type=float, default=0.01)
    args = parser.parse_args()
    if args.hotel_id <= 0 or not 0 <= args.max_error_rate <= 1:
        parser.error("hotel-id must be positive and max-error-rate must be between 0 and 1")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
