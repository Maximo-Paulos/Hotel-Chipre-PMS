# PostgreSQL Performance Benchmarks

Date: 2026-10-07

Status: an isolated local PostgreSQL 16 benchmark is recorded in the latest revalidation section below. It is synthetic and does not establish production latency or production query plans.

> The notes dated 2026-06-14 and 2026-08-28 are historical. The current benchmark script requires an explicit loopback `DATABASE_URL_TEST`; it never derives a target from `.env` and refuses remote databases.

## Scope

Benchmark script: `tests/perf/benchmark_pg.py`

Database safety rule: the script only runs against an explicitly configured loopback PostgreSQL database named `hotel_chipre_test`. It never reads `.env`, never falls back to `DATABASE_URL`, and refuses remote/shared hosts.

Seed scope:

| Entity | Volume |
| --- | ---: |
| Hotel | 1 dedicated benchmark hotel with a random ID in the benchmark-only range |
| Room categories | 5 |
| Rooms | 40 |
| Guests | 2,000 |
| Reservations | 2,000 |
| Transactions | about 1 per 3 reservations |
| Room blocks | 12 |

The seed runs in one transaction and commits only after checking that its random hotel ID is unused and the active sample reservation exists. Cleanup runs only after seeding succeeds; a failed preflight rolls back without deleting rows.

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

## Historical Results — 2026-06-14

The attempt below predates the loopback-only safety rule and is kept for provenance. It tried to reach a remote Supabase pooler and failed during Alembic; it is not a measurement of the current script or current provider state.

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

## Historical EXPLAIN Evidence — before 2026-10-07

The benchmark script runs `EXPLAIN (ANALYZE, BUFFERS)` for the hot SQL behind:

- reservation overlap availability
- allocation reservation window
- transaction balance lookup
- daily report balance candidates
- guest first-name and last-name search

At the time of the 2026-06-14 attempt, measured plans were pending because the remote PostgreSQL endpoint could not be reached. Current local plan evidence appears in the latest revalidation section below.

## Index Review

Existing migration coverage:

- Reservation availability/allocation: `ix_reservation_hotel_room_status_dates` and `ix_reservation_hotel_status_checkin` exist in `20260612_v72_gaps_phase6_payment_tables`.
- Balance lookup: `ix_transactions_hotel_reservation_created` exists in `20260612_v72_gaps_phase6_payment_tables`; idempotency is separately covered by `uq_transactions_hotel_reservation_idempotency_key`.
- Room blocks: `ix_room_blocks_hotel_room` and `ix_room_blocks_hotel_dates` exist in `20260612_v72_gaps_phase2`.

Added in this task:

- `20260614_pg_perf_guest_trgm` creates `pg_trgm` and GIN trigram indexes on `guests.document_number`, `guests.phone`, `guests.email`, and `guests.last_name`; `20260820_guest_search_first_name_index` adds the corresponding `guests.first_name` indexes for the `%term%` `ILIKE` guest search hot path.

Rationale: the service query uses substring `ILIKE` across those columns. Existing B-tree indexes on `(hotel_id, field)` help exact or prefix patterns, but they do not reliably protect the documented fuzzy/substring search path at larger guest volumes.

## Safe Measurement Procedure

Start a fresh isolated local PostgreSQL instance, create a database named `hotel_chipre_test`, and pass its loopback DSN explicitly. Do not use production or a shared remote database. For example:

```sh
DATABASE_URL_TEST='postgresql+psycopg2://<local-user>:<local-password>@127.0.0.1:<port>/hotel_chipre_test' python tests/perf/benchmark_pg.py --iterations 25
```

Expected output format:

```text
query | median ms | p95 ms | median SQL statements | index-used
--- | ---: | ---: | ---: | :---:
availability.check_room_availability | ...
...
```

The script reports targeted sequential scans as notes below 10,000 examined rows and as review candidates at or above that threshold. A plan note is not grounds to add an index: review table size, selectivity, buffers, and representative query latency first.

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

