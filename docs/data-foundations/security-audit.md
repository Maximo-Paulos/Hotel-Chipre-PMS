# Hotel Chipre PMS — Security Audit

**Date:** 2026-06-12  
**Status:** Sprint 1 baseline  
**Scope:** Data layer, authentication, multi-tenancy, PII, secrets

---

## 1. Multi-tenancy isolation

| Check | Status | Evidence |
|-------|--------|---------|
| Every domain table has `hotel_id NOT NULL FK` | ✅ | All 40+ domain tables — verified in `test_multi_tenancy_isolation.py` |
| Unique constraints are hotel-scoped (not global) | ✅ | 17 isolation tests pass |
| Guest dedup per hotel (not global) | ✅ | `uq_guest_document_per_hotel` |
| OTA dedup per hotel | ✅ | `uq_reservation_ota_external_id` |
| API keys per hotel | ✅ | `uq_hotel_api_key_name` |
| Cross-hotel query leakage tested | ✅ | `tests/test_multi_tenancy_isolation.py` (17 tests) |
| PostgreSQL RLS (row-level security) | ⚠️ NOT IMPLEMENTED | Planned post-launch; app-level scoping used now |
| Service layer requires hotel_id on all operations | ✅ | Enforced by service method signatures |

**Risk:** A bug in query construction that omits `hotel_id` filter could expose cross-hotel data.  
**Mitigation:** Multi-tenancy test suite + code review gate. PG RLS as defense-in-depth post-launch.

---

## 2. Authentication and secrets

| Check | Status | Evidence |
|-------|--------|---------|
| Hotel API keys: only `key_hash` + `key_prefix` stored, never plaintext | ✅ | `hotel_api_keys` model — no `secret` column |
| Session tokens: stored as hash in `security_tokens` | ✅ | `security_tokens.token_hash` |
| Password storage: password_hash column, no plaintext | ✅ | `users.password_hash` |
| API key cleartext never logged | ✅ | `key_prefix` (8 chars) in logs only |
| Payment webhook secrets: not stored in DB | ✅ | Loaded from env vars at runtime |
| `DATABASE_URL` / Redis URL in environment, not committed | ✅ | `.env` in `.gitignore` |
| Supabase service key / JWT secret in env | ✅ | Not in codebase |

**Gap:** Digital signatures (`guests.digital_signature`) stored as base64 in DB. For large files, move to Supabase Storage with presigned URL pattern.

---

## 3. PII handling

| PII Field | Location | Protection |
|-----------|----------|-----------|
| Guest name | `guests.first_name`, `last_name` | Encrypted at rest (disk/TDE) |
| Guest document | `guests.document_number` | Encrypted at rest; indexed for search |
| Guest email | `guests.email` | Encrypted at rest; no logging |
| Guest phone | `guests.phone` | Encrypted at rest; no logging |
| Guest address | `guests.address_line1..country` | Encrypted at rest |
| Guest DOB | `guests.date_of_birth` | Encrypted at rest |
| Digital signature | `guests.digital_signature` | base64 in DB; move to storage post-launch |
| Companion PII | `guest_companions.*` | Encrypted at rest |
| Company contact | `companies.contact_email`, `contact_phone` | Encrypted at rest |
| Payment amounts | `transactions.amount` | Numeric, no card numbers stored |

**Retention policy:**
- `guests.retention_until` default now+5yr
- Scheduled job required: soft-delete or anonymize records past `retention_until`
- NOT yet implemented — scheduled for post-launch compliance sprint

**Logging rule:** Never log guest name, document number, email, phone. Log `guest_id`, `hotel_id`, action only.

---

## 4. Financial integrity

