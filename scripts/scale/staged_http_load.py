#!/usr/bin/env python3
"""Run bounded steady/burst HTTP load against an isolated preview.

This runner is intentionally provider-agnostic. It emits aggregate metrics
only, never credentials or response bodies. Use it with the provider-bound
preview manifest and an environment-scoped bearer token.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Iterable

import httpx


@dataclass(slots=True)
class PhaseMetrics:
    name: str
    concurrency: int
    duration_seconds: float
    latencies_ms: list[float] = field(default_factory=list)
    statuses: dict[str, int] = field(default_factory=dict)
    errors: int = 0

    def as_payload(self) -> dict[str, object]:
        ordered = sorted(self.latencies_ms)
        return {
            "phase": self.name,
            "concurrency": self.concurrency,
            "duration_seconds": self.duration_seconds,
            "requests": len(ordered),
            "errors": self.errors,
            "status_counts": dict(sorted(self.statuses.items())),
            "latency_ms": {
                "median": percentile(ordered, 0.50),
                "p95": percentile(ordered, 0.95),
                "p99": percentile(ordered, 0.99),
                "max": ordered[-1] if ordered else 0.0,
            },
        }


@dataclass(frozen=True, slots=True)
class LoadConfig:
    base_url: str
    paths: tuple[str, ...]
    request_timeout_seconds: float
    max_errors: int


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    if not 0 <= quantile <= 1:
        raise ValueError("quantile must be between 0 and 1")
    index = min(len(values) - 1, max(0, int(round((len(values) - 1) * quantile))))
    return round(values[index], 2)


def safe_headers() -> dict[str, str]:
    headers: dict[str, str] = {"Accept": "application/json"}
    token = os.getenv("LOADTEST_BEARER_TOKEN", "").strip()
    hotel_id = os.getenv("LOADTEST_HOTEL_ID", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if hotel_id:
        headers["X-Hotel-Id"] = hotel_id
    return headers


def _absolute_url(base_url: str, path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    return base_url.rstrip("/") + path


async def run_phase(config: LoadConfig, *, name: str, concurrency: int, duration_seconds: float) -> PhaseMetrics:
    if concurrency <= 0 or duration_seconds <= 0:
        raise ValueError("concurrency and duration_seconds must be positive")
    metrics = PhaseMetrics(name=name, concurrency=concurrency, duration_seconds=duration_seconds)
    deadline = time.monotonic() + duration_seconds
    headers = safe_headers()
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=min(concurrency, 1000))

    async with httpx.AsyncClient(timeout=config.request_timeout_seconds, limits=limits, headers=headers) as client:
        async def worker(worker_index: int):
            path = config.paths[worker_index % len(config.paths)]
            while time.monotonic() < deadline:
                started = time.perf_counter()
                try:
                    response = await client.get(_absolute_url(config.base_url, path))
                    elapsed_ms = (time.perf_counter() - started) * 1000
                    metrics.latencies_ms.append(elapsed_ms)
                    status_key = str(response.status_code)
                    metrics.statuses[status_key] = metrics.statuses.get(status_key, 0) + 1
                    if response.status_code >= 400:
                        metrics.errors += 1
                except (httpx.HTTPError, OSError):
                    metrics.errors += 1

        await asyncio.gather(*(worker(index) for index in range(concurrency)))
    return metrics


def _parse_paths(values: Iterable[str]) -> tuple[str, ...]:
    paths = tuple(value.strip() for value in values if value.strip())
    if not paths:
        raise ValueError("at least one --path is required")
    return paths


async def _run(args: argparse.Namespace) -> int:
    config = LoadConfig(
        base_url=args.base_url,
        paths=_parse_paths(args.path or ["/health"]),
        request_timeout_seconds=args.timeout,
        max_errors=args.max_errors,
    )
    phases = [
        await run_phase(config, name="steady", concurrency=args.concurrency, duration_seconds=args.duration),
        await run_phase(config, name="burst", concurrency=args.burst_concurrency, duration_seconds=args.burst_duration),
    ]
    payload = {"base_url": config.base_url, "paths": list(config.paths), "phases": [phase.as_payload() for phase in phases]}
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    total_errors = sum(phase.errors for phase in phases)
    return 1 if total_errors > config.max_errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Isolated preview API origin, without credentials")
    parser.add_argument("--path", action="append", default=None, help="GET path; repeat for a mixed workload (default: /health)")
    parser.add_argument("--concurrency", type=int, default=100, help="Steady worker count")
    parser.add_argument("--burst-concurrency", type=int, default=200, help="Burst worker count")
    parser.add_argument("--duration", type=float, default=30.0, help="Steady phase seconds")
    parser.add_argument("--burst-duration", type=float, default=10.0, help="Burst phase seconds")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout seconds")
    parser.add_argument("--max-errors", type=int, default=0, help="Allowed transport errors before a non-zero exit")
    args = parser.parse_args()
    if args.max_errors < 0:
        parser.error("--max-errors cannot be negative")
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
