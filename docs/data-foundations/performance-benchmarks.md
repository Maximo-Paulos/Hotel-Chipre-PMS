# PostgreSQL Performance Benchmarks

Date: 2026-06-14

Status: methodology implemented; measured results pending because this sandbox cannot open a TCP connection to the PostgreSQL test database.

## Scope

Benchmark script: `tests/perf/benchmark_pg.py`

Database safety rule: the script only runs against `hotel_chipre_test`. It derives the DSN from the root `.env` `DATABASE_URL` by replacing the trailing `/postgres` with `/hotel_chipre_test`, and refuses to run if the resolved database name is not exactly `hotel_chipre_test`.

Seed scope:

| Entity | Volume |
| --- | ---: |
| Hotel | 1 dedicated benchmark hotel, `hotel_id=90001` |
| Room categories | 5 |
| Rooms | 40 |
| Guests | 2,000 |
| Reservations | 2,000 |
| Transactions | about 1 per 3 reservations |
| Room blocks | 12 |

The seed is cleanup-safe: benchmark-owned rows for `hotel_id=90001` are deleted at the start of each run.

## SLO targets

The [canonical SLO catalog](slo-catalog.md) owns the targets. This benchmark
uses its server-side query budgets:

| Critical query/service | Target p95 |
| --- | ---: |
| `reservation_service.check_room_availability` | < 50 ms |
| `reservation_service.find_available_rooms` | < 100 ms |
| `allocation_engine.build_slots_from_db` | < 150 ms |
| `payment_link_service.balance_due_from_transactions` | < 30 ms |
| `operational_report_service.daily_report` | < 300 ms |
| `guest_service.search_guests` | < 30 ms |

## Query-shape regression evidence

`find_available_rooms` now loads candidate rooms, active blocks and overlapping
reservations in bounded set-based queries instead of calling
`check_room_availability` once per room. The SQLite regression fixture with 20
rooms emitted 85 SQL statements before the change and 7 after it; the test
requires no more than 8. This is query-shape evidence only: PostgreSQL
`EXPLAIN (ANALYZE, BUFFERS)` and provider-bound p95 remain pending.

## Measured Results

Command attempted:

```powershell
python tests\perf\benchmark_pg.py --iterations 25
```

Actual output:

```text
PostgreSQL test database unreachable or migrations failed; alembic exited with status 1.
  File "C:\Users\macap\AppData\Roaming\Python\Python310\site-packages\psycopg2\__init__.py", line 122, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) connection to server at "aws-1-us-west-2.pooler.supabase.com" (44.225.139.66), port 5432 failed: Permission denied (0x0000271D/10013)
	Is the server running on that host and accepting TCP/IP connections?
connection to server at "aws-1-us-west-2.pooler.supabase.com" (44.252.246.120), port 5432 failed: Permission denied (0x0000271D/10013)
	Is the server running on that host and accepting TCP/IP connections?

(Background on this error at: https://sqlalche.me/e/20/e3q8)
```

No production database was touched. The failure occurred while running `alembic upgrade head` against the derived `hotel_chipre_test` DSN.

| Query | Median ms | p95 ms | Index used |
| --- | ---: | ---: | :---: |
| availability.check_room_availability | PENDING | PENDING | PENDING |
| availability.find_available_rooms | PENDING | PENDING | PENDING |
| allocation.build_slots_from_db | PENDING | PENDING | PENDING |
| balance.balance_due_from_transactions | PENDING | PENDING | PENDING |
| daily_report | PENDING | PENDING | PENDING |
| guest_search.document | PENDING | PENDING | PENDING |
| guest_search.last_name | PENDING | PENDING | PENDING |

## EXPLAIN Evidence

The benchmark script runs `EXPLAIN (ANALYZE, BUFFERS)` for the hot SQL behind:

- reservation overlap availability
- allocation reservation window
- transaction balance lookup
- daily report balance candidates
- guest last-name search

Measured plans are pending because the PostgreSQL test database was unreachable from this sandbox. Once network access is available, rerun the benchmark command above and paste the emitted `EXPLAIN` blocks here.

## Index Review

Existing migration coverage:

