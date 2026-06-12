# v72 Business Requirements → Database Traceability Matrix

**Last updated:** 2026-06-12  
**Worktree:** `clever-chebyshev-98b486`  
**Alembic HEAD:** `20260612_v72_gaps_phase6_payment_tables`

---

## How to read this document

| Column | Meaning |
|--------|---------|
| **v72 §** | Section in `business-requirements-master-v72.md` |
| **Requirement** | What the spec mandates |
| **Table / Field** | SQLAlchemy model and column(s) |
| **Constraint / Index** | DB-level enforcement |
| **Migration** | Alembic revision that creates/alters |
| **Test** | Test(s) that verify the requirement |
| **Status** | ✅ done · ⚠️ partial · ❌ missing |

---

## §1 — Hotel Configuration & Multi-Tenancy

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §1.1 | Each hotel is an isolated tenant | `hotel_configuration.id` as FK root on all domain tables | `hotel_id NOT NULL` everywhere | baseline | `test_multi_hotel_isolation_contracts.py` | ✅ |
| §1.2 | Hotel name, active flag | `hotel_configuration.hotel_name`, `subscription_active` | NOT NULL | baseline | implicit | ✅ |
| §1.3 | No cross-hotel data leakage | All domain tables have `hotel_id` FK | `hotel_id` scoped queries in all services | all | `test_multi_hotel_isolation_contracts.py` | ✅ |

---

## §2 — Guests

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §2.1 | Guest dedup by document per hotel | `guests.(hotel_id, document_type, document_number)` | `uq_guest_document_per_hotel` | `20260612_v72_gaps_phase1` | `test_guest_dedup_by_document` | ✅ |
| §2.2 | Full identity: first/last name, doc type/number, nationality, DOB, gender | `guests.*` | NOT NULL on first/last | baseline | `test_guest_has_valid_identity` | ✅ |
| §2.3 | Contact: email, phone, address | `guests.(email, phone, address_line1…postal_code, country)` | nullable | baseline | implicit | ✅ |
| §2.4 | Fast search by name, phone, email, document | `guests.(hotel_id, last_name)`, `(hotel_id, email)`, `(hotel_id, phone)`, `(hotel_id, document_number)` | Composite indexes | `20260612_v72_gaps_phase2` | `test_guest_search_indexes_exist` | ✅ |
| §2.5 | Companions / additional occupants | `guest_companions.(guest_id, first_name, last_name, document_type, document_number, nationality, DOB)` | FK CASCADE | baseline | implicit | ✅ |
| §2.6 | Guest rating: normal / excelente / complicado | `guests.rating` (GuestRatingEnum) | server_default='normal' | `20260612_v72_gaps_phase1` | `test_guest_rating_persists` | ✅ |
| §2.6 | Guest behavioral tags | `guest_tags.(tag_type)`: no_pago, robo, conflictivo, robo_cosas, prohibido_alojar, requiere_deposito, vip, alergias, otro | FK CASCADE, index hotel+guest | `20260612_v72_gaps_phase1` + `phase2` | `test_guest_tag_persists`, `test_guest_tag_prohibido_alojar_enum_value` | ✅ |
| §2.6 | Tag notes and expiry | `guest_tags.(note, expires_at)` | nullable | `20260612_v72_gaps_phase1` | `test_guest_tag_persists` | ✅ |
| §2.7 | `prohibido_alojar` blocks check-in | `guest_tags.tag_type = 'prohibido_alojar'` | `perform_checkin()` blocks active tag by hotel+guest | `20260612_v72_gaps_phase1` | `tests/test_checkin_security.py` (`test_prohibido_alojar_*`) | ✅ |
| §2.8 | Data retention policy | `guests.retention_until` | default = now+5yr | baseline | implicit | ✅ |

---

