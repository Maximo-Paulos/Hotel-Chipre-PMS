# Graph Report - .  (2026-09-26)

## Corpus Check
- Large corpus: 1306 files · ~1,882,432 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 11140 nodes · 29268 edges · 526 communities detected
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 6122 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: contains: 7537 · uses: 6122 · calls: 5489 · MODIFIES: 3004 · rationale_for: 1493 · imports: 1389 · ON_BRANCH: 1201 · imports_from: 1126 · inherits: 818 · method: 749 · PARENT_OF: 336 · re_exports: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1306 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 14 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `222ef84`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Base` - 376 edges
2. `Reservation` - 277 edges
3. `HotelConfiguration` - 261 edges
4. `ReservationStatusEnum` - 220 edges
5. `Room` - 207 edges
6. `RoomCategory` - 173 edges
7. `HotelMembership` - 169 edges
8. `AuditActionEnum` - 158 edges
9. `SecurityAuditLog` - 143 edges
10. `ReservationError` - 131 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Portable job-dispatch port with Celery as the first implementation.` --uses--> `JobDispatchRecord`  [INFERRED]
  app/adapters/job_dispatcher.py → app/models/job_runtime.py
- `Create one durable intent per tenant/task/key before dispatching.      A duplica` --uses--> `JobDispatchRecord`  [INFERRED]
  app/adapters/job_dispatcher.py → app/models/job_runtime.py
- `Rate limiter with DB-backed persistence for security-sensitive endpoints.  When` --uses--> `RateLimitEvent`  [INFERRED]
  app/adapters/rate_limiter.py → app/models/rate_limit_event.py
- `Staff management endpoints for hotel public API keys.` --uses--> `HotelAPIKeyError`  [INFERRED]
  app/api/hotel_api_keys.py → app/services/hotel_api_key_service.py

## Communities

### Community 411 - "Community 411"
Cohesion: 0.53
Nodes (5): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som

### Community 494 - "Community 494"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 360 - "Community 360"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table.

### Community 495 - "Community 495"
Cohesion: 0.50
Nodes (1): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho

### Community 496 - "Community 496"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 497 - "Community 497"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 463 - "Community 463"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 498 - "Community 498"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 499 - "Community 499"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 500 - "Community 500"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 501 - "Community 501"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 502 - "Community 502"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 503 - "Community 503"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 504 - "Community 504"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 505 - "Community 505"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 399 - "Community 399"
Cohesion: 0.48
Nodes (5): _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260

### Community 464 - "Community 464"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 15 - "Community 15"
Cohesion: 0.02
Nodes (32): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin, v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_, v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus, v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume, v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_, v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event, Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open, laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026 (+24 more)

### Community 435 - "Community 435"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 506 - "Community 506"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 507 - "Community 507"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 508 - "Community 508"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 509 - "Community 509"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 361 - "Community 361"
Cohesion: 0.46
Nodes (7): _sqlite_rebuild_constraints(), _repair_sqlite(), _existing_enum_labels(), _rename_postgres_enum_values(), upgrade(), downgrade(), Align allocation enum storage with the model values.  The original allocation mi

### Community 400 - "Community 400"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat

### Community 436 - "Community 436"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), _drop_successor_reference(), upgrade(), downgrade(), Add zero-balance cash rotation and custody handoffs.

### Community 437 - "Community 437"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio

### Community 438 - "Community 438"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Complete tenant-leading foreign keys outside the core booking domain.  The core

### Community 401 - "Community 401"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (88): _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision, _ensure_adjustment_permission(), StockItemCreate (+80 more)

