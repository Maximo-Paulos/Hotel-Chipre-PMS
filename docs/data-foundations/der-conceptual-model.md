# Hotel Chipre PMS — Data Model: Conceptual, Logical, Physical

**Date:** 2026-06-12  
**Alembic HEAD:** `20260612_v72_gaps_phase4`

---

## 1. Conceptual model

Core entities and their relationships in business terms.

```
HOTEL (tenant)
│
├── USERS (staff: owner, co-owner, manager, receptionist, housekeeping)
│   └── HOTEL_MEMBERSHIPS (role per hotel)
│
├── GUESTS (unique per hotel by document)
│   ├── GUEST_COMPANIONS (additional occupants at check-in)
│   ├── GUEST_TAGS (alerts: no_pago, prohibido_alojar, vip, etc.)
│   └── RESERVATIONS (1 guest → many reservations)
│
├── ROOMS (physical units)
│   ├── ROOM_CATEGORIES (type/tier: standard, superior, suite)
│   ├── ROOM_BLOCKS (maintenance/VIP hold/owner use blocks)
│   └── ROOM_MOVE_EVENTS (history of room changes, grouped by RoomMovementGroup)
│
├── COMPANIES (corporate accounts)
│   └── COMPANY_DOCUMENTS (PDFs, vouchers, signature required)
│
├── RESERVATIONS (core booking lifecycle)
│   ├── STATE: pending → deposit_paid → fully_paid → pre_check_in → checked_in → checked_out
│   │         └─ (cancelled / no_show from appropriate states)
│   ├── TRANSACTIONS (payment ledger)
│   ├── BILLING_ADJUSTMENTS (charges/credits post-booking)
│   ├── RESERVATION_ADJUSTMENTS (date change, room change records)
│   ├── WAITLIST_ENTRIES (overbooking queue — never counted as occupants)
│   └── COMPANY_DOCUMENTS (linked via reservation)
│
├── PAYMENTS & FINANCIALS
│   ├── TRANSACTIONS (amount, method, type, status — Numeric(12,2))
│   ├── HOTEL_VOUCHERS (credit vouchers issued on refund)
│   ├── VOUCHER_REDEMPTIONS (usage records)
│   ├── REFUND_REQUESTS (3 paths: gateway/voucher/manual_review)
│   └── PAYMENT_SURCHARGE_CONFIGS (recargos per payment method)
│
├── CASH REGISTER (caja)
│   ├── CASH_SESSIONS (turno: open/closed/pending_approval)
│   ├── CASH_MOVEMENTS (income/expense/adjustment per session)
│   └── CASH_CLOSE_REPORTS (arqueo: expected vs declared, supervisor approval)
│
├── PRICING / COMMERCIAL
│   ├── SELLABLE_PRODUCTS
│   ├── RATE_PLANS + RATE_PLAN_PRICES
│   ├── TAX_POLICIES + TAX_RULES
│   └── FX_POLICIES
│
├── OTA / CHANNEL
│   ├── OTA_PROVIDERS + OTA_CONNECTIONS
│   ├── OTA_PROPERTY/ROOM/RATE_PLAN MAPPINGS
│   ├── OTA_INVENTORY/PRICE/CANCELLATION/COMMISSION RULES
│   └── OTA_SYNC_JOBS + OTA_SYNC_EVENTS
│
├── ALLOCATION ENGINE
│   ├── ALLOCATION_POLICY_PROFILES + VERSIONS
│   ├── ALLOCATION_RUNS + ASSIGNMENTS
│   ├── ROOM_MOVEMENT_GROUPS + ROOM_MOVE_EVENTS
│   └── SOLVER_METRICS + LLM_POLICY_SUGGESTIONS
│
├── SECURITY / API
│   ├── HOTEL_API_KEYS (key_hash + key_prefix, no cleartext)
│   ├── SECURITY_TOKENS (sessions)
│   └── RATE_LIMIT_EVENTS
│
├── AUDIT
│   └── AUDIT_LOGS (append-only: who did what, when, to which entity)
│
└── ANALYTICS (fact tables for reporting)
    ├── FACT_RESERVATION_DAILY
    ├── FACT_ROOM_OCCUPANCY_DAILY
    ├── ROOM_STATE_EVENTS
    └── HOTEL_AUDIT_EVENTS
```

---

## 2. Logical model (key entity-relationship details)

### 2.1 Guest