## §3 — Companies (Corporate Accounts)

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §3.1 | Company legal and display name | `companies.(legal_name, display_name)` | NOT NULL, `uq_companies_hotel_display_name` | baseline | `test_companies_schema` | ✅ |
| §3.2 | Tax ID dedup per hotel (when not null) | `companies.tax_id` | partial unique index `uq_companies_hotel_tax_id_not_null` | baseline | `test_companies_schema` | ✅ |
| §3.3 | Contact person: name, email, phone, admin contact | `companies.(contact_name, contact_email, contact_phone, administrative_contact)` | nullable | `20260612_v72_gaps_phase2` | `test_company_commercial_fields_exist`, `test_company_commercial_fields_persists` | ✅ |
| §3.4 | Negotiated base rate per company | `companies.base_price` (Numeric(12,2)) | nullable | `20260612_v72_gaps_phase2` | `test_company_commercial_fields_persists` | ✅ |
| §3.5 | Deferred payment / voucher / signature requirements | `companies.(payment_deferred, deferred_days, requires_voucher, requires_signature)` | server_default=false | `20260612_v72_gaps_phase2` | `test_company_commercial_fields_persists` | ✅ |
| §3.6 | Company linked to reservation | `reservations.company_id` FK companies | nullable | baseline | implicit | ✅ |
| §3.6 | Company documents / vouchers for reservations | `company_documents.(hotel_id, reservation_id, company_id, doc_type, status, requires_signature, signed_at)` | FK to reservation/company, hotel indexes | `20260612_v72_gaps_phase4` | `tests/test_postgres_validation.py` (`test_enum_types_exist_in_postgres`) | ✅ |

---

## §4 — Rooms

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §4.1 | Room number, floor | `rooms.(room_number, floor)` | NOT NULL | baseline | implicit | ✅ |
| §4.2 | Room category with base price | `room_categories.base_price_per_night` (Numeric(12,2)) | NOT NULL, ≥0 | `20260612_v72_gaps_phase1` | `test_room_category_base_price_is_numeric` | ✅ |
| §4.3 | Preference score 1-10 for allocation tiebreaker | `rooms.score` (Integer, nullable) | `ck_room_score_range` (1-10) | `20260612_v72_gaps_phase1` | `test_room_score_and_accessibility` | ✅ |
| §4.4 | Accessibility flag for mobility-restricted guests | `rooms.is_accessible` (Boolean) | NOT NULL, default false | `20260612_v72_gaps_phase1` | `test_room_score_and_accessibility` | ✅ |
| §4.5 | Room status / housekeeping state | `room_state_events.(event_type, reason_code)` | enum types | analytics migration | `test_room_state_events_*` | ✅ |
| §4.6 | Room description | `rooms.description` (Text, nullable) | nullable | `20260612_v72_gaps_phase3` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |

---

## §5 — Room Moves & Operations

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §5.1 | Track individual room move events | `room_move_events.(reservation_id, movement_group_id, from_room_id, to_room_id, move_type, reason_code, reason_note, trigger_event, state_before, state_after, occurred_at, created_by_user_id)` | FK to reservations+rooms+room_movement_groups | `20260612_audit_log_and_transaction_fk` + `20260612_v72_gaps_phase3` + `20260612_v72_gaps_phase4` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |
| §5.2 | Move audit trail | `audit_logs` for move events | append-only | `20260612_audit_log_and_transaction_fk` | `test_audit_log_model.py` | ✅ |
| §5.3 | Owner/manager can revert moves | Service-layer concern; DB has all FKs needed | — | — | — | ⚠️ DB ready / service pending |
| §5.4 | Room movement groups (multiple rooms, same cause) | `room_movement_groups` + `room_move_events.movement_group_id` | FK `fk_room_move_events_movement_group_id`, index `ix_room_move_events_group_id` | `20260612_v72_gaps_phase3` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |
| §5.5 | Room move audit context fields | `room_move_events.(reason_note, trigger_event, state_before, state_after)` | nullable audit context | `20260612_v72_gaps_phase4` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |

---