### Community 362 - "Community 362"
Cohesion: 0.36
Nodes (6): _has_unique(), _has_fk(), _add_constraint_if_missing(), upgrade(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in

### Community 465 - "Community 465"
Cohesion: 0.60
Nodes (4): _constraint(), upgrade(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could

### Community 510 - "Community 510"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 300 - "Community 300"
Cohesion: 0.31
Nodes (9): upgrade(), _create_linen_tables(), _migrate_linen_data(), _finalize_laundry_vendor_columns(), _drop_kind_column(), downgrade(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li (+1 more)

### Community 511 - "Community 511"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (124): add external-effect mode to payment links  Revision ID: 20260812_external_effect, _mercadopago_webhook_impl(), mercadopago_payment_link_webhook(), Settings, BaseSettings, get_settings(), _normalized_env_value(), _has_value() (+116 more)

### Community 211 - "Community 211"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), _install_rls(), _remove_rls(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), upgrade(), downgrade(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill (+5 more)

### Community 226 - "Community 226"
Cohesion: 0.24
Nodes (12): _insert_permission_rows(), _upsert_default(), _backfill_defaults(), _copy_role_overrides(), upgrade(), _install_user_override_rls(), _remove_user_override_rls(), _contract_legacy_rows() (+4 more)

### Community 363 - "Community 363"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 364 - "Community 364"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table.

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (38): repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/, add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide, _authorize_override(), checkin(), checkin_partial(), _LenientDateTime, TypeDecorator, Guest and GuestCompanion models. Exhaustive fields for check-in panel: identity (+30 more)

### Community 512 - "Community 512"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 365 - "Community 365"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state.

### Community 513 - "Community 513"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 466 - "Community 466"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), upgrade(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima

### Community 514 - "Community 514"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 515 - "Community 515"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 516 - "Community 516"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 517 - "Community 517"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 402 - "Community 402"
Cohesion: 0.52
Nodes (6): _columns(), _decode(), _backfill_authoritative_values(), upgrade(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea

### Community 439 - "Community 439"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), seed section visibility permissions and their role defaults  Revision ID: 202608

### Community 35 - "Community 35"
Cohesion: 0.07
Nodes (38): store public marketing inquiries and notification state  Revision ID: 20260828_p, Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, Public marketing inquiries submitted through the website., StructuredData, SeoProps, socialImage, Seo(), BreadcrumbItem (+30 more)

### Community 403 - "Community 403"
Cohesion: 0.57
Nodes (6): _index_map(), _ensure_index(), _drop_index_if_present(), upgrade(), downgrade(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar

### Community 440 - "Community 440"
Cohesion: 0.60
Nodes (5): _has_table(), _has_column(), upgrade(), downgrade(), Fold legacy category pricing into seasonal price periods.

### Community 441 - "Community 441"
Cohesion: 0.60
Nodes (5): _set_role_default(), _restore_session_permission(), upgrade(), downgrade(), Align section defaults and remove the self-session catalog permission.  Revision

### Community 518 - "Community 518"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 301 - "Community 301"
Cohesion: 0.29
Nodes (9): _install_rls(), _remove_rls(), _insert_permission_rows(), _insert_default_rows(), upgrade(), downgrade(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects. (+1 more)

### Community 442 - "Community 442"
Cohesion: 0.47
Nodes (5): _set_role_default(), upgrade(), downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns.

### Community 443 - "Community 443"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083

### Community 366 - "Community 366"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add durable realtime domain event outbox  Revision ID: 20260901_domain_event_out, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 40 - "Community 40"
Cohesion: 0.06
Nodes (38): _has_column(), upgrade(), downgrade(), Add the per-hotel application interface language.  The existing ``languages`` co, _columns(), upgrade(), Move payment-proof bytes off Postgres, into object storage.  `payment_proof_blob, ReferenceCountry (+30 more)

### Community 306 - "Community 306"
Cohesion: 0.28
Nodes (4): Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  `, Regression guard for a real bug: `dee1bd0660f6_ota_allocation_foundation` create, 7b40538 Merge pull request #97 from Maximo-Paulos/fix/ota-lifecycle-enum-case-mismatch, e679aa5 fix(db): sync ota_reservation_lifecycle_enum labels with the ORM

### Community 334 - "Community 334"
Cohesion: 0.42
Nodes (8): _columns(), _indexes(), _create_index_if_missing(), _drop_index_if_present(), _seed_audit_permission(), upgrade(), downgrade(), Operational audit fields, daily cash indexes, and audit read permission.

### Community 77 - "Community 77"
Cohesion: 0.08
Nodes (18): add public marketing pricing plans and early-access leads  Revision ID: 20260910, requestVerification(), verifyEmail(), BrandMarkProps, BrandMark(), storePendingOwner(), getPendingOwner(), clearPendingOwner() (+10 more)

### Community 404 - "Community 404"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op

### Community 405 - "Community 405"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat

### Community 406 - "Community 406"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what

### Community 467 - "Community 467"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), upgrade(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (84): _columns(), upgrade(), Add hotel-scoped staff aliases and password-login capability state.  Revision ID, Persist short-lived MFA step-up ticket use to prevent cross-worker replay., _assert_assignable_role(), _assert_manageable_membership(), _assert_manageable_role(), _membership_user_info() (+76 more)

### Community 367 - "Community 367"
Cohesion: 0.36
Nodes (7): _install_rls(), _remove_rls(), _assert_downgrade_lossless(), upgrade(), downgrade(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins.

### Community 407 - "Community 407"
Cohesion: 0.48
Nodes (6): _enum_labels(), _quote_identifier(), _rename_enum_labels(), upgrade(), downgrade(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:

### Community 154 - "Community 154"
Cohesion: 0.14
Nodes (7): _pg_cron_migration_enabled(), _secure_marketing_leads(), upgrade(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role., 3be6190 fix: align retention timing with privacy notice, 6a4ec23 fix: align retention and login providers with product policy

### Community 368 - "Community 368"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table.

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (67): sync_model_drift_missing_columns  Revision ID: 3eaf48a79290 Revises: 20260419_on, Staff management endpoints for hotel public API keys., _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+59 more)

### Community 519 - "Community 519"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 520 - "Community 520"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 468 - "Community 468"
Cohesion: 0.60
Nodes (4): _check_clause(), upgrade(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (46): add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op, APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote (+38 more)

### Community 521 - "Community 521"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 369 - "Community 369"
Cohesion: 0.46
Nodes (7): _user_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _alter_user_column(), upgrade(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2

### Community 370 - "Community 370"
Cohesion: 0.46
Nodes (7): _hotel_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _replace_fk(), upgrade(), downgrade(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs.

### Community 522 - "Community 522"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 523 - "Community 523"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 524 - "Community 524"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 525 - "Community 525"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 526 - "Community 526"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 527 - "Community 527"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 528 - "Community 528"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 469 - "Community 469"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 444 - "Community 444"
Cohesion: 0.47
Nodes (4): _utcnow(), _seed_ota_providers(), upgrade(), ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l

### Community 27 - "Community 27"
Cohesion: 0.04
Nodes (56): laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7, RemitoDirection, LaundryVendor, LaundryVendorCreate, LaundryVendorUpdate, LaundryVendorPrice, LaundryVendorPriceUpsert, LaundryRemitoLine (+48 more)

### Community 371 - "Community 371"
Cohesion: 0.39
Nodes (7): _has_unique(), _ensure_subscription_composite_target(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b

### Community 529 - "Community 529"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 445 - "Community 445"
Cohesion: 0.60
Nodes (5): _policy_name(), _quoted_table(), upgrade(), downgrade(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL

### Community 408 - "Community 408"
Cohesion: 0.43
Nodes (6): _event_id_type(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i

### Community 470 - "Community 470"
Cohesion: 0.50
Nodes (3): _rls(), upgrade(), Add durable job dedupe and worker heartbeat metadata.

### Community 530 - "Community 530"
Cohesion: 0.50
Nodes (1): Add tenant-scoped object metadata without deleting legacy file references.

### Community 20 - "Community 20"
Cohesion: 0.03
Nodes (49): _DecimalAwareEncoder, _is_demo_mode_enabled(), _require_demo_mode(), _seed_permission_matrix_once(), lifespan(), _InvitationAccessLogFilter, _safe_request_path_for_logging(), security_headers() (+41 more)

### Community 136 - "Community 136"
Cohesion: 0.10
Nodes (8): CacheStore, Protocol, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, AnalyticsAIProvider, RenderRequester, JsonGetter

### Community 273 - "Community 273"
Cohesion: 0.24
Nodes (6): JobSpec, JobDispatcher, CeleryJobDispatcher, dispatch_once(), Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica

### Community 227 - "Community 227"
Cohesion: 0.20
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process fields delivered by a Mercado Pago callback without querying         the

### Community 197 - "Community 197"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 41 - "Community 41"
Cohesion: 0.09
Nodes (45): SimpleRateLimiter, MasterAdminSession, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminContext, _now(), _as_aware(), _hash_value() (+37 more)

### Community 372 - "Community 372"
Cohesion: 0.29
Nodes (3): Telemetry, LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default.

### Community 166 - "Community 166"
Cohesion: 0.24
Nodes (16): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+8 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (63): _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _attach_user_session_cookies(), _audit_security_event(), _run_notification_cycle_best_effort(), _issue_auth_response() (+55 more)

### Community 19 - "Community 19"
Cohesion: 0.07
Nodes (85): Auth endpoints: register, login, email verification and password reset. Verifica, Prefer a hotel whose onboarding is already complete.      When a user belongs to, Set the session cookies and return the raw CSRF token.      The caller must put, Project a global identity event into every hotel the user actively belongs to., No Celery beat runs in this deployment (no worker/beat/Redis     provisioned --, Return a session only after the required account MFA factor succeeds., Verify the Google token and return (claims, normalized email, sub).      The lib, Expose public auth capabilities without returning secrets. (+77 more)

### Community 185 - "Community 185"
Cohesion: 0.22
Nodes (13): _require_demo_mode(), _booking_to_read(), _project_booking_graph(), availability(), price_quote(), list_bookings(), create_booking(), get_booking() (+5 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (135): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses the ca, Quickly seed demo bookings (requires DEMO_MODE=true)., Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., FastAPI routes for Guest management. (+127 more)

### Community 59 - "Community 59"
Cohesion: 0.06
Nodes (22): _require_cash_difference_approval_when_requested(), export_cash_ledger_csv(), recover_domain_events(), stream_domain_events(), Read-only integral operations audit endpoint., Tenant-scoped audit log for tracking mutations across core tables. Every write t, OperationalAuditItemRead, OperationalAuditRead (+14 more)

### Community 37 - "Community 37"
Cohesion: 0.19
Nodes (50): CheckInRequest, FastAPI routes for Check-in / Check-out., B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, _to_read(), _is_manager_context(), _ensure_action_permission(), register_settlement(), cancel_reservation() (+42 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (131): BaseModel, PaymentProofStatusEnum, AllocationPolicyVersionCreate, AllocationPolicyVersionRead, ActiveAllocationPolicyRead, AllocationPolicySuggestionCreate, AllocationPolicySuggestionRead, AllocationPolicySuggestionReviewRequest (+123 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (29): _ticket_key(), _require_permission(), _require_resource_lane(), _realtime_client_or_503(), create_collaboration_ticket(), _patch_conflict_response(), patch_collaborative_resource(), _consume_ticket() (+21 more)

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (91): _RoomTransport, Authenticated field-level collaboration endpoints.  Drafts are ephemeral and saf, Keep collaboration permissions aligned with the normal resource API., Issue a short-lived, one-use ticket for one tenant resource., Persist an optimistic, field-level merge under the current tenant., Process-local peers plus best-effort Redis pub/sub fan-out., Authenticate with a one-use ticket, then exchange safe draft signals., Recover invalidation domains after a cursor without exposing payloads. (+83 more)

### Community 68 - "Community 68"
Cohesion: 0.09
Nodes (21): FastAPI routes for the commercial configuration domain., CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy() (+13 more)

### Community 73 - "Community 73"
Cohesion: 0.10
Nodes (27): Company, CompanyPayload, CompanyDocumentType, CompanyDocumentStatus, CompanyDocument, CompanyDocumentPayload, listCompanies(), createCompany() (+19 more)

### Community 336 - "Community 336"
Cohesion: 0.32
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (91): email_status(), FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., Category, listCategories(), SessionLike, ActionStepUpChallenge, ActionStepUpTicket (+83 more)

### Community 198 - "Community 198"
Cohesion: 0.20
Nodes (9): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection. (+1 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (100): DailyRateOut, Config, DailyRateFallbackOut, DailyRateIn, BulkRateIn, BulkFieldRateIn, BulkRateOut, PricePeriodIn (+92 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (84): _require_demo_mode(), seed_demo(), reset_demo(), Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Operational task inbox and shift handoff endpoints. (+76 more)

### Community 212 - "Community 212"
Cohesion: 0.19
Nodes (8): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, EmailSendResponse, EmailVerifyResponse, SmtpStatus

### Community 213 - "Community 213"
Cohesion: 0.24
Nodes (9): FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, get_all_rates(), get_usd_oficial_rate(), get_single_rate(), create_fx_snapshot() (+1 more)

### Community 153 - "Community 153"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 75 - "Community 75"
Cohesion: 0.13
Nodes (32): _get_tenant_guest(), create_restriction(), list_restrictions(), resolve_restriction(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, GuestRestrictionStatusEnum, GuestRestriction (+24 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (62): Read and resolve the guest room-rejection lifecycle., MovementEventRead, MovementGroupRead, ReservationAllocationLock, GuestRoomAvoidanceStatusEnum, GuestRoomAvoidance, Tenant-scoped room rejections recorded for an individual guest., A guest's active or resolved rejection of one physical room.      ``RoomMoveEven (+54 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (84): _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), add_companions(), GuestRestrictionStatus, GuestRestriction, GuestRestrictionCreatePayload, GuestRestrictionResolvePayload (+76 more)

### Community 45 - "Community 45"
Cohesion: 0.07
Nodes (41): _postgres_healthcheck(), _redis_healthcheck(), _critical_lock_readiness(), live_healthcheck(), ready_healthcheck(), _clickhouse_healthcheck(), datastores_healthcheck(), Process liveness only; never depends on PostgreSQL or Redis. (+33 more)

### Community 66 - "Community 66"
Cohesion: 0.09
Nodes (35): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _store_oauth_code(), _authorize_oauth_state_actor() (+27 more)

### Community 86 - "Community 86"
Cohesion: 0.11
Nodes (20): Revalidate the actor embedded in a short-lived OAuth state token.      Provider, SystemEmailStatus, _normalize_display_from(), EmailProviderError, EmailProvider, ResendEmailProvider, NullEmailProvider, get_email_provider() (+12 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (17): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+9 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (46): VendorCreate, VendorUpdate, VendorRead, VendorPriceUpsert, VendorPriceRead, RemitoLineIn, RemitoCreate, RemitoLineRead (+38 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (66): _schedule_to_read(), get_daily_report_schedule(), update_daily_report_schedule(), FastAPI routes for the notification backend: inbox, push subscriptions, preferen, NEVER_CACHE_PREFIXES, NotificationSeverity, NotificationItem, NotificationListResponse (+58 more)

### Community 32 - "Community 32"
Cohesion: 0.04
Nodes (34): FastAPI routes for the onboarding flow used by smoke tests., OnboardingProviderSetup, OnboardingStatus, OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, CategoryPayload, RoomPayload (+26 more)

### Community 199 - "Community 199"
Cohesion: 0.32
Nodes (11): _can(), _is_operator_scoped(), _can_read_reservation_context(), _report_type_allowed(), _conflict(), get_operational_tasks(), create_operational_task(), patch_operational_task() (+3 more)

### Community 373 - "Community 373"
Cohesion: 0.57
Nodes (5): _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), _guarded_json_payload()

### Community 67 - "Community 67"
Cohesion: 0.12
Nodes (10): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., InboundProviderEventsDisabled, Raised when provider-originated callbacks are disabled for this runtime., OTAError, OTAAuthError (+2 more)

### Community 4 - "Community 4"
Cohesion: 0.05
Nodes (149): PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, FastAPI routes for Payments., ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum, BillingAdjustmentTypeEnum, ReservationAdjustment (+141 more)

### Community 21 - "Community 21"
Cohesion: 0.03
Nodes (50): CollaborationTicketRequest, CollaborationTicketResponse, CollaborationPatchRequest, Transport schemas for authenticated field-level collaboration., utcnow(), hash_invitation_token(), issue_invitation(), find_by_token() (+42 more)

### Community 110 - "Community 110"
Cohesion: 0.09
Nodes (19): _visibility_window_response(), read_visibility_windows(), update_visibility_window(), consume_temporary_action_grant(), PermissionDetail, PermissionCell, PermissionMatrix, PermissionCatalogResponse (+11 more)

### Community 374 - "Community 374"
Cohesion: 0.48
Nodes (7): _temporary_grant_actor(), _temporary_grant_response(), _raise_temporary_grant_http_error(), create_temporary_action_grant(), read_pending_temporary_action_grants(), approve_temporary_action_grant(), deny_temporary_action_grant()

### Community 214 - "Community 214"
Cohesion: 0.21
Nodes (13): _validate_role(), _validate_code(), _target_membership_or_404(), _assert_manageable_membership(), _update_role_override(), update_permission_override(), restore_role_permission_override(), restore_role_permission_defaults() (+5 more)

### Community 53 - "Community 53"
Cohesion: 0.07
Nodes (32): update_promotion(), simulate_promotion_pricing(), Promotions API (v72 mobile-first pricing/promotions task).  CRUD for versioned,, Creates a new immutable version; the previous version is deactivated.     Reserv, Return which promotions would apply and the resulting price breakdown     for a, PromotionBenefitType, PromotionScope, PromotionConditions (+24 more)

### Community 275 - "Community 275"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status()

### Community 127 - "Community 127"
Cohesion: 0.16
Nodes (20): Public contact form endpoint for the marketing site., _request_source(), create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, PublicInquiryNotificationStatus, PublicInquiry, A contact request captured by the public marketing site.      The table is inten, PublicInquiryRateLimitError (+12 more)

### Community 111 - "Community 111"
Cohesion: 0.14
Nodes (21): RateCalendarChannelRestrictions, RateCalendarMeta, GetRateCalendarDailyParams, getRateCalendarDaily(), DailyRatePrices, DailyRateOut, getCategoryDailyRates(), BulkRateResult (+13 more)

### Community 83 - "Community 83"
Cohesion: 0.09
Nodes (25): daily_report(), occupancy_report(), revenue_report(), OperationalReservationSummary, OperationalReservationGroup, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead (+17 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (123): _ensure_manual_rate_permission(), _trigger_reoptimization_bg(), _project_reservation_graph(), create_new_reservation(), create_or_update_manual_ota(), list_reservations(), occupancy_grid(), get_reservation() (+115 more)

### Community 25 - "Community 25"
Cohesion: 0.07
Nodes (73): RoleCatalogItem, RoleListResponse, RoleResponse, CreateCustomRoleRequest, RenameCustomRoleRequest, ArchiveCustomRoleRequest, _role_item(), _rollback_and_raise() (+65 more)

### Community 36 - "Community 36"
Cohesion: 0.05
Nodes (50): _require_manager_room_lane(), _serialize_reallocation_result(), _attach_current_rate(), _housekeeping_room(), list_categories(), get_category(), list_rooms(), room_availability() (+42 more)

### Community 245 - "Community 245"
Cohesion: 0.33
Nodes (10): _current_user(), _safe_resource_id(), _validate_audit_timeline_range(), _build_audit_timeline_csv(), _attach_actor_names(), security_overview(), recent_security_events(), audit_timeline() (+2 more)

### Community 78 - "Community 78"
Cohesion: 0.10
Nodes (25): _remaining_trial_days(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial(), admin_comped_override(), SubscriptionPlan, SubscriptionLimit (+17 more)

### Community 112 - "Community 112"
Cohesion: 0.11
Nodes (14): API routes for reservation waitlist operations., Reservation, WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload, WaitlistPromoteResponse, listWaitlistEntries() (+6 more)

### Community 246 - "Community 246"
Cohesion: 0.31
Nodes (10): _require_plan(), channel_status(), complete_channel(), inbox(), send_message(), create_note(), update_assignment(), update_status() (+2 more)

### Community 337 - "Community 337"
Cohesion: 0.36
Nodes (7): _nested(), _verify_token(), _app_secret(), verify_webhook(), receive_webhook(), Meta Cloud API webhook boundary.  The endpoint verifies Meta's signature before, Walk a chain of dict keys, tolerating non-dict values at any level.      Meta's

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (159): Base, DeclarativeBase, Base class for all ORM models., Base, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings, MasterStripeWebhookEvent (+151 more)

### Community 548 - "Community 548"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 549 - "Community 549"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (30): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change() (+22 more)

### Community 550 - "Community 550"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (36): AuthContext, _parse_header_hotel_id(), _parse_token_hotel_id(), _decode_authorization_header(), _authenticate_user(), _resolve_membership(), get_auth_context(), _action_step_up_tickets() (+28 more)

### Community 247 - "Community 247"
Cohesion: 0.24
Nodes (10): redis_namespace(), namespaced_key(), _client_signature(), get_sync_redis_client(), get_async_redis_client(), reset_clients(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Return one sync client per process, or None for empty configuration. (+2 more)

### Community 554 - "Community 554"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 308 - "Community 308"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 106 - "Community 106"
Cohesion: 0.09
Nodes (5): _serialize_user(), login(), complete_mfa_login(), me(), dashboard_summary()

### Community 138 - "Community 138"
Cohesion: 0.17
Nodes (20): put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi, MasterAdminLoginRequest, MasterAdminMfaLoginRequest, MasterAdminMfaEnrollRequest, MasterAdminMfaCodeRequest, MasterAdminMfaDisableRequest, MasterAdminUserPayload (+12 more)

### Community 248 - "Community 248"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (187): User accounts for authentication. Stores hashed passwords and basic profile flag, 009a9ed docs(tech-0140): pin final local verification, 0254334 Merge branch 'agent-ux' into codex/feature/pms-e2e-scale-hardening, 02908b1 feat(storage): add verified tenant object metadata, 052b93d Merge branch 'agent-stockedit' into codex/feature/pms-e2e-scale-hardening, 078e798 feat(realtime): add durable outbox v2 replay state, 09011b1 feat(security): add revocable server-side sessions alongside existing JWT (TECH-0021 phase 1/2) (#45), 094cf6c Add tenant-scoped RBAC overrides (+179 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (37): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, GemmaActionRunError, get_action_run(), approve_action_run() (+29 more)

### Community 51 - "Community 51"
Cohesion: 0.11
Nodes (41): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, AllocationExplanation (+33 more)

### Community 31 - "Community 31"
Cohesion: 0.11
Nodes (61): str, AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, AnalyticsExportStatusEnum, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsExportJob, AnalyticsAIUsageMonthly (+53 more)

### Community 230 - "Community 230"
Cohesion: 0.27
Nodes (9): CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentStatusUpdate, CompanyDocumentRead (+1 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (48): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., DomainEvent, QueuedDomainChange, _scalar_event_value(), _model_hotel_id(), _model_event_payload(), queue_model_changes() (+40 more)

### Community 279 - "Community 279"
Cohesion: 0.44
Nodes (9): DocumentTypeEnum, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead (+1 more)

### Community 64 - "Community 64"
Cohesion: 0.07
Nodes (31): IntegrationCatalog, IntegrationEvent, WhatsAppChannelStatusEnum, WhatsAppConversationStatusEnum, WhatsAppMessageDirectionEnum, WhatsAppMessageStatusEnum, Tenant-scoped WhatsApp CRM persistence.  The legacy public bot hooks remain sepa, WhatsAppContactRead (+23 more)

### Community 167 - "Community 167"
Cohesion: 0.29
Nodes (15): IntegrationConnection, WhatsAppCRMError, InboundMessageResult, normalize_phone(), complete_embedded_signup(), _channel(), _conversation(), _event() (+7 more)

### Community 115 - "Community 115"
Cohesion: 0.16
Nodes (21): MarketingPricingPlan, MarketingLead, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, Someone who asked for access from the public site.      Email is unique so a rep, _decode_features(), _plan_to_public(), _ordered_plans() (+13 more)

### Community 72 - "Community 72"
Cohesion: 0.16
Nodes (32): NotificationChannelEnum, NotificationOutboxStatusEnum, Notification, PushSubscription, NotificationPreference, NotificationOutbox, DailyReportSchedule, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+24 more)

### Community 155 - "Community 155"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 93 - "Community 93"
Cohesion: 0.13
Nodes (22): PaymentLinkTest, PaymentLinkTestError, _validate_email(), _mercadopago_access_token(), _mercadopago_connection_payload(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email() (+14 more)

### Community 61 - "Community 61"
Cohesion: 0.10
Nodes (33): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, mask_to_weekdays(), PromotionConditions, PromotionCreate (+25 more)

### Community 145 - "Community 145"
Cohesion: 0.23
Nodes (15): ReservationEmailKindEnum, ReservationEmailStatusEnum, ReservationEmailDelivery, Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, HotelOutboundSendResult, ReservationCommunicationError, ReservationEmailSendOutcome (+7 more)

### Community 249 - "Community 249"
Cohesion: 0.24
Nodes (7): StoredObjectStatusEnum, StoredObject, Durable tenant-scoped metadata for private object-storage blobs., Metadata and lifecycle state; bytes remain outside PostgreSQL., register_uploaded_object(), Upload/verify/register object-storage bytes without exposing them in events., Persist pending metadata, upload, stat and mark ready after verification.

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (43): SubscriptionEvent, SubscriptionAdjustment, Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, _now(), _as_utc(), _plan_defaults(), plan_catalog() (+35 more)

### Community 116 - "Community 116"
Cohesion: 0.17
Nodes (22): UserMfaSecret, UserMfaRecoveryCode, TOTP MFA secrets and one-time recovery codes for normal user accounts., MfaSecretUnavailableError, get_user_mfa_secret(), get_active_mfa_secret(), encrypt_totp_secret(), decrypt_totp_secret() (+14 more)

### Community 340 - "Community 340"
Cohesion: 0.25
Nodes (5): AnalyticsInsightRequest, AnalyticsInsightStatusRead, AnalyticsInsightRead, AnalyticsAIChatRequest, AnalyticsAIChatRead

### Community 117 - "Community 117"
Cohesion: 0.12
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 448 - "Community 448"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 309 - "Community 309"
Cohesion: 0.22
Nodes (6): GuestRestrictionOverrideRequest, GuestRestrictionCreate, GuestRestrictionResolveRequest, GuestRestrictionRead, Pydantic schemas for GuestRestriction (formal lodging-prohibition entity)., Carried on reservation/checkin/quote requests to authorize bypassing     an acti

### Community 449 - "Community 449"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceResolveRequest, GuestRoomAvoidanceRead, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 341 - "Community 341"
Cohesion: 0.29
Nodes (4): _normalize_currency(), HotelConfigRead, HotelConfigUpdate, Pydantic schemas for HotelConfiguration.

### Community 231 - "Community 231"
Cohesion: 0.17
Nodes (9): PublicPricingPlan, PublicPricingResponse, LeadCreateRequest, LeadCreateResponse, MasterPricingPlanPayload, MasterPricingPlanListPayload, MasterLeadPayload, MasterLeadListPayload (+1 more)

### Community 232 - "Community 232"
Cohesion: 0.17
Nodes (10): NotificationRead, NotificationListResponse, NotificationMarkReadRequest, PushSubscriptionRegisterRequest, PushSubscriptionUnregisterRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, DailyReportScheduleRead (+2 more)

### Community 141 - "Community 141"
Cohesion: 0.10
Nodes (14): OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, ProviderSetupPayload, PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, CategoriesPayload (+6 more)

### Community 281 - "Community 281"
Cohesion: 0.20
Nodes (9): VisibilityWindowUpdate, VisibilityWindowRead, RolePermissionOverrideRequest, UserPermissionOverrideRequest, PermissionDecision, PermissionCatalogItem, TemporaryActionGrantRequest, TemporaryActionGrantApproveRequest (+1 more)

### Community 217 - "Community 217"
Cohesion: 0.19
Nodes (6): _clean_required(), _clean_optional(), PublicInquiryCreate, PublicInquiryAccepted, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 188 - "Community 188"
Cohesion: 0.17
Nodes (14): RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryOperationalRead, RoomCategoryUpdate, RoomBase, RoomCreate, RoomRead (+6 more)

### Community 310 - "Community 310"
Cohesion: 0.22
Nodes (8): SecurityCurrentUserRead, SecurityOverviewRead, SecurityEventRead, SecurityEventsRead, AuditTimelineItemRead, AuditTimelineRead, RevokeAllSessionsResponse, Public, redacted contracts for hotel security settings.

### Community 379 - "Community 379"
Cohesion: 0.29
Nodes (6): WaitlistEntryCreate, WaitlistEntryUpdate, WaitlistEntryRead, WaitlistPromoteRequest, WaitlistPromoteResponse, Schemas for hotel-scoped waitlist entries.

### Community 380 - "Community 380"
Cohesion: 0.33
Nodes (4): ChatMessage, ChatCompletionRequest, chat_completions(), _extract_latest_user_message()

### Community 311 - "Community 311"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, repair_cash_handoff_schema(), missing_model_tables(), main(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it.

### Community 538 - "Community 538"
Cohesion: 0.67
Nodes (1): One-shot notification cycle: generate due daily reports, then deliver pending ou

### Community 176 - "Community 176"
Cohesion: 0.14
Nodes (15): permission_requires_step_up(), create_action_step_up_ticket(), is_permission_admin_read_action(), create_permission_admin_read_step_up_ticket(), permission_admin_read_step_up_ticket_matches(), action_step_up_ticket_matches(), consume_action_step_up_tickets(), Issue action-bound step-up tickets and a narrow MFA-backed RBAC read scope. (+7 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, GemmaProvider (+12 more)

### Community 107 - "Community 107"
Cohesion: 0.17
Nodes (24): reservation_status_to_outcome(), infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code(), backfill_channel_code(), split_amount_evenly(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact() (+16 more)

### Community 97 - "Community 97"
Cohesion: 0.15
Nodes (22): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _flatten_payload_rows(), _rows_to_csv_bytes(), _png_from_rows(), _sheet_xml_from_table() (+14 more)

### Community 118 - "Community 118"
Cohesion: 0.17
Nodes (21): detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), touch_reservation_fact_window(), calculate_pickup_30d(), _reservation_row_kind(), _resolve_no_show_policy(), _reservation_monetary_totals() (+13 more)

### Community 450 - "Community 450"
Cohesion: 0.50
Nodes (4): _as_utc_datetime(), annotate_analytics_payload(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 218 - "Community 218"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.11
Nodes (53): _now(), _facts_data_as_of(), _hotel_local_now(), _ensure_utc(), _money(), _money_str(), _utc_date_range(), _analytics_window() (+45 more)

### Community 342 - "Community 342"
Cohesion: 0.50
Nodes (7): _decimal(), _value(), _utc(), _utc_bounds(), _db_utc_bounds(), _actor_name(), get_daily_summary()

### Community 169 - "Community 169"
Cohesion: 0.27
Nodes (14): CashRegisterError, _money(), _require_open_session(), open_session(), add_movement(), get_open_session(), record_cash_payment_movement(), _movement_sign() (+6 more)

### Community 343 - "Community 343"
Cohesion: 0.46
Nodes (5): CompanyDocumentError, _get_reservation(), _get_company(), create_document(), set_signature_status()

### Community 251 - "Community 251"
Cohesion: 0.29
Nodes (10): _settings(), _get_redis_client(), _required(), _try_postgres_advisory_lock(), distributed_lock(), with_distributed_lock(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru (+2 more)

### Community 553 - "Community 553"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 104 - "Community 104"
Cohesion: 0.14
Nodes (11): ABC, Foundational OTA adapter interfaces and orchestration services., BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, A provider operation failed before it could return normalized data., Acknowledge processed reservation messages in Booking's queue., OTAAdapterContext, OTAOperationResult (+3 more)

### Community 219 - "Community 219"
Cohesion: 0.22
Nodes (8): Mailer, send_platform_email(), send_verification_email(), send_reset_password_email(), send_verification_success_email(), send_generic_auth_notice_email(), Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists.

### Community 478 - "Community 478"
Cohesion: 0.50
Nodes (3): get_encryption_fernet(), Shared Fernet encryption for secrets stored in the database.  The integration en, Return the repository's existing Fernet instance for stored secrets.

### Community 282 - "Community 282"
Cohesion: 0.38
Nodes (9): _is_cache_fresh(), _get_async(), fetch_all_rates(), fetch_rate(), get_usd_official_rate(), get_usd_rate_for_type(), get_all_rates_snapshot(), get_cached_rates() (+1 more)

### Community 413 - "Community 413"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 539 - "Community 539"
Cohesion: 1.00
Nodes (2): build_gemma_hotel_context(), _enum_value()

### Community 414 - "Community 414"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 189 - "Community 189"
Cohesion: 0.29
Nodes (14): _now(), _audit(), _get_guest(), _active_tag_filter(), find_or_create_guest(), _escape_like_term(), _guest_search_rank(), search_guests() (+6 more)

### Community 344 - "Community 344"
Cohesion: 0.39
Nodes (7): apply_configuration_update(), set_identity(), set_deposit_policy(), set_payment_methods(), set_ota_channels(), Shared writes for hotel configuration concepts., Apply a validated Settings payload to one hotel configuration row.

### Community 252 - "Community 252"
Cohesion: 0.22
Nodes (9): ensure_plans_seeded(), get_or_create_hotel_for_owner(), _ensure_membership_and_subscription(), ensure_all_ota_webhook_secrets(), Hotel helper utilities (ownership + bootstrap)., Seed default plans if missing., Find a hotel configuration owned by the given email, or create a new one.     Al, Create owner membership and starter subscription if missing. (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.15
Nodes (23): redact_integration_error(), _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload(), get_connection_payload() (+15 more)

### Community 451 - "Community 451"
Cohesion: 0.50
Nodes (4): JurisdictionProfile, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 129 - "Community 129"
Cohesion: 0.10
Nodes (18): create_vendor(), get_vendor(), set_vendor_price(), create_remito(), vendor_balance(), vendor_spend(), _quarter_bounds(), vendor_settlements() (+10 more)

### Community 84 - "Community 84"
Cohesion: 0.13
Nodes (24): _utcnow(), _validate_payload(), _insert_ignore(), _redact(), _role_recipient_ids(), _actor_role(), get_effective_notification_preference(), _in_quiet_hours() (+16 more)

### Community 156 - "Community 156"
Cohesion: 0.25
Nodes (10): ObjectStorageError, ObjectStat, _safe_relative_path(), GCSObjectStorage, get_object_storage(), Minimal object-storage abstraction: put/get/delete bytes by key.  Why this exist, Raised when a storage backend cannot complete an operation., Reject any key that could escape the storage root (no `..`, no leading `/`). (+2 more)

### Community 381 - "Community 381"
Cohesion: 0.29
Nodes (2): ObjectStorage, Content-addressed-ish blob store: put/get/delete bytes by string key.

### Community 312 - "Community 312"
Cohesion: 0.33
Nodes (2): LocalObjectStorage, Stores objects as files under a local directory root.      Generalizes the patte

### Community 345 - "Community 345"
Cohesion: 0.25
Nodes (2): S3ObjectStorage, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar

### Community 119 - "Community 119"
Cohesion: 0.28
Nodes (23): OnboardingError, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload(), _current_subscription_context() (+15 more)

### Community 253 - "Community 253"
Cohesion: 0.36
Nodes (10): _utc(), _value(), _money(), _bounds(), _date_filter(), _actor_name(), _area_for(), _row() (+2 more)

### Community 157 - "Community 157"
Cohesion: 0.19
Nodes (15): _guest_name(), _reservation_summary(), _group(), _active_room_blocks(), _available_with_review(), _cash_session(), _alerts(), daily_report() (+7 more)

### Community 79 - "Community 79"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 200 - "Community 200"
Cohesion: 0.14
Nodes (3): OTAProviderAdapter, FakeBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event()

### Community 183 - "Community 183"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 184 - "Community 184"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 280 - "Community 280"
Cohesion: 0.33
Nodes (1): OTAOrchestratorService

### Community 477 - "Community 477"
Cohesion: 0.67
Nodes (3): build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 220 - "Community 220"
Cohesion: 0.37
Nodes (12): create_or_update_manual_ota_reservation(), release_no_guarantee(), _attempt_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean(), _apply_manual_amounts() (+4 more)

### Community 120 - "Community 120"
Cohesion: 0.15
Nodes (23): _create_mercadopago_preference(), _default_email_delivery(), _money(), _is_safe_provider_url(), _signing_secret(), _signature(), sign_external_reference(), resolve_signed_external_reference() (+15 more)

### Community 254 - "Community 254"
Cohesion: 0.42
Nodes (9): PaymentProofError, _decode_image(), _safe_filename(), _reservation(), submit_transfer_proof(), get_transfer_proof(), approve_transfer_proof(), reject_transfer_proof() (+1 more)

### Community 255 - "Community 255"
Cohesion: 0.38
Nodes (10): validate_mercadopago_webhook_signature(), _payload_value(), _normalize_status(), _completed_at(), _is_allowed_status_transition(), _find_existing_event(), _insert_event(), _transaction_exists() (+2 more)

### Community 313 - "Community 313"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 98 - "Community 98"
Cohesion: 0.20
Nodes (25): _settings(), _cache_enabled(), _redis_failure_cooldown_seconds(), _mark_redis_unavailable(), _mark_redis_available(), _get_redis_client(), _load_json(), _store_json() (+17 more)

### Community 146 - "Community 146"
Cohesion: 0.22
Nodes (18): get_reservation_operations_summary(), list_pending_reservation_actions(), _candidate_reservation_ids(), _row_could_generate_action(), resolve_external_channel_follow_up(), clear_reservation_manual_review(), _guest_display_name(), _fmt_date() (+10 more)

### Community 56 - "Community 56"
Cohesion: 0.11
Nodes (44): active_reservations(), _hotel_today_and_timezone(), visible_reservations(), active_reservations_select(), _active_reservations_without_hotel(), generate_confirmation_code(), _invalidate_availability_cache(), _touch_facts() (+36 more)

### Community 452 - "Community 452"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 382 - "Community 382"
Cohesion: 0.43
Nodes (6): sync_room_statuses_after_move(), get_group(), list_groups(), create_grouped_room_move(), revert_group(), _active_reservation_conflicts_for_room()

### Community 233 - "Community 233"
Cohesion: 0.23
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 540 - "Community 540"
Cohesion: 0.67
Nodes (1): Small durable heartbeat API for workers and schedulers.

### Community 142 - "Community 142"
Cohesion: 0.23
Nodes (19): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), _upsert_plan_entitlement(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements() (+11 more)

### Community 147 - "Community 147"
Cohesion: 0.16
Nodes (18): _apply_setting(), _remember_setting(), _set_context_value(), reapply_tenant_context_on_connection(), set_tenant_user_context(), set_tenant_hotel_context(), set_invitation_token_hash_context(), set_tenant_context() (+10 more)

### Community 256 - "Community 256"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 201 - "Community 201"
Cohesion: 0.19
Nodes (13): get_country_catalog(), get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), local_today(), hotel_today(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return the curated country -> timezone catalog as {code, name, timezone} dicts. (+5 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (23): _now(), _as_aware(), _hash_value(), _issue_token(), _session_cookie_secure(), _session_cookie_samesite(), _device_label_from_request(), create_session() (+15 more)

### Community 283 - "Community 283"
Cohesion: 0.44
Nodes (8): WaitlistError, _get_waitlist_entry(), add_to_waitlist(), update_waitlist_entry(), promote_from_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), request_payment_link_for_waitlist()

### Community 383 - "Community 383"
Cohesion: 0.57
Nodes (6): WhatsAppBookingError, availability_lookup(), price_quote(), options_with_prices(), create_reservation(), generate_payment_link()

### Community 202 - "Community 202"
Cohesion: 0.22
Nodes (10): _date_window(), _decimal_total(), _project_operational_window(), _parse_datetime(), detect_no_shows(), project_reservation_facts_to_clickhouse(), project_operational_facts_to_clickhouse(), _project_all_hotels_window() (+2 more)

### Community 307 - "Community 307"
Cohesion: 0.31
Nodes (6): session, jsonResponse(), stepUpRequired(), permissionAdminReadStepUpRequired(), tick(), waitFor()

### Community 113 - "Community 113"
Cohesion: 0.09
Nodes (12): source, { code }, Lead, SOURCE_LABELS, DATE, HEADERS, toCsvCell(), The marketing site's own origin must not depend on an env var being set.  hotels (+4 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (69): credentials, credentials, credentials, backendURL, StoredSession, credentials, SHOTS, VIEWPORTS (+61 more)

### Community 277 - "Community 277"
Cohesion: 0.36
Nodes (5): emailOutboxPath, resetEmailOutbox(), cleanupEmailOutbox(), readLatestCode(), waitForCode()

### Community 22 - "Community 22"
Cohesion: 0.05
Nodes (59): authResponse, CredentialResponse, Window, FakeResponse, _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend() (+51 more)

### Community 304 - "Community 304"
Cohesion: 0.22
Nodes (6): credentials, 00af83e chore(graphify): regenerate graph after B4 manual OTA + manual tarifa + B4.2, 09d638d fix(reservations): revalidate capacity and gate repricing on cross-category room move (B5), 2618f7c feat(rates): expose PayPal and credit card columns in the rate editor (B4.2), 2faa743 feat(reservations): wire "Cargar reserva de OTA" button + manual tarifa on reserva directa, e08928f chore(graphify): regenerate graph after B5 room-move capacity/pricing fix

### Community 143 - "Community 143"
Cohesion: 0.11
Nodes (14): credentials, queryClient, normalize_instruction_paths(), main(), Replace this repository's absolute root in generated instructions only., 3c24834 perf(frontend): stop shipping sourcemaps to production, 4b1d076 perf(frontend): lazy-load all router pages, Suspense at shell boundaries, 634dee4 fix(perf): prefilter pending-actions candidates in SQL instead of scanning all reservations (+6 more)

### Community 534 - "Community 534"
Cohesion: 0.67
Nodes (1): owner

### Community 412 - "Community 412"
Cohesion: 0.33
Nodes (1): credentials

### Community 536 - "Community 536"
Cohesion: 0.67
Nodes (1): credentials

### Community 23 - "Community 23"
Cohesion: 0.06
Nodes (58): MARKETING_ROUTES, replaceTag(), renderRouteHtml(), marketingHtmlPlugin(), indexHtml, vercel, PublicPricingPlan, PublicPricing (+50 more)

### Community 476 - "Community 476"
Cohesion: 0.50
Nodes (2): frontendRoot, publicRoot

### Community 34 - "Community 34"
Cohesion: 0.05
Nodes (45): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, IssueHotelApiKeyPayload, listApiKeys(), issueApiKey(), revokeApiKey(), setPasswordWithGoogle() (+37 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (41): CashSessionStatus, CashMovementType, CashSession, CashMovement, CashCloseReport, CashCustodyHandoff, CashSessionSummary, CashDailyPaymentMethod (+33 more)

### Community 48 - "Community 48"
Cohesion: 0.06
Nodes (29): ApiError, RequestOptions, readCookie(), setMasterAdminCsrfToken(), clearMasterAdminCsrfToken(), safeJson(), masterAdminFetch(), MasterAdminUser (+21 more)

### Community 60 - "Community 60"
Cohesion: 0.08
Nodes (34): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+26 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (43): OperationalTaskType, OperationalTaskStatus, OperationalTaskPriority, OperationalTask, OperationalTaskEvent, ShiftHandoff, OperationalTaskCreate, listOperationalTasks() (+35 more)

### Community 63 - "Community 63"
Cohesion: 0.05
Nodes (33): BuiltinPermissionRole, PermissionRole, PermissionCatalogItem, PermissionProfileMatrix, PermissionMatrixResponse, PermissionOverrideResponse, UserPermissionOverrideResponse, VisibilityWindowHours (+25 more)

### Community 54 - "Community 54"
Cohesion: 0.08
Nodes (39): refreshAfterMutation(), refreshReservationState(), refreshReservationGuestState(), refreshPaymentState(), refreshGuestState(), refreshCashState(), refreshRoomState(), refreshStockState() (+31 more)

### Community 128 - "Community 128"
Cohesion: 0.10
Nodes (15): RateCalendarChannelPrice, RateCalendarChannelDay, RateCalendarDay, RateCalendarGridProps, ChannelSummary, DATE_LABEL, INTEGER_LABEL, ARRIVAL_LABELS (+7 more)

### Community 186 - "Community 186"
Cohesion: 0.14
Nodes (10): RateCalendarResponse, RateEditorGridProps, PRICE_ROWS, WEEKDAY, MONTH, INTEGER_LABEL, SOURCE_LABEL, currencySymbol() (+2 more)

### Community 276 - "Community 276"
Cohesion: 0.20
Nodes (7): DailyRateRangeRow, PriceField, PRICE_FIELDS, WEEKDAY_LABEL, DAY_LABEL, RateEditorMobileCardsProps, RateEditorMobileCards()

### Community 338 - "Community 338"
Cohesion: 0.25
Nodes (5): CLIENT_ID, REDIRECT_URI, AppleAuthorization, AppleSignInResult, Window

### Community 475 - "Community 475"
Cohesion: 0.50
Nodes (3): InfoTipProps, PopoverPosition, InfoTip()

### Community 29 - "Community 29"
Cohesion: 0.03
Nodes (66): PermissionGate(), navItems, MasterAdminRoot(), MasterAdminProtectedShell(), MasterAdminSessionProvider(), LoginPage, RegisterOwnerPage, ForgotPasswordPage (+58 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (33): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+25 more)

### Community 333 - "Community 333"
Cohesion: 0.22
Nodes (6): Stay, Row, Group, DAYS, GROUPS, OccupancyBoard()

### Community 144 - "Community 144"
Cohesion: 0.15
Nodes (16): trimTrailingSlash(), ensureLeadingSlash(), normalizeUrl(), PUBLIC_SITE_URL, PUBLIC_APP_URL, APP_URL_HOSTNAME, SITE_URL_HOSTNAME, PREVIEW_APP_HOST_SUFFIXES (+8 more)

### Community 339 - "Community 339"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 137 - "Community 137"
Cohesion: 0.10
Nodes (15): useRateCalendar(), useCategoryDailyRates(), SingleRateInput, useUpsertDailyRate(), useBulkUpsertRates(), useBulkUpdateRateField(), usePricePeriods(), usePricePeriodMutations() (+7 more)

### Community 409 - "Community 409"
Cohesion: 0.80
Nodes (5): SharedSandboxBootstrapError, load_env(), _literal(), build_sql(), main()

### Community 410 - "Community 410"
Cohesion: 0.47
Nodes (5): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 228 - "Community 228"
Cohesion: 0.36
Nodes (11): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+3 more)

### Community 274 - "Community 274"
Cohesion: 0.49
Nodes (9): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+1 more)

### Community 302 - "Community 302"
Cohesion: 0.42
Nodes (8): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots.

### Community 531 - "Community 531"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 229 - "Community 229"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 81 - "Community 81"
Cohesion: 0.16
Nodes (29): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+21 more)

### Community 446 - "Community 446"
Cohesion: 0.80
Nodes (4): _write_json(), _archive_historical(), _build_cases(), main()

### Community 303 - "Community 303"
Cohesion: 0.44
Nodes (8): OperationalQAError, _utc_now(), _json_bytes(), _write(), _catalog(), initialize(), validate(), main()

### Community 126 - "Community 126"
Cohesion: 0.26
Nodes (20): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+12 more)

### Community 105 - "Community 105"
Cohesion: 0.22
Nodes (23): AttestationError, _sha256(), _canonical_json(), _b64url_encode(), _b64url_decode(), _read_regular_nofollow(), _read_limited(), _json_object() (+15 more)

### Community 335 - "Community 335"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 243 - "Community 243"
Cohesion: 0.25
Nodes (7): example(), test_only_a_newer_observation_timestamp_may_change(), test_any_provider_subject_drift_is_rejected(), test_final_observation_cannot_predate_probes(), test_cli_rejects_symlinked_manifest(), Regression tests for final provider-evidence continuity., e2ae869 Use Render production as cloud QA surface

### Community 471 - "Community 471"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 94 - "Community 94"
Cohesion: 0.22
Nodes (16): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+8 more)

### Community 532 - "Community 532"
Cohesion: 1.00
Nodes (2): validate(), main()

### Community 244 - "Community 244"
Cohesion: 0.40
Nodes (10): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+2 more)

### Community 472 - "Community 472"
Cohesion: 0.83
Nodes (3): run(), validate_json(), main()

### Community 165 - "Community 165"
Cohesion: 0.23
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 62 - "Community 62"
Cohesion: 0.15
Nodes (38): VerificationError, ReadOnlyJsonApi, VerificationConfig, ProviderClients, _dict(), _list(), _string(), _validate_config() (+30 more)

### Community 473 - "Community 473"
Cohesion: 0.83
Nodes (3): _non_empty(), validate_manifest(), main()

### Community 187 - "Community 187"
Cohesion: 0.33
Nodes (14): DrillError, _validate_tables(), _sqlite_path(), _sqlite_counts(), _verify_local_objects(), _run_sqlite(), _postgres_parts(), _pg_command() (+6 more)

### Community 49 - "Community 49"
Cohesion: 0.09
Nodes (47): QABootstrapError, Persona, QABootstrapConfig, QABootstrapResult, ProviderEvidence, _required(), _flag(), _required_port() (+39 more)

### Community 377 - "Community 377"
Cohesion: 0.57
Nodes (6): command(), heading(), fenced(), frontend_routes(), write(), main()

### Community 250 - "Community 250"
Cohesion: 0.33
Nodes (8): PhaseMetrics, LoadConfig, percentile(), safe_headers(), run_phase(), _parse_paths(), _run(), main()

### Community 378 - "Community 378"
Cohesion: 0.52
Nodes (5): RealtimeMetrics, validate_target(), run_load(), _run(), main()

### Community 168 - "Community 168"
Cohesion: 0.20
Nodes (14): E2ESafetyError, prepare_e2e_environment(), reset_e2e_database(), _credentials(), _role_credentials(), _step_up_test_projects(), run_migrations(), upsert_seed_data() (+6 more)

### Community 82 - "Community 82"
Cohesion: 0.07
Nodes (28): _validated_pg_dsn_or_skip(), pg_engine(), _stub_transactional_auth_email(), _isolate_object_storage(), _reset_permission_seed_cache(), db_engine(), db(), sample_categories() (+20 more)

### Community 278 - "Community 278"
Cohesion: 0.31
Nodes (9): reset_projection_clients(), _close_clients(), _enable(), test_mongo_audit_projection_lands_document(), test_neo4j_reservation_assignment_lands_nodes(), _cassandra_probe(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each (+1 more)

### Community 447 - "Community 447"
Cohesion: 0.60
Nodes (4): _migration_dsn(), _run_alembic(), test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips(), Disposable live PostgreSQL proof for the forward Alembic release path.  The rele

### Community 132 - "Community 132"
Cohesion: 0.13
Nodes (18): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), Migration coverage for the deduplication sweep., _run_alembic(), _seed_pre_split_data() (+10 more)

### Community 216 - "Community 216"
Cohesion: 0.28
Nodes (12): BenchmarkResult, derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure(), explain() (+4 more)

### Community 537 - "Community 537"
Cohesion: 0.67
Nodes (1): Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati

### Community 257 - "Community 257"
Cohesion: 0.35
Nodes (10): PostgresTargetSafetyError, _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot (+2 more)

### Community 384 - "Community 384"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 415 - "Community 415"
Cohesion: 0.53
Nodes (5): _receptionist_context(), _open_cash_session(), _create_receptionist_user(), test_receptionist_can_view_and_make_reservation_payments(), POST /api/payments and GET /api/payments/summary/{id} only allowed     owner/co_

### Community 158 - "Community 158"
Cohesion: 0.24
Nodes (16): _auth_context(), step_up_client(), _code_at(), _invalid_code(), _issue_ticket(), test_sensitive_permission_requires_a_matching_ticket_before_handler(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket() (+8 more)

### Community 140 - "Community 140"
Cohesion: 0.14
Nodes (10): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), _tracked_files(), test_raw_graphify_graph_is_not_tracked(), test_tracked_graphify_artifacts_stay_small() (+2 more)

### Community 109 - "Community 109"
Cohesion: 0.17
Nodes (6): make_rooms(), make_res(), TestOverlap, TestGreedyAllocation, TestCPSATAllocation, Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).

### Community 284 - "Community 284"
Cohesion: 0.56
Nodes (8): _seed_hotel(), _guest(), _reservation(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_previous_completed_room_signal_requires_the_new_reservation_category(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query()

### Community 285 - "Community 285"
Cohesion: 0.60
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+1 more)

### Community 385 - "Community 385"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 346 - "Community 346"
Cohesion: 0.46
Nodes (7): _slot(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(), test_allocation_run_creates_movement_group_and_events(), _seed_hotel_rooms_guests(), _reservation()

### Community 258 - "Community 258"
Cohesion: 0.24
Nodes (4): _Response, _Client, test_provider_receives_only_curated_hotel_analytics_payload(), test_provider_chat_uses_curated_hotel_context_and_controlled_message()

### Community 203 - "Community 203"
Cohesion: 0.30
Nodes (11): assert_freshness_metadata(), _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads() (+3 more)

### Community 204 - "Community 204"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed(), test_operational_schema_covers_dimensions_and_non_pii_facts()

### Community 159 - "Community 159"
Cohesion: 0.12
Nodes (7): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_add_reservation_guests_matches_existing_document_despite_whitespace(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), Spin up the real FastAPI app against an in-memory SQLite database., A legacy row with untrimmed whitespace must still be found by the     bulk looku

### Community 259 - "Community 259"
Cohesion: 0.35
Nodes (7): FakeJwkClient, _token(), _verify(), test_valid_apple_token_is_verified(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch()

### Community 148 - "Community 148"
Cohesion: 0.35
Nodes (18): _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation(), _audit_for() (+10 more)

### Community 347 - "Community 347"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 160 - "Community 160"
Cohesion: 0.11
Nodes (11): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_hotel_delete_is_restricted(), test_audit_log_all_actions_persist(), test_transaction_hotel_id_has_fk_constraint(), test_failed_audit_log_insert_does_not_roll_back_callers_change(), TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence. (+3 more)

### Community 316 - "Community 316"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_surfaces_retryable_provider_outage(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue()

### Community 453 - "Community 453"
Cohesion: 0.50
Nodes (3): _override_auth(), test_receptionist_can_get_price_quote(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t

### Community 70 - "Community 70"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+24 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (16): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+8 more)

### Community 99 - "Community 99"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+16 more)

### Community 417 - "Community 417"
Cohesion: 0.60
Nodes (5): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable(), Cancelling a reservation must cancel its still-payable seña links (BR §M).

### Community 348 - "Community 348"
Cohesion: 0.32
Nodes (3): _load_migration(), FakeInspector, test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 121 - "Community 121"
Cohesion: 0.21
Nodes (23): _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_is_allowed(), test_cash_movement_requires_open_session(), test_close_report_expected_balance_from_confirmed_cash(), test_close_with_difference_requires_approval() (+15 more)

### Community 170 - "Community 170"
Cohesion: 0.13
Nodes (6): opened_cash_register(), TestGuestValidation, TestCheckIn, TestCheckOut, Tests for Check-in Service. Validates guest data requirements before allowing ch, Operational tests must prepare the caja before collecting cash.

### Community 222 - "Community 222"
Cohesion: 0.32
Nodes (12): _override_auth(), _client_with_db(), _seed_fully_paid_reservation(), test_checkin_without_new_fields_fails_with_clear_message(), test_checkin_captures_missing_fields_in_same_request(), test_partial_checkin_reaches_pre_check_in_then_final_checkin(), test_partial_checkin_requires_fully_paid(), test_add_companion_during_checkin_flow_appears_in_additional_guests() (+4 more)

### Community 100 - "Community 100"
Cohesion: 0.20
Nodes (25): _make_hotel(), _make_guest(), _make_room(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin(), test_prohibido_tag_from_different_hotel_does_not_block() (+17 more)

### Community 317 - "Community 317"
Cohesion: 0.58
Nodes (8): _get_db_override_target(), _override_auth(), _seed_hotel(), _build_client(), _cleanup_client(), test_owner_can_create_and_update_commercial_configuration(), test_manager_has_no_access_to_commercial_configuration(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories()

### Community 419 - "Community 419"
Cohesion: 0.47
Nodes (4): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi

### Community 386 - "Community 386"
Cohesion: 0.71
Nodes (6): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation()

### Community 387 - "Community 387"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_reservation_is_allocation_locked()

### Community 234 - "Community 234"
Cohesion: 0.26
Nodes (7): get_db_override_target(), get_auth_context_target(), client_with_db(), ctx(), _override_role(), test_manager_without_config_manage_permission_is_denied(), test_owner_can_grant_manager_config_manage_override()

### Community 388 - "Community 388"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 130 - "Community 130"
Cohesion: 0.09
Nodes (1): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva

### Community 190 - "Community 190"
Cohesion: 0.26
Nodes (13): _create_role(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), _step_up_headers(), test_roles_api_contract_read_access_and_owner_only_mutations(), test_role_archive_refuses_active_members_and_pending_invites(), test_expired_pending_invitation_is_not_counted_or_blocking_role_archive(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed() (+5 more)

### Community 420 - "Community 420"
Cohesion: 0.40
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 177 - "Community 177"
Cohesion: 0.21
Nodes (9): FakeRedis, _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_optional_lock_can_degrade_when_redis_is_unavailable(), FakePostgresSession, test_required_lock_uses_postgres_advisory_lock_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 223 - "Community 223"
Cohesion: 0.31
Nodes (9): _seed_hotels(), _outbox_row(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision(), test_worker_records_bounded_failure_and_backoff_without_error_message() (+1 more)

### Community 85 - "Community 85"
Cohesion: 0.11
Nodes (20): _event_engine(), FakeRedis, _settings(), test_realtime_fallback_poll_budget_is_below_ten_seconds(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_permission_invalidation_publishes_without_error_logging(), test_optional_backend_degrades_without_fabricating_an_event(), test_required_backend_raises_when_unavailable() (+12 more)

### Community 191 - "Community 191"
Cohesion: 0.21
Nodes (10): ExplodingDB, ExplodingRequest, test_credential_access_and_email_stop_before_db_or_network(), test_connections_flag_alone_closes_credential_lane(), test_payment_link_test_stops_before_db_or_provider(), test_google_login_stops_before_transport_or_db(), test_apple_login_stops_before_jwks_or_db(), test_provider_callbacks_stop_before_body_parse() (+2 more)

### Community 421 - "Community 421"
Cohesion: 0.53
Nodes (5): _alembic(), _seed_legacy_links(), _assert_migrated(), test_payment_link_migration_backfills_provider_history_and_reupgrades(), Data-contract regression for the payment-link execution-mode migration.

### Community 114 - "Community 114"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 287 - "Community 287"
Cohesion: 0.29
Nodes (5): _integration_client(), _Response, test_validate_gmail_credentials_rejects_missing_send_scope(), test_send_hotel_email_uses_connected_gmail(), test_gmail_oauth_callback_uses_signed_state()

### Community 480 - "Community 480"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_direct_guest_and_companion_audits_exclude_pii(), test_decorator_mongo_projection_excludes_guest_pii()

### Community 481 - "Community 481"
Cohesion: 0.67
Nodes (3): _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite(), B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio

### Community 482 - "Community 482"
Cohesion: 0.67
Nodes (3): _override_auth(), test_create_guest_via_api_accepts_new_checkin_profile_fields(), Regression guard for a real bug B3.2 uncovered: POST /api/guests/ dumps every Gu

### Community 390 - "Community 390"
Cohesion: 0.52
Nodes (6): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) -- skip/

### Community 391 - "Community 391"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_legacy_tags(), _load_migration(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls()

### Community 260 - "Community 260"
Cohesion: 0.38
Nodes (10): _seed_hotel(), _seed_guest_inventory(), _reservation(), _create_payload(), test_restriction_lifecycle_distinguishes_active_expired_and_resolved(), test_restriction_is_tenant_scoped_for_reads_and_resolution(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override() (+2 more)

### Community 454 - "Community 454"
Cohesion: 0.80
Nodes (4): _client(), _move(), test_receptionist_can_record_complaint_but_cannot_resolve_it(), test_second_complaint_reactivates_the_same_guest_room_row()

### Community 455 - "Community 455"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 205 - "Community 205"
Cohesion: 0.46
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 261 - "Community 261"
Cohesion: 0.18
Nodes (3): utc_server_clock(), The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today

### Community 484 - "Community 484"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 50 - "Community 50"
Cohesion: 0.07
Nodes (30): get_db_override_target(), get_auth_context_target(), _invitation_token(), client_with_db(), owner_ctx(), test_atomic_invitation_consumption_rejects_a_rotated_token_hash(), test_existing_user_invitation_requires_matching_authenticated_user(), test_existing_user_invitation_with_own_auth_attaches_without_resetting_account() (+22 more)

### Community 376 - "Community 376"
Cohesion: 0.33
Nodes (3): _FakeDispatcher, JobDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 486 - "Community 486"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 171 - "Community 171"
Cohesion: 0.36
Nodes (16): _override_auth(), _client_with_db(), _teardown(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_vendor_price_write_requires_laundry_price_permission(), test_owner_can_manage_linen_items_and_receptionist_cannot(), test_owner_can_register_a_linen_movement_and_load_an_opening_balance(), test_housekeeping_can_operate_remitos_but_not_manage_vendors() (+8 more)

### Community 149 - "Community 149"
Cohesion: 0.25
Nodes (18): _seed_hotels(), _seed_house_stock(), test_create_vendor_creates_its_own_linen_location(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_remito_line_snapshots_price_and_flags_missing_price() (+10 more)

### Community 101 - "Community 101"
Cohesion: 0.15
Nodes (17): env_page(), FakeRender, mutations(), acquire_lease(), release_lease(), test_acquire_validates_before_writing_and_commits_id_last(), test_acquire_refuses_every_drift_without_mutation(), test_same_production_and_qa_identity_is_rejected_before_get() (+9 more)

### Community 42 - "Community 42"
Cohesion: 0.07
Nodes (37): FakeResponse, _seed_platform_admin(), _complete_master_login(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_admin_absolute_ttl_expires_recently_active_session(), test_master_login_bootstraps_env_account() (+29 more)

### Community 422 - "Community 422"
Cohesion: 0.40
Nodes (4): _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it(), C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1

### Community 235 - "Community 235"
Cohesion: 0.36
Nodes (9): _reservation(), _create_link(), _sign(), _post_webhook(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_duplicate_webhook_delivery_does_not_double_charge(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing() (+1 more)

### Community 392 - "Community 392"
Cohesion: 0.43
Nodes (5): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), This bool-returning shim delegates to the SAME raising validator every     real

### Community 350 - "Community 350"
Cohesion: 0.25
Nodes (5): TestTransactionModel, Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship.

### Community 178 - "Community 178"
Cohesion: 0.13
Nodes (9): TestRoomModels, Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify the hotel has exactly 38 rooms., Same room_number can exist in different hotels without conflict., Verify room string representation. (+1 more)

### Community 288 - "Community 288"
Cohesion: 0.20
Nodes (6): TestGuestModel, Tests for Guest and GuestCompanion models., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Create companions and verify relationship., Verify auto-generated timestamps.

### Community 289 - "Community 289"
Cohesion: 0.20
Nodes (6): TestReservationModel, Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify can_transition_to method., Verify balance_due computed property., Verify nights calculation.

### Community 349 - "Community 349"
Cohesion: 0.25
Nodes (5): TestHotelConfigModel, Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies.

### Community 351 - "Community 351"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 318 - "Community 318"
Cohesion: 0.39
Nodes (8): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel(), test_reset_endpoint_allows_testing_env()

### Community 150 - "Community 150"
Cohesion: 0.20
Nodes (16): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+8 more)

### Community 89 - "Community 89"
Cohesion: 0.09
Nodes (20): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+12 more)

### Community 290 - "Community 290"
Cohesion: 0.20
Nodes (9): test_normalizes_generated_instruction_paths_without_touching_external_paths(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized(), Regression coverage for portable Graphify artifact normalization., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+1 more)

### Community 319 - "Community 319"
Cohesion: 0.50
Nodes (8): _auth(), _client(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_push_subscription_register_and_unregister(), test_preferences_crud(), test_daily_report_schedule_is_owner_co_owner_only(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and

### Community 122 - "Community 122"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), test_enqueue_dedupes_same_event_recipient_channel(), test_enqueue_same_dedupe_key_isolated_per_hotel(), test_enqueue_skips_recipient_without_entity_read_permission(), test_enqueue_skips_recipient_without_active_membership(), test_enqueue_role_based_fanout(), test_enqueue_respects_channel_preference() (+15 more)

### Community 487 - "Community 487"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), test_process_outbox_delivers_across_every_active_hotel(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t

### Community 320 - "Community 320"
Cohesion: 0.50
Nodes (8): _owner(), _outbox_event_types(), test_reservation_lifecycle_enqueues_notifications(), test_no_show_enqueues_notification(), test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), Integration coverage: the real domain-event call sites (reservation lifecycle, c

### Community 206 - "Community 206"
Cohesion: 0.21
Nodes (9): _reserve(), test_reservation_spanning_the_window_is_returned_unclipped(), test_reservation_entirely_before_or_after_window_is_excluded(), test_cancelled_reservation_is_excluded(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(), test_custom_housekeeping_role_gets_anonymized_occupancy_grid(), Tests for B2: GET /api/reservations/occupancy-grid (planilla de ocupación).  Cro (+1 more)

### Community 321 - "Community 321"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database.

### Community 456 - "Community 456"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 322 - "Community 322"
Cohesion: 0.36
Nodes (7): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records(), API coverage for the expanded onboarding wizard.

### Community 263 - "Community 263"
Cohesion: 0.27
Nodes (6): _user(), _reservation(), _transaction(), test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(), test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(), Focused coverage for the operational audit and hotel-local cash projection.

### Community 264 - "Community 264"
Cohesion: 0.40
Nodes (8): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped(), test_available_with_review_surfaces_in_report(), test_daily_report_pending_payments_reflect_consumption_charges(), A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m

### Community 291 - "Community 291"
Cohesion: 0.36
Nodes (8): _user(), test_task_lifecycle_history_and_stale_version(), test_maintenance_task_keeps_block_until_authorized_release(), test_handoff_is_tenant_scoped_and_acknowledged(), test_operator_scope_matches_role_and_assignment(), test_report_only_custom_manager_cannot_read_or_mutate_out_of_scope_tasks(), test_task_links_cannot_cross_tenant(), test_list_tasks_orders_priority_and_due_date()

### Community 352 - "Community 352"
Cohesion: 0.54
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 179 - "Community 179"
Cohesion: 0.28
Nodes (14): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel() (+6 more)

### Community 489 - "Community 489"
Cohesion: 0.50
Nodes (1): TestBookingWebhook

### Community 423 - "Community 423"
Cohesion: 0.33
Nodes (4): TestOTARaceCondition, Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room.

### Community 265 - "Community 265"
Cohesion: 0.25
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret(), test_despegar_webhook_scopes_by_hotel_and_secret()

### Community 323 - "Community 323"
Cohesion: 0.31
Nodes (4): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation(), test_payment_links_api_rejects_manager_without_cash_operate()

### Community 172 - "Community 172"
Cohesion: 0.27
Nodes (15): _enable_external_effects(), _reservation(), test_create_payment_link_persists_link_without_transaction(), test_connections_flag_closed_forces_local_only_before_gateway(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_link_best_effort_when_gateway_fails() (+7 more)

### Community 161 - "Community 161"
Cohesion: 0.22
Nodes (17): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_submit_transfer_proof_validates_image_and_stores_metadata(), test_submit_transfer_proof_reencodes_and_removes_exif(), test_submit_transfer_proof_rejects_non_image_disguised_as_png(), test_submit_transfer_proof_rejects_oversized_payload(), test_proof_bytes_are_tenant_scoped() (+9 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (29): ensure_category_pricing_table(), opened_cash_register(), _assign_hotel(), TestDepositPayment, TestFullPayment, TestBalancePaymentAtCheckin, TestHotelIsolation, TestPaymentEdgeCases (+21 more)

### Community 292 - "Community 292"
Cohesion: 0.47
Nodes (7): _override_auth(), _build_client(), _cleanup(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_reactivate_deactivated_surcharge_via_patch()

### Community 173 - "Community 173"
Cohesion: 0.24
Nodes (15): _reservation(), _link(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key(), test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(), test_rejected_payment_cannot_be_flipped_to_completed_by_later_webhook() (+7 more)

### Community 139 - "Community 139"
Cohesion: 0.21
Nodes (12): _step_up_headers(), _auth(), _client(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_owner_cannot_change_or_restore_another_owners_user_overrides(), test_owner_can_restore_one_role_override_to_catalog_default_with_audit(), test_owner_can_restore_one_user_override_to_role_default_with_audit() (+4 more)

### Community 266 - "Community 266"
Cohesion: 0.29
Nodes (8): _seed_hotel(), test_permission_override_can_deny_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_owner_override_can_grant_permission_missing_from_role_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_get_matrix_includes_hotel_overrides(), test_resolve_seeds_the_matrix_once_per_engine_not_per_call(), A1: resolve() used to call seed_default_permissions() on every invocation      (

### Community 123 - "Community 123"
Cohesion: 0.25
Nodes (23): _override_auth(), _step_up_headers(), _client_with_db(), test_permissions_matrix_available_to_permission_manager_only(), test_permissions_matrix_exposes_only_canonical_rows_with_ui_metadata(), test_revoking_each_section_view_permission_blocks_its_read_endpoint(), test_permission_catalog_exposes_owner_only_normal_metadata_and_help_text(), test_permission_administration_reads_require_mfa_and_share_a_read_only_ticket() (+15 more)

### Community 180 - "Community 180"
Cohesion: 0.26
Nodes (11): _load_migration(), _Result, _RecordingBind, _uppercase_catalog(), test_upgrade_normalizes_only_remaining_enum_labels_and_is_idempotent(), test_downgrade_reverses_only_the_new_migration(), test_upgrade_fails_closed_if_both_enum_labels_exist(), test_upgrade_fails_closed_when_an_expected_label_is_missing() (+3 more)

### Community 131 - "Community 131"
Cohesion: 0.09
Nodes (21): _reset_pg_to_clean_head(), test_alembic_upgrade_on_empty_database(), test_alembic_downgrade_and_reupgrade(), test_numeric_precision_enforced_on_postgres(), test_enum_types_exist_in_postgres(), test_unique_constraints_enforced_on_postgres(), test_explain_analyze_guest_search_index(), test_explain_analyze_reservation_date_range_index() (+13 more)

### Community 76 - "Community 76"
Cohesion: 0.10
Nodes (30): _bootstrap_environment(), _provider_manifest(), _local_evidence_payload(), _safe_environment(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_remote_target_rejects_self_attested_json_without_signed_token() (+22 more)

### Community 124 - "Community 124"
Cohesion: 0.21
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 74 - "Community 74"
Cohesion: 0.11
Nodes (26): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+18 more)

### Community 424 - "Community 424"
Cohesion: 0.60
Nodes (5): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity()

### Community 236 - "Community 236"
Cohesion: 0.44
Nodes (11): _seed_hotel(), _seed_daily_rates(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_missing_fx_rate_raises() (+3 more)

### Community 207 - "Community 207"
Cohesion: 0.29
Nodes (12): _seed_hotel(), _ctx(), test_create_promotion_rejects_percentage_over_100(), test_create_promotion_rejects_duplicate_code(), test_find_applicable_promotions_matches_typed_conditions(), test_find_applicable_promotions_respects_weekday_and_date_range(), test_find_applicable_promotions_matches_guest_tag_type(), test_apply_promotions_never_goes_negative() (+4 more)

### Community 393 - "Community 393"
Cohesion: 0.71
Nodes (6): _override_auth(), _build_client(), _cleanup(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 90 - "Community 90"
Cohesion: 0.17
Nodes (21): manifest(), token_for(), env_page(), FakeRender, HealthResponse, FakeRenderCleanupFailure, FakeRenderPutResponseLost, _mutating_calls() (+13 more)

### Community 237 - "Community 237"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 162 - "Community 162"
Cohesion: 0.29
Nodes (16): _payload(), _configured_settings(), _inquiry_rows(), test_public_inquiry_persists_and_notifies_after_acceptance(), test_public_inquiry_keeps_record_when_notification_fails(), test_public_inquiry_rejects_invalid_required_fields(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_rate_limited_by_source_and_email() (+8 more)

### Community 151 - "Community 151"
Cohesion: 0.12
Nodes (5): _plan(), TestPublicPricing, TestLeadCapture, The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page.

### Community 458 - "Community 458"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 181 - "Community 181"
Cohesion: 0.23
Nodes (14): tagged(), write_fixture(), test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_unsigned_or_fabricated_attestation_is_rejected(), test_altered_signature_is_rejected(), test_signed_attestation_missing_a_summary_hash_is_rejected() (+6 more)

### Community 208 - "Community 208"
Cohesion: 0.48
Nodes (12): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+4 more)

### Community 133 - "Community 133"
Cohesion: 0.10
Nodes (16): get_db_override_target(), get_auth_context_target(), client_with_db(), authed_client(), test_verify_email_code_guessing_is_rate_limited(), test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate(), test_register_is_rate_limited_by_source(), test_concurrent_db_requests_record_each_attempt_before_deciding() (+8 more)

### Community 324 - "Community 324"
Cohesion: 0.56
Nodes (8): _client(), _close(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_stock_read_movement_and_admin_are_independently_enforced_without_mutation(), test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(), test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation(), test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation(), test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation()

### Community 394 - "Community 394"
Cohesion: 0.48
Nodes (6): _load_migration(), _alembic(), _engine(), _seed_pre_revision(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal()

### Community 134 - "Community 134"
Cohesion: 0.15
Nodes (14): FakeRedis, BrokenRedis, _cache_settings(), _reset_cache_client_state(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising(), test_cache_disabled_returns_computed_value_without_constructing_redis() (+6 more)

### Community 325 - "Community 325"
Cohesion: 0.36
Nodes (6): _add_event(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_missing_or_zero_cursor_requires_full_refetch(), test_stale_cursor_requires_full_refetch(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch()

### Community 326 - "Community 326"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 135 - "Community 135"
Cohesion: 0.24
Nodes (17): iso(), write_bundle(), rewrite_summary(), rewrite_manifest(), errors_for(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_short_code_sha_is_rejected(), test_manifest_byte_hash_is_required() (+9 more)

### Community 459 - "Community 459"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 293 - "Community 293"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 267 - "Community 267"
Cohesion: 0.33
Nodes (8): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors(), R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).  No real em

### Community 268 - "Community 268"
Cohesion: 0.22
Nodes (6): _mk_reservation(), _count_queries(), test_pending_actions_query_count_scales_with_candidates_not_total_reservations(), test_pending_actions_prefilter_matches_unfiltered_scan_for_every_trigger_type(), The real N+1 this fix targets: query count must track the number of     reservat, Every distinct way `_build_pending_actions` can produce an action must     still

### Community 460 - "Community 460"
Cohesion: 0.60
Nodes (4): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), Tests for operator-created reservation consumption charges.

### Community 425 - "Community 425"
Cohesion: 0.60
Nodes (5): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly(), test_invalid_recipient_is_rejected_before_provider()

### Community 353 - "Community 353"
Cohesion: 0.46
Nodes (7): _create_sample_reservation(), _completed_transaction(), test_no_show_can_be_marked_without_auto_charge(), test_date_change_without_payments_cancels_and_recreates(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_extension_requires_payment_or_link_action(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 238 - "Community 238"
Cohesion: 0.26
Nodes (9): _make_reservations(), test_default_limit_caps_result_at_50(), test_skip_and_limit_page_through_results(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_listing_uses_one_scalar_reservation_query(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati (+1 more)

### Community 192 - "Community 192"
Cohesion: 0.40
Nodes (14): _override_auth(), _build_client(), _cleanup_client(), _seed_bookable_state(), _payload(), test_receptionist_cannot_set_manual_total_amount(), test_co_owner_cannot_set_manual_total_amount_by_default(), test_manager_cannot_set_manual_total_amount_by_default() (+6 more)

### Community 294 - "Community 294"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 163 - "Community 163"
Cohesion: 0.12
Nodes (5): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields(), test_move_reservation_room_updates_room_status_for_checked_in_reservation(), Room.status is a persisted column, not derived from reservations --     a checke

### Community 426 - "Community 426"
Cohesion: 0.47
Nodes (3): _quote(), test_reservation_rejects_quote_after_pricing_revision_changes(), test_confirmed_reservation_stores_pricing_revision()

### Community 354 - "Community 354"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 395 - "Community 395"
Cohesion: 0.48
Nodes (6): _reservation(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty(), test_search_does_not_leak_across_hotels(), Tests for the reservation global search filter (B1 header search).  Search is a

### Community 57 - "Community 57"
Cohesion: 0.04
Nodes (21): TestConfirmationCode, TestAvailability, TestReservationCreation, TestStateTransitions, Tests for Reservation Service — booking creation, availability checks, state tra, Tests for confirmation code generation., Tests for room availability checking., A room with no reservations should be available. (+13 more)

### Community 182 - "Community 182"
Cohesion: 0.25
Nodes (14): _role_connection(), _seed_engine(), _seed_session(), test_invitation_token_resolves_its_custom_role_under_forced_rls(), test_tenant_isolation_blocks_cross_hotel_reads(), test_no_tenant_context_hides_all_rows(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_after_commit_listener_reapplies_hotel_context() (+6 more)

### Community 224 - "Community 224"
Cohesion: 0.44
Nodes (12): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+4 more)

### Community 327 - "Community 327"
Cohesion: 0.44
Nodes (6): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_housekeeping_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 396 - "Community 396"
Cohesion: 0.29
Nodes (3): test_duplicate_room_number_returns_409(), Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro

### Community 269 - "Community 269"
Cohesion: 0.36
Nodes (7): _seed_move_shapes(), _move(), test_receptionist_is_limited_to_same_category_moves(), test_manager_can_move_each_shape(), test_existing_wide_roles_still_move_anywhere(), test_capacity_tier_alone_includes_each_narrower_tier(), test_manager_capacity_permission_does_not_bypass_occupancy_validation()

### Community 427 - "Community 427"
Cohesion: 0.73
Nodes (5): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation(), _seed_group()

### Community 428 - "Community 428"
Cohesion: 0.40
Nodes (5): _create_rooms_with_soft_deleted_tail(), test_soft_deleted_rooms_are_excluded_from_every_room_count_surface(), Regression coverage for room soft-delete visibility across count surfaces., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th

### Community 328 - "Community 328"
Cohesion: 0.33
Nodes (7): _override_auth(), test_receptionist_can_list_rooms(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_custom_housekeeping_role_receives_safe_room_projection(), Reception needs to read room data to build reservations (room picker, availabili, GET /api/rooms/categories feeds the category picker on both the     Reservations

### Community 239 - "Community 239"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 193 - "Community 193"
Cohesion: 0.23
Nodes (13): _headers(), test_security_overview_and_events_are_redacted_and_tenant_scoped(), test_manager_cannot_read_security_settings(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv(), test_security_csv_treats_formula_prefixed_actor_alias_as_text(), test_audit_surfaces_do_not_expose_mutating_methods(), test_unified_audit_timeline_combines_sources_orders_redacts_and_isolates_tenant(), test_unified_audit_timeline_supports_inclusive_date_filters_and_role_guard() (+5 more)

### Community 429 - "Community 429"
Cohesion: 0.53
Nodes (4): _values(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_env_file_requires_owner_only_permissions()

### Community 355 - "Community 355"
Cohesion: 0.50
Nodes (6): _seed_category(), _delete_audit(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits(), test_room_delete_lists_only_active_blocking_reservations_and_allows_delete_after_move(), test_price_period_delete_soft_deletes_hides_and_audits()

### Community 95 - "Community 95"
Cohesion: 0.09
Nodes (10): Surface, _request_context(), _make_reservation(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _card_value(), _starter_analytics() (+2 more)

### Community 430 - "Community 430"
Cohesion: 0.53
Nodes (5): _migrate(), _unique_column_sets(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi

### Community 194 - "Community 194"
Cohesion: 0.31
Nodes (14): _seed_hotels(), _movement(), test_consumption_report_totals_and_variation_between_periods(), test_consumption_report_only_counts_out_and_adjustment_out(), test_consumption_report_is_hotel_scoped(), test_consumption_report_variation_is_none_without_a_previous_baseline(), test_consumption_report_rejects_invalid_group_by(), test_consumption_report_rejects_inverted_range() (+6 more)

### Community 96 - "Community 96"
Cohesion: 0.12
Nodes (26): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_stock_outbound_cannot_make_quantity_negative(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(), test_stock_adjustment_can_correct_quantity_downward(), test_stock_adjustment_downward_cannot_make_quantity_negative(), test_current_stock_location_filter_is_additive_and_hotel_wide_total_unchanged() (+18 more)

### Community 174 - "Community 174"
Cohesion: 0.21
Nodes (13): _ensure_hotel(), _auth_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_records_audit_event(), test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_comped_override_rejects_unknown_hotel_without_subscription_state(), test_role_gating_for_trial_and_comped_override(), test_manual_transitions_emit_events() (+5 more)

### Community 490 - "Community 490"
Cohesion: 0.67
Nodes (3): _index_names(), test_hot_path_composite_indexes_exist_in_models(), Focused regression tests for the TECH-0063 OLTP audit fixes.

### Community 102 - "Community 102"
Cohesion: 0.26
Nodes (23): _reservation_id(), _create_reservation(), _request(), _approve(), _set_cancel_permission(), _consume(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(), test_ordinary_permission_allows_cancel_without_consuming_supplied_grant() (+15 more)

### Community 356 - "Community 356"
Cohesion: 0.25
Nodes (3): test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(), C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them.

### Community 103 - "Community 103"
Cohesion: 0.11
Nodes (17): _load_rls_migration(), _load_user_override_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract(), test_extended_composite_fk_migration_covers_every_remaining_scoped_fk(), test_extended_composite_fk_migration_has_unique_target_for_every_parent() (+9 more)

### Community 91 - "Community 91"
Cohesion: 0.14
Nodes (18): iso(), evidence_bytes(), FakeGitHub, prepare(), test_trusted_prepare_and_finalize_accept_only_byte_identical_provider_artifact(), test_finalize_rejects_artifact_with_different_bytes(), test_prepare_rejects_release_change_after_qa_code_sha(), test_prepare_rejects_unsuccessful_provider_workflow() (+10 more)

### Community 209 - "Community 209"
Cohesion: 0.16
Nodes (3): _bearer_headers(), test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_session_listing_individual_revoke_logout_and_revoke_all()

### Community 46 - "Community 46"
Cohesion: 0.09
Nodes (17): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _make_reservation(), _make_transaction(), TestOpenSession (+9 more)

### Community 152 - "Community 152"
Cohesion: 0.15
Nodes (18): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price(), test_extend_stay_blocked_when_room_occupied() (+10 more)

### Community 357 - "Community 357"
Cohesion: 0.25
Nodes (6): opened_cash_register(), _pay_full(), V72 §7.1 — Check-in Payment Gate Tests.  Requirement: "No se puede hacer check-i, Payment-gate scenarios start with an explicitly opened caja., Pay the full amount → FULLY_PAID., Cannot checkout a FULLY_PAID reservation that was never checked in.

### Community 295 - "Community 295"
Cohesion: 0.22
Nodes (7): _make_reservation(), TestConfigFlag, Create a PENDING reservation using the first available category., Verify the hotel config flag is respected (default = True → gate enforced)., Config flag is True by default; gate is active for PENDING reservation., Even if document/terms config flags are disabled, payment gate remains active., Cannot checkout a PENDING reservation.

### Community 240 - "Community 240"
Cohesion: 0.21
Nodes (8): _pay_deposit(), TestPaymentGateDepositPaid, Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.      Note, Deposit-only payment (30%) must NOT allow check-in., §7.1: Reservation in DEPOSIT_PAID status raises CheckInError., §7.1: Error message tells the operator the required status is 'fully_paid'., §7.1: Error message also reveals the current (blocking) status., §7.1 positive: paying the remaining balance after deposit allows check-in.

### Community 431 - "Community 431"
Cohesion: 0.33
Nodes (4): TestPaymentGatePending, PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment.

### Community 241 - "Community 241"
Cohesion: 0.17
Nodes (7): TestGuestValidationGates, Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest who has NOT accepted terms is blocked (terms_accepted=False)., When require_document_for_checkin=False, missing document is not an error., When require_terms_acceptance=False, missing terms is not an error.

### Community 271 - "Community 271"
Cohesion: 0.25
Nodes (6): TestCheckoutGate, Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp., After checkout, the assigned room status is set to CLEANING., Calling perform_checkout twice on the same reservation raises CheckInError on se

### Community 329 - "Community 329"
Cohesion: 0.39
Nodes (8): opened_cash_register(), _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains(), Tests for v72 check-out balance reconciliation., Checkout balance scenarios collect cash through an open caja.

### Community 195 - "Community 195"
Cohesion: 0.42
Nodes (12): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+4 more)

### Community 432 - "Community 432"
Cohesion: 0.33
Nodes (2): TestResolveRateCalendar, V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai

### Community 296 - "Community 296"
Cohesion: 0.22
Nodes (6): _make_period(), TestPricePeriodOverlap, DailyRate explicit row takes priority over an active PricePeriod., When two PricePeriods overlap, the one with higher priority is returned., Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics).

### Community 175 - "Community 175"
Cohesion: 0.12
Nodes (9): TestGetPriceForDate, Tier-1: explicit DailyRate row wins over everything else., Tier-2: active PricePeriod used when no DailyRate exists., An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used. (+1 more)

### Community 242 - "Community 242"
Cohesion: 0.17
Nodes (6): TestApplyPricePeriod, apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price.

### Community 330 - "Community 330"
Cohesion: 0.22
Nodes (5): TestDailyRateModelConstraints, Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss.

### Community 397 - "Community 397"
Cohesion: 0.29
Nodes (4): TestPricePeriodModel, PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on

### Community 331 - "Community 331"
Cohesion: 0.42
Nodes (8): opened_cash_register(), _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_no_future_conflict_extends_normally(), Immediate cash settlement scenarios require an operator-opened caja.

### Community 125 - "Community 125"
Cohesion: 0.12
Nodes (13): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_reservation_is_motor_protected_set_on_manual_move(), test_reservation_edit_room_change_protects_manual_assignment(), test_reservation_is_wait_listed_field() (+5 more)

### Community 196 - "Community 196"
Cohesion: 0.20
Nodes (13): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_terminal_reservation_allows_only_arrival_metadata_and_audits_values(), test_update_mobility_restriction_triggers_reoptimization(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_room_move_allows_receptionist_within_the_same_category() (+5 more)

### Community 297 - "Community 297"
Cohesion: 0.36
Nodes (8): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_movement_group_hotel_isolation(), test_revert_already_reverted_group_returns_400(), _seed_group()

### Community 298 - "Community 298"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 164 - "Community 164"
Cohesion: 0.11
Nodes (11): TestReoptimizationTrigger, TestReoptimizationIntegration, V72 §5.2 — Reoptimización continua del motor de asignación.  After each new rese, §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — Integration: after new booking, allocation engine receives correct args. (+3 more)

### Community 492 - "Community 492"
Cohesion: 0.50
Nodes (3): tiny_hotel(), Tests for V72 §9 — Waitlist and Overbooking.  Key implementation details discove, Hotel with one Standard room.  Returns a dict with keys:       config, category_

### Community 332 - "Community 332"
Cohesion: 0.31
Nodes (5): _make_reservation(), TestWaitlistListing, Helper — create a reservation through the service layer., Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted).

### Community 398 - "Community 398"
Cohesion: 0.29
Nodes (4): TestWaitlistModelFields, The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room., Verify is_wait_listed survives a round-trip through the database.

### Community 433 - "Community 433"
Cohesion: 0.33
Nodes (4): TestOverbookingBlocked, When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError.

### Community 434 - "Community 434"
Cohesion: 0.33
Nodes (4): TestWaitlistCreation, When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable.

### Community 225 - "Community 225"
Cohesion: 0.21
Nodes (7): TestWaitlistResolveLogic, Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed., Resolving with a room of a different category must be blocked., Resolving with an already-occupied room must be blocked., Trying to resolve with a non-existent room raises ReservationError., After resolve, the DB row reflects the updated state.

### Community 358 - "Community 358"
Cohesion: 0.25
Nodes (5): TestWaitlistIsolation, is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati, A normal reservation blocks the room; a waitlisted one does not.

### Community 272 - "Community 272"
Cohesion: 0.29
Nodes (6): _context(), _reserve(), _hotel_today(), test_visibility_window_filters_far_future_and_null_is_unlimited(), test_in_house_guest_remains_visible_when_check_in_predates_window(), Regression tests for tenant-scoped, per-role reservation visibility.

### Community 493 - "Community 493"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation()

### Community 462 - "Community 462"
Cohesion: 0.70
Nodes (4): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 359 - "Community 359"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 299 - "Community 299"
Cohesion: 0.53
Nodes (8): _seed_hotel(), _issue_key(), _headers(), _whatsapp_quote(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

### Community 210 - "Community 210"
Cohesion: 0.31
Nodes (12): _signature(), _post(), _message(), _delivery(), test_rejects_a_delivery_whose_signature_does_not_match(), test_ingests_a_signed_inbound_message(), test_one_unusable_message_does_not_discard_the_rest_of_the_batch(), test_tolerates_a_payload_whose_nested_fields_are_not_objects() (+4 more)

### Community 305 - "Community 305"
Cohesion: 0.22
Nodes (9): 16fdc4a test(security): lock in cross-hotel id-collision isolation (Fase 12), 255306b test(payments): explicit evidence that proof uploads reject magic-byte spoofing and oversized payloads, 7040c65 fix(master-admin): Stripe webhook retry redelivery no longer 500s, 9c0cf78 chore(catalog): record commit sha for fase12 cross-hotel audit row, bcbaf10 fix(payments): unify dead MP webhook signature validator + guard payment status regressions, d190bed chore(graphify): regenerate graph after Fase 12 cross-hotel audit tests, d19fd80 fix(frontend): close double-submit race on reservation create/check-in/check-out and stock movements, e82f3cf chore(graphify): regenerate graph after regression-catalog update (+1 more)

### Community 215 - "Community 215"
Cohesion: 0.15
Nodes (13): 2447732 fix(security): bump fastapi/starlette to clear starlette CVEs, 3574c6f qa(catalog): record Fase 14 data/logs/dependencies security findings, 45be255 qa(catalog): record Fase 14b dependency-CVE closure findings, 51c2d3a fix(security): bump react-router-dom 6.30.3 to 7.18.1, fix broken onboarding pill nav, 534f3e8 fix(security): bump Pillow 10.3.0 to 12.3.0 to clear CVEs, 672b76d chore(graphify): regenerate graph after Fase 14b CVE closure, 7eea9ed chore(graphify): regenerate graph after Fase 14 security hardening, 954f79c chore(graphify): regenerate graph after Fase 13 security fixes (+5 more)

### Community 533 - "Community 533"
Cohesion: 0.67
Nodes (3): 393ea8c Refresh generated knowledge inventories, 7433859 Align generated inventories with graph refresh, c50af40 Refresh Graphify knowledge graph

## Knowledge Gaps
- **1277 isolated node(s):** `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.`, `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho` (+1272 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 494`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 495`** (1 nodes): `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 496`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 497`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 498`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 499`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 500`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 501`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 502`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 503`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 504`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 505`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 506`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 507`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 508`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 509`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 510`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 511`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 512`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 513`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 514`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 515`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 516`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 517`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 518`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 519`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 520`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 521`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 522`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 523`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 524`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 525`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 526`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 527`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 528`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 529`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 530`** (1 nodes): `Add tenant-scoped object metadata without deleting legacy file references.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 548`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 549`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 550`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 554`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 155`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 538`** (1 nodes): `One-shot notification cycle: generate due daily reports, then deliver pending ou`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 553`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 539`** (2 nodes): `build_gemma_hotel_context()`, `_enum_value()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 381`** (2 nodes): `ObjectStorage`, `Content-addressed-ish blob store: put/get/delete bytes by string key.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 312`** (2 nodes): `LocalObjectStorage`, `Stores objects as files under a local directory root.      Generalizes the patte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 345`** (2 nodes): `S3ObjectStorage`, `Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 183`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 184`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 280`** (1 nodes): `OTAOrchestratorService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 540`** (1 nodes): `Small durable heartbeat API for workers and schedulers.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 534`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 412`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 536`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 476`** (2 nodes): `frontendRoot`, `publicRoot`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 531`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 532`** (2 nodes): `validate()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 537`** (1 nodes): `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 420`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 484`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 489`** (1 nodes): `TestBookingWebhook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 326`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 432`** (2 nodes): `TestResolveRateCalendar`, `V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 1` to `Community 411`, `Community 14`, `Community 7`, `Community 71`, `Community 41`, `Community 17`, `Community 51`, `Community 30`, `Community 31`, `Community 5`, `Community 59`, `Community 11`, `Community 230`, `Community 198`, `Community 43`, `Community 40`, `Community 213`, `Community 279`, `Community 24`, `Community 75`, `Community 28`, `Community 0`, `Community 18`, `Community 9`, `Community 64`, `Community 167`, `Community 33`, `Community 115`, `Community 72`, `Community 155`, `Community 4`, `Community 93`, `Community 6`, `Community 61`, `Community 127`, `Community 35`, `Community 145`, `Community 19`, `Community 8`, `Community 249`, `Community 55`, `Community 116`, `Community 2`, `Community 311`?**
  _High betweenness centrality (0.110) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 11` to `Community 19`, `Community 37`, `Community 5`, `Community 14`, `Community 9`, `Community 0`, `Community 138`, `Community 40`, `Community 1`, `Community 31`, `Community 4`, `Community 344`, `Community 145`, `Community 252`, `Community 33`, `Community 129`, `Community 72`, `Community 119`, `Community 67`, `Community 93`, `Community 55`, `Community 201`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 5` to `Community 14`, `Community 37`, `Community 31`, `Community 1`, `Community 30`, `Community 51`, `Community 343`, `Community 230`, `Community 75`, `Community 119`, `Community 11`, `Community 67`, `Community 4`, `Community 254`, `Community 145`, `Community 18`, `Community 383`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 373 inferred relationships involving `Base` (e.g. with `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` and `Demo-only utilities: seed sample data and reset the database. Exposed only when`) actually correct?**
  _`Base` has 373 INFERRED edges - model-reasoned connections that need verification._
- **Are the 270 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Lightweight availability placeholder. When all parameters are provided,     it r`) actually correct?**
  _`Reservation` has 270 INFERRED edges - model-reasoned connections that need verification._
- **Are the 254 inferred relationships involving `HotelConfiguration` (e.g. with `AcceptPayload` and `GoogleInvitationAcceptPayload`) actually correct?**
  _`HotelConfiguration` has 254 INFERRED edges - model-reasoned connections that need verification._
- **Are the 218 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Lightweight availability placeholder. When all parameters are provided,     it r`) actually correct?**
  _`ReservationStatusEnum` has 218 INFERRED edges - model-reasoned connections that need verification._