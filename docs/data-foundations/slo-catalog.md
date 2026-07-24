# Hotel Chipre PMS — SLO catalog

**Status:** canonical targets; provider-bound measurement pending.

This is the single source for performance and reliability acceptance targets.
The targets describe p95 latency unless a different percentile or window is
shown. Local SQLite and fake warehouse runs may validate instrumentation and
correctness, but they do not prove these targets for production capacity.

## User-visible operation SLOs

| Operation | Target p95 | Error budget / invariant |
| --- | ---: | --- |
| Calendar and availability view | < 200 ms | No stale data presented as current |
| Quote and payment request | < 200 ms | No duplicate financial effect |
| Reservation create/update | < 300 ms | No overbooking or cross-tenant write |
| Stock movement | < 300 ms | No negative stock from a concurrent egreso |
| Cash close | < 500 ms | Exactly one close/custody effect per idempotency key |
| Analytics response | < 1 s | `data_as_of` and lag are always exposed |
| Unexpected API errors | — | < 0.1% of requests |
| CDC / warehouse freshness | — | p95 lag < 30 s; hard maximum 60 s |

## Server-side query budgets

These are stricter internal budgets. They leave room for transport, encoding,
authorization and UI work inside the user-visible SLOs above.

| Query or service | Target p95 |
| --- | ---: |
| `reservation_service.check_room_availability` | < 50 ms |
| `reservation_service.find_available_rooms` | < 100 ms |
| `allocation_engine.build_slots_from_db` | < 150 ms |
| `payment_link_service.balance_due_from_transactions` | < 30 ms |
| `operational_report_service.daily_report` | < 300 ms |
| `guest_service.search_guests` | < 30 ms |

## Measurement contract

Every provider-bound result must include the code SHA, dataset profile, request
mix, concurrency, p50/p95/p99, error rate, database connection-pool wait,
Redis/Valkey latency and contention, worker/queue lag, CPU, memory, I/O and
warehouse lag. PostgreSQL query budgets require `EXPLAIN (ANALYZE, BUFFERS)`
from a co-located isolated database. A local result must be labeled local and
cannot replace provider-bound evidence.

## Ownership and change control

Changes to these targets require updating the goal evidence, the benchmark
methodology and the release gate together. Do not define a second SLO table in
an architecture or QA document; link back here instead.