## §6 — Check-In / Check-Out

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §6.1 | Actual check-in/out timestamps | `reservations.(actual_check_in, actual_check_out)` | nullable DateTime | baseline | `test_reservation_state_machine*` | ✅ |
| §6.2 | Mobility restriction flag | `reservations.mobility_restriction` (Boolean) | NOT NULL, default false | `20260612_v72_gaps_phase1` | `test_mobility_restriction` | ✅ |
| §6.3 | Arrival time hint | `reservations.arrival_time_hint` (String 80) | nullable | baseline | implicit | ✅ |
| §6.4 | Guest identity required before check-in | `guests.has_valid_identity` property | service enforces | — | `test_guest_has_valid_identity` | ✅ |
| §6.5 | Terms accepted + digital signature | `guests.(terms_accepted, digital_signature)` | boolean + text | baseline | implicit | ✅ |
| §6.6 | Companion registration at check-in | `guest_companions.*` | FK to guests | baseline | implicit | ✅ |

---

## §7 — Reservations & State Machine

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §7.1 | State machine: pending→deposit_paid→fully_paid→pre_check_in→checked_in→checked_out | `reservations.status` (ReservationStatusEnum) + `VALID_TRANSITIONS` | Enum + service validation | baseline + `20260612_v72_gaps_phase4` | `test_reservation_state_machine*`, `tests/test_checkin_security.py::test_pre_check_in_status_allows_checkin` | ✅ |
| §7.2 | Cancellation from any pre-check-in state | `VALID_TRANSITIONS[PENDING/DEPOSIT_PAID/FULLY_PAID]` includes CANCELLED | code + `can_transition_to()` | baseline | `test_reservation_state_machine*` | ✅ |
| §7.3 | No-show from fully_paid | `VALID_TRANSITIONS[FULLY_PAID]` includes NO_SHOW | code | baseline | implicit | ✅ |
| §7.4 | Cancellation metadata | `reservations.(cancelled_at, cancelled_by_user_id, cancellation_reason_code, cancellation_reason_note)` | nullable | baseline | implicit | ✅ |
| §7.5 | No-show policy applied | `reservations.no_show_policy_applied` (NoShowPolicyAppliedEnum) | NOT NULL, default NONE | baseline | implicit | ✅ |
| §7.6 | Date constraint: checkout > checkin | `ck_reservation_dates` | CheckConstraint | baseline | `test_reservation_date_constraint` | ✅ |
| §7.7 | Num adults ≥ 1, children ≥ 0 | `ck_reservation_adults_positive`, `ck_reservation_children_positive` | CheckConstraint | baseline | implicit | ✅ |
| §7.8 | Optimistic locking for reservation updates | `reservations.version` + `update_reservation_fields(..., client_version=...)` | NOT NULL default 0; service rejects stale versions and increments on update | `20260612_v72_gaps_phase5` | `tests/test_checkin_security.py` (`test_*version*`, `test_stale_version_raises_reservation_error`) | ✅ |

---

