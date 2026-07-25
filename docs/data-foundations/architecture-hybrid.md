# Hotel Chipre PMS — Hybrid Architecture

**Date:** 2026-06-12  
**Status:** Canonical reference  
**Scope:** Backend data layer for Sprint 1 and beyond

---

## Architectural principle: source of truth per data class

Each data class has exactly ONE source of truth. No dual writes to two authoritative stores.

| Data Class | Source of Truth | Rationale |
|------------|----------------|-----------|
| Reservations, guests, rooms | PostgreSQL | ACID, relational, audit trail required |
| Payments, transactions, financials | PostgreSQL | Decimal precision, idempotency, audit |
| Cash register (caja) | PostgreSQL | Arqueo must be reproducible, supervisor approval |
| Hotel configuration, permissions | PostgreSQL | Multi-tenant, critical, must be transactional |
| OTA mappings, allocation rules | PostgreSQL | Relational references, audit |
| Session tokens, rate limit counters | Redis | TTL-based, ephemeral, high-frequency writes |
| Availability cache | Redis | Read-heavy, invalidated on reservation write |
| Idempotency keys (payment, OTA) | Redis | Short-lived, prevent replay |
| Distributed locks (allocation runs) | Redis | Prevent concurrent solver races |
| Full-text search index | PostgreSQL pg_trgm | Volume doesn't justify external engine; benchmarks show <50ms |
| AI assistant sessions/messages | PostgreSQL | Persistent, auditable |
| Analytics/reporting facts | PostgreSQL (Fact tables) | Authoritative, auditable facts; ClickHouse is a derived read model for scale |
| Analytics warehouse | ClickHouse | PII-free derived facts, replayable projection and explicit PG↔warehouse reconciliation |

---

## PostgreSQL — primary OLTP store

### Schema ownership and startup safety

Alembic is the only schema owner in production, preview, QA, and staging. The
application refuses to start in those environments unless it is connected to
PostgreSQL with a populated `alembic_version` table. `Base.metadata.create_all`
and additive self-healing remain available only for local development/test
harnesses; they must never silently repair production drift during boot.

### Why PostgreSQL, not NoSQL

- v72 requires reproducible arqueo, idempotent payments, and append-only audit. These require ACID transactions with row-level locking.
- Relational references between reservations, guests, rooms, payments, and OTA mappings would be orphaned FK violations in document stores.
- Multi-tenancy via `hotel_id` scoped on every table is a relational pattern.
- PostgreSQL supports JSONB for flexible attributes without abandoning transactions.

### Schemas in use

All domain tables use `hotel_id` as the first partition key (not a PostgreSQL partition — a discriminating FK column scoped on every query).

### Isolation level

**Read Committed** (PostgreSQL default) for most operations.  
**Serializable** for:
- Allocation solver runs (prevents double-assignment)
- Cash close/arqueo (prevents concurrent close)
- Availability check + reservation insert (prevents double-booking)

Pattern: `SELECT FOR UPDATE` on the target room row before inserting reservation.

### Connection pool

- Production: PgBouncer in transaction mode, pool_size=25 per app instance
- ORM: SQLAlchemy pool_size=10, max_overflow=20, pool_timeout=30
- Never use statement-mode pgBouncer (incompatible with advisory locks and prepared statements)

### Key indexes (beyond model defaults)

```sql
-- Availability query: hotel + dates overlap
CREATE INDEX ix_reservations_hotel_date_status
  ON reservations(hotel_id, check_in_date, check_out_date, status)
  WHERE status NOT IN ('cancelled', 'no_show');

-- Guest search: pg_trgm for fuzzy name lookup
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_guest_last_name_trgm
  ON guests USING gin(last_name gin_trgm_ops);
CREATE INDEX ix_guest_first_name_trgm
  ON guests USING gin(first_name gin_trgm_ops);

-- Reservation calendar view
CREATE INDEX ix_reservations_hotel_checkin
  ON reservations(hotel_id, check_in_date)
  WHERE status NOT IN ('cancelled', 'no_show');

-- Active room blocks affecting availability
CREATE INDEX ix_room_blocks_active
  ON room_blocks(hotel_id, room_id, starts_at, ends_at)
  WHERE resolved_at IS NULL;

-- OTA dedup fast lookup
-- Already: uq_reservation_ota_external_id
```

### JSONB usage policy

