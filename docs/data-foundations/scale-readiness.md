# Hotel Chipre PMS — Scale readiness ledger

**Updated:** 2026-07-24
**Decision:** local hardening is progressing; provider-bound scale certification remains open.

This document separates executable local evidence from claims that require the
isolated preview stack and a real load generator. The target remains 10,000
hotels, 10,000 concurrent users, and a 20,000-user burst without cross-tenant
leakage or financial inconsistency. No target is marked achieved without
provider-bound evidence.

## Evidence available in this worktree

| Area | Local evidence | Status |
| --- | --- | --- |
| Tenant isolation | Hotel-scoped service queries, RLS migration, multi-hotel regression tests | ✅ contract-covered |
| Read cache | Hotel-prefixed availability/analytics keys, invalidation tests, PostgreSQL fallback | ✅ contract-covered |
| Critical concurrency | Redis/Valkey lease for cash close and persisted allocation, PostgreSQL row locks, production fail-closed config | ✅ contract-covered |
| Analytics provenance | All analytics envelopes expose `data_as_of`, `source_lag_seconds`, and `data_source`; UI renders them | ✅ contract-covered |
| Health visibility | `/health/datastores` reports PostgreSQL and Redis roles separately, including distributed locks | ✅ contract-covered |
| iPhone-sized web layout | Fresh Chromium E2E at 375×812, 390×844, and 430×932 | ✅ local evidence |

## Provider-bound evidence still required

1. Provision an isolated Vercel/Render/Supabase preview with dedicated
   database, Redis/Valkey, credentials, and webhook endpoints. The example
   manifest is not evidence.
2. Run the co-located PostgreSQL benchmark and capture server-side `EXPLAIN`
   plus median/p95 for availability, allocation candidates, payment balance,
   daily reports, and guest search.
3. Add the warehouse path only behind explicit freshness metadata: PostgreSQL
   remains the transactional source of truth, CDC/outbox drives ClickHouse,
   and dashboards must show the measured lag rather than implying real-time
   data.
4. Run staged load tests at 10k steady concurrency and 20k burst, with
   per-tenant error rate, p95/p99 latency, connection-pool saturation, Redis
   contention, queue lag, and database CPU/IO captured as artifacts.
5. Verify rollback, alerting, autoscaling, backup/PITR, and tenant-isolation
   probes against the same isolated environment.
6. Run the complete journey in WebKit/Safari/iOS evidence. The current machine
   does not expose `xcrun simctl`, so Apple Simulator evidence is blocked until
   an Apple-capable runner is provisioned.

## Honest gate

Until those artifacts exist, the system may be called **locally hardened and
ready for provider validation**, but not “10k/20k scale certified”, “warehouse
freshness certified”, or “Apple mobile certified”.