## §8 — Payments & Financial Precision

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §8.1 | All monetary amounts Numeric(12,2) | All financial columns across all tables | Numeric(12,2) type | `20260612_v72_gaps_phase1` | `test_*_financial_precision` | ✅ |
| §8.2 | Transaction ledger | `transactions.(amount, gross_amount, tax_amount, fee_amount, net_amount)` all Numeric | NOT NULL | `20260612_v72_gaps_phase1` | `test_transaction_amounts_are_numeric` | ✅ |
| §8.3 | Payment method tracking | `transactions.payment_method` (PaymentMethodEnum) | Enum | baseline | implicit | ✅ |
| §8.4 | Deposit tracking | `reservations.(deposit_amount, amount_paid)` | Numeric(12,2), ≥0 | `20260612_v72_gaps_phase1` | `test_reservation_financial_precision` | ✅ |
| §8.5 | Tax/fee/commission breakdown | `reservations.(tax_amount, fee_amount, commission_amount, net_amount)` | Numeric(12,2) | `20260612_v72_gaps_phase1` | implicit | ✅ |
| §8.6 | FX rate snapshot | `reservations.fx_rate_snapshot` (Float) | nullable | baseline | implicit | ✅ |
| §8.7 | Refund path 1: gateway | `refund_requests.path = 'gateway'` | RefundPathEnum | `20260612_vouchers_refunds_pending_actions` | `test_refund_request_*` | ✅ |
| §8.7 | Refund path 2: hotel voucher | `hotel_vouchers` + `voucher_redemptions` | FK + unique code per hotel | `20260612_vouchers_refunds_pending_actions` | `test_hotel_voucher_*` | ✅ |
| §8.7 | Refund path 3: manual review | `refund_requests.path = 'manual_review'` | RefundPathEnum | `20260612_vouchers_refunds_pending_actions` | `test_refund_request_*` | ✅ |
| §8.8 | Payment surcharge config | `payment_surcharge_configs.(hotel_id, payment_method, surcharge_pct, surcharge_fixed)` | `uq_surcharge_hotel_method` | `20260612_v72_gaps_phase1` | `test_payment_surcharge_config_*` | ✅ |
| §8.9 | Billing adjustments | `billing_adjustments`, `reservation_adjustments` with Numeric(12,2) amounts | FK to reservations | `20260612_audit_log_and_transaction_fk` + `20260612_v72_gaps_phase3` | `tests/test_postgres_validation.py::test_numeric_precision_enforced_on_postgres` | ✅ |
| §8.10 | Gateway payment tracking | `payments` — `app/models/payment.py::Payment` | amount > 0, FK `(hotel_id, reservation_id)`, unique `(hotel_id, provider, external_payment_id)`, performance indexes | `20260612_v72_gaps_phase6_payment_tables` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |
| §8.11 | Guest-facing payment links | `payment_links` — `app/models/payment.py::PaymentLink` | amount checks, FK `(hotel_id, reservation_id)`, unique `link_code`, unique external reference, status indexes | `20260612_v72_gaps_phase6_payment_tables` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |
| §8.12 | Payment webhook raw event log | `payment_webhook_events` — `app/models/payment.py::PaymentWebhookEvent` | FK `(hotel_id, payment_id)`, unique `(hotel_id, provider, webhook_id)`, unprocessed webhook index | `20260612_v72_gaps_phase6_payment_tables` | `tests/test_postgres_validation.py` migration upgrade coverage | ✅ |
| §8.13 | Transactions vs payments source-of-truth rule | `transactions` remains canonical ledger; `payments` is gateway state only | documented idempotency/source-of-truth split | `20260612_v72_gaps_phase6_payment_tables` | `docs/data-foundations/transactions-vs-payments.md` | ✅ documented |

---

## §9 — Waitlist / Overbooking

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §9.1 | Waitlist separate from reservations | `waitlist_entries` (own table, NOT in reservations) | — | `20260612_v72_gaps_phase1` | `test_waitlist_entry_persists` | ✅ |
| §9.2 | Waitlist never counted as occupants | Queries on `waitlist_entries` are separate from availability queries | architectural | — | `test_waitlist_entry_persists` (no room assigned) | ✅ |
| §9.3 | Waitlist status lifecycle | `waitlist_entries.status`: waiting→promoted/cancelled/expired | WaitlistStatusEnum | `20260612_v72_gaps_phase1` | `test_waitlist_entry_persists` | ✅ |
| §9.4 | Promoted reservation link | `waitlist_entries.promoted_reservation_id` FK | nullable | `20260612_v72_gaps_phase1` | implicit | ✅ |
| §9.5 | Priority ordering | `waitlist_entries.priority` (Integer) | ≥0, default 100 | `20260612_v72_gaps_phase1` | implicit | ✅ |

---

