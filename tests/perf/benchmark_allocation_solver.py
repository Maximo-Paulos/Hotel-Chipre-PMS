"""Measure allocation solver time and process memory on synthetic hotel data.

Run from the repository root with ``python tests/perf/benchmark_allocation_solver.py``.
The scenario uses one hotel, 391 reservations, 40 rooms, four categories and a
365-day optimization horizon. It does not connect to a database or provider.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import platform
import resource
import subprocess
import time
from datetime import date, timedelta

from app.services.allocation_engine import ReservationSlot, RoomSlot, run_allocation


def _resident_bytes() -> int:
    resident_kib = int(
        subprocess.check_output(
            ["ps", "-o", "rss=", "-p", str(os.getpid())],
            text=True,
        ).strip()
    )
    return resident_kib * 1024


def _peak_resident_bytes() -> int:
    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if platform.system() == "Darwin" else peak * 1024


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, int((len(ordered) * quantile) + 0.999999) - 1))
    return ordered[index]


def _scenario() -> tuple[list[ReservationSlot], list[RoomSlot], date]:
    start = date(2026, 1, 1)
    reservations = []
    for index in range(391):
        check_in = start + timedelta(days=(index * 17) % 365)
        reservations.append(
            ReservationSlot(
                reservation_id=index + 1,
                category_id=index % 4 + 1,
                check_in=check_in,
                check_out=check_in + timedelta(days=2 + index % 4),
                current_room_id=None,
                is_locked=False,
                num_guests=2,
            )
        )
    rooms = [
        RoomSlot(
            room_id=index + 1,
            room_number=f"R{index + 1:03d}",
            category_id=index % 4 + 1,
        )
        for index in range(40)
    ]
    return reservations, rooms, start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    if args.iterations < 1 or args.iterations > 20:
        parser.error("--iterations must be between 1 and 20")

    reservations, rooms, horizon_start = _scenario()
    measurements = []
    for iteration in range(args.iterations):
        started = time.perf_counter()
        result = run_allocation(
            reservations,
            rooms,
            optimization_horizon=(horizon_start, horizon_start + timedelta(days=365)),
        )
        measurements.append(
            {
                "iteration": iteration + 1,
                "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                "assigned_reservations": len(result.assignments),
                "unassigned_reservations": len(result.unassigned_reservations),
                "success": result.success,
                "resident_bytes": _resident_bytes(),
                "peak_resident_bytes": _peak_resident_bytes(),
            }
        )

    durations = [float(row["duration_ms"]) for row in measurements]
    print(
        json.dumps(
            {
                "scenario": {
                    "hotels": 1,
                    "reservations": len(reservations),
                    "rooms": len(rooms),
                    "room_categories": 4,
                    "horizon_days": 365,
                    "synthetic_only": True,
                },
                "runtime": {
                    "python": platform.python_version(),
                    "ortools": importlib.metadata.version("ortools"),
                },
                "summary": {
                    "duration_p50_ms": round(_percentile(durations, 0.50), 2),
                    "duration_p95_ms": round(_percentile(durations, 0.95), 2),
                    "peak_resident_bytes": max(
                        int(row["peak_resident_bytes"]) for row in measurements
                    ),
                },
                "measurements": measurements,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if all(row["success"] for row in measurements) else 1


if __name__ == "__main__":
    raise SystemExit(main())
