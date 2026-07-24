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
| Analytics/reporting facts | PostgreSQL (Fact tables) | OLAP queries via indexed fact tables; columnar engine if >10M rows/hotel |

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
- On Redis unavailability: degrade gracefully — query PG directly (no availability cache miss causes incorrect data, only slower response)
- Never serve stale availability as authoritative without re-checking PG

### Distributed lock pattern (allocation solver)

```python
lock_key = f"lock:allocation:{hotel_id}"
acquired = redis.set(lock_key, worker_id, nx=True, px=30000)  # 30s TTL
if not acquired:
    raise AlreadyRunningError("Solver already running for this hotel")
try:
    run_solver(hotel_id)
finally:
    # Only release if we own the lock
    if redis.get(lock_key) == worker_id:
        redis.delete(lock_key)
```

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
- SLO: < 100ms for up to 100K guests per hotel
- Threshold for external engine: > 500K guests per hotel or > 500ms p95 response (monitor before migrating)

### Reservation/calendar search

- Fields: confirmation_code (exact), date ranges, status, guest name (join)
- Strategy: composite B-tree indexes + date range overlap queries
- SLO: < 200ms for calendar view (60-day window, any hotel size)

---

## SLO definitions

| Operation | Target p50 | Target p95 | Target p99 |
|-----------|-----------|-----------|-----------|
| Guest search (name/doc/phone) | 30ms | 100ms | 250ms |
| Reservation list (calendar view, 60 days) | 50ms | 200ms | 500ms |
| Reservation create (with availability check) | 80ms | 300ms | 800ms |
| Payment record (transaction insert) | 50ms | 200ms | 500ms |
| Check-in flow (all validations) | 100ms | 400ms | 1000ms |
| Cash close report (arqueo) | 100ms | 500ms | 1500ms |
| Allocation solver (single hotel, 50 rooms) | 200ms | 1000ms | 3000ms |
| API key validation (cache hit) | 1ms | 5ms | 20ms |
| API key validation (cache miss → DB) | 20ms | 80ms | 200ms |

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

Isolation mechanism: **application-level scoping** (all queries filter by hotel_id).  
No PostgreSQL row-level security (RLS) in Sprint 1 — planned for post-launch hardening.

Risk: a bug in query construction could accidentally omit `hotel_id` filter.  
Mitigation:
1. All service methods require `hotel_id` as a mandatory parameter
2. All ORM queries through `db.query(Model).filter_by(hotel_id=hotel_id)` pattern
3. Multi-tenancy isolation test suite (`tests/test_multi_tenancy_isolation.py`) verifies 17 isolation contracts

---

## What is NOT in Sprint 1

| Feature | Reason | When |
|---------|--------|------|
| PostgreSQL RLS | Adds complexity; app-level scoping sufficient for pilot | Post-launch |
| Columnar analytics store | Volume not yet reached | >10M fact rows/hotel |
| External search engine (Elasticsearch) | pg_trgm sufficient at current scale | Benchmark triggers |
| Kafka/event streaming | Outbox pattern sufficient for Sprint 1 | High-volume integrations |
| Redis Cluster | Single Redis node sufficient for pilot | >10K concurrent users |
| Read replicas | Primary sufficient for pilot | >1000 concurrent reservations |