## §10 — OTA / Channel Manager

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §10.1 | OTA reservation deduplication | `reservations.(hotel_id, source_provider_code, external_id)` | `uq_reservation_ota_external_id` | `20260612_v72_gaps_phase2` | `test_reservation_ota_dedup_constraint_exists` | ✅ |
| §10.2 | OTA provider registry | `ota_providers` | — | `dee1bd0660f6_ota_allocation_foundation` | implicit | ✅ |
| §10.3 | OTA connection per hotel+provider | `ota_connections` | — | `dee1bd0660f6` | implicit | ✅ |
| §10.4 | Room/rate plan/property mappings | `ota_room_mappings`, `ota_rate_plan_mappings`, `ota_property_mappings` | — | `dee1bd0660f6` | implicit | ✅ |
| §10.5 | Inventory/price/cancellation/commission rules | `ota_inventory_rules`, `ota_price_rules`, `ota_cancellation_rules`, `ota_commission_rules` | — | `dee1bd0660f6` | implicit | ✅ |
| §10.6 | Sync jobs + events | `ota_sync_jobs`, `ota_sync_events` | — | `dee1bd0660f6` | implicit | ✅ |
| §10.7 | External reservation link | `ota_reservation_links`, `reservations.(external_id, external_confirmation_code)` | — | baseline + `dee1bd0660f6` | implicit | ✅ |
| §10.8 | Source channel code | `reservations.channel_code` (ReservationChannelCodeEnum) | Enum | baseline | implicit | ✅ |

---

## §11 — Allocation Engine

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §11.1 | Allocation policy profiles + versions | `allocation_policy_profiles`, `allocation_policy_versions` | — | `dee1bd0660f6` | implicit | ✅ |
| §11.2 | Allocation runs + assignments | `allocation_runs`, `allocation_assignments` | — | `dee1bd0660f6` | implicit | ✅ |
| §11.3 | Manual override reasons | `manual_override_reasons` | — | `dee1bd0660f6` | implicit | ✅ |
| §11.4 | Room score used as tiebreaker | `rooms.score` (1-10) consumed by solver | allocation service | `20260612_v72_gaps_phase1` | `test_room_score_and_accessibility` | ⚠️ DB ✅ / solver integration pending |
| §11.5 | Mobility-restricted guest → accessible room | `reservations.mobility_restriction` + `rooms.is_accessible` | solver uses both | `20260612_v72_gaps_phase1` | `test_mobility_restriction` | ⚠️ DB ✅ / solver integration pending |
| §11.6 | Allocation lock | `reservation_allocation_locks` | — | `dee1bd0660f6` | implicit | ✅ |
| §11.7 | LLM policy suggestions | `llm_policy_suggestions`, `llm_feedback_events` | — | `dee1bd0660f6` | implicit | ✅ |

---

## §12 — Pricing / Rate Plans / Tax Policies

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §12.1 | Sellable products + room compatibility | `sellable_products`, `product_room_compatibility` | — | baseline | implicit | ✅ |
| §12.2 | Rate plans + prices | `rate_plans`, `rate_plan_prices` | — | baseline | implicit | ✅ |
| §12.3 | Payment surcharges per method | `payment_surcharge_configs.(surcharge_pct, surcharge_fixed)` | `uq_surcharge_hotel_method`, range checks | `20260612_v72_gaps_phase1` | `test_payment_surcharge_config_*` | ✅ |
| §12.4 | Tax policies + rules | `tax_policies`, `tax_rules` | — | baseline | implicit | ✅ |
| §12.5 | FX policies | `fx_policies` | — | baseline | implicit | ✅ |
| §12.6 | Category pricing overrides | `category_pricing` | — | baseline | implicit | ✅ |

---