JSONB is used ONLY for:
- `reservations.pricing_snapshot` — point-in-time tariff snapshot (immutable once set)
- `reservations.requested_attributes_json` — OTA-supplied free attributes
- `allocation_explanations` — solver rationale (nested, variable structure)
- `ai_assistant_*` — LLM session context (variable schema)

JSONB is NOT used for:
- Any entity that needs to be queried by its fields (use proper columns)
- Any financial amount (use Numeric columns)
- Any relationship that needs referential integrity (use FK columns)
- Hotel configuration, permissions, status, enums

---

## Redis — cache, sessions, ephemeral state

### Why Redis, not Memcached

- Supports TTL, pub/sub, sorted sets, atomic operations (INCR, SETNX)
- Needed for: idempotency keys (SET NX EX), rate counters (INCR), distributed locks (SET NX PX), leaderboards

### Key namespaces

```
hotel:{hotel_id}:availability:{category_id}:{date}   TTL=60s   (availability cache)
hotel:{hotel_id}:rate_limit:{user_id}:{minute}         TTL=70s   (rate limiting)
session:{token_hash}                                   TTL=86400s (auth sessions)
idempotency:{hotel_id}:payment:{key}                   TTL=86400s (payment dedup)
idempotency:{hotel_id}:ota:{channel}:{external_id}     TTL=3600s  (OTA dedup)
lock:allocation:{hotel_id}                             TTL=30s   (solver lock)
lock:cash_close:{hotel_id}:{session_id}                TTL=60s   (arqueo lock)
```

### Cache invalidation

- Availability cache invalidated on: reservation insert/update/cancel, room block create/resolve
- Pattern: write-through invalidation (write PG first, then DEL Redis key)
- On Redis unavailability: read caches degrade gracefully — query PG directly (no availability cache miss causes incorrect data, only slower response)
- Cash close and allocation locks are different: Redis/Valkey is the primary lease, with a transaction-scoped PostgreSQL advisory-lock fallback when Redis is unavailable. Production must set `DISTRIBUTED_LOCK_ENABLED=true` and `DISTRIBUTED_LOCK_REQUIRED=true`; it fails closed only when neither lock backend can be acquired.
- Never serve stale availability as authoritative without re-checking PG

### Tenant-scoped realtime invalidation

`/api/events/stream` is an authenticated SSE stream backed by Redis/Valkey
pub/sub. Channels and revision counters are hotel-scoped:

```text
hotel:{hotel_id}:events
hotel:{hotel_id}:revision:{domain}
```

Events contain only domain, revision, entity identifiers and operational
metadata. They never contain guest PII, credentials, payment proof bytes or
tokens. The web client uses them only to invalidate React Query keys and then
refetches PostgreSQL-backed APIs. `BroadcastChannel` plus the storage fallback
keeps multiple tabs coherent without crossing hotel scopes.

### ClickHouse derived warehouse

`app.services.analytics_warehouse` owns the provider boundary. It creates only
PII-free dimensions (`dim_hotel`, `dim_date`, `dim_room`,
`dim_room_category`) and `ReplacingMergeTree` facts for reservations, payments,
cash movements and stock movements. Facts are partitioned by `(hotel_id,
month)` and ordered by tenant/date/entity. PostgreSQL remains the source of
truth for all transactional data. The Celery projector is replayable and
reports hard count-plus-amount reconciliation for each hotel/date window; a
mismatch is retried, logged as an alert signal, and must block publication.
The five-minute bounded replay and nightly full-window job are recovery and
verification paths, not a claim that ClickPipes CDC has been provisioned.
Provider connectivity, measured CDC lag and 10k/20k scale evidence remain
deployment prerequisites, not local claims.

### Distributed lock pattern (allocation solver)

```python
with distributed_lock(f"lock:allocation:{hotel_id}", ttl_seconds=30):
    run_solver(hotel_id)
```

`app.services.distributed_lock` uses a random lease token and an atomic Lua
compare-and-delete on release, so a worker cannot delete a successor worker's
lease after its own TTL has expired. `close_session` uses the equivalent
`lock:cash_close:{hotel_id}:{session_id}` lease.

---

## Transactional outbox pattern (async integrations)

For email sends, OTA webhooks, payment link creation, and WhatsApp notifications:

1. Write the domain record AND an outbox event in the SAME transaction:
   ```sql
   INSERT INTO reservations (...) VALUES (...);
   INSERT INTO pending_operational_actions (type, payload, status)
     VALUES ('send_payment_link_email', '{"reservation_id": 123}', 'pending');
   COMMIT;
   ```