## Query-shape and cache work (2026-08-28)

Migration `20260828_query_shape_indexes` adds the requested benchmark candidates
`rooms(hotel_id, category_id)` and `reservations(hotel_id, deleted_at)`, reconciles
the two V72 reservation indexes in the model, and makes the audit-event entity index
tenant-leading. It removes the duplicate guest, daily-rate, and reservation hotel
indexes with inspector guards and a reversible downgrade.

The rate calendar, daily operational report, and occupancy grid now use the existing
fail-open read-model cache. Reservation, room-block, room, and daily-rate writes
invalidate the affected hotel's operational cache families. The occupancy-grid key
also includes role visibility so cached responses cannot cross visibility policies.

The ORM hot paths use explicit projections or bounded batch queries. Query-count
regression tests cover rate-calendar reservations, period daily rates, analytics
category/company loads, and reservation listing. PostgreSQL `EXPLAIN (ANALYZE)` and
before/after latency remain unmeasured in this checkout because both the local Docker
socket and the configured PostgreSQL endpoint were inaccessible; therefore index-use
confirmation is still pending and no new index is claimed as confirmed here.

Slow-query visibility is available through `SLOW_QUERY_LOG_MS`, default `0` (disabled).
When enabled, SQLAlchemy logs duration and statement text only; bound parameter values
are intentionally excluded because they may contain guest PII.

## Latest isolated revalidation — 2026-10-07

Environment: PostgreSQL 16 in a disposable container bound to `127.0.0.1`, database `hotel_chipre_test`; 2,000 synthetic reservations and guests, 40 rooms, 5 categories, about 667 transactions, 12 blocks; 3 warmups and 100 measured iterations per operation. The script removed its randomized benchmark hotel and related rows after the successful run.

| Operation | p50 ms | p95 ms | Median SQL statements |
| --- | ---: | ---: | ---: |
| `reservation.create_service` (explicit total) | 74.12 | 81.59 | 33 |
| `reservation.create_auto_priced_service` | 17.73 | 90.12 | 38 |
| `availability.check_room_availability` | 1.80 | 1.91 | 3 |
| `availability.find_available_rooms` | 1.83 | 1.90 | 4 |
| `allocation.build_slots_from_db` | 22.03 | 25.62 | 7 |
| `balance.balance_due_from_transactions` | 25.58 | 30.89 | 9 |
| `daily_report` | 104.95 | 137.56 | 21 |
| `guest_search.document` | 21.52 | 23.34 | 8 |
| `guest_search.last_name` | 24.62 | 26.90 | 8 |

These are loopback timings, not provider-bound latencies. A prior 25-iteration run had materially different reservation-creation medians (86.88 ms auto-priced; 24.57 ms explicit total), so these measurements are too variable to characterize a stable application baseline. The SQL statement counts are a more direct within-run signal, but they still do not measure bytes or prove that the same path is hot in production.

Plan notes from this fixture: availability used `ix_reservation_hotel_room_dates`; balance used `ix_transactions_hotel_reservation_created`; allocation, daily-report candidates, and last-name search used sequential scans over at most 2,000 rows. Those small scans do not justify new indexes. The benchmark's `index-used` field is `n/a` when there is no matching plan; when it reports `y` or `n`, it describes one representative SQL plan and not every query inside a multi-query service operation.

For the reported Render/Supabase incident, the missing evidence is provider-bound and byte-level: Render's outbound bandwidth split by service and hour; Supabase's project/org egress split among Database API, Shared Pooler, Realtime, Auth, and Storage; query frequency and rows returned; and request-level SQL/pool/serialization/network timings. Supabase's API Gateway path logs can help locate request volume but do not currently expose response bytes. This benchmark does not attribute the reported 7.18 GB Render `Service-Initiated` traffic or 5.976 GB Supabase egress.