## §13 — Cash Register (Caja)

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §13.1 | Cash session lifecycle: open→closed/pending_approval | `cash_sessions.(status, opened_at, closed_at, opening_balance)` | `ck_cash_sessions_opening_nonneg` | `20260612_v72_gaps_phase1` | `test_cash_session_lifecycle` | ✅ |
| §13.2 | Cash movements: income/expense/adjustment | `cash_movements.(movement_type, amount)` | `ck_cash_movements_amount_positive` | `20260612_v72_gaps_phase1` | `test_cash_movement_persists` | ✅ |
| §13.3 | Link movements to reservations/transactions | `cash_movements.(reservation_id, transaction_id)` | nullable FK | `20260612_v72_gaps_phase1` | implicit | ✅ |
| §13.4 | Close report: expected vs declared, difference, supervisor approval | `cash_close_reports.(expected_balance, declared_balance, difference, difference_approved, approved_by_user_id)` | unique per session | `20260612_v72_gaps_phase1` | `test_cash_close_report_persists` | ✅ |

---

## §14 — Room Blocks

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §14.1 | Date-ranged room blocks | `room_blocks.(starts_at, ends_at)` | `ck_room_block_dates` | `20260612_v72_gaps_phase2` | `test_room_block_persists`, `test_room_block_indefinite` | ✅ |
| §14.2 | Indefinite blocks (no end date) | `room_blocks.(is_indefinite=true, ends_at=NULL)` | `ck_room_block_indefinite_consistency` | `20260612_v72_gaps_phase2` | `test_room_block_indefinite` | ✅ |
| §14.3 | Block reason codes | `room_blocks.reason_code` (RoomBlockReasonEnum): maintenance/deep_cleaning/owner_use/vip_hold/overbooking_buffer/other | Enum | `20260612_v72_gaps_phase2` | `test_room_block_persists` | ✅ |
| §14.4 | Block resolution (lift) + trigger reoptimization | `room_blocks.(resolved_at, resolved_by_user_id)` | nullable | `20260612_v72_gaps_phase2` | `test_room_block_persists` (is_active) | ⚠️ DB ✅ / reoptimization trigger pending |
| §14.5 | Blocks affect availability | Availability queries must exclude `room_blocks` active date ranges | service-layer | — | — | ⚠️ service pending |

---

## §15 — Audit & Security

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §15.1 | Append-only audit log | `audit_logs.(hotel_id, table_name, record_id, action, actor_user_id, payload_before, payload_after, created_at)` | `ix_audit_logs_hotel_created`, `ix_audit_logs_hotel_table_record` | `20260612_audit_log_and_transaction_fk` | `test_audit_log_model.py` | ✅ |
| §15.2 | Security tokens (sessions) | `security_tokens` | — | `20260408_security_tokens` | implicit | ✅ |
| §15.3 | Rate limit events | `rate_limit_events` | — | `20260408_launch_security_hardening` | implicit | ✅ |

---

## §16 — Hotel API Keys

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §16.1 | API keys per hotel (WhatsApp, web engine, channel managers) | `hotel_api_keys.(hotel_id, name, purpose, key_prefix, key_hash)` | `uq_hotel_api_key_name` | `20260612_v72_gaps_phase1` | `test_hotel_api_key_persists` | ✅ |
| §16.2 | No cleartext secret stored | Only `key_hash` + `key_prefix` (8 chars) stored | no `secret` column | `20260612_v72_gaps_phase1` | `test_hotel_api_key_persists` | ✅ |
| §16.3 | Key revocation | `hotel_api_keys.(is_active, revoked_at, revoked_by_user_id)` | nullable | `20260612_v72_gaps_phase1` | implicit | ✅ |

---

## §17 — Analytics & Reporting

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §17.1 | Fact tables for daily occupancy + reservations | `fact_reservation_daily`, `fact_room_occupancy_daily` | — | `20260424_analytics_r1_base` | analytics schema tests | ✅ |
| §17.2 | Room state events | `room_state_events` | — | `20260424_analytics_r1_base` | analytics schema tests | ✅ |
| §17.3 | Hotel audit events | `hotel_audit_events` | — | `20260424_analytics_r1_base` | analytics schema tests | ✅ |
| §17.4 | Analytics alert settings + export jobs | `analytics_alert_settings`, `analytics_export_jobs` | — | `20260424_analytics_r1_base` | analytics schema tests | ✅ |