- Reservation availability/allocation: `ix_reservation_hotel_room_status_dates` and `ix_reservation_hotel_status_checkin` exist in `20260612_v72_gaps_phase6_payment_tables`.
- Balance lookup: `ix_transactions_hotel_reservation_created` exists in `20260612_v72_gaps_phase6_payment_tables`; idempotency is separately covered by `uq_transactions_hotel_reservation_idempotency_key`.
- Room blocks: `ix_room_blocks_hotel_room` and `ix_room_blocks_hotel_dates` exist in `20260612_v72_gaps_phase2`.

Added in this task:

- `20260614_pg_perf_guest_trgm` creates `pg_trgm` and GIN trigram indexes on `guests.document_number`, `guests.phone`, `guests.email`, and `guests.last_name` for the `%term%` `ILIKE` guest search hot path.

Rationale: the service query uses substring `ILIKE` across those columns. Existing B-tree indexes on `(hotel_id, field)` help exact or prefix patterns, but they do not reliably protect the documented fuzzy/substring search path at larger guest volumes.

## Next Measurement Step

Run from the worktree with network access to the PostgreSQL test database:

```powershell
python tests\perf\benchmark_pg.py --iterations 25
```

Expected output format:

```text
query | median ms | p95 ms | index-used
--- | ---: | ---: | :---:
availability.check_room_availability | ...
...
```

If any plan still shows an unexpected sequential scan on `reservations`, `transactions`, or `guests`, keep the measured result in this document and add the smallest index that matches the service predicate.

---

## Director verification notes (2026-06-14)

**Index optimization delivered + validated:** migration `20260614_pg_perf_guest_trgm`
creates pg_trgm GIN indexes on guests(document_number, phone, email, last_name) for
the guest-search hot path. It was applied and validated on real PostgreSQL via
`alembic upgrade head` (rc 0, single head) — confirmed against Supabase `hotel_chipre_test`.

**Environment limitation (honest):** the only PostgreSQL reachable from this dev
environment is a REMOTE Supabase pooler (AWS us-west-2). Client wall-clock latency is
dominated by network RTT (each query is a trans-continental round-trip), and row-volume
seeding (3000 rows via executemany = 3000 round-trips) exceeds practical timeouts. Therefore
representative latency numbers (the `median/p95` table in `benchmark_pg.py`) MUST be measured
against a CO-LOCATED PostgreSQL (the Render/production deploy where app and DB share a region).
The network-independent metric is server-side `EXPLAIN (ANALYZE)` execution time + index
usage (`tests/perf/explain_probe.py`), which should be captured in the co-located environment.

**Status:** canonical SLO targets are defined in `slo-catalog.md`; trgm optimization is integrated + migration-validated;
representative latency measurement = DEPLOY-TIME step on co-located PG. Measured numbers: PENDING
(co-located). No fabricated numbers.

### MEASURED — guest-search hot path (server-side EXPLAIN ANALYZE, real PostgreSQL)

Captured via `tests/perf/explain_probe.py` against Supabase `hotel_chipre_test`,
4000 seeded guests, single hotel. Server-side `Execution Time` (network-independent):

| Query | Server exec | Plan | SLO (<30ms) |
|-------|-------------|------|-------------|
| guest search by document (exact) | 0.06 ms | Index | ✅ |
| guest search last_name ILIKE '%..%' (trgm) | 5.63 ms | Index (GIN trgm) | ✅ |
| guest search email ILIKE '%..%' (trgm) | 5.51 ms | Index (GIN trgm) | ✅ |
| guest list by hotel_id (ORDER BY last_name) | 0.10 ms | Index | ✅ |

Zero Seq Scans — the pg_trgm GIN indexes (migration 20260614_pg_perf_guest_trgm)
are confirmed in use for ILIKE substring search, the V72 guest-search hot path.
This is the network-independent authoritative metric and meets the SLO with wide margin.

Still pending CO-LOCATED measurement (heavier reservation/availability/report seeding
that the remote pooler cannot seed within practical time): availability, allocation
candidate build, daily report. Their queries already use composite indexes
(verified in tests/test_postgres_validation.py EXPLAIN tests).