```
Guest
├── PK: id
├── FK: hotel_id → hotel_configuration.id
├── identity: first_name, last_name, document_type, document_number, nationality, DOB, gender
├── contact: email, phone, address_line1..country
├── behavioral: rating (normal/excelente/complicado), terms_accepted, digital_signature
├── retention: retention_until (default now+5yr)
├── UNIQUE: (hotel_id, document_type, document_number)  ← per-hotel dedup
└── INDEXES: hotel_id+last_name, hotel_id+email, hotel_id+phone, hotel_id+document_number
```

### 2.2 Reservation state machine

```
                     ┌──────────────┐
                     │   PENDING    │
                     └──────┬───────┘
                    ┌───────┴────────┐
              DEPOSIT_PAID      CANCELLED ◄──── (any pre-check-in)
                    │
              FULLY_PAID ──────────── NO_SHOW
                    │
             PRE_CHECK_IN  (§7.2: docs loaded, awaiting room entry)
                    │
               CHECKED_IN
                    │
              CHECKED_OUT (terminal)
```

Constraint: `CHECKED_IN` and `CHECKED_OUT` cannot transition to `CANCELLED` or `NO_SHOW`.

### 2.3 Financial precision

All monetary amounts: `Numeric(12, 2)`.  
Arithmetic: always via `Decimal(str(value))` — never `float(value)` before Decimal ops.  
JSON serialization: `default=lambda o: float(o) if isinstance(o, Decimal) else str(o)`.

### 2.4 Room assignment model

```
Room ← assigned_to → Reservation
 │                        │
 └── RoomBlock            └── WaitlistEntry (not a real reservation — no room)
      (date-ranged,
       affects availability)
```

Availability rule:
```sql
-- Room is available for (hotel_id, room_id, start, end) if:
-- 1. No active reservation overlaps (status NOT IN ('cancelled','no_show'))
-- 2. No active room block overlaps (resolved_at IS NULL)
```

### 2.5 Room move lifecycle

```
RoomMovementGroup (batch cause)
  ├── trigger_reason, created_at, is_reverted
  └── RoomMoveEvent[] (individual moves)
       ├── reservation_id, from_room_id, to_room_id
       ├── move_type, reason_code, reason_note (required for manual)
       ├── trigger_event, state_before, state_after
       └── occurred_at, created_by_user_id
```

When a group is reverted: all moves are reversed, reverted reservations become `allocation_locked=True`.

### 2.6 Cash register lifecycle

```
CashSession
├── status: open → pending_approval → closed
├── opening_balance (Numeric(12,2))
└── CashMovement[] (income/expense/adjustment, amount > 0)
     └── linked to reservation/transaction (optional)

CashCloseReport (1:1 per session)
├── expected_balance = opening_balance + sum(income) - sum(expense)
├── declared_balance (staff count)
├── difference = declared - expected
└── supervisor approval if difference != 0
```

### 2.7 Multi-tenancy isolation

Every domain table has `hotel_id NOT NULL FK` as the primary scoping key.  
Unique constraints are always hotel-scoped:
- Guest: `UNIQUE(hotel_id, document_type, document_number)`
- OTA: `UNIQUE(hotel_id, source_provider_code, external_id)`
- API keys: `UNIQUE(hotel_id, name)`
- Voucher codes: `UNIQUE(hotel_id, voucher_code)`
- Company display name: `UNIQUE(hotel_id, display_name)`

---

## 3. Physical model (table inventory, 2026-06-12)

### 3.1 Core domain (40 tables)

| Table | Records estimate | Key indexes |
|-------|-----------------|-------------|
| hotel_configuration | 1-100 | PK |
| users | 1-1000 | email |
| hotel_memberships | n/a | hotel_id+user_id |
| rooms | 5-500/hotel | hotel_id, category_id |
| room_categories | 2-20/hotel | hotel_id+code, hotel_id+name |
| guests | 100-100K/hotel | hotel_id+last_name, hotel_id+document |
| guest_companions | n/a | guest_id |
| guest_tags | n/a | hotel_id+guest_id |
| reservations | 100-500K/hotel | hotel_id+dates, hotel_id+status |
| reservation_additional_guests | n/a | reservation_id |
| transactions | 1-3/reservation | reservation_id, hotel_id |
| billing_adjustments | n/a | reservation_id |
| reservation_adjustments | n/a | reservation_id |
| reservation_status_history | n/a | reservation_id |
| room_move_events | n/a | reservation_id, group_id |
| room_movement_groups | n/a | hotel_id |
| room_blocks | n/a | hotel_id+room_id, hotel_id+dates |
| waitlist_entries | n/a | hotel_id+status, hotel_id+category+dates |
| companies | n/a | hotel_id |
| company_documents | n/a | hotel_id+reservation_id |