---

## §18 — SaaS / Subscriptions

| v72 § | Requirement | Table / Field | Constraint / Index | Migration | Test | Status |
|-------|-------------|---------------|--------------------|-----------|------|--------|
| §18.1 | Subscription plans + hotel subscriptions | `subscriptions`, `subscription_events` | — | `20260407_subscription_tables` | implicit | ✅ |
| §18.2 | Integration catalog + connections | `integration_catalog`, `integration_connections`, `integration_events` | — | `9b0becb6c658_add_integration_catalog` | implicit | ✅ |

---

## Cross-cutting PostgreSQL Validation

| Area | Requirement | Evidence | Migration scope | Test | Status |
|------|-------------|----------|-----------------|------|--------|
| all | Real PostgreSQL validation suite exists for v72 database foundation | 8 skip-gated tests: empty DB upgrade, downgrade+reupgrade, Numeric precision, enum types, unique constraints, two EXPLAIN index checks, SELECT FOR UPDATE concurrency pattern | full Alembic chain through `20260612_v72_gaps_phase6_payment_tables` | `tests/test_postgres_validation.py` | ✅ suite present / not run in this docs-only task |

---

## Gap summary

### Critical gaps (blocking DATABASE_FOUNDATION_COMPLETE)

| Gap | Section | What's missing | Priority |
|-----|---------|----------------|----------|
| `room_blocks` availability integration | §14.5 | Availability queries must exclude active blocks | HIGH |
| ~~Payment SQLAlchemy models~~ | §8.10-§8.12 | RESOLVED 2026-06-12: `app/models/payment.py` adds Payment, PaymentLink, PaymentWebhookEvent mirroring phase6; registered in `app/models/__init__.py` | RESOLVED |

### Non-critical gaps (post-foundation)

| Gap | Section | Note |
|-----|---------|------|
| Solver uses `rooms.score` as tiebreaker | §11.4 | DB ready; allocation solver integration pending |
| Solver uses `mobility_restriction` + `is_accessible` | §11.5 | DB ready; solver integration pending |
| Room move group revert (manager/co-owner) | §5.3 | Service-layer feature; all FKs present |
| Block release triggers reoptimization | §14.4 | Service-layer event; `resolved_at` field present |
| Pydantic `Expected float but got Decimal` warnings | — | Use `Annotated[float, PlainValidator(float)]` in schemas |
| PayPal webhook verification | — | Needs real provider test |

---

## Migration chain (HEAD)

```
cb9001557529_baseline
  → 20260404_add_hotel_scope
  → 20260407_subscription_tables
  → 20260408_launch_security_hardening
  → 20260410_reservation_financial_lifecycle
  → 20260411_ai_assistant_sessions
  → 20260412_ai_assistant_insights
  → 20260419_onboarding_wizard_state
  → 20260421_master_admin_panel
  → 20260424_analytics_r1_base
  → 20260612_audit_log_and_transaction_fk
  → 20260612_vouchers_refunds_pending_actions
  → 20260612_v72_gaps_phase1
  → 20260612_v72_gaps_phase2
  → 20260612_v72_gaps_phase3
  → 20260612_v72_gaps_phase4
  → 20260612_v72_gaps_phase5
  → 20260612_v72_gaps_phase6_payment_tables   ← HEAD
```

Historical branches (non-blocking): `20260408_security_tokens`, `20260408_payment_link_email_sender_metadata`, `20260419_subscription_trial_comped`, `20260421_master_admin_system_owner`, `b7c1f0a8f9d2_add_payment_link_tests`, `d4f8c21e7b10_extend_payment_link_tests_states`, `9c0d2f3e1a44_guest_legal_profile`, `a7f3d2c1b9e8_ota_hardening`, `3eaf48a79290_sync_model_drift_missing_columns`, `dee1bd0660f6_ota_allocation_foundation`, `9b0becb6c658_add_integration_catalog`.