2. Background worker polls `pending_operational_actions` WHERE status='pending'
3. On success: update status='done'
4. On failure: retry with exponential backoff, escalate to 'failed' after N attempts
5. Idempotency: each outbox event has a unique key; worker checks Redis before processing

This ensures emails/webhooks are never lost even if the app crashes after the DB write.

---

## Search strategy

### Guest search

- Fields: first_name, last_name, document_number, email, phone
- Strategy: PostgreSQL `pg_trgm` GIN indexes for name fuzzy search; B-tree indexes for document/email/phone exact lookup
- Query budget: < 30ms p95; the user-visible operation SLO is defined in the
  [canonical SLO catalog](slo-catalog.md)
- Threshold for external engine: > 500K guests per hotel or > 500ms p95 response (monitor before migrating)

### Reservation/calendar search

- Fields: confirmation_code (exact), date ranges, status, guest name (join)
- Strategy: composite B-tree indexes + date range overlap queries
- User-visible SLO: < 200ms p95 for the calendar view; see the
  [canonical SLO catalog](slo-catalog.md)

---

## SLO definitions

The [canonical SLO catalog](slo-catalog.md) owns the p95 targets for
user-visible operations and their internal query budgets. This document keeps
the data-flow design; it must not define a competing latency table.

---

## PII and data retention

- Guest PII (name, document, email, phone, address): stored in PostgreSQL, encrypted at rest via Supabase/PG TDE or disk encryption
- `guests.retention_until`: default now+5yr; enforced by scheduled job
- No PII in logs; log reservation_id, hotel_id, action — never guest name/document
- Digital signatures stored as base64 in `guests.digital_signature`; consider external storage for large files
- `company_documents.file_url`: storage URL (S3/Supabase Storage); URL contains no auth token in the DB; presigned URLs generated on demand

---

## Backup and PITR

- Daily full backup
- WAL archiving for PITR (point-in-time recovery) to 7-day window
- Monthly restore test to verify backup integrity
- Target RPO: 1 hour | Target RTO: 4 hours

---

## Multi-tenancy model

All domain tables have `hotel_id NOT NULL` FK to `hotel_configuration.id`.

Cross-entity links use tenant-leading composite keys such as
`(hotel_id, reservation_id) -> (hotel_id, id)`. The migrations
`20260724_core_tenant_composite_fks` and
`20260724_extended_tenant_composite_fks` cover reservations, guests, rooms,
commercial pricing, payments, cash, stock, OTA, allocation, vouchers,
operations, AI-assistant records, and derived facts. This prevents a valid
global row id from being reused across hotels as a relationship. The database
constraints are PostgreSQL-only and must be validated against the isolated
Supabase preview before release; SQLite remains a local metadata-driven test
dialect.

Isolation is enforced in two layers:

1. **Application scoping:** every authenticated request resolves an active
   `AuthContext.hotel_id`; service methods require the hotel id explicitly.
2. **PostgreSQL RLS:** migration `20260724_tenant_rls_context` enables and
   forces row-level policies on every ORM table with `hotel_id`. Policies read
   transaction-local `app.hotel_id` and fail closed when no context exists.

The membership table additionally uses transaction-local `app.user_id` while
the active hotel is being resolved. The public API-key table is the only
documented exception: a SHA-256 hash lookup must resolve the hotel before an
RLS context exists; all subsequent public operations set `app.hotel_id`.

Mitigation and review gates:
1. All service methods require `hotel_id` as a mandatory parameter
2. All ORM queries through `db.query(Model).filter_by(hotel_id=hotel_id)` pattern
3. Multi-tenancy isolation test suite (`tests/test_multi_tenancy_isolation.py`) verifies API behavior
4. `tests/test_tenant_rls_contract.py` verifies the migration covers every hotel-scoped model table
5. Worker and background entry points must call `set_tenant_context` before tenant-scoped work

---

## What is NOT in Sprint 1

| Feature | Reason | When |
|---------|--------|------|
| PostgreSQL RLS | Defense in depth for production scale; requires explicit transaction context | Implemented in `20260724_tenant_rls_context` |
| Columnar analytics store | Volume not yet reached | >10M fact rows/hotel |
| External search engine (Elasticsearch) | pg_trgm sufficient at current scale | Benchmark triggers |
| Kafka/event streaming | Outbox pattern sufficient for Sprint 1 | High-volume integrations |
| Redis Cluster | Single Redis node sufficient for pilot | >10K concurrent users |
| Read replicas | Primary sufficient for pilot | >1000 concurrent reservations |