### 3.2 Financial (6 tables)

| Table | Key constraint |
|-------|---------------|
| hotel_vouchers | UNIQUE(hotel_id, voucher_code) |
| voucher_redemptions | FK: voucher_id, reservation_id |
| refund_requests | FK: reservation_id; enum path |
| payment_surcharge_configs | UNIQUE(hotel_id, payment_method) |
| cash_sessions | Index: hotel_id+status |
| cash_movements | FK: session_id; amount > 0 |
| cash_close_reports | UNIQUE: session_id |

### 3.3 OTA / Allocation (20+ tables)

ota_providers, ota_connections, ota_property_mappings, ota_room_mappings, ota_rate_plan_mappings, ota_inventory_rules, ota_price_rules, ota_cancellation_rules, ota_commission_rules, ota_currency_rates, ota_reservation_links, ota_sync_jobs, ota_sync_events, allocation_policy_profiles, allocation_policy_versions, allocation_runs, allocation_assignments, reservation_allocation_locks, allocation_explanations, solver_metrics, manual_override_reasons, llm_policy_suggestions, llm_feedback_events

### 3.4 Security / Auth (4 tables)

hotel_api_keys, security_tokens, rate_limit_events, audit_logs

### 3.5 Analytics (7 tables)

fact_reservation_daily, fact_room_occupancy_daily, room_state_events, hotel_audit_events, analytics_alert_settings, analytics_export_jobs, analytics_ai_usage_monthly

### 3.6 SaaS / Platform (8 tables)

subscriptions, subscription_events, integration_catalog, integration_connections, integration_events, onboarding_state, ai_assistant_sessions, ai_assistant_messages, ai_assistant_action_runs, ai_assistant_insights

---

## 4. Critical constraints summary

| Constraint | Table | Type |
|------------|-------|------|
| `uq_guest_document_per_hotel` | guests | UNIQUE(hotel_id, doc_type, doc_number) |
| `uq_reservation_ota_external_id` | reservations | UNIQUE(hotel_id, source_provider_code, external_id) |
| `uq_hotel_api_key_name` | hotel_api_keys | UNIQUE(hotel_id, name) |
| `uq_surcharge_hotel_method` | payment_surcharge_configs | UNIQUE(hotel_id, payment_method) |
| `uq_voucher_hotel_code` | hotel_vouchers | UNIQUE(hotel_id, voucher_code) |
| `ck_reservation_dates` | reservations | check_out > check_in |
| `ck_room_score_range` | rooms | score IS NULL OR (1 ≤ score ≤ 10) |
| `ck_room_block_dates` | room_blocks | ends_at IS NULL OR ends_at > starts_at |
| `ck_cash_movements_amount_positive` | cash_movements | amount > 0 |
| `ck_reservation_total_positive` | reservations | total_amount ≥ 0 |
| `ck_reservation_adults_positive` | reservations | num_adults > 0 |
| `ck_room_block_indefinite_consistency` | room_blocks | is_indefinite=1 ↔ ends_at IS NULL |

---

## 5. Alembic migration chain

```
cb9001557529_baseline
  → [historical branches: security_tokens, payment_link, OTA, analytics...]
  → 20260424_analytics_r1_base           (fact tables, room state events)
  → 20260612_audit_log_and_transaction_fk
  → 20260612_vouchers_refunds_pending_actions
  → 20260612_v72_gaps_phase1             (Numeric, guest dedup/rating/tags, rooms, caja, waitlist)
  → 20260612_v72_gaps_phase2             (guest indexes, OTA dedup, room_blocks, company fields)
  → 20260612_v72_gaps_phase3             (room_movement_groups, BillingAdjustment Numeric)
  → 20260612_v72_gaps_phase4             (PRE_CHECK_IN, RoomMove audit, company_documents)
                                          ← HEAD
```

Each migration is safe with existing data: uses `batch_alter_table` for SQLite compat, runtime `is_postgres` checks for PG-specific DDL (enum creation, ALTER TYPE ADD VALUE).