| Check | Status | Evidence |
|-------|--------|---------|
| All monetary columns Numeric(12,2) | ✅ | All 20+ financial columns verified in tests |
| No Float in any financial column | ✅ | Phases 1-3 migrations |
| Payment idempotency keys | ⚠️ PARTIAL | `pending_operational_actions` used; dedicated idempotency key table pending |
| Decimal arithmetic in service layer | ✅ | `Decimal(str(value))` pattern throughout |
| Balance due reproducible from stored columns | ✅ | `balance_due` property: `total_amount - amount_paid` |
| Arqueo reproducible from stored movements | ✅ | `expected_balance = opening + income - expense` |

---

## 5. Audit trail

| Check | Status | Evidence |
|-------|--------|---------|
| Append-only audit_logs table | ✅ | `audit_logs` — no UPDATE/DELETE in model |
| Guest data modifications audited | ✅ | v72 §2.2: service layer must write audit record |
| Room move events audited | ✅ | `room_move_events` with trigger_event, state_before/after |
| Permission overrides audited | ✅ | `audit_logs.action` captures authorization events |
| `prohibido_alojar` override audited | ⚠️ SERVICE PENDING | DB ready; service enforcement not yet implemented |
| Cash close approval audited | ✅ | `cash_close_reports.approved_by_user_id` + `approved_at` |
| OTA internal release audited | ⚠️ SERVICE PENDING | DB has audit_logs; service pattern not yet wired |

---

## 6. Availability and concurrency integrity

| Check | Status | Evidence |
|-------|--------|---------|
| Double-booking prevention | ⚠️ DB PARTIAL | UniqueConstraint patterns exist; `SELECT FOR UPDATE` pattern documented in architecture-hybrid.md; service implementation needed |
| Concurrent cash close prevention | ⚠️ SERVICE PENDING | `lock:cash_close:{hotel_id}:{session_id}` Redis lock documented; not yet implemented |
| Concurrent allocation solver prevention | ⚠️ SERVICE PENDING | `lock:allocation:{hotel_id}` Redis lock documented; not yet implemented |
| Optimistic locking for reservation updates | ❌ NOT IMPLEMENTED | No `version` column; use `updated_at` comparison or add PG row version |

**Gap:** No optimistic locking (version column) on `reservations`. Risk: concurrent updates could silently overwrite each other.  
**Recommendation:** Add `version = Column(Integer, default=0)` to `reservations`, increment on every update; reject if version mismatch.

---

## 7. Injection and input validation

| Check | Status | Evidence |
|-------|--------|---------|
| SQL injection: SQLAlchemy ORM used throughout | ✅ | Parameterized queries via ORM |
| Raw SQL: none in codebase | ✅ | No `text()` with user input |
| Pydantic v2 validation at API boundary | ✅ | FastAPI request models use Pydantic |
| Enum validation: SQLAlchemy Enum types | ✅ | All enum columns reject invalid values |
| File URL in company_documents | ⚠️ | URL stored in DB; must not contain embedded auth tokens |

---

## 8. Rate limiting

| Check | Status | Evidence |
|-------|--------|---------|
| API rate limiting by hotel/key | ✅ | `rate_limit_events` table + middleware |
| Per-IP rate limiting | ⚠️ PARTIAL | Middleware exists; Redis counter pattern documented |
| Payment link expiry | ⚠️ PENDING | Link expiry not yet enforced at DB level |

---

## 9. Open security gaps (prioritized)

| Gap | Severity | Action |
|-----|----------|--------|
| `prohibido_alojar` check-in block not enforced in service layer | HIGH | Implement before pilot |
| No optimistic locking on reservations | HIGH | Add `version` column + check in reservation service |
| PII retention schedule not automated | MEDIUM | Scheduled job post-launch |
| PostgreSQL RLS not implemented | MEDIUM | Defense-in-depth layer post-launch |
| Redis distributed locks not wired to services | MEDIUM | Before high-concurrency deploy |
| Payment idempotency key pattern incomplete | MEDIUM | Before Mercado Pago / PayPal go-live |
| Digital signature storage in DB (should be external) | LOW | Move to Supabase Storage post-launch |
| Pydantic `Expected float but got Decimal` warnings | LOW | Use `Annotated[float, PlainValidator(float)]` |
