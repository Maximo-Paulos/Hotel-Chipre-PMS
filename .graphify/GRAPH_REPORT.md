# Graph Report - .  (2026-10-06)

## Corpus Check
- Large corpus: 1532 files · ~2,132,091 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 13801 nodes · 45306 edges · 651 communities detected
- Extraction: 76% EXTRACTED · 24% INFERRED · 0% AMBIGUOUS · INFERRED: 10934 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 10934 · contains: 9234 · calls: 6895 · ON_BRANCH: 6835 · MODIFIES: 4185 · rationale_for: 2179 · imports: 1632 · imports_from: 1312 · inherits: 942 · method: 836 · PARENT_OF: 318 · re_exports: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1532 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 15 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `d5da108`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 468 edges
2. `HotelConfiguration` - 434 edges
3. `Base` - 408 edges
4. `ReservationStatusEnum` - 378 edges
5. `Room` - 339 edges
6. `RoomCategory` - 288 edges
7. `HotelMembership` - 246 edges
8. `SecurityAuditLog` - 246 edges
9. `Company` - 226 edges
10. `AuditActionEnum` - 222 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Portable job-dispatch port with Celery as the first implementation.` --uses--> `JobDispatchRecord`  [INFERRED]
  app/adapters/job_dispatcher.py → app/models/job_runtime.py
- `Create one durable intent per tenant/task/key before dispatching.      A duplica` --uses--> `JobDispatchRecord`  [INFERRED]
  app/adapters/job_dispatcher.py → app/models/job_runtime.py
- `Manage and inspect per-night extras on corporate reservations.` --uses--> `CompanyNightChargeError`  [INFERRED]
  app/api/company_night_charges.py → app/services/company_night_charge_service.py
- `invite_user()` --calls--> `InviteResponse`  [EXTRACTED]
  app/api/users.py → frontend/src/api/users.ts

## Communities

### Community 470 - "Community 470"
Cohesion: 0.53
Nodes (5): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (223): hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house, Separate historical cash receipts from the active drawer and seed access.  Revis, Add a dedicated permission for recording OTA reservations.  Revision ID: 2026092, Add read access for the privacy-safe housekeeping board.  Revision ID: 20260930_, Separate housekeeping state from room availability.  Revision ID: 20260930_house, Version laundry vendor prices by effective date and restrict default edits.  Rev, Link the outgoing and incoming ledger rows for atomic stock transfers., Add per-hotel bounded manual reservation rates and their audit fields. (+215 more)

### Community 583 - "Community 583"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 414 - "Community 414"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table.

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (43): Publish owner-approved monthly subscription prices.  Revision ID: 11be7c9387c4 R, persist missing linen declared on laundry return slips  Revision ID: 20261005_la, Persist idempotent payment receipt email outcomes.  Revision ID: 20261016_paymen, Track neutral supplier follow-up for declared laundry shortages.  Revision ID: 2, Merge week two remediation heads  Revision ID: 4f3c177c4ba4 Revises: 20261005_ou, Idempotency and outcome record for explicit payment receipt emails., credentials, credentials (+35 more)

### Community 584 - "Community 584"
Cohesion: 0.50
Nodes (1): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho

### Community 585 - "Community 585"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 586 - "Community 586"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 543 - "Community 543"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 587 - "Community 587"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 588 - "Community 588"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 589 - "Community 589"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 590 - "Community 590"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 591 - "Community 591"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 592 - "Community 592"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 593 - "Community 593"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 594 - "Community 594"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 457 - "Community 457"
Cohesion: 0.48
Nodes (5): _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260

### Community 544 - "Community 544"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 595 - "Community 595"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 596 - "Community 596"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 597 - "Community 597"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 598 - "Community 598"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 599 - "Community 599"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 600 - "Community 600"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 500 - "Community 500"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 601 - "Community 601"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 602 - "Community 602"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 603 - "Community 603"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 604 - "Community 604"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 605 - "Community 605"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 606 - "Community 606"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 607 - "Community 607"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 608 - "Community 608"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 609 - "Community 609"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 610 - "Community 610"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 611 - "Community 611"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 612 - "Community 612"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 613 - "Community 613"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 614 - "Community 614"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 615 - "Community 615"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 415 - "Community 415"
Cohesion: 0.46
Nodes (7): _sqlite_rebuild_constraints(), _repair_sqlite(), _existing_enum_labels(), _rename_postgres_enum_values(), upgrade(), downgrade(), Align allocation enum storage with the model values.  The original allocation mi

### Community 458 - "Community 458"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat

### Community 501 - "Community 501"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), _drop_successor_reference(), upgrade(), downgrade(), Add zero-balance cash rotation and custody handoffs.

### Community 502 - "Community 502"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio

### Community 503 - "Community 503"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Complete tenant-leading foreign keys outside the core booking domain.  The core

### Community 616 - "Community 616"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 617 - "Community 617"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 459 - "Community 459"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (108): _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7, Read-only integral operations audit endpoint., _has_per_method_nightly_price() (+100 more)

### Community 416 - "Community 416"
Cohesion: 0.36
Nodes (6): _has_unique(), _has_fk(), _add_constraint_if_missing(), upgrade(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in

### Community 618 - "Community 618"
Cohesion: 0.50
Nodes (1): Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re

### Community 619 - "Community 619"
Cohesion: 0.50
Nodes (1): Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for

### Community 545 - "Community 545"
Cohesion: 0.60
Nodes (4): _constraint(), upgrade(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could

### Community 620 - "Community 620"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 621 - "Community 621"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 351 - "Community 351"
Cohesion: 0.31
Nodes (9): upgrade(), _create_linen_tables(), _migrate_linen_data(), _finalize_laundry_vendor_columns(), _drop_kind_column(), downgrade(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li (+1 more)

### Community 622 - "Community 622"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 623 - "Community 623"
Cohesion: 0.50
Nodes (1): stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision

### Community 624 - "Community 624"
Cohesion: 0.50
Nodes (1): add external-effect mode to payment links  Revision ID: 20260812_external_effect

### Community 246 - "Community 246"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), _install_rls(), _remove_rls(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), upgrade(), downgrade(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill (+5 more)

### Community 268 - "Community 268"
Cohesion: 0.24
Nodes (12): _insert_permission_rows(), _upsert_default(), _backfill_defaults(), _copy_role_overrides(), upgrade(), _install_user_override_rls(), _remove_user_override_rls(), _contract_legacy_rows() (+4 more)

### Community 417 - "Community 417"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 418 - "Community 418"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table.

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (32): repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/, add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide, _authorize_override(), checkin(), checkin_partial(), ExampleInstrumentedTest, MainActivity, BridgeActivity (+24 more)

### Community 625 - "Community 625"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 419 - "Community 419"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state.

### Community 626 - "Community 626"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 546 - "Community 546"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), upgrade(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima

### Community 627 - "Community 627"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 628 - "Community 628"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 629 - "Community 629"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 630 - "Community 630"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 460 - "Community 460"
Cohesion: 0.52
Nodes (6): _columns(), _decode(), _backfill_authoritative_values(), upgrade(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea

### Community 504 - "Community 504"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), seed section visibility permissions and their role defaults  Revision ID: 202608

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (354): store public marketing inquiries and notification state  Revision ID: 20260828_p, Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  `, add public marketing pricing plans and early-access leads  Revision ID: 20260910, _pg_cron_migration_enabled(), _secure_marketing_leads(), upgrade(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role. (+346 more)

### Community 461 - "Community 461"
Cohesion: 0.57
Nodes (6): _index_map(), _ensure_index(), _drop_index_if_present(), upgrade(), downgrade(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar

### Community 505 - "Community 505"
Cohesion: 0.60
Nodes (5): _has_table(), _has_column(), upgrade(), downgrade(), Fold legacy category pricing into seasonal price periods.

### Community 506 - "Community 506"
Cohesion: 0.60
Nodes (5): _set_role_default(), _restore_session_permission(), upgrade(), downgrade(), Align section defaults and remove the self-session catalog permission.  Revision

### Community 631 - "Community 631"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 352 - "Community 352"
Cohesion: 0.29
Nodes (9): _install_rls(), _remove_rls(), _insert_permission_rows(), _insert_default_rows(), upgrade(), downgrade(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects. (+1 more)

### Community 507 - "Community 507"
Cohesion: 0.47
Nodes (5): _set_role_default(), upgrade(), downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns.

### Community 508 - "Community 508"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083

### Community 420 - "Community 420"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add durable realtime domain event outbox  Revision ID: 20260901_domain_event_out, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 547 - "Community 547"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), Add the per-hotel application interface language.  The existing ``languages`` co

### Community 548 - "Community 548"
Cohesion: 0.50
Nodes (3): _columns(), upgrade(), Move payment-proof bytes off Postgres, into object storage.  `payment_proof_blob

### Community 384 - "Community 384"
Cohesion: 0.42
Nodes (8): _columns(), _indexes(), _create_index_if_missing(), _drop_index_if_present(), _seed_audit_permission(), upgrade(), downgrade(), Operational audit fields, daily cash indexes, and audit read permission.

### Community 462 - "Community 462"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op

### Community 463 - "Community 463"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat

### Community 464 - "Community 464"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what

### Community 549 - "Community 549"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), upgrade(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs

### Community 550 - "Community 550"
Cohesion: 0.50
Nodes (3): _columns(), upgrade(), Add hotel-scoped staff aliases and password-login capability state.  Revision ID

### Community 632 - "Community 632"
Cohesion: 0.50
Nodes (1): Persist short-lived MFA step-up ticket use to prevent cross-worker replay.

### Community 421 - "Community 421"
Cohesion: 0.36
Nodes (7): _install_rls(), _remove_rls(), _assert_downgrade_lossless(), upgrade(), downgrade(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins.

### Community 465 - "Community 465"
Cohesion: 0.48
Nodes (6): _enum_labels(), _quote_identifier(), _rename_enum_labels(), upgrade(), downgrade(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:

### Community 353 - "Community 353"
Cohesion: 0.40
Nodes (9): _cron_is_required(), _create_and_secure_retention_holds(), _upgrade_sqlite(), _downgrade_sqlite(), _install_purge_function(), _reschedule_purge_job(), upgrade(), downgrade() (+1 more)

### Community 509 - "Community 509"
Cohesion: 0.53
Nodes (5): _has_columns(), _indexes(), upgrade(), downgrade(), Add check-in policy, manual receipt references, and auditable refunds.

### Community 385 - "Community 385"
Cohesion: 0.50
Nodes (8): _has_columns(), _set_global_role_defaults(), _set_manager_operational_defaults(), _set_housekeeping_whatsapp_defaults(), _backfill_external_ota_credits(), upgrade(), downgrade(), Backfill legacy OTA credits and operational role defaults.  This data migration

### Community 633 - "Community 633"
Cohesion: 0.50
Nodes (1): Separate payment-proof reading/review from financial reports.  Revision ID: 2026

### Community 634 - "Community 634"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reverting room-movement groups.  Revision ID: 202

### Community 551 - "Community 551"
Cohesion: 0.60
Nodes (4): _install_purge_function(), upgrade(), downgrade(), Backfill the public inquiry retention clock and update the purge function.  Revi

### Community 635 - "Community 635"
Cohesion: 0.50
Nodes (1): Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026

### Community 510 - "Community 510"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), Add tenant-scoped groups for multi-room reservations.

### Community 466 - "Community 466"
Cohesion: 0.43
Nodes (5): _has_unique(), _has_fk(), _enable_tenant_rls(), upgrade(), Harden company nightly charge tenant keys and row level security.

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (48): Store hotel FX market preferences and conversion provenance.  Revision ID: 20261, Add separately guarded, MFA-protected manual cash adjustments.  Revision ID: 202, _remaining_trial_days(), _require_master_admin_write(), _master_admin_hotel_id(), _serialize_status_payload(), subscription_status(), change_plan() (+40 more)

### Community 636 - "Community 636"
Cohesion: 0.50
Nodes (1): Record payment tender separately from reservation balance currency.  Revision ID

### Community 422 - "Community 422"
Cohesion: 0.36
Nodes (7): _enable_tenant_rls(), _disable_tenant_rls(), _disable_silent_rls_filtering(), upgrade(), downgrade(), Add effective-dated company extra-person rates and audited charge corrections., Make destructive downgrade guards fail if PostgreSQL would hide rows.

### Community 423 - "Community 423"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table.

### Community 511 - "Community 511"
Cohesion: 0.40
Nodes (4): _restore_reservations_hotel_index(), downgrade(), sync_model_drift_missing_columns  Revision ID: 3eaf48a79290 Revises: 20260419_on, Restore the legacy index even if a later downgrade already did so.

### Community 512 - "Community 512"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), linen location par levels  Revision ID: 41d66acfb13a Revises: 015f7e36b9cd Creat

### Community 637 - "Community 637"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 638 - "Community 638"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 552 - "Community 552"
Cohesion: 0.60
Nodes (4): _check_clause(), upgrade(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in

### Community 639 - "Community 639"
Cohesion: 0.50
Nodes (1): add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op

### Community 640 - "Community 640"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 424 - "Community 424"
Cohesion: 0.46
Nodes (7): _user_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _alter_user_column(), upgrade(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2

### Community 641 - "Community 641"
Cohesion: 0.50
Nodes (1): laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre

### Community 425 - "Community 425"
Cohesion: 0.46
Nodes (7): _hotel_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _replace_fk(), upgrade(), downgrade(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs.

### Community 642 - "Community 642"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 643 - "Community 643"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 644 - "Community 644"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 645 - "Community 645"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 646 - "Community 646"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 647 - "Community 647"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 648 - "Community 648"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 386 - "Community 386"
Cohesion: 0.33
Nodes (8): _install_rls(), _remove_rls(), _assert_no_duplicate_remitos(), _guard_day2_downgrade_data(), upgrade(), downgrade(), Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, a, Refuse rollback when it would discard operational data or session state.

### Community 553 - "Community 553"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 513 - "Community 513"
Cohesion: 0.47
Nodes (4): _utcnow(), _seed_ota_providers(), upgrade(), ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l

### Community 426 - "Community 426"
Cohesion: 0.39
Nodes (7): _has_unique(), _ensure_subscription_composite_target(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b

### Community 649 - "Community 649"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 514 - "Community 514"
Cohesion: 0.60
Nodes (5): _policy_name(), _quoted_table(), upgrade(), downgrade(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL

### Community 467 - "Community 467"
Cohesion: 0.43
Nodes (6): _event_id_type(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i

### Community 554 - "Community 554"
Cohesion: 0.50
Nodes (3): _rls(), upgrade(), Add durable job dedupe and worker heartbeat metadata.

### Community 153 - "Community 153"
Cohesion: 0.10
Nodes (8): CacheStore, Protocol, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, AnalyticsAIProvider, RenderRequester, JsonGetter

### Community 320 - "Community 320"
Cohesion: 0.24
Nodes (6): JobSpec, JobDispatcher, CeleryJobDispatcher, dispatch_once(), Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica

### Community 269 - "Community 269"
Cohesion: 0.20
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process fields delivered by a Mercado Pago callback without querying         the

### Community 233 - "Community 233"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (54): SimpleRateLimiter, Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, MasterAdminSession, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminContext, _now(), _as_aware() (+46 more)

### Community 427 - "Community 427"
Cohesion: 0.29
Nodes (3): Telemetry, LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default.

### Community 187 - "Community 187"
Cohesion: 0.24
Nodes (16): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+8 more)

### Community 100 - "Community 100"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_png(), export_analytics_csv(), export_analytics_xlsx()

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (120): _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _attach_user_session_cookies(), _audit_security_event(), _run_notification_cycle_best_effort(), _issue_auth_response() (+112 more)

### Community 188 - "Community 188"
Cohesion: 0.23
Nodes (16): _booking_status_label_es(), _require_demo_mode(), _ensure_subscription_active(), _ensure_permission_tier(), _is_manager_context(), _booking_to_read(), _project_booking_graph(), list_bookings() (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.21
Nodes (81): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses the ca, Quickly seed demo bookings (requires DEMO_MODE=true)., CheckInRequest (+73 more)

### Community 122 - "Community 122"
Cohesion: 0.13
Nodes (18): _close_report_read(), _cash_expense_read(), _csv_local_datetime(), _csv_local_date(), _csv_decimal(), export_cash_ledger_csv(), latest_cash_close_report(), pending_cash_close_reports() (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.04
Nodes (221): _require_cash_difference_approval_when_requested(), Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, PaymentReceiptEmailRequest, PaymentReceiptEmailRead (+213 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (163): BaseModel, Replace the public pricing table.      The landing page renders exactly what thi, MasterAdminLoginRequest, MasterAdminMfaLoginRequest, MasterAdminMfaEnrollRequest, MasterAdminMfaCodeRequest, MasterAdminMfaDisableRequest, MasterAdminUserPayload (+155 more)

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (27): _ticket_key(), _require_permission(), _require_resource_lane(), _realtime_client_or_503(), create_collaboration_ticket(), _patch_conflict_response(), patch_collaborative_resource(), _consume_ticket() (+19 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (92): _Peer, _RoomTransport, Authenticated field-level collaboration endpoints.  Drafts are ephemeral and saf, Keep collaboration permissions aligned with the normal resource API., Issue a short-lived, one-use ticket for one tenant resource., Persist an optimistic, field-level merge under the current tenant., Process-local peers plus best-effort Redis pub/sub fan-out., Authenticate with a one-use ticket, then exchange safe draft signals. (+84 more)

### Community 357 - "Community 357"
Cohesion: 0.44
Nodes (1): CollaborationManager

### Community 70 - "Community 70"
Cohesion: 0.09
Nodes (21): FastAPI routes for the commercial configuration domain., CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy() (+13 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (45): get_company_options(), Company, CompanyPayload, CompanyOption, CompanyNightlyRate, CompanyNightlyRatesResponse, CompanyNightlyRatePayload, listCompanyNightlyRates() (+37 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (107): CompanyOptionRead, Return only the names needed to link a reservation to a company., AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsAIUsageMonthly, RoomStateEventTypeEnum, RoomStateEventReasonCodeEnum, CompanyBase (+99 more)

### Community 295 - "Community 295"
Cohesion: 0.22
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 42 - "Community 42"
Cohesion: 0.06
Nodes (37): get_interface_language(), email_status(), HotelConfig, HotelConfigUpdate, HotelInterfaceLanguage, getHotelConfig(), getHotelInterfaceLanguage(), updateHotelConfig() (+29 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (139): FastAPI routes for Hotel Configuration (Admin Panel)., Expose only the selected UI language to authenticated hotel members., Lightweight status so the frontend can check the active system email provider., _reject_direct_rate_write(), DailyRateOut, Config, DailyRateFallbackOut, PaymentMethodOptionsOut (+131 more)

### Community 234 - "Community 234"
Cohesion: 0.20
Nodes (9): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection. (+1 more)

### Community 198 - "Community 198"
Cohesion: 0.19
Nodes (14): _require_demo_mode(), seed_demo(), reset_demo(), Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard demo mutations behind both an approved runtime and an explicit flag., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, DemoResetSafetyError (+6 more)

### Community 248 - "Community 248"
Cohesion: 0.19
Nodes (8): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, EmailSendResponse, EmailVerifyResponse, SmtpStatus

### Community 358 - "Community 358"
Cohesion: 0.25
Nodes (8): _until_disconnect(), recover_domain_events(), Adapt sync and async streams to ASGI disconnects and always close them., Recover invalidation domains after a cursor without exposing payloads., DomainEventRecoveryResponse, Safe cursor response used to repair missed realtime invalidations., Recover invalidation domains after a cursor without exposing payloads., Recover invalidation domains after a cursor without exposing payloads.

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (100): _build_authorization_check(), stream_domain_events(), Revalidate stream access while tolerating a brief database pool outage.      The, Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, RoleCatalogItem, RoleListResponse, CreateCustomRoleRequest, RenameCustomRoleRequest (+92 more)

### Community 217 - "Community 217"
Cohesion: 0.18
Nodes (12): FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, FxConversionQuoteRequest, FxConversionQuoteRead, get_all_rates(), get_conversion_quote() (+4 more)

### Community 174 - "Community 174"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 60 - "Community 60"
Cohesion: 0.11
Nodes (39): _restriction_error_detail(), _get_tenant_guest(), list_active_restriction_guest_ids(), create_restriction(), list_restrictions(), resolve_restriction(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of (+31 more)

### Community 559 - "Community 559"
Cohesion: 0.50
Nodes (1): Read and resolve the guest room-rejection lifecycle.

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (84): _guest_service_error_detail(), _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), get_guest_quick_profile(), get_guest_tags(), create_guest_tag(), resolve_tag() (+76 more)

### Community 24 - "Community 24"
Cohesion: 0.06
Nodes (75): add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest., CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir (+67 more)

### Community 46 - "Community 46"
Cohesion: 0.07
Nodes (41): _postgres_healthcheck(), _redis_healthcheck(), _critical_lock_readiness(), live_healthcheck(), ready_healthcheck(), _clickhouse_healthcheck(), datastores_healthcheck(), Process liveness only; never depends on PostgreSQL or Redis. (+33 more)

### Community 113 - "Community 113"
Cohesion: 0.11
Nodes (19): Staff management endpoints for hotel public API keys., get_public_api_context(), require_public_api_purpose(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val, HotelAPIKey, Per-hotel API credential. `key_hash` stores a hashed version of the secret; (+11 more)

### Community 64 - "Community 64"
Cohesion: 0.09
Nodes (36): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _reject_generic_whatsapp_mutation(), _store_oauth_code() (+28 more)

### Community 147 - "Community 147"
Cohesion: 0.21
Nodes (22): _source_key(), _available_invitation(), _activate_invitation_for_user(), _raise_preview_error(), get_invitation_preview(), AcceptPayload, LoginRequest, _pending_invitation_claim() (+14 more)

### Community 101 - "Community 101"
Cohesion: 0.09
Nodes (17): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+9 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (60): VendorCreate, VendorUpdate, VendorRead, VendorPriceUpsert, VendorPriceRead, RemitoLineIn, RemitoCreate, RemitoLineRead (+52 more)

### Community 322 - "Community 322"
Cohesion: 0.38
Nodes (9): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+1 more)

### Community 20 - "Community 20"
Cohesion: 0.04
Nodes (69): _schedule_to_read(), get_daily_report_schedule(), update_daily_report_schedule(), FastAPI routes for the notification backend: inbox, push subscriptions, preferen, NEVER_CACHE_PREFIXES, NotificationSeverity, NotificationItem, NotificationListResponse (+61 more)

### Community 27 - "Community 27"
Cohesion: 0.04
Nodes (38): OnboardingProviderSetup, OnboardingStatus, OnboardingSubscription, OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, CategoryPayload, RoomPayload (+30 more)

### Community 175 - "Community 175"
Cohesion: 0.25
Nodes (15): _can(), _is_operator_scoped(), _can_read_reservation_context(), _report_type_allowed(), _conflict(), get_operational_tasks(), create_operational_task(), patch_operational_task() (+7 more)

### Community 65 - "Community 65"
Cohesion: 0.20
Nodes (35): Operational task inbox and shift handoff endpoints., Match direct task access to the user's effective shared-read/manage grants., OperationalTaskTypeEnum, OperationalTaskStatusEnum, OperationalTaskPriorityEnum, ShiftHandoffStatusEnum, OperationalTask, OperationalTaskEvent (+27 more)

### Community 428 - "Community 428"
Cohesion: 0.57
Nodes (5): _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), _guarded_json_payload()

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (182): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., Base, DeclarativeBase, Base class for all ORM models., Base (+174 more)

### Community 429 - "Community 429"
Cohesion: 0.33
Nodes (2): _mercadopago_webhook_impl(), mercadopago_payment_link_webhook()

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (273): email_payment_receipt(), _reservation_status_label_es(), _to_read(), _is_manager_context(), _ensure_manual_rate_permission(), _ensure_action_permission(), _trigger_reoptimization_bg(), _project_reservation_graph() (+265 more)

### Community 86 - "Community 86"
Cohesion: 0.08
Nodes (24): _validate_role(), _assert_role_profile_mutation_allowed(), _update_role_override(), update_permission_override(), _visibility_window_response(), read_visibility_windows(), update_visibility_window(), restore_role_permission_override() (+16 more)

### Community 430 - "Community 430"
Cohesion: 0.48
Nodes (7): _temporary_grant_actor(), _temporary_grant_response(), _raise_temporary_grant_http_error(), create_temporary_action_grant(), read_pending_temporary_action_grants(), approve_temporary_action_grant(), deny_temporary_action_grant()

### Community 359 - "Community 359"
Cohesion: 0.36
Nodes (9): _validate_code(), _target_membership_or_404(), _assert_manageable_membership(), read_user_overrides(), update_user_override(), update_permission_overrides_batch(), restore_user_permission_override(), restore_user_permission_defaults() (+1 more)

### Community 45 - "Community 45"
Cohesion: 0.13
Nodes (50): consume_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Keep ownership-role cells immutable except the owner's explicit rate control., Keep permission exceptions aligned with the staff-management boundary., Apply a user-reviewed set of permission changes atomically with one MFA ticket., Ask for one exceptional permission without changing the requester's role., Retired: grants are consumed only inside their protected action., TemporaryActionGrantStatusEnum (+42 more)

### Community 135 - "Community 135"
Cohesion: 0.12
Nodes (17): Promotions API (v72 mobile-first pricing/promotions task).  CRUD for versioned,, Promotion, PromotionCreatePayload, PromotionUpdatePayload, PromotionSimulateParams, PromotionAppliedEntry, PromotionSimulateNight, FxQuoteDetails (+9 more)

### Community 106 - "Community 106"
Cohesion: 0.12
Nodes (25): update_promotion(), simulate_promotion_pricing(), Creates a new immutable version; the previous version is deactivated.     Reserv, Return which promotions would apply and the resulting price breakdown     for a, Promotion, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, PromotionError, _quantize() (+17 more)

### Community 323 - "Community 323"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status()

### Community 32 - "Community 32"
Cohesion: 0.06
Nodes (55): Public contact form endpoint for the marketing site., PrivacyRetentionHold, Current legal-retention exception for one public lead or inquiry.      Changes a, _validate_case_reference(), RetentionHoldCreate, RetentionHoldRelease, RetentionTargetSearch, RetentionHoldRead (+47 more)

### Community 17 - "Community 17"
Cohesion: 0.03
Nodes (69): RateCalendarChannelPrice, RateCalendarChannelRestrictions, RateCalendarChannelDay, RateCalendarDay, RateCalendarMeta, RateCalendarResponse, GetRateCalendarDailyParams, getRateCalendarDaily() (+61 more)

### Community 71 - "Community 71"
Cohesion: 0.13
Nodes (34): RateChangeItemIn, RateChangeDraftIn, RateChangeDecisionIn, RateChangeDraftOut, _raise_draft_http(), _safe_rollback(), create_draft(), get_draft() (+26 more)

### Community 431 - "Community 431"
Cohesion: 0.29
Nodes (6): ReferenceCountry, list_timezones(), list_countries(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog., Return the curated country -> primary IANA timezone catalog.

### Community 18 - "Community 18"
Cohesion: 0.03
Nodes (59): booked_value_report(), _safe_csv_cell(), export_revenue_report_csv(), credentials, credentials, owner, manager, OperationalReservationSummary (+51 more)

### Community 176 - "Community 176"
Cohesion: 0.18
Nodes (17): RoleResponse, _role_item(), _rollback_and_raise(), read_roles(), create_role(), rename_role(), delete_role(), HotelRoleCode (+9 more)

### Community 77 - "Community 77"
Cohesion: 0.13
Nodes (24): RoomBlockCreate, RoomBlockRead, RoomBlockConflictPreview, RoomBlockExtensionConflictPreview, RoomBlockExtensionInput, preview_room_block_conflicts_endpoint(), Return counts only; guest identity and reservation IDs are not needed for this w, RoomBlockError (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (182): _require_manager_room_lane(), _serialize_reallocation_result(), _attach_current_rate(), _housekeeping_room(), get_category(), list_rooms(), room_availability(), get_housekeeping_board() (+174 more)

### Community 218 - "Community 218"
Cohesion: 0.21
Nodes (14): _current_user(), _safe_resource_id(), _validate_audit_timeline_range(), _build_audit_timeline_csv(), _attach_actor_names(), security_overview(), recent_security_events(), audit_timeline() (+6 more)

### Community 35 - "Community 35"
Cohesion: 0.04
Nodes (32): _ensure_adjustment_permission(), get_stock_summary(), create_movement(), StockItem, StockLocation, StockMovement, StockTransferResult, CurrentStock (+24 more)

### Community 68 - "Community 68"
Cohesion: 0.10
Nodes (36): StockItemCreate, StockItemUpdate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementCreate, StockMovementRead, StockTransferCreate (+28 more)

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (32): _require_plan(), channel_status(), complete_channel(), inbox(), send_message(), create_note(), update_assignment(), update_status() (+24 more)

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (35): Settings, BaseSettings, get_settings(), _normalized_env_value(), _has_value(), _cors_contains_wildcard(), _is_public_https_url(), _mercadopago_is_active() (+27 more)

### Community 115 - "Community 115"
Cohesion: 0.07
Nodes (27): _install_slow_query_listener(), get_engine(), _render_server_default(), _column_fill_value(), _backfill_not_null_nulls(), _sync_missing_columns(), init_db(), get_session_factory() (+19 more)

### Community 662 - "Community 662"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 560 - "Community 560"
Cohesion: 0.83
Nodes (3): _contact_points(), get_cassandra_session(), cassandra_healthcheck()

### Community 663 - "Community 663"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (31): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change() (+23 more)

### Community 664 - "Community 664"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (38): _parse_header_hotel_id(), _parse_token_hotel_id(), _decode_authorization_header(), _authenticate_user(), _resolve_membership(), get_auth_context(), _action_step_up_tickets(), _matching_action_step_up_ticket() (+30 more)

### Community 236 - "Community 236"
Cohesion: 0.18
Nodes (13): redis_namespace(), namespaced_key(), _client_signature(), get_sync_redis_client(), get_async_redis_client(), reset_clients(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Return a process-local sync client, or None for empty configuration.      The op (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (57): _DecimalAwareEncoder, _InvitationAccessLogFilter, _safe_request_path_for_logging(), _is_database_pool_timeout(), security_headers(), request_telemetry(), SafeStaticFiles, StaticFiles (+49 more)

### Community 388 - "Community 388"
Cohesion: 0.25
Nodes (8): _seed_permission_matrix_once(), lifespan(), Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup.

### Community 272 - "Community 272"
Cohesion: 0.17
Nodes (12): _frontend_placeholder(), serve_frontend(), serve_spa(), Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin (+4 more)

### Community 671 - "Community 671"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 361 - "Community 361"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 199 - "Community 199"
Cohesion: 0.20
Nodes (12): _dev_outbox_path(), _record_dev_email(), SystemEmailStatus, _normalize_account_email(), _sender_parts(), _build_unavailable_message(), _current_status(), get_system_email_status() (+4 more)

### Community 123 - "Community 123"
Cohesion: 0.09
Nodes (6): _serialize_user(), login(), complete_mfa_login(), me(), dashboard_summary(), put_pricing_plans()

### Community 298 - "Community 298"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 116 - "Community 116"
Cohesion: 0.10
Nodes (25): ActionStepUpTicketUse, Tenant-scoped replay ledger for MFA step-up tickets., Persist only the random ticket id and action binding after first use., permissions_requiring_step_up(), permission_requires_step_up(), create_action_step_up_ticket(), is_permission_admin_read_action(), create_permission_admin_read_step_up_ticket() (+17 more)

### Community 66 - "Community 66"
Cohesion: 0.11
Nodes (18): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., GemmaIntent, GemmaChatError (+10 more)

### Community 117 - "Community 117"
Cohesion: 0.20
Nodes (25): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, AllocationExplanation (+17 more)

### Community 52 - "Community 52"
Cohesion: 0.12
Nodes (42): ReservationAllocationLock, GuestRoomAvoidanceStatusEnum, GuestRoomAvoidance, A guest's active or resolved rejection of one physical room.      ``RoomMoveEven, RoomMovementGroup, Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).     Suppo, AllocationError, Exception (+34 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (173): AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, AnalyticsExportStatusEnum, AnalyticsExportJob, HotelAuditEvent, RoomStateEvent, FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum (+165 more)

### Community 178 - "Community 178"
Cohesion: 0.16
Nodes (18): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., QueuedDomainChange, discard_queued_domain_changes(), _session_transaction_id(), get_domain_event_outbox_metrics(), Tenant-scoped realtime domain events backed by Redis/Valkey pub/sub.  Postgres r, A safe invalidation signal waiting for the surrounding DB commit. (+10 more)

### Community 325 - "Community 325"
Cohesion: 0.44
Nodes (9): DocumentTypeEnum, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.06
Nodes (48): APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote, PublicReservationCreate (+40 more)

### Community 653 - "Community 653"
Cohesion: 0.67
Nodes (1): Tenant-scoped custom roles layered over a built-in permission profile.

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (27): IntegrationCatalog, IntegrationEvent, redact_integration_error(), _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status() (+19 more)

### Community 654 - "Community 654"
Cohesion: 0.67
Nodes (1): Persisted staff invitations and their one-time acceptance state.

### Community 93 - "Community 93"
Cohesion: 0.17
Nodes (28): LinenItem, LinenLocation, LinenMovement, LinenParLevel, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Configured minimum quantity for one linen item at one hotel location., list_missing_follow_ups(), update_missing_follow_up() (+20 more)

### Community 49 - "Community 49"
Cohesion: 0.11
Nodes (43): NotificationOutboxStatusEnum, Notification, PushSubscription, NotificationPreference, NotificationOutbox, DailyReportSchedule, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre, A single in-app inbox item for one recipient. (+35 more)

### Community 179 - "Community 179"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 137 - "Community 137"
Cohesion: 0.19
Nodes (21): PaymentProofStatusEnum, PaymentProof, PaymentProofBlob, Manual bank-transfer evidence and approval lifecycle., Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., PaymentProofError, _delete_uncommitted_object() (+13 more)

### Community 249 - "Community 249"
Cohesion: 0.15
Nodes (12): PaymentReceiptEmailDelivery, One attempted receipt email, without retaining the guest's email address.      `, MergeResult, merge_field_changes(), Merge non-overlapping changes and report same-field conflicts.      A field is s, GuestProfile, GuestProfileError, get_guest_profile() (+4 more)

### Community 164 - "Community 164"
Cohesion: 0.20
Nodes (12): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, mask_to_weekdays(), PromotionConditions, PromotionCreate, PromotionUpdate, PromotionRead (+4 more)

### Community 138 - "Community 138"
Cohesion: 0.18
Nodes (19): ReservationEmailKindEnum, ReservationEmailStatusEnum, ReservationEmailDelivery, Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, HotelOutboundIdentity, HotelOutboundSendResult, ensure_hotel_gmail_ready() (+11 more)

### Community 53 - "Community 53"
Cohesion: 0.12
Nodes (45): Subscription, SubscriptionEvent, SubscriptionAdjustment, Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, _now(), _as_utc(), _plan_defaults() (+37 more)

### Community 139 - "Community 139"
Cohesion: 0.17
Nodes (22): UserMfaSecret, UserMfaRecoveryCode, TOTP MFA secrets and one-time recovery codes for normal user accounts., MfaSecretUnavailableError, get_user_mfa_secret(), get_active_mfa_secret(), encrypt_totp_secret(), decrypt_totp_secret() (+14 more)

### Community 392 - "Community 392"
Cohesion: 0.25
Nodes (5): AnalyticsInsightRequest, AnalyticsInsightStatusRead, AnalyticsInsightRead, AnalyticsAIChatRequest, AnalyticsAIChatRead

### Community 518 - "Community 518"
Cohesion: 0.40
Nodes (4): CollaborationTicketRequest, CollaborationTicketResponse, CollaborationPatchRequest, Transport schemas for authenticated field-level collaboration.

### Community 124 - "Community 124"
Cohesion: 0.11
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 251 - "Community 251"
Cohesion: 0.15
Nodes (9): CompanyNightlySurchargeRateCreate, CompanyNightlySurchargeRateRead, CompanyNightlySurchargeRatesRead, CompanyNightChargeAmountAdjustmentRequest, CompanyNightChargeAmountAdjustmentSetRequest, CompanyNightChargeAmountAdjustmentRead, CompanyNightChargeSetRequest, CompanyNightChargeRead (+1 more)

### Community 519 - "Community 519"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 362 - "Community 362"
Cohesion: 0.22
Nodes (6): GuestRestrictionOverrideRequest, GuestRestrictionCreate, GuestRestrictionResolveRequest, GuestRestrictionRead, Pydantic schemas for GuestRestriction (formal lodging-prohibition entity)., Carried on reservation/checkin/quote requests to authorize bypassing     an acti

### Community 520 - "Community 520"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceResolveRequest, GuestRoomAvoidanceRead, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 326 - "Community 326"
Cohesion: 0.20
Nodes (2): _normalize_currency(), HotelConfigUpdate

### Community 275 - "Community 275"
Cohesion: 0.17
Nodes (9): PublicPricingPlan, PublicPricingResponse, LeadCreateRequest, LeadCreateResponse, MasterPricingPlanPayload, MasterPricingPlanListPayload, MasterLeadPayload, MasterLeadListPayload (+1 more)

### Community 276 - "Community 276"
Cohesion: 0.17
Nodes (10): NotificationRead, NotificationListResponse, NotificationMarkReadRequest, PushSubscriptionRegisterRequest, PushSubscriptionUnregisterRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, DailyReportScheduleRead (+2 more)

### Community 150 - "Community 150"
Cohesion: 0.09
Nodes (15): OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, ProviderSetupPayload, PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, CategoriesPayload (+7 more)

### Community 237 - "Community 237"
Cohesion: 0.14
Nodes (11): VisibilityWindowUpdate, VisibilityWindowRead, RolePermissionOverrideRequest, UserPermissionOverrideRequest, PermissionOverrideBatchChange, PermissionOverrideBatchRequest, PermissionDecision, PermissionCatalogItem (+3 more)

### Community 252 - "Community 252"
Cohesion: 0.19
Nodes (6): _clean_required(), _clean_optional(), PublicInquiryCreate, PublicInquiryAccepted, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 125 - "Community 125"
Cohesion: 0.09
Nodes (25): OperationalReservationSummary, OperationalReservationGroup, ArrivalCountRead, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead, OperationalAlertRead, DailyOperationalReportRead (+17 more)

### Community 472 - "Community 472"
Cohesion: 0.33
Nodes (5): ReservationEmailKind, ReservationEmailStatus, ReservationEmailSendRequest, ReservationEmailDeliveryRead, ReservationEmailSendResponse

### Community 327 - "Community 327"
Cohesion: 0.20
Nodes (5): ReservationGroupPaymentAllocationRequest, ReservationGroupPaymentCreate, ReservationGroupPaymentAllocationRead, ReservationGroupPaymentRead, Request and read contracts for one group collection with child allocations.

### Community 253 - "Community 253"
Cohesion: 0.15
Nodes (12): WhatsAppContactRead, WhatsAppMessageRead, WhatsAppConversationRead, WhatsAppConversationListResponse, WhatsAppMessageCreate, WhatsAppAssignmentUpdate, WhatsAppNoteCreate, WhatsAppConversationStatusUpdate (+4 more)

### Community 437 - "Community 437"
Cohesion: 0.33
Nodes (4): ChatMessage, ChatCompletionRequest, chat_completions(), _extract_latest_user_message()

### Community 363 - "Community 363"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, repair_cash_handoff_schema(), missing_model_tables(), main(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it.

### Community 300 - "Community 300"
Cohesion: 0.35
Nodes (9): _check_overlap(), _one_night_gap_penalty_for_room(), _adjacency_bonus_for_room(), _guest_room_signal_score(), run_allocation(), _run_allocation_greedy(), _lowest_compatible_floor(), _lowest_available_compatible_floor() (+1 more)

### Community 522 - "Community 522"
Cohesion: 0.60
Nodes (4): AllocationQuestionnaireDraft, AllocationFeedbackDraft, draft_policy_from_questionnaire(), draft_policy_from_feedback()

### Community 201 - "Community 201"
Cohesion: 0.28
Nodes (12): AllocationPolicyError, ensure_default_policy_profile(), ensure_default_policy_version(), get_active_policy_settings(), list_policy_versions(), create_policy_version(), publish_policy_version(), get_policy_suggestion() (+4 more)

### Community 41 - "Community 41"
Cohesion: 0.09
Nodes (53): ValueError, LookupError, canonical_permission_code(), _permission_help_es(), _legacy_permission_deny(), _role_permissions(), immutable_permission_decision(), can_role_hold_permission() (+45 more)

### Community 87 - "Community 87"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, GemmaProvider (+12 more)

### Community 118 - "Community 118"
Cohesion: 0.15
Nodes (23): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _flatten_payload_rows(), _rows_to_csv_bytes(), _png_from_rows(), _sheet_xml_from_table() (+15 more)

### Community 130 - "Community 130"
Cohesion: 0.16
Nodes (22): detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), touch_reservation_fact_window(), calculate_pickup_30d(), _reservation_row_kind(), _resolve_no_show_policy(), _reservation_monetary_totals() (+14 more)

### Community 523 - "Community 523"
Cohesion: 0.50
Nodes (4): _as_utc_datetime(), annotate_analytics_payload(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 254 - "Community 254"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 393 - "Community 393"
Cohesion: 0.50
Nodes (7): _decimal(), _value(), _utc(), _utc_bounds(), _db_utc_bounds(), _actor_name(), get_daily_summary()

### Community 238 - "Community 238"
Cohesion: 0.35
Nodes (13): CashExpenseError, _money(), _delete_object_key(), _decode_receipt(), _safe_filename(), _require_open_session(), create_cash_expense(), list_cash_expenses() (+5 more)

### Community 239 - "Community 239"
Cohesion: 0.27
Nodes (11): normalize_resource_type(), get_resource_spec(), _json_safe(), resource_revision(), _model_dump_for_wire(), _model_dump_for_database(), validate_draft_changes(), editable_resource_values() (+3 more)

### Community 255 - "Community 255"
Cohesion: 0.36
Nodes (10): CompanyDocumentError, _decode_company_pdf(), _safe_company_filename(), _get_reservation(), _get_company(), _get_reservation_company(), create_document(), upload_company_document() (+2 more)

### Community 256 - "Community 256"
Cohesion: 0.33
Nodes (11): _reservation(), _company(), _rate_for_date(), list_company_nightly_surcharge_rates(), create_company_nightly_surcharge_rate(), _paid_and_pending_by_charge(), get_company_night_charges(), add_company_night_charges() (+3 more)

### Community 301 - "Community 301"
Cohesion: 0.29
Nodes (10): _settings(), _get_redis_client(), _required(), _try_postgres_advisory_lock(), distributed_lock(), with_distributed_lock(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru (+2 more)

### Community 189 - "Community 189"
Cohesion: 0.16
Nodes (15): DomainEvent, _settings(), _get_redis_client(), _get_realtime_fast_fail_client(), _required(), _unavailable(), publish_domain_event(), get_realtime_client() (+7 more)

### Community 473 - "Community 473"
Cohesion: 0.33
Nodes (5): channel_for_hotel(), iter_event_stream(), Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped stream and close when membership is revoked.

### Community 257 - "Community 257"
Cohesion: 0.15
Nodes (12): _OutboxPublishAttempt, publish_queued_domain_changes(), _record_outbox_attempt(), Redis outcome to persist after every publish in the batch has finished., Open or extend the cooldown after an actual durable publish fails., Publish committed signals without allowing Redis to break the request.      This, Record one publish attempt on a durable outbox row, if it still exists., Record one publish attempt on a durable outbox row, if it still exists. (+4 more)

### Community 258 - "Community 258"
Cohesion: 0.15
Nodes (10): _OutboxPublishPermit, _OutboxPublishCooldown, A durable Redis attempt, optionally owning the single recovery probe., Process-local gate for durable after-commit Redis publishes only., Return a permit, or skip while cooling down / another probe runs., A successful recovery probe closes only the cooldown it owns., A durable Redis attempt, optionally owning the single recovery probe., Process-local gate for durable after-commit Redis publishes only. (+2 more)

### Community 328 - "Community 328"
Cohesion: 0.24
Nodes (10): _scalar_event_value(), _model_hotel_id(), _model_event_payload(), queue_model_changes(), queue_domain_change(), validate_event_input(), Collect safe domain signals from ORM writes before a transaction ends., Queue one tenant-scoped change for publication after commit.      Services can c (+2 more)

### Community 180 - "Community 180"
Cohesion: 0.12
Nodes (18): revision_key_for_hotel(), _validate_hotel_id(), get_domain_event_recovery(), _outbox_sse_payload(), iter_postgres_event_stream(), aiter_postgres_event_stream(), format_sse(), Return changed domains after a tenant-scoped outbox cursor.      V2 rows use ``s (+10 more)

### Community 394 - "Community 394"
Cohesion: 0.25
Nodes (8): _outbox_backoff_seconds(), publish_pending_domain_events(), Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th

### Community 666 - "Community 666"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 197 - "Community 197"
Cohesion: 0.19
Nodes (8): _mask_email(), _mask_recipients(), _normalize_display_from(), EmailProvider, ABC, ResendEmailProvider, NullEmailProvider, get_email_provider()

### Community 259 - "Community 259"
Cohesion: 0.22
Nodes (8): Mailer, send_platform_email(), send_verification_email(), send_reset_password_email(), send_verification_success_email(), send_generic_auth_notice_email(), Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists.

### Community 190 - "Community 190"
Cohesion: 0.18
Nodes (15): DolarApiRatesDisabled, external_effects_enabled(), inbound_provider_events_enabled(), google_login_enabled(), apple_login_enabled(), dolarapi_rates_enabled(), require_external_effects(), require_external_connections() (+7 more)

### Community 277 - "Community 277"
Cohesion: 0.41
Nodes (10): _money(), _hotel_bounds(), _local_day(), _aggregate_rows(), _booked_nights_in_window(), _booked_amount_in_window(), _validate_report_window(), _build_booked_value_projection() (+2 more)

### Community 107 - "Community 107"
Cohesion: 0.20
Nodes (27): _cache_key(), _cache_key_for_display_rate(), _cached_rate(), _store_rate(), parse_provider_updated_at(), quote_is_fresh(), _quote_matches_supported_market(), _quote_matches_conversion_market() (+19 more)

### Community 474 - "Community 474"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 260 - "Community 260"
Cohesion: 0.45
Nodes (11): GemmaActionRunError, get_action_run(), approve_action_run(), reject_action_run(), review_action_run_draft(), apply_action_run_draft(), _load_json_dict(), _coerce_numeric_dict() (+3 more)

### Community 561 - "Community 561"
Cohesion: 0.83
Nodes (3): classify_gemma_intent(), _normalize(), _extract_keywords()

### Community 69 - "Community 69"
Cohesion: 0.12
Nodes (6): GemmaPolicyDraft, GemmaServiceError, GemmaService, Gemma-aware policy suggestion service.  This module keeps the PMS safe by treati, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 475 - "Community 475"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 220 - "Community 220"
Cohesion: 0.29
Nodes (14): _now(), _audit(), _get_guest(), _active_tag_filter(), find_or_create_guest(), _escape_like_term(), _guest_search_rank(), search_guests() (+6 more)

### Community 395 - "Community 395"
Cohesion: 0.39
Nodes (7): apply_configuration_update(), set_identity(), set_deposit_policy(), set_payment_methods(), set_ota_channels(), Shared writes for hotel configuration concepts., Apply a validated Settings payload to one hotel configuration row.

### Community 476 - "Community 476"
Cohesion: 0.47
Nodes (4): ensure_plans_seeded(), get_or_create_hotel_for_owner(), _ensure_membership_and_subscription(), ensure_all_ota_webhook_secrets()

### Community 329 - "Community 329"
Cohesion: 0.20
Nodes (10): utcnow(), hash_invitation_token(), issue_invitation(), find_by_token(), is_expired(), consume_invitation(), Return a naive UTC timestamp, matching the current SQLAlchemy models., Hash a high-entropy bearer token before it is persisted. (+2 more)

### Community 524 - "Community 524"
Cohesion: 0.50
Nodes (4): JurisdictionProfile, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 54 - "Community 54"
Cohesion: 0.05
Nodes (43): is_duplicate_remito_integrity_error(), create_vendor(), get_vendor(), set_vendor_price(), create_remito(), remito_creator_labels(), vendor_balance(), vendor_spend() (+35 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (71): sweep_no_shows(), run_no_show_sweep(), CLI entry point for the database-only no-show Render Cron job., _reservation(), test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(), test_sweep_sql_cutoff_filter_matches_elapsed_utc_hours_across_dst(), test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(), test_sweep_excludes_checked_in_and_is_idempotent() (+63 more)

### Community 95 - "Community 95"
Cohesion: 0.13
Nodes (24): _utcnow(), _validate_payload(), _insert_ignore(), _redact(), _role_recipient_ids(), _actor_role(), get_effective_notification_preference(), _in_quiet_hours() (+16 more)

### Community 181 - "Community 181"
Cohesion: 0.25
Nodes (10): ObjectStorageError, ObjectStat, _safe_relative_path(), GCSObjectStorage, get_object_storage(), Minimal object-storage abstraction: put/get/delete bytes by key.  Why this exist, Raised when a storage backend cannot complete an operation., Reject any key that could escape the storage root (no `..`, no leading `/`). (+2 more)

### Community 221 - "Community 221"
Cohesion: 0.13
Nodes (4): ObjectStorage, S3ObjectStorage, Content-addressed-ish blob store: put/get/delete bytes by string key., Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar

### Community 364 - "Community 364"
Cohesion: 0.33
Nodes (2): LocalObjectStorage, Stores objects as files under a local directory root.      Generalizes the patte

### Community 131 - "Community 131"
Cohesion: 0.25
Nodes (24): resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload(), _current_subscription_context(), _payment_method_options() (+16 more)

### Community 261 - "Community 261"
Cohesion: 0.31
Nodes (12): _utc(), _value(), _money(), _bounds(), _date_filter(), _actor_name(), _area_for(), _safe_detail_value() (+4 more)

### Community 151 - "Community 151"
Cohesion: 0.16
Nodes (19): _guest_name(), _reservation_summary(), _group(), company_night_extra_balances_by_reservation(), filter_pms_revenue_transactions(), _active_room_blocks(), _available_with_review(), _cash_session() (+11 more)

### Community 148 - "Community 148"
Cohesion: 0.17
Nodes (18): _decode_task_photo(), _safe_task_photo_name(), _now(), _enum_value(), _get_task(), _validate_user_membership(), _validate_links(), _append_event() (+10 more)

### Community 149 - "Community 149"
Cohesion: 0.18
Nodes (10): Foundational OTA adapter interfaces and orchestration services., BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, A provider operation failed before it could return normalized data., Acknowledge processed reservation messages in Booking's queue., OTAAdapterContext, OTAOperationResult, NormalizedOTAReservation (+2 more)

### Community 84 - "Community 84"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 159 - "Community 159"
Cohesion: 0.12
Nodes (5): OTAProviderAdapter, FakeBookingAdapter, FailingBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event(), test_ota_orchestrator_records_failed_verification()

### Community 215 - "Community 215"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 216 - "Community 216"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 200 - "Community 200"
Cohesion: 0.13
Nodes (4): OTAProviderAdapter, build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 262 - "Community 262"
Cohesion: 0.37
Nodes (12): create_or_update_manual_ota_reservation(), release_no_guarantee(), _attempt_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean(), _apply_manual_amounts() (+4 more)

### Community 140 - "Community 140"
Cohesion: 0.15
Nodes (23): _create_mercadopago_preference(), _default_email_delivery(), _money(), _is_safe_provider_url(), _signing_secret(), _signature(), sign_external_reference(), resolve_signed_external_reference() (+15 more)

### Community 141 - "Community 141"
Cohesion: 0.16
Nodes (20): PaymentLinkTestError, _validate_email(), _mercadopago_access_token(), _mercadopago_connection_payload(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email(), _notification_url() (+12 more)

### Community 365 - "Community 365"
Cohesion: 0.44
Nodes (8): _normalize_email(), _key_hash(), _recipient_fingerprint(), _load_receipt_and_registered_email(), _format_money(), _receipt_email_content(), _existing_delivery(), send_payment_receipt_email()

### Community 302 - "Community 302"
Cohesion: 0.38
Nodes (10): validate_mercadopago_webhook_signature(), _payload_value(), _normalize_status(), _completed_at(), _is_allowed_status_transition(), _find_existing_event(), _insert_event(), _transaction_exists() (+2 more)

### Community 263 - "Community 263"
Cohesion: 0.29
Nodes (12): quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount(), _convert_amount(), _resolve_conversion_quote() (+4 more)

### Community 396 - "Community 396"
Cohesion: 0.36
Nodes (7): _period_price(), get_price_for_date(), resolve_rate_calendar(), resolve_current_rates_for_categories(), get_prices_for_range(), apply_price_period(), build_pricing_revision()

### Community 366 - "Community 366"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 108 - "Community 108"
Cohesion: 0.18
Nodes (27): _settings(), _cache_enabled(), _redis_failure_cooldown_seconds(), _redis_timeout_seconds(), _mark_redis_unavailable(), _mark_redis_available(), _get_redis_client(), _load_json() (+19 more)

### Community 81 - "Community 81"
Cohesion: 0.10
Nodes (32): get_reservation_operations_summary(), _get_operations_related_data(), list_pending_reservation_actions(), _load_pending_action_reservations(), _latest_ota_links_by_reservation(), _related_adjustments_by_reservation(), _pending_action_financial_inputs(), _candidate_reservation_ids() (+24 more)

### Community 89 - "Community 89"
Cohesion: 0.13
Nodes (30): _validate_direct_individual_extension_target(), required_room_move_permission(), _room_move_permission_candidates(), _room_move_categories(), enforce_room_move_permission(), _invalidate_availability_cache(), _touch_facts(), _hotel_default_currency() (+22 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (91): ReservationError, requires_large_total_adjustment_confirmation(), _direct_manual_rate_reference_quote(), active_reservations(), _hotel_today_and_timezone(), visible_reservations(), active_reservations_select(), _active_reservations_without_hotel() (+83 more)

### Community 525 - "Community 525"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 562 - "Community 562"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 278 - "Community 278"
Cohesion: 0.23
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 477 - "Community 477"
Cohesion: 0.33
Nodes (3): register_uploaded_object(), Upload/verify/register object-storage bytes without exposing them in events., Persist pending metadata, upload, stat and mark ready after verification.

### Community 160 - "Community 160"
Cohesion: 0.23
Nodes (19): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), _upsert_plan_entitlement(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements() (+11 more)

### Community 165 - "Community 165"
Cohesion: 0.16
Nodes (18): _apply_setting(), _remember_setting(), _set_context_value(), reapply_tenant_context_on_connection(), set_tenant_user_context(), set_tenant_hotel_context(), set_invitation_token_hash_context(), set_tenant_context() (+10 more)

### Community 303 - "Community 303"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 330 - "Community 330"
Cohesion: 0.20
Nodes (10): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), local_today(), hotel_today(), Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name. (+2 more)

### Community 526 - "Community 526"
Cohesion: 0.40
Nodes (3): find_user_by_email(), Exact, case-insensitive lookup helpers for user identity fields., Find an exact email match without treating SQL wildcard characters specially.

### Community 119 - "Community 119"
Cohesion: 0.12
Nodes (25): _now(), _as_aware(), _hash_value(), _issue_token(), _issue_rotation_successor(), _session_cookie_secure(), _session_cookie_samesite(), _device_label_from_request() (+17 more)

### Community 331 - "Community 331"
Cohesion: 0.44
Nodes (8): WaitlistError, _get_waitlist_entry(), add_to_waitlist(), update_waitlist_entry(), promote_from_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), request_payment_link_for_waitlist()

### Community 240 - "Community 240"
Cohesion: 0.22
Nodes (10): _date_window(), _decimal_total(), _project_operational_window(), _parse_datetime(), detect_no_shows(), project_reservation_facts_to_clickhouse(), project_operational_facts_to_clickhouse(), _project_all_hotels_window() (+2 more)

### Community 296 - "Community 296"
Cohesion: 0.22
Nodes (8): _session(), process_outbox(), generate_daily_reports(), Celery tasks for the notification backend: process the outbox (bounded retry/exp, Deliver each hotel's pending outbox rows under that hotel's RLS     context. not, Same per-hotel RLS-context requirement as process_outbox above --     daily_repo, Regression guard: verify the notification backend migration against a REAL `alem, e9c258b feat(notifications): outbox-backed notification/push/email backend (Task 8)

### Community 479 - "Community 479"
Cohesion: 0.60
Nodes (5): _active_hotel_ids(), _send_report_for_hotel(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports()

### Community 235 - "Community 235"
Cohesion: 0.23
Nodes (9): validatedSha(), resolveCodeSha(), buildMetaPlugin(), MARKETING_ROUTES, replaceTag(), renderRouteHtml(), marketingHtmlPlugin(), indexHtml (+1 more)

### Community 112 - "Community 112"
Cohesion: 0.08
Nodes (19): CashMovement, CashCloseReport, CashDailyEntry, CashMovementPayload, downloadCashLedgerCsv(), downloadCashExpensesCsv(), downloadCashExpenseReceipt(), cashSessionsKey() (+11 more)

### Community 177 - "Community 177"
Cohesion: 0.16
Nodes (14): RouteScenario, Persona, ApiRequestMetric, ApiResponseMetric, UiActionMetric, personas, durationSeconds, normalizePath() (+6 more)

### Community 471 - "Community 471"
Cohesion: 0.33
Nodes (3): credentials, backendURL, StoredSession

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (21): escapeRegExp(), localizedName(), localizedText(), owner, localIsoDate(), parseMoney(), ensureCashSessionOpen(), createReservation() (+13 more)

### Community 360 - "Community 360"
Cohesion: 0.22
Nodes (6): permissions, reservation, transaction, financialSummary, ReceiptEmailResult, InterceptedApiRequest

### Community 652 - "Community 652"
Cohesion: 0.67
Nodes (1): owner

### Community 297 - "Community 297"
Cohesion: 0.18
Nodes (5): manager, owner, ids, fixtures, transactionsByReservation

### Community 516 - "Community 516"
Cohesion: 0.40
Nodes (4): migratedFiles, localeFiles, spanishLiteralPatterns, backendCheckinValidationMessages

### Community 391 - "Community 391"
Cohesion: 0.29
Nodes (5): frontendRoot, sourceRoot, pluralSuffixes, flattenKeys(), loadKeys()

### Community 51 - "Community 51"
Cohesion: 0.08
Nodes (36): OperationalTaskType, OperationalTaskStatus, OperationalTaskPriority, OperationalTask, OperationalTaskEvent, ShiftHandoff, OperationalTaskAttachment, OperationalTaskCreate (+28 more)

### Community 273 - "Community 273"
Cohesion: 0.17
Nodes (10): publicSiteBaseURL, frontendDir, repoRoot, pythonCandidates, pythonExecutablePath, pythonExecutable, e2eDbPath, postgresE2eURL (+2 more)

### Community 247 - "Community 247"
Cohesion: 0.17
Nodes (9): mfaStatusQueryKey(), getMfaStatus(), ActionStepUpChallenge, ActionStepUpTicket, setActionStepUpHandler(), PendingStepUp, ActionStepUpResponse, ActionStepUpProvider() (+1 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (38): CashSessionStatus, CashMovementType, CashSession, CashCustodyHandoff, CashSessionSummary, CashDailyPaymentMethod, CashDailyCollector, CashDailyPriorReceipt (+30 more)

### Community 34 - "Community 34"
Cohesion: 0.05
Nodes (40): ApiError, RequestOptions, readCookie(), setMasterAdminCsrfToken(), clearMasterAdminCsrfToken(), safeJson(), masterAdminFetch(), MasterAdminUser (+32 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (34): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+26 more)

### Community 39 - "Community 39"
Cohesion: 0.05
Nodes (45): RemitoDirection, LaundryVendor, LaundryVendorCreate, LaundryVendorUpdate, LaundryVendorPrice, LaundryVendorPriceUpsert, LaundryRemitoLine, LaundryRemito (+37 more)

### Community 114 - "Community 114"
Cohesion: 0.07
Nodes (24): LinenItem, LinenLocation, LinenItemCreate, LinenLocationCreate, LinenMovementCreate, LinenMovement, CurrentLinenStock, LinenSummaryEntry (+16 more)

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (53): PublicPricingPlan, PublicPricing, LeadPayload, fetchPublicPricing(), submitLead(), EarlyAccessFormProps, Status, MESSAGES (+45 more)

### Community 67 - "Community 67"
Cohesion: 0.05
Nodes (31): BuiltinPermissionRole, PermissionRole, PermissionCatalogItem, PermissionProfileMatrix, PermissionMatrixResponse, UserPermissionOverrideResponse, PermissionOverrideBatchChange, PermissionOverrideBatchResponse (+23 more)

### Community 158 - "Community 158"
Cohesion: 0.11
Nodes (13): PromotionBenefitType, PromotionScope, PromotionConditions, PromotionSimulateResult, usePromotionMutations(), WEEKDAY_OPTIONS, PAYMENT_METHOD_OPTIONS, GUEST_TAG_OPTIONS (+5 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (36): PublicInquiryPayload, PublicInquiryResponse, submitPublicInquiry(), StructuredData, SeoProps, socialImage, Seo(), BreadcrumbItem (+28 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (51): RESERVATION_QUERY_PREFIXES, PAYMENT_QUERY_PREFIXES, CASH_QUERY_PREFIXES, RESERVATION_ENTITY_QUERY_PREFIXES, GUEST_QUERY_PREFIXES, ROOM_QUERY_PREFIXES, ReservationRecordRefreshOptions, refreshAfterMutation() (+43 more)

### Community 389 - "Community 389"
Cohesion: 0.25
Nodes (5): CLIENT_ID, REDIRECT_URI, AppleAuthorization, AppleSignInResult, Window

### Community 31 - "Community 31"
Cohesion: 0.03
Nodes (64): PermissionGate(), navItems, MasterAdminRoot(), MasterAdminProtectedShell(), MasterAdminSessionProvider(), LoginPage, RegisterOwnerPage, ForgotPasswordPage (+56 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (34): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+26 more)

### Community 390 - "Community 390"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 668 - "Community 668"
Cohesion: 1.00
Nodes (2): latestCloseReportKey(), useLatestCashCloseReport()

### Community 670 - "Community 670"
Cohesion: 1.00
Nodes (2): pendingCloseReportsKey(), usePendingCashCloseReports()

### Community 669 - "Community 669"
Cohesion: 1.00
Nodes (2): pendingCashCustodyReportsKey(), usePendingCashCustodyReports()

### Community 667 - "Community 667"
Cohesion: 1.00
Nodes (2): dailySummaryKey(), useCashDailySummary()

### Community 439 - "Community 439"
Cohesion: 0.33
Nodes (5): InterfaceLanguage, normalizeInterfaceLanguage(), interfaceLanguageToLocale(), queryClient, SessionProvider()

### Community 274 - "Community 274"
Cohesion: 0.18
Nodes (5): Lead, SOURCE_LABELS, DATE, HEADERS, toCsvCell()

### Community 468 - "Community 468"
Cohesion: 0.80
Nodes (5): SharedSandboxBootstrapError, load_env(), _literal(), build_sql(), main()

### Community 469 - "Community 469"
Cohesion: 0.47
Nodes (5): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 270 - "Community 270"
Cohesion: 0.36
Nodes (11): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+3 more)

### Community 321 - "Community 321"
Cohesion: 0.49
Nodes (9): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+1 more)

### Community 354 - "Community 354"
Cohesion: 0.42
Nodes (8): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots.

### Community 650 - "Community 650"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 271 - "Community 271"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 88 - "Community 88"
Cohesion: 0.16
Nodes (29): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+21 more)

### Community 555 - "Community 555"
Cohesion: 0.67
Nodes (3): normalize_instruction_paths(), main(), Replace this repository's absolute root in generated instructions only.

### Community 515 - "Community 515"
Cohesion: 0.80
Nodes (4): _write_json(), _archive_historical(), _build_cases(), main()

### Community 355 - "Community 355"
Cohesion: 0.44
Nodes (8): OperationalQAError, _utc_now(), _json_bytes(), _write(), _catalog(), initialize(), validate(), main()

### Community 146 - "Community 146"
Cohesion: 0.26
Nodes (20): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+12 more)

### Community 129 - "Community 129"
Cohesion: 0.22
Nodes (23): AttestationError, _sha256(), _canonical_json(), _b64url_encode(), _b64url_decode(), _read_regular_nofollow(), _read_limited(), _json_object() (+15 more)

### Community 387 - "Community 387"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 556 - "Community 556"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 111 - "Community 111"
Cohesion: 0.22
Nodes (16): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+8 more)

### Community 651 - "Community 651"
Cohesion: 1.00
Nodes (2): validate(), main()

### Community 294 - "Community 294"
Cohesion: 0.40
Nodes (10): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+2 more)

### Community 557 - "Community 557"
Cohesion: 0.83
Nodes (3): run(), validate_json(), main()

### Community 186 - "Community 186"
Cohesion: 0.23
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 85 - "Community 85"
Cohesion: 0.21
Nodes (32): VerificationError, _dict(), _list(), _string(), _validate_config(), _decode_lease_entropy(), _validate_baseline_lease_id(), _verify_dedicated_baseline_lease() (+24 more)

### Community 356 - "Community 356"
Cohesion: 0.22
Nodes (6): ReadOnlyJsonApi, VerificationConfig, ProviderClients, _required_env(), main(), Small GET-only API client with bounded retries and redacted failures.

### Community 558 - "Community 558"
Cohesion: 0.83
Nodes (3): _non_empty(), validate_manifest(), main()

### Community 219 - "Community 219"
Cohesion: 0.33
Nodes (14): DrillError, _validate_tables(), _sqlite_path(), _sqlite_counts(), _verify_local_objects(), _run_sqlite(), _postgres_parts(), _pg_command() (+6 more)

### Community 50 - "Community 50"
Cohesion: 0.09
Nodes (47): QABootstrapError, Persona, QABootstrapConfig, QABootstrapResult, ProviderEvidence, _required(), _flag(), _required_port() (+39 more)

### Community 435 - "Community 435"
Cohesion: 0.57
Nodes (6): command(), heading(), fenced(), frontend_routes(), write(), main()

### Community 299 - "Community 299"
Cohesion: 0.33
Nodes (8): PhaseMetrics, LoadConfig, percentile(), safe_headers(), run_phase(), _parse_paths(), _run(), main()

### Community 436 - "Community 436"
Cohesion: 0.52
Nodes (5): RealtimeMetrics, validate_target(), run_load(), _run(), main()

### Community 94 - "Community 94"
Cohesion: 0.13
Nodes (26): E2ESafetyError, _enabled(), _postgres_e2e_connection(), _postgres_e2e_seed_connection(), _is_postgres_e2e_target(), _assert_postgres_e2e_database_empty(), prepare_e2e_environment(), reset_e2e_database() (+18 more)

### Community 521 - "Community 521"
Cohesion: 0.50
Nodes (3): _prepare_environment(), seed(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2

### Community 55 - "Community 55"
Cohesion: 0.04
Nodes (45): _reject_unqualified_postgres_locks_over_outer_joins(), _reset_durable_realtime_publish_cooldown(), _validated_pg_dsn_or_skip(), pg_engine(), _stub_transactional_auth_email(), _isolate_object_storage(), _reset_permission_seed_cache(), db_engine() (+37 more)

### Community 324 - "Community 324"
Cohesion: 0.31
Nodes (9): reset_projection_clients(), _close_clients(), _enable(), test_mongo_audit_projection_lands_document(), test_neo4j_reservation_assignment_lands_nodes(), _cassandra_probe(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each (+1 more)

### Community 517 - "Community 517"
Cohesion: 0.60
Nodes (4): _migration_dsn(), _run_alembic(), test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips(), Disposable live PostgreSQL proof for the forward Alembic release path.  The rele

### Community 397 - "Community 397"
Cohesion: 0.29
Nodes (6): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), Migration coverage for the deduplication sweep.

### Community 250 - "Community 250"
Cohesion: 0.28
Nodes (12): BenchmarkResult, derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure(), explain() (+4 more)

### Community 304 - "Community 304"
Cohesion: 0.35
Nodes (10): PostgresTargetSafetyError, _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot (+2 more)

### Community 438 - "Community 438"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 478 - "Community 478"
Cohesion: 0.53
Nodes (5): _receptionist_context(), _open_cash_session(), _create_receptionist_user(), test_receptionist_can_view_and_make_reservation_payments(), POST /api/payments and GET /api/payments/summary/{id} only allowed     owner/co_

### Community 182 - "Community 182"
Cohesion: 0.25
Nodes (16): _auth_context(), step_up_client(), _code_at(), _invalid_code(), _issue_ticket(), test_sensitive_permission_requires_a_matching_ticket_before_handler(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket() (+8 more)

### Community 166 - "Community 166"
Cohesion: 0.15
Nodes (9): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), _tracked_files(), test_raw_graphify_graph_is_not_tracked(), test_tracked_graphify_artifacts_stay_small() (+1 more)

### Community 132 - "Community 132"
Cohesion: 0.17
Nodes (6): make_rooms(), make_res(), TestOverlap, TestGreedyAllocation, TestCPSATAllocation, Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).

### Community 332 - "Community 332"
Cohesion: 0.56
Nodes (8): _seed_hotel(), _guest(), _reservation(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_previous_completed_room_signal_requires_the_new_reservation_category(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query()

### Community 333 - "Community 333"
Cohesion: 0.60
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+1 more)

### Community 440 - "Community 440"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 398 - "Community 398"
Cohesion: 0.46
Nodes (7): _slot(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(), test_allocation_run_creates_movement_group_and_events(), _seed_hotel_rooms_guests(), _reservation()

### Community 305 - "Community 305"
Cohesion: 0.24
Nodes (4): _Response, _Client, test_provider_receives_only_curated_hotel_analytics_payload(), test_provider_chat_uses_curated_hotel_context_and_controlled_message()

### Community 202 - "Community 202"
Cohesion: 0.26
Nodes (13): assert_freshness_metadata(), _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_exports_png_csv_xlsx(), test_company_exports_require_sensitive_company_view_permission() (+5 more)

### Community 82 - "Community 82"
Cohesion: 0.09
Nodes (12): _make_refresh_test_reservation(), _enable_bounded_fact_refresh(), test_stale_fact_window_is_refreshed_within_31_day_cap(), test_partial_fact_window_refreshes_both_tables(), test_targeted_touch_keeps_unaffected_age_visible_and_read_repairs_ttl_and_fx(), test_wide_fact_window_does_not_refresh_or_mask_stale_metadata(), _make_fact_refresh_reservation(), _fact_business_snapshot() (+4 more)

### Community 368 - "Community 368"
Cohesion: 0.28
Nodes (3): _safe_worker_env(), test_celery_process_accepts_explicit_closed_production_profile(), test_celery_process_rejects_missing_production_policy_before_startup()

### Community 241 - "Community 241"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed(), test_operational_schema_covers_dimensions_and_non_pii_facts()

### Community 142 - "Community 142"
Cohesion: 0.10
Nodes (11): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_add_reservation_guests_matches_existing_document_despite_whitespace(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_n06_cancel_errors_match_between_reservation_and_booking_routes(), test_n06_terminal_edit_and_stale_version_errors_are_localized_on_both_routes(), Spin up the real FastAPI app against an in-memory SQLite database. (+3 more)

### Community 306 - "Community 306"
Cohesion: 0.35
Nodes (7): FakeJwkClient, _token(), _verify(), test_valid_apple_token_is_verified(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch()

### Community 161 - "Community 161"
Cohesion: 0.31
Nodes (19): _post_request(), _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation() (+11 more)

### Community 399 - "Community 399"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 167 - "Community 167"
Cohesion: 0.11
Nodes (11): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_hotel_delete_is_restricted(), test_audit_log_all_actions_persist(), test_transaction_hotel_id_has_fk_constraint(), test_failed_audit_log_insert_does_not_roll_back_callers_change(), TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence. (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.06
Nodes (60): FakeResponse, _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend(), test_password_policy_requires_twelve_characters_for_register_and_reset(), test_register_verify_and_reset_use_resend_provider(), test_register_is_anti_enumeration_and_does_not_touch_existing_credentials() (+52 more)

### Community 369 - "Community 369"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_surfaces_retryable_provider_outage(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue()

### Community 527 - "Community 527"
Cohesion: 0.50
Nodes (3): _override_auth(), test_receptionist_can_get_price_quote(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t

### Community 73 - "Community 73"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+24 more)

### Community 58 - "Community 58"
Cohesion: 0.06
Nodes (16): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+8 more)

### Community 126 - "Community 126"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+16 more)

### Community 480 - "Community 480"
Cohesion: 0.60
Nodes (5): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable(), Cancelling a reservation must cancel its still-payable seña links (BR §M).

### Community 400 - "Community 400"
Cohesion: 0.32
Nodes (3): _load_migration(), FakeInspector, test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 74 - "Community 74"
Cohesion: 0.12
Nodes (37): _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_and_currency_is_allowed(), test_cash_movement_requires_open_session(), test_cash_movement_rejects_non_positive_amount_with_spanish_message(), test_close_report_expected_balance_from_confirmed_cash() (+29 more)

### Community 528 - "Community 528"
Cohesion: 0.40
Nodes (1): TestGuestValidation

### Community 481 - "Community 481"
Cohesion: 0.40
Nodes (1): TestCheckIn

### Community 264 - "Community 264"
Cohesion: 0.32
Nodes (12): _override_auth(), _client_with_db(), _seed_fully_paid_reservation(), test_checkin_without_new_fields_fails_with_clear_message(), test_checkin_captures_missing_fields_in_same_request(), test_partial_checkin_reaches_pre_check_in_then_final_checkin(), test_partial_checkin_requires_full_payment_under_default_policy(), test_add_companion_during_checkin_flow_appears_in_additional_guests() (+4 more)

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (27): _make_hotel(), _make_guest(), _make_room(), anchor_hotel_day_to_fixture_arrival(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin() (+19 more)

### Community 265 - "Community 265"
Cohesion: 0.17
Nodes (2): FakeTicketRedis, collaboration_client()

### Community 168 - "Community 168"
Cohesion: 0.23
Nodes (16): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), test_register_settlement_rolls_back_when_audit_cannot_be_written(), _company_reservation(), test_deferred_company_extension_does_not_calculate_or_record_base_price(), test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(), test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies() (+8 more)

### Community 370 - "Community 370"
Cohesion: 0.64
Nodes (8): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation(), test_company_document_cannot_be_attached_to_unlinked_reservation(), test_uploaded_company_voucher_is_private_signature_aware_and_tenant_scoped()

### Community 441 - "Community 441"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_reservation_is_allocation_locked()

### Community 529 - "Community 529"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_columns(), test_company_extension_request_migration_upgrade_downgrade_upgrade(), SQLite round-trip for company extension request fields.

### Community 203 - "Community 203"
Cohesion: 0.25
Nodes (15): _company_reservation(), _transaction(), test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(), test_company_night_charges_use_effective_rate_and_extra_person_quantity(), test_company_charge_quantity_cannot_exceed_registered_additional_people(), test_terminal_company_reservations_cannot_receive_new_nightly_charges(), test_legacy_rate_does_not_price_a_night_before_safe_cutover(), test_explicit_charge_correction_audits_delta_without_rewriting_payment_history() (+7 more)

### Community 401 - "Community 401"
Cohesion: 0.46
Nodes (6): _run_alembic(), _seed_legacy_company(), test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only(), test_company_nightly_rate_downgrade_refuses_to_discard_user_history(), test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots(), SQLite upgrade coverage for company nightly rate cutover and rollback guard.

### Community 402 - "Community 402"
Cohesion: 0.39
Nodes (6): example(), test_only_a_newer_observation_timestamp_may_change(), test_any_provider_subject_drift_is_rejected(), test_final_observation_cannot_predate_probes(), test_cli_rejects_symlinked_manifest(), Regression tests for final provider-evidence continuity.

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (14): get_db_override_target(), get_auth_context_target(), client_with_db(), ctx(), test_config_read_permission_allows_get_without_allowing_updates(), test_co_owner_can_change_fx_market_after_step_up(), _override_role(), test_manager_without_config_manage_permission_is_denied() (+6 more)

### Community 442 - "Community 442"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 483 - "Community 483"
Cohesion: 0.33
Nodes (1): The marketing site's own origin must not depend on an env var being set.  hotels

### Community 110 - "Community 110"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 222 - "Community 222"
Cohesion: 0.28
Nodes (13): _create_role(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), _step_up_headers(), test_roles_api_contract_and_owner_co_owner_admin_mutations(), test_role_archive_refuses_active_members_and_pending_invites(), test_expired_pending_invitation_is_not_counted_or_blocking_role_archive(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed() (+5 more)

### Community 371 - "Community 371"
Cohesion: 0.44
Nodes (8): _create_remitos(), _load_migration(), test_remito_preflight_reports_ids_and_trimmed_duplicates(), test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace(), test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved(), test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint(), test_remito_preflight_is_empty_when_no_duplicate_exists(), test_day2_downgrade_refuses_to_discard_persisted_operational_data()

### Community 334 - "Community 334"
Cohesion: 0.42
Nodes (9): _legacy_deferred_reservation(), _payment(), test_deferred_reservation_read_and_list_mask_legacy_lodging_money(), test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(), test_pending_company_night_extra_remains_due_until_payment_completes(), test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(), test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(), test_deferred_reservation_group_masks_legacy_group_total() (+1 more)

### Community 191 - "Community 191"
Cohesion: 0.12
Nodes (6): client(), test_seed_and_reset_blocked_by_default(), test_seed_and_reset_allowed_when_demo_enabled(), FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Explicit development environments retain the DEMO_MODE workflow.

### Community 204 - "Community 204"
Cohesion: 0.21
Nodes (9): FakeRedis, _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_optional_lock_can_degrade_when_redis_is_unavailable(), FakePostgresSession, test_required_lock_uses_postgres_advisory_lock_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 192 - "Community 192"
Cohesion: 0.25
Nodes (12): _seed_hotels(), _outbox_row(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision(), test_worker_records_bounded_failure_and_backoff_without_error_message() (+4 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (36): _event_engine(), _thread_safe_event_engine(), FakeRedis, _settings(), _successful_publisher(), test_realtime_fallback_poll_budget_is_below_ten_seconds(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_permission_invalidation_publishes_without_error_logging() (+28 more)

### Community 223 - "Community 223"
Cohesion: 0.17
Nodes (5): _postgres_e2e_environment(), test_seed_guard_accepts_only_explicit_loopback_postgres_e2e_database(), test_seed_guard_requires_a_distinct_explicit_seed_role_on_the_same_local_database(), test_seed_guard_rejects_postgres_without_the_dedicated_local_test_boundary(), test_reset_e2e_database_never_deletes_postgres_target_files()

### Community 205 - "Community 205"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, test_credential_access_and_email_stop_before_db_or_network(), test_connections_flag_alone_closes_credential_lane(), test_payment_link_test_stops_before_db_or_provider(), test_google_login_stops_before_transport_or_db(), test_apple_login_stops_before_jwks_or_db(), test_provider_callbacks_stop_before_body_parse() (+2 more)

### Community 484 - "Community 484"
Cohesion: 0.53
Nodes (5): _alembic(), _seed_legacy_links(), _assert_migrated(), test_payment_link_migration_backfills_provider_history_and_reupgrades(), Data-contract regression for the payment-link execution-mode migration.

### Community 485 - "Community 485"
Cohesion: 0.60
Nodes (5): _f003_environment(), test_f003_seed_accepts_only_dedicated_local_fixture_target(), test_f003_seed_requires_explicit_opt_in(), test_f003_seed_rejects_sqlite_even_with_opt_in(), test_f003_seed_rejects_database_outside_its_dedicated_namespace()

### Community 206 - "Community 206"
Cohesion: 0.21
Nodes (11): _make_completed_transaction(), test_daily_report_totals_a_completed_transaction_without_crashing(), test_revenue_report_totals_multiple_completed_transactions_without_crashing(), test_revenue_refunds_and_transaction_bounds_use_hotel_local_days(), test_booked_value_includes_and_prorates_stays_overlapping_the_report_window(), test_booked_value_endpoint_matches_full_report_with_bounded_query_count(), _reservation_for_report(), test_revenue_keeps_currencies_separate_and_uses_reportable_channel() (+3 more)

### Community 224 - "Community 224"
Cohesion: 0.18
Nodes (7): _FakeResponse, _quote(), test_fresh_quote_rejects_crossed_buy_sell_values(), test_blue_equivalent_for_non_usd_currency_is_explicitly_derived(), test_blue_equivalent_fails_closed_when_any_source_quote_is_stale(), test_stale_selected_usd_quote_fails_closed_without_requesting_official_fallback(), test_usd_conversion_rejects_provider_quote_for_wrong_currency_or_market()

### Community 372 - "Community 372"
Cohesion: 0.33
Nodes (5): _supported_official_quote(), _store_expired_display_quote(), test_disabled_async_fx_uses_cache_without_constructing_client(), test_disabled_sync_fx_uses_stale_cache_without_network(), test_production_sandbox_can_read_dolarapi_without_enabling_integrations()

### Community 136 - "Community 136"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 373 - "Community 373"
Cohesion: 0.28
Nodes (3): _read(), test_generates_only_allowed_synthetic_values_with_private_permissions(), test_explicit_rotation_replaces_values_and_preserves_mode()

### Community 308 - "Community 308"
Cohesion: 0.22
Nodes (3): _Response, test_validate_gmail_credentials_requires_send_scope(), test_verify_connection_health_for_gmail_updates_connection()

### Community 335 - "Community 335"
Cohesion: 0.29
Nodes (5): _integration_client(), _Response, test_validate_gmail_credentials_rejects_missing_send_scope(), test_send_hotel_email_uses_connected_gmail(), test_gmail_oauth_callback_uses_signed_state()

### Community 565 - "Community 565"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_direct_guest_and_companion_audits_exclude_pii(), test_decorator_mongo_projection_excludes_guest_pii()

### Community 566 - "Community 566"
Cohesion: 0.67
Nodes (3): _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite(), B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio

### Community 280 - "Community 280"
Cohesion: 0.42
Nodes (10): _seed_hotel(), _seed_reservation(), _step_up_headers(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_rejects_invalid_and_overlong_date_ranges(), test_guest_export_excludes_soft_deleted_guest_identity() (+2 more)

### Community 444 - "Community 444"
Cohesion: 0.52
Nodes (6): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) -- skip/

### Community 403 - "Community 403"
Cohesion: 0.61
Nodes (7): _auth(), _client(), test_restriction_api_permissions_tenant_isolation_and_event(), test_active_restriction_summary_is_batched_tenant_scoped_and_nondisclosing(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_restriction_override_reason_rejects_whitespace()

### Community 445 - "Community 445"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_legacy_tags(), _load_migration(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls()

### Community 309 - "Community 309"
Cohesion: 0.38
Nodes (10): _seed_hotel(), _seed_guest_inventory(), _reservation(), _create_payload(), test_restriction_lifecycle_distinguishes_active_expired_and_resolved(), test_restriction_is_tenant_scoped_for_reads_and_resolution(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override() (+2 more)

### Community 530 - "Community 530"
Cohesion: 0.80
Nodes (4): _client(), _move(), test_receptionist_can_record_complaint_but_cannot_resolve_it(), test_second_complaint_reactivates_the_same_guest_room_row()

### Community 531 - "Community 531"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 225 - "Community 225"
Cohesion: 0.41
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 310 - "Community 310"
Cohesion: 0.18
Nodes (3): utc_server_clock(), The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today

### Community 336 - "Community 336"
Cohesion: 0.24
Nodes (5): _Response, _seed_gmail_connection(), _seed_mercadopago_connection(), test_send_hotel_email_uses_connected_gmail(), test_payment_link_test_requires_hotel_gmail_connection()

### Community 568 - "Community 568"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_hotel_schedule_migration_preserves_existing_settings_and_round_trips(), SQLite migration round-trip for hotel-local check-in and check-out times.

### Community 486 - "Community 486"
Cohesion: 0.53
Nodes (5): _run_alembic(), _assert_backfill(), test_housekeeping_status_migration_backfills_and_reverses_cleanly(), test_housekeeping_board_permission_migration_seeds_only_intended_roles(), Data migration guard for separating housekeeping state from room status.

### Community 569 - "Community 569"
Cohesion: 0.83
Nodes (3): _load_migration(), _run_migration(), test_migration_backfills_existing_accounts_and_retains_alias_on_rollback()

### Community 532 - "Community 532"
Cohesion: 0.60
Nodes (4): _DB, _client(), test_owner_and_co_owner_can_enter_secret_connection_mutations(), test_generic_whatsapp_connection_mutations_are_rejected_before_writing()

### Community 570 - "Community 570"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (53): get_db_override_target(), get_auth_context_target(), _invitation_token(), client_with_db(), owner_ctx(), _manage_users_request(), test_invite_returns_token_and_accepts(), test_atomic_invitation_consumption_rejects_a_rotated_token_hash() (+45 more)

### Community 434 - "Community 434"
Cohesion: 0.33
Nodes (3): _FakeDispatcher, JobDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 571 - "Community 571"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_missing_follow_up_migration_backfills_shorts_and_guards_downgrade(), Backfill and preserve neutral follow-up for declared laundry shortages.

### Community 572 - "Community 572"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_missing_quantity_migration_defaults_existing_lines_and_round_trips(), Persist declared laundry losses without changing historical remito lines.

### Community 573 - "Community 573"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_house_location_migration_preserves_old_remitos_and_round_trips(), Add a nullable hotel-side location to new laundry remitos safely.

### Community 574 - "Community 574"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 97 - "Community 97"
Cohesion: 0.20
Nodes (29): _override_auth(), _client_with_db(), _teardown(), test_duplicate_remito_returns_conflict_but_other_direction_is_allowed(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_vendor_price_write_requires_laundry_price_permission(), test_manager_needs_explicit_vendor_price_permission(), test_owner_can_manage_linen_items_and_receptionist_cannot() (+21 more)

### Community 90 - "Community 90"
Cohesion: 0.15
Nodes (30): _seed_hotels(), _seed_house_stock(), test_create_vendor_creates_its_own_linen_location(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_inbound_reverses_the_transfer(), test_remito_number_is_unique_per_hotel_vendor_and_direction(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails() (+22 more)

### Community 575 - "Community 575"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_linen_par_level_migration_constraints_and_upgrade_downgrade_upgrade(), Migration contract and SQLite round trip for location-specific linen minima.

### Community 337 - "Community 337"
Cohesion: 0.36
Nodes (9): _seed_hotels(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped(), test_linen_opening_count_batch_is_atomic_and_only_applies_before_location_history(), test_linen_summary_marks_zero_balance_as_having_history(), test_linen_transfer_is_atomic_linked_and_idempotent(), test_linen_transfer_rejects_insufficient_source_without_partial_rows(), test_linen_minimums_are_location_specific_and_allow_zero() (+1 more)

### Community 446 - "Community 446"
Cohesion: 0.43
Nodes (6): _run_alembic(), _seed_pre_split_data(), test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade(), _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly, Hand-insert a real 'linen' StockItem plus movements and a laundry     vendor/pri

### Community 127 - "Community 127"
Cohesion: 0.15
Nodes (17): env_page(), FakeRender, mutations(), acquire_lease(), release_lease(), test_acquire_validates_before_writing_and_commits_id_last(), test_acquire_refuses_every_drift_without_mutation(), test_same_production_and_qa_identity_is_rejected_before_get() (+9 more)

### Community 404 - "Community 404"
Cohesion: 0.43
Nodes (7): _load_migration(), _load_data_migration(), test_migration_backfills_default_policy_and_is_idempotent(), test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(), test_ota_backfill_locks_row_before_recomputing_completed_ledger(), SQLite contract test for the new manual-payment/check-in-policy migration., A payment committed after candidate discovery must be in the backfill snapshot.

### Community 98 - "Community 98"
Cohesion: 0.10
Nodes (15): _manual_payment(), _step_up_header(), test_manual_in_person_payment_requires_reference_and_records_actor(), test_receipt_endpoint_uses_persisted_values_and_does_not_create_another_payment(), test_receipt_endpoint_respects_cash_operation_denial(), test_refund_requires_manager_permission_and_one_use_step_up(), test_refund_cannot_exceed_original_payment_by_one_cent(), test_cancelling_paid_reservation_requires_manager_step_up_without_auto_refund() (+7 more)

### Community 533 - "Community 533"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_schema(), test_manual_rate_policy_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for bounded manual reservation rates.

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (58): FakeResponse, _seed_platform_admin(), _complete_master_login(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_admin_absolute_ttl_expires_recently_active_session(), test_master_login_bootstraps_env_account() (+50 more)

### Community 405 - "Community 405"
Cohesion: 0.32
Nodes (6): _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it(), test_master_admin_dashboard_reads_hotels_without_outbox_rls_failure(), C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, A master-admin dashboard read may seed a missing subscription safely.      Snaps

### Community 281 - "Community 281"
Cohesion: 0.36
Nodes (9): _reservation(), _create_link(), _sign(), _post_webhook(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_duplicate_webhook_delivery_does_not_double_charge(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing() (+1 more)

### Community 447 - "Community 447"
Cohesion: 0.43
Nodes (5): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), This bool-returning shim delegates to the SAME raising validator every     real

### Community 374 - "Community 374"
Cohesion: 0.22
Nodes (5): TestTransactionModel, Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship.

### Community 207 - "Community 207"
Cohesion: 0.13
Nodes (9): TestRoomModels, Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify the hotel has exactly 38 rooms., Same room_number can exist in different hotels without conflict., Verify room string representation. (+1 more)

### Community 338 - "Community 338"
Cohesion: 0.20
Nodes (6): TestGuestModel, Tests for Guest and GuestCompanion models., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Create companions and verify relationship., Verify auto-generated timestamps.

### Community 339 - "Community 339"
Cohesion: 0.20
Nodes (6): TestReservationModel, Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify can_transition_to method., Verify balance_due computed property., Verify nights calculation.

### Community 406 - "Community 406"
Cohesion: 0.25
Nodes (5): TestHotelConfigModel, Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies.

### Community 407 - "Community 407"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 576 - "Community 576"
Cohesion: 0.67
Nodes (3): _alembic(), test_migration_seeds_dedicated_permission_and_safe_role_defaults(), Regression coverage for the additive movement-group permission migration.

### Community 375 - "Community 375"
Cohesion: 0.39
Nodes (8): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel(), test_reset_endpoint_allows_testing_env()

### Community 169 - "Community 169"
Cohesion: 0.20
Nodes (16): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+8 more)

### Community 103 - "Community 103"
Cohesion: 0.09
Nodes (20): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+12 more)

### Community 340 - "Community 340"
Cohesion: 0.20
Nodes (9): test_normalizes_generated_instruction_paths_without_touching_external_paths(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized(), Regression coverage for portable Graphify artifact normalization., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+1 more)

### Community 376 - "Community 376"
Cohesion: 0.50
Nodes (8): _auth(), _client(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_push_subscription_register_and_unregister(), test_preferences_crud(), test_daily_report_schedule_is_owner_co_owner_only(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and

### Community 143 - "Community 143"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), test_enqueue_dedupes_same_event_recipient_channel(), test_enqueue_same_dedupe_key_isolated_per_hotel(), test_enqueue_skips_recipient_without_entity_read_permission(), test_enqueue_skips_recipient_without_active_membership(), test_enqueue_role_based_fanout(), test_enqueue_respects_channel_preference() (+15 more)

### Community 577 - "Community 577"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), test_process_outbox_delivers_across_every_active_hotel(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t

### Community 377 - "Community 377"
Cohesion: 0.50
Nodes (8): _owner(), _outbox_event_types(), test_reservation_lifecycle_enqueues_notifications(), test_no_show_enqueues_notification(), test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), Integration coverage: the real domain-event call sites (reservation lifecycle, c

### Community 312 - "Community 312"
Cohesion: 0.27
Nodes (9): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_owner_registration_without_outbox_override_does_not_return_503(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers. (+1 more)

### Community 534 - "Community 534"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 313 - "Community 313"
Cohesion: 0.31
Nodes (9): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_new_hotel_starts_with_cash_only(), test_onboarding_cannot_activate_paid_plan_without_checkout(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records() (+1 more)

### Community 282 - "Community 282"
Cohesion: 0.26
Nodes (7): _user(), _reservation(), _transaction(), test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(), test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(), test_operational_audit_filters_only_successful_logins(), Focused coverage for the operational audit and hotel-local cash projection.

### Community 242 - "Community 242"
Cohesion: 0.36
Nodes (11): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_today_arrival_count_is_server_side_hotel_local_and_not_page_limited(), test_operational_daily_report_separates_no_shows_from_arrivals(), test_occupancy_report_counts_pre_check_in_reservations(), test_daily_report_is_hotel_scoped() (+3 more)

### Community 341 - "Community 341"
Cohesion: 0.24
Nodes (3): MemoryObjectStorage, _create_task_context(), test_task_photo_is_private_tenant_scoped_and_integrity_checked()

### Community 378 - "Community 378"
Cohesion: 0.50
Nodes (7): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_with_confirmed_external_payment_requires_settlement_review(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 208 - "Community 208"
Cohesion: 0.28
Nodes (14): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel() (+6 more)

### Community 193 - "Community 193"
Cohesion: 0.12
Nodes (8): TestBookingWebhook, TestExpediaWebhook, TestOTARaceCondition, TestAvailabilityUpdate, Tests for OTA Integration — Race condition handling and webhook processing., Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room.

### Community 283 - "Community 283"
Cohesion: 0.23
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret(), test_despegar_webhook_scopes_by_hotel_and_secret()

### Community 183 - "Community 183"
Cohesion: 0.25
Nodes (16): _enable_external_effects(), _reservation(), test_create_payment_link_persists_link_without_transaction(), test_local_payment_link_rejects_currency_different_from_reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp() (+8 more)

### Community 154 - "Community 154"
Cohesion: 0.20
Nodes (20): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_submit_transfer_proof_validates_image_and_stores_metadata(), test_concurrent_metadata_conflict_deletes_the_uncommitted_upload(), test_failed_commit_after_upload_rolls_back_metadata_and_deletes_object(), test_ambiguous_commit_that_persisted_proof_keeps_its_object(), test_submit_transfer_proof_reencodes_and_removes_exif() (+12 more)

### Community 243 - "Community 243"
Cohesion: 0.41
Nodes (13): _completed_payment(), _mock_receipt_email(), _receipt_headers(), test_receipt_email_sends_persisted_receipt_once_and_records_auditable_outcome(), test_receipt_email_accepts_a_refunded_receipt_transaction(), test_receipt_email_denied_permission_does_not_call_gmail(), test_receipt_email_requires_action_bound_mfa_before_provider_call(), test_receipt_email_rejects_invalid_or_unregistered_recipient_without_send() (+5 more)

### Community 75 - "Community 75"
Cohesion: 0.06
Nodes (18): _assign_hotel(), TestDepositPayment, TestHotelIsolation, TestPaymentEdgeCases, TestPaymentActorAudit, Assign hotel scope to reservation (hotel_id column provided by A1)., Tests for deposit (señas) payment flow., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status → (+10 more)

### Community 579 - "Community 579"
Cohesion: 0.50
Nodes (3): TestFullPayment, Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid.

### Community 536 - "Community 536"
Cohesion: 0.40
Nodes (3): TestBalancePaymentAtCheckin, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi

### Community 342 - "Community 342"
Cohesion: 0.47
Nodes (7): _override_auth(), _build_client(), _cleanup(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_reactivate_deactivated_surcharge_via_patch()

### Community 162 - "Community 162"
Cohesion: 0.22
Nodes (18): _reservation(), _link(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key(), test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(), test_rejected_payment_cannot_be_flipped_to_completed_by_later_webhook() (+10 more)

### Community 343 - "Community 343"
Cohesion: 0.33
Nodes (9): _alembic(), test_permission_catalog_migration_is_additive_and_reversible(), test_operational_audit_cash_migration_is_safe_on_existing_schema(), test_housekeeping_occupancy_default_migration_tightens_without_touching_grant(), test_room_move_tier_migration_is_additive_idempotent_and_preserves_overrides(), test_permission_enforcement_migration_backfills_defaults_and_removes_sessions(), test_migrated_defaults_match_the_code_default_matrix(), Regression coverage for the additive permission-catalog migration. (+1 more)

### Community 284 - "Community 284"
Cohesion: 0.38
Nodes (12): _step_up_headers(), _auth(), _client(), test_owner_and_co_owner_can_use_administration_catalog_but_manager_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_owner_cannot_change_or_restore_another_owners_user_overrides(), test_owner_can_restore_one_role_override_to_catalog_default_with_audit(), test_owner_can_restore_one_user_override_to_role_default_with_audit() (+4 more)

### Community 194 - "Community 194"
Cohesion: 0.20
Nodes (14): _seed_hotel(), test_company_night_rate_permission_defaults_allow_management_roles(), test_permission_override_can_deny_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_owner_override_can_grant_permission_missing_from_role_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_resolve_many_preserves_user_role_and_hotel_override_precedence(), test_resolve_many_preserves_legacy_deny_fallback_and_invariants() (+6 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (33): _override_auth(), _step_up_headers(), _client_with_db(), _enable_whatsapp_plan_for_api_test(), test_permissions_matrix_available_to_permission_manager_only(), test_permissions_matrix_exposes_only_canonical_rows_with_ui_metadata(), test_revoking_each_section_view_permission_blocks_its_read_endpoint(), test_subscription_status_does_not_claim_active_when_source_is_unavailable() (+25 more)

### Community 209 - "Community 209"
Cohesion: 0.26
Nodes (11): _load_migration(), _Result, _RecordingBind, _uppercase_catalog(), test_upgrade_normalizes_only_remaining_enum_labels_and_is_idempotent(), test_downgrade_reverses_only_the_new_migration(), test_upgrade_fails_closed_if_both_enum_labels_exist(), test_upgrade_fails_closed_when_an_expected_label_is_missing() (+3 more)

### Community 133 - "Community 133"
Cohesion: 0.09
Nodes (23): _reset_pg_to_empty_schema(), _reset_pg_to_clean_head(), test_alembic_upgrade_on_empty_database(), test_alembic_downgrade_and_reupgrade(), test_numeric_precision_enforced_on_postgres(), test_enum_types_exist_in_postgres(), test_unique_constraints_enforced_on_postgres(), test_explain_analyze_guest_search_index() (+15 more)

### Community 79 - "Community 79"
Cohesion: 0.10
Nodes (30): _bootstrap_environment(), _provider_manifest(), _local_evidence_payload(), _safe_environment(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_remote_target_rejects_self_attested_json_without_signed_token() (+22 more)

### Community 488 - "Community 488"
Cohesion: 0.47
Nodes (4): safe_preview_settings(), test_preview_runtime_accepts_explicitly_disabled_external_effects(), test_preview_runtime_rejects_external_effects_configuration(), Fail-closed safeguards for cloud QA external integrations.

### Community 144 - "Community 144"
Cohesion: 0.21
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 76 - "Community 76"
Cohesion: 0.11
Nodes (26): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+18 more)

### Community 266 - "Community 266"
Cohesion: 0.29
Nodes (12): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(), test_all_supported_fx_pairs_use_directional_quotes_via_ars(), test_global_blue_market_dominates_fx_policy_source_and_side(), test_missing_selected_blue_market_does_not_fall_back_to_official_snapshot() (+4 more)

### Community 285 - "Community 285"
Cohesion: 0.44
Nodes (11): _seed_hotel(), _seed_daily_rates(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_applies_tax_policy(), test_canonical_promotion_pricing_converts_non_ars_currency_with_fx_snapshot(), test_canonical_pricing_missing_fx_rate_raises() (+3 more)

### Community 244 - "Community 244"
Cohesion: 0.29
Nodes (12): _seed_hotel(), _ctx(), test_create_promotion_rejects_percentage_over_100(), test_create_promotion_rejects_duplicate_code(), test_find_applicable_promotions_matches_typed_conditions(), test_find_applicable_promotions_respects_weekday_and_date_range(), test_find_applicable_promotions_matches_guest_tag_type(), test_apply_promotions_never_goes_negative() (+4 more)

### Community 448 - "Community 448"
Cohesion: 0.71
Nodes (6): _override_auth(), _build_client(), _cleanup(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 449 - "Community 449"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_pre_migration_surcharge(), _load_migration(), test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data(), test_promotions_migration_owns_reversible_postgresql_rls()

### Community 104 - "Community 104"
Cohesion: 0.17
Nodes (21): manifest(), token_for(), env_page(), FakeRender, HealthResponse, FakeRenderCleanupFailure, FakeRenderPutResponseLost, _mutating_calls() (+13 more)

### Community 286 - "Community 286"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 184 - "Community 184"
Cohesion: 0.29
Nodes (16): _payload(), _configured_settings(), _inquiry_rows(), test_public_inquiry_persists_and_notifies_after_acceptance(), test_public_inquiry_keeps_record_when_notification_fails(), test_public_inquiry_rejects_invalid_required_fields(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_rate_limited_by_source_and_email() (+8 more)

### Community 163 - "Community 163"
Cohesion: 0.12
Nodes (5): _plan(), TestPublicPricing, TestLeadCapture, The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page.

### Community 537 - "Community 537"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 210 - "Community 210"
Cohesion: 0.23
Nodes (14): tagged(), write_fixture(), test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_unsigned_or_fabricated_attestation_is_rejected(), test_altered_signature_is_rejected(), test_signed_attestation_missing_a_summary_hash_is_rejected() (+6 more)

### Community 226 - "Community 226"
Cohesion: 0.47
Nodes (13): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+5 more)

### Community 211 - "Community 211"
Cohesion: 0.32
Nodes (14): seed_rate_context(), test_rate_draft_requires_confirmation_and_keeps_reservation_price(), test_rate_confirmation_rolls_back_business_change_if_audit_write_fails(), test_stale_rate_draft_cannot_overwrite_a_newer_rate(), test_rate_draft_is_tenant_scoped(), test_rate_draft_rejects_unsafe_fields_and_duplicate_dates(), _period_draft_payload(), _period_values() (+6 more)

### Community 170 - "Community 170"
Cohesion: 0.12
Nodes (12): get_db_override_target(), get_auth_context_target(), client_with_db(), authed_client(), test_verify_email_code_guessing_is_rate_limited(), test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate(), test_register_is_rate_limited_by_source(), test_concurrent_db_requests_record_each_attempt_before_deciding() (+4 more)

### Community 450 - "Community 450"
Cohesion: 0.48
Nodes (6): _load_migration(), _alembic(), _engine(), _seed_pre_revision(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal()

### Community 145 - "Community 145"
Cohesion: 0.15
Nodes (16): FakeRedis, BrokenRedis, _cache_settings(), _reset_cache_client_state(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising(), test_cache_disabled_returns_computed_value_without_constructing_redis() (+8 more)

### Community 379 - "Community 379"
Cohesion: 0.36
Nodes (6): _add_event(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_missing_or_zero_cursor_requires_full_refetch(), test_stale_cursor_requires_full_refetch(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch()

### Community 380 - "Community 380"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 152 - "Community 152"
Cohesion: 0.24
Nodes (17): iso(), write_bundle(), rewrite_summary(), rewrite_manifest(), errors_for(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_short_code_sha_is_rejected(), test_manifest_byte_hash_is_required() (+9 more)

### Community 433 - "Community 433"
Cohesion: 0.48
Nodes (6): _load_workflow(), _job_block(), test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes(), test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled(), Contracts for opting provider-bound PR evidence checks in by label., adf208e Remove undeclared YAML dependency from workflow test

### Community 538 - "Community 538"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 344 - "Community 344"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 314 - "Community 314"
Cohesion: 0.33
Nodes (8): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors(), R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).  No real em

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (37): test_overdue_checked_in_stay_is_a_serialized_manual_review_action(), test_pending_action_candidate_cap_does_not_hide_later_critical_action(), _mk_reservation(), test_completed_paid_amounts_group_net_completed_transactions_and_scope_hotel(), test_pending_action_adjustment_batch_omits_rows_that_cannot_create_actions(), test_cancelled_reservation_never_offers_collection_action(), test_cancelled_direct_booking_with_net_paid_amount_surfaces_manual_refund_review(), test_no_show_direct_booking_with_legacy_net_paid_amount_surfaces_manual_refund_review() (+29 more)

### Community 490 - "Community 490"
Cohesion: 0.33
Nodes (1): Regression coverage for reservation arrival metadata and internal comments.

### Community 491 - "Community 491"
Cohesion: 0.53
Nodes (5): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_uses_reservation_currency_and_rejects_mismatch(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), Tests for operator-created reservation consumption charges.

### Community 492 - "Community 492"
Cohesion: 0.60
Nodes (5): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly(), test_invalid_recipient_is_rejected_before_provider()

### Community 288 - "Community 288"
Cohesion: 0.39
Nodes (9): _seed_hotel(), _add_reservation(), _rows(), _step_up_headers(), test_reservation_export_requires_dedicated_permission(), test_reservation_export_uses_inclusive_occupancy_dates_and_hotel_scope(), test_reservation_export_neutralizes_formula_like_text(), test_reservation_export_rejects_invalid_and_overlong_date_ranges() (+1 more)

### Community 493 - "Community 493"
Cohesion: 0.53
Nodes (5): _group_payloads(), test_create_four_room_company_group_and_aggregate_summary(), test_group_rejects_room_count_outside_bounds(), test_group_rejects_inconsistent_company_and_manual_totals(), Atomic multi-room reservation grouping and aggregate balance contracts.

### Community 315 - "Community 315"
Cohesion: 0.36
Nodes (10): _create_sample_reservation(), _completed_transaction(), test_no_show_can_be_marked_without_auto_charge(), test_date_change_without_payments_cancels_and_recreates(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_paid_date_change_refreshes_analytics_facts_once(), test_extension_requires_payment_or_link_action(), test_extension_rejects_checkout_not_after_current_checkout_in_spanish() (+2 more)

### Community 289 - "Community 289"
Cohesion: 0.26
Nodes (9): _make_reservations(), test_default_limit_caps_result_at_50(), test_skip_and_limit_page_through_results(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_listing_uses_one_scalar_reservation_query(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati (+1 more)

### Community 128 - "Community 128"
Cohesion: 0.31
Nodes (25): _override_auth(), _build_client(), _cleanup_client(), _seed_bookable_state(), _payload(), _manual_ota_payload(), test_receptionist_cannot_set_manual_total_amount(), test_co_owner_uses_confirmed_owner_level_manual_rate_access() (+17 more)

### Community 345 - "Community 345"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 155 - "Community 155"
Cohesion: 0.10
Nodes (6): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields(), test_move_reservation_room_updates_room_status_for_checked_in_reservation(), Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke

### Community 539 - "Community 539"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_permission_defaults(), test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade(), SQLite round-trip for the configurable reservation price permission.

### Community 409 - "Community 409"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 451 - "Community 451"
Cohesion: 0.48
Nodes (6): _reservation(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty(), test_search_does_not_leak_across_hotels(), Tests for the reservation global search filter (B1 header search).  Search is a

### Community 267 - "Community 267"
Cohesion: 0.15
Nodes (7): TestAvailability, Tests for room availability checking., A room with no reservations should be available., A room with an overlapping reservation should not be available., Check-out day == next check-in day should be allowed (no overlap)., Find available rooms after booking some., Availability lookup must not issue one reservation query per room.

### Community 171 - "Community 171"
Cohesion: 0.11
Nodes (9): TestReservationCreation, Tests for reservation creation logic., Create a standard reservation and verify computed fields., B4: manual tarifa on a direct reservation with no company_id -- the         auto, Reserve a specific room., Should fail for non-existent guest., Should fail when check-out is before check-in., Should fail when room doesn't match the requested category. (+1 more)

### Community 494 - "Community 494"
Cohesion: 0.33
Nodes (2): TestStateTransitions, Tests for reservation state machine transitions.

### Community 657 - "Community 657"
Cohesion: 0.67
Nodes (1): Regression guard for a real bug B3.1 uncovered: on a SQLite database built from

### Community 212 - "Community 212"
Cohesion: 0.25
Nodes (14): _role_connection(), _seed_engine(), _seed_session(), test_invitation_token_resolves_its_custom_role_under_forced_rls(), test_tenant_isolation_blocks_cross_hotel_reads(), test_no_tenant_context_hides_all_rows(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_after_commit_listener_reapplies_hotel_context() (+6 more)

### Community 227 - "Community 227"
Cohesion: 0.42
Nodes (14): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+6 more)

### Community 228 - "Community 228"
Cohesion: 0.31
Nodes (12): _override_auth(), _seed_room(), _seed_reservation(), test_create_and_resolve_room_block_api(), test_room_block_conflict_preview_returns_counts_without_reservation_identity(), test_room_block_conflict_preview_uses_create_permission_and_validates_dates(), test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(), test_room_block_extension_preview_and_mutation_keep_end_exclusive() (+4 more)

### Community 452 - "Community 452"
Cohesion: 0.29
Nodes (3): test_duplicate_room_number_returns_409(), Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro

### Community 346 - "Community 346"
Cohesion: 0.60
Nodes (9): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_receptionist_can_read_but_cannot_revert_room_movement_group(), test_explicit_receptionist_grant_can_revert_group(), test_company_group_revert_denies_reception_even_with_individual_company_manage_override(), test_housekeeping_cannot_read_or_revert_room_movement_group(), test_room_movement_group_cross_hotel_isolation() (+1 more)

### Community 410 - "Community 410"
Cohesion: 0.32
Nodes (7): _create_rooms_with_soft_deleted_tail(), test_soft_deleted_rooms_are_excluded_from_every_room_count_surface(), test_inline_fact_repair_commits_with_expired_outbox_objects(), Regression coverage for room soft-delete visibility across count surfaces., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, Analytics repair can commit while queued outbox ORM objects are expired.

### Community 347 - "Community 347"
Cohesion: 0.31
Nodes (8): _override_auth(), test_receptionist_can_list_rooms_without_loading_reservations(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_room_category_rates_are_batched_and_keep_daily_period_and_base_precedence(), test_custom_housekeeping_role_receives_safe_room_projection(), Reception needs to read room data to build reservations (room picker, availabili, GET /api/rooms/categories feeds the category picker on both the     Reservations

### Community 290 - "Community 290"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 676 - "Community 676"
Cohesion: 1.00
Nodes (2): test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured(), MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set.

### Community 677 - "Community 677"
Cohesion: 1.00
Nodes (2): test_validate_runtime_security_ignores_incomplete_optional_integrations(), Partial integration env vars should not block production startup.

### Community 678 - "Community 678"
Cohesion: 1.00
Nodes (2): test_validate_runtime_security_rejects_localhost_redirect_when_service_configured(), OAuth redirect URIs are only validated when the corresponding service credential

### Community 679 - "Community 679"
Cohesion: 1.00
Nodes (2): test_validate_runtime_security_rejects_weak_master_admin_password_in_production(), Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc

### Community 229 - "Community 229"
Cohesion: 0.23
Nodes (13): _headers(), test_security_overview_and_events_are_redacted_and_tenant_scoped(), test_manager_cannot_read_security_settings(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv(), test_security_csv_treats_formula_prefixed_actor_alias_as_text(), test_audit_surfaces_do_not_expose_mutating_methods(), test_unified_audit_timeline_combines_sources_orders_redacts_and_isolates_tenant(), test_unified_audit_timeline_supports_inclusive_date_filters_and_role_guard() (+5 more)

### Community 495 - "Community 495"
Cohesion: 0.53
Nodes (4): _values(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_env_file_requires_owner_only_permissions()

### Community 120 - "Community 120"
Cohesion: 0.09
Nodes (10): Surface, _request_context(), _make_reservation(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _card_value(), _starter_analytics() (+2 more)

### Community 496 - "Community 496"
Cohesion: 0.53
Nodes (5): _migrate(), _unique_column_sets(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi

### Community 453 - "Community 453"
Cohesion: 0.43
Nodes (4): RecordingMailer, test_staff_welcome_notice_contains_access_details_without_capabilities(), test_staff_role_notice_names_the_hotel_and_both_roles(), test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details()

### Community 213 - "Community 213"
Cohesion: 0.30
Nodes (15): _override_auth(), _client_with_db(), _teardown(), _second_hotel(), test_owner_can_delete_item_and_recreate_it_with_the_same_name(), test_duplicate_active_name_returns_clean_409_not_a_500(), test_stock_item_unit_cost_is_exposed_on_create_and_update(), test_stock_item_full_edit_updates_name_sku_unit_and_min_quantity() (+7 more)

### Community 230 - "Community 230"
Cohesion: 0.31
Nodes (14): _seed_hotels(), _movement(), test_consumption_report_totals_and_variation_between_periods(), test_consumption_report_excludes_adjustments_and_location_transfers(), test_consumption_report_is_hotel_scoped(), test_consumption_report_variation_is_none_without_a_previous_baseline(), test_consumption_report_rejects_invalid_group_by(), test_consumption_report_rejects_inverted_range() (+6 more)

### Community 99 - "Community 99"
Cohesion: 0.11
Nodes (29): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_stock_outbound_cannot_make_quantity_negative(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(), test_stock_adjustment_can_correct_quantity_downward(), test_stock_adjustment_downward_cannot_make_quantity_negative(), test_current_stock_location_filter_is_additive_and_hotel_wide_total_unchanged() (+21 more)

### Community 540 - "Community 540"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_transfer_schema(), test_stock_transfer_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for linked stock transfer movements.

### Community 454 - "Community 454"
Cohesion: 0.33
Nodes (2): _Session, test_subscription_session_closes_before_asgi_work()

### Community 497 - "Community 497"
Cohesion: 0.73
Nodes (5): _run_alembic(), _plan_values(), test_publishes_approved_prices_without_overwriting_admin_values(), test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(), test_price_migration_downgrade_restores_preexisting_currency_and_period()

### Community 172 - "Community 172"
Cohesion: 0.18
Nodes (15): _ensure_hotel(), _auth_headers(), _step_up_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_trial_does_not_replace_existing_legacy_paid_plan(), test_comped_override_requires_master_admin_session_before_disclosing_hotel_state(), test_role_gating_for_trial_and_comped_override() (+7 more)

### Community 580 - "Community 580"
Cohesion: 0.67
Nodes (3): _index_names(), test_hot_path_composite_indexes_exist_in_models(), Focused regression tests for the TECH-0063 OLTP audit fixes.

### Community 121 - "Community 121"
Cohesion: 0.24
Nodes (24): _reservation_id(), _create_reservation(), _request(), _approve(), _set_cancel_permission(), _consume(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(), test_ordinary_permission_allows_cancel_without_consuming_supplied_grant() (+16 more)

### Community 411 - "Community 411"
Cohesion: 0.25
Nodes (3): test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(), C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them.

### Community 91 - "Community 91"
Cohesion: 0.10
Nodes (22): _load_rls_migration(), _load_user_override_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_company_night_charge_tenant_migration(), _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract(), test_tenant_composite_fk_migrations_cover_every_scoped_relationship() (+14 more)

### Community 105 - "Community 105"
Cohesion: 0.14
Nodes (18): iso(), evidence_bytes(), FakeGitHub, prepare(), test_trusted_prepare_and_finalize_accept_only_byte_identical_provider_artifact(), test_finalize_rejects_artifact_with_different_bytes(), test_prepare_rejects_release_change_after_qa_code_sha(), test_prepare_rejects_unsuccessful_provider_workflow() (+10 more)

### Community 173 - "Community 173"
Cohesion: 0.12
Nodes (6): _bearer_headers(), test_postgres_concurrent_refreshes_recover_the_same_successor(), test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_session_listing_individual_revoke_logout_and_revoke_all(), Real row locks serialize overlapping refreshes without losing the cookie., Real row locks serialize overlapping refreshes without losing the cookie.

### Community 48 - "Community 48"
Cohesion: 0.08
Nodes (18): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _http_request(), _make_reservation(), _make_transaction() (+10 more)

### Community 157 - "Community 157"
Cohesion: 0.14
Nodes (20): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_preserves_explicit_negotiated_nightly_rate(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price() (+12 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (25): _make_reservation(), _pay_deposit(), _pay_full(), TestPaymentGateDepositPaid, TestPaymentGatePending, TestConfigFlag, TestCheckoutGate, Create a PENDING reservation using the first available category. (+17 more)

### Community 291 - "Community 291"
Cohesion: 0.17
Nodes (7): TestGuestValidationGates, Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest who has NOT accepted terms is blocked (terms_accepted=False)., When require_document_for_checkin=False, missing document is not an error., When require_terms_acceptance=False, missing terms is not an error.

### Community 381 - "Community 381"
Cohesion: 0.39
Nodes (8): opened_cash_register(), _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains(), Tests for v72 check-out balance reconciliation., Checkout balance scenarios collect cash through an open caja.

### Community 231 - "Community 231"
Cohesion: 0.42
Nodes (12): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+4 more)

### Community 498 - "Community 498"
Cohesion: 0.33
Nodes (2): TestResolveRateCalendar, V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai

### Community 348 - "Community 348"
Cohesion: 0.22
Nodes (6): _make_period(), TestPricePeriodOverlap, DailyRate explicit row takes priority over an active PricePeriod., When two PricePeriods overlap, the one with higher priority is returned., Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics).

### Community 195 - "Community 195"
Cohesion: 0.12
Nodes (9): TestGetPriceForDate, Tier-1: explicit DailyRate row wins over everything else., Tier-2: active PricePeriod used when no DailyRate exists., An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used. (+1 more)

### Community 292 - "Community 292"
Cohesion: 0.17
Nodes (6): TestApplyPricePeriod, apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price.

### Community 382 - "Community 382"
Cohesion: 0.22
Nodes (5): TestDailyRateModelConstraints, Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss.

### Community 455 - "Community 455"
Cohesion: 0.29
Nodes (4): TestPricePeriodModel, PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on

### Community 317 - "Community 317"
Cohesion: 0.35
Nodes (10): opened_cash_register(), _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_extension_card_payment_with_pos_reference_is_completed_and_audited(), test_extension_manual_card_payment_requires_reference_before_mutating_stay() (+2 more)

### Community 134 - "Community 134"
Cohesion: 0.12
Nodes (13): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_reservation_is_motor_protected_set_on_manual_move(), test_reservation_edit_room_change_protects_manual_assignment(), test_reservation_is_wait_listed_field() (+5 more)

### Community 232 - "Community 232"
Cohesion: 0.20
Nodes (13): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_terminal_reservation_allows_only_arrival_metadata_and_audits_values(), test_update_mobility_restriction_triggers_reoptimization(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_room_move_allows_receptionist_within_the_same_category() (+5 more)

### Community 196 - "Community 196"
Cohesion: 0.22
Nodes (15): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_receptionist_can_list_movement_groups_but_cannot_revert_them(), test_housekeeping_cannot_list_read_or_revert_movement_groups(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_refuses_original_room_with_insufficient_capacity() (+7 more)

### Community 349 - "Community 349"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 185 - "Community 185"
Cohesion: 0.11
Nodes (11): TestReoptimizationTrigger, TestReoptimizationIntegration, V72 §5.2 — Reoptimización continua del motor de asignación.  After each new rese, §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — Integration: after new booking, allocation engine receives correct args. (+3 more)

### Community 581 - "Community 581"
Cohesion: 0.50
Nodes (3): tiny_hotel(), Tests for V72 §9 — Waitlist and Overbooking.  Key implementation details discove, Hotel with one Standard room.  Returns a dict with keys:       config, category_

### Community 318 - "Community 318"
Cohesion: 0.24
Nodes (7): _make_reservation(), TestWaitlistListing, Helper — create a reservation through the service layer., Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted)., Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted).

### Community 456 - "Community 456"
Cohesion: 0.29
Nodes (4): TestWaitlistModelFields, The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room., Verify is_wait_listed survives a round-trip through the database.

### Community 412 - "Community 412"
Cohesion: 0.25
Nodes (5): TestOverbookingBlocked, When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., Six physical Twin rooms hold six overlapping stays; the seventh is         rejec

### Community 383 - "Community 383"
Cohesion: 0.22
Nodes (7): TestWaitlistCreation, When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable.

### Community 214 - "Community 214"
Cohesion: 0.16
Nodes (11): TestWaitlistResolveLogic, Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed., Resolving with a room of a different category must be blocked., Resolving with an already-occupied room must be blocked., After resolve, the DB row reflects the updated state., Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed. (+3 more)

### Community 659 - "Community 659"
Cohesion: 0.67
Nodes (2): Trying to resolve with a non-existent room raises ReservationError., Trying to resolve with a non-existent room raises ReservationError.

### Community 293 - "Community 293"
Cohesion: 0.17
Nodes (9): TestWaitlistIsolation, is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati, A normal reservation blocks the room; a waitlisted one does not., is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati (+1 more)

### Community 319 - "Community 319"
Cohesion: 0.29
Nodes (6): _context(), _reserve(), _hotel_today(), test_visibility_window_filters_far_future_and_null_is_unlimited(), test_in_house_guest_remains_visible_when_check_in_predates_window(), Regression tests for tenant-scoped, per-role reservation visibility.

### Community 582 - "Community 582"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation()

### Community 499 - "Community 499"
Cohesion: 0.60
Nodes (5): _request(), test_rejects_oversized_content_length_before_reading_body(), test_rejects_chunked_body_that_exceeds_limit(), test_accepts_body_at_exact_limit(), test_rejects_malformed_content_length()

### Community 542 - "Community 542"
Cohesion: 0.70
Nodes (4): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 413 - "Community 413"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 350 - "Community 350"
Cohesion: 0.53
Nodes (8): _seed_hotel(), _issue_key(), _headers(), _whatsapp_quote(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

### Community 245 - "Community 245"
Cohesion: 0.31
Nodes (12): _signature(), _post(), _message(), _delivery(), test_rejects_a_delivery_whose_signature_does_not_match(), test_ingests_a_signed_inbound_message(), test_one_unusable_message_does_not_discard_the_rest_of_the_batch(), test_tolerates_a_payload_whose_nested_fields_are_not_objects() (+4 more)

## Knowledge Gaps
- **1754 isolated node(s):** `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.` (+1749 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 583`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 584`** (1 nodes): `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 585`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 586`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 587`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 588`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 589`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 590`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 591`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 592`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 593`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 594`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 595`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 596`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 597`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 598`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 599`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 600`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 601`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 602`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 603`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 604`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 605`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 606`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 607`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 608`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 609`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 610`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 611`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 612`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 613`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 614`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 615`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 616`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 617`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 618`** (1 nodes): `Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 619`** (1 nodes): `Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 620`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 621`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 622`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 623`** (1 nodes): `stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 624`** (1 nodes): `add external-effect mode to payment links  Revision ID: 20260812_external_effect`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 625`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 626`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 627`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 628`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 629`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 630`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 631`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 632`** (1 nodes): `Persist short-lived MFA step-up ticket use to prevent cross-worker replay.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 633`** (1 nodes): `Separate payment-proof reading/review from financial reports.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 634`** (1 nodes): `Add a dedicated permission for reverting room-movement groups.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 635`** (1 nodes): `Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 636`** (1 nodes): `Record payment tender separately from reservation balance currency.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 637`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 638`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 639`** (1 nodes): `add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 640`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 641`** (1 nodes): `laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 642`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 643`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 644`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 645`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 646`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 647`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 648`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 649`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 357`** (1 nodes): `CollaborationManager`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 559`** (1 nodes): `Read and resolve the guest room-rejection lifecycle.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 429`** (2 nodes): `_mercadopago_webhook_impl()`, `mercadopago_payment_link_webhook()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 662`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 663`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 664`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 671`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 653`** (1 nodes): `Tenant-scoped custom roles layered over a built-in permission profile.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 654`** (1 nodes): `Persisted staff invitations and their one-time acceptance state.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 179`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 326`** (2 nodes): `_normalize_currency()`, `HotelConfigUpdate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 666`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 364`** (2 nodes): `LocalObjectStorage`, `Stores objects as files under a local directory root.      Generalizes the patte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 215`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 216`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 652`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 668`** (2 nodes): `latestCloseReportKey()`, `useLatestCashCloseReport()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 670`** (2 nodes): `pendingCloseReportsKey()`, `usePendingCashCloseReports()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 669`** (2 nodes): `pendingCashCustodyReportsKey()`, `usePendingCashCustodyReports()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 667`** (2 nodes): `dailySummaryKey()`, `useCashDailySummary()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 650`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 651`** (2 nodes): `validate()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 528`** (1 nodes): `TestGuestValidation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 481`** (1 nodes): `TestCheckIn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 265`** (2 nodes): `FakeTicketRedis`, `collaboration_client()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 483`** (1 nodes): `The marketing site's own origin must not depend on an env var being set.  hotels`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 570`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 380`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 490`** (1 nodes): `Regression coverage for reservation arrival metadata and internal comments.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 494`** (2 nodes): `TestStateTransitions`, `Tests for reservation state machine transitions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 657`** (1 nodes): `Regression guard for a real bug B3.1 uncovered: on a SQLite database built from`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 676`** (2 nodes): `test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured()`, `MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 677`** (2 nodes): `test_validate_runtime_security_ignores_incomplete_optional_integrations()`, `Partial integration env vars should not block production startup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 678`** (2 nodes): `test_validate_runtime_security_rejects_localhost_redirect_when_service_configured()`, `OAuth redirect URIs are only validated when the corresponding service credential`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 679`** (2 nodes): `test_validate_runtime_security_rejects_weak_master_admin_password_in_production()`, `Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 454`** (2 nodes): `_Session`, `test_subscription_session_closes_before_asgi_work()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 498`** (2 nodes): `TestResolveRateCalendar`, `V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 659`** (2 nodes): `Trying to resolve with a non-existent room raises ReservationError.`, `Trying to resolve with a non-existent room raises ReservationError.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 3` to `Community 470`, `Community 198`, `Community 4`, `Community 72`, `Community 33`, `Community 32`, `Community 116`, `Community 66`, `Community 117`, `Community 52`, `Community 11`, `Community 8`, `Community 9`, `Community 6`, `Community 24`, `Community 0`, `Community 234`, `Community 178`, `Community 325`, `Community 60`, `Community 30`, `Community 113`, `Community 19`, `Community 15`, `Community 653`, `Community 80`, `Community 78`, `Community 654`, `Community 93`, `Community 49`, `Community 179`, `Community 65`, `Community 137`, `Community 249`, `Community 12`, `Community 106`, `Community 164`, `Community 138`, `Community 53`, `Community 45`, `Community 139`, `Community 1`, `Community 363`, `Community 115`?**
  _High betweenness centrality (0.100) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 9` to `Community 16`, `Community 6`, `Community 147`, `Community 19`, `Community 113`, `Community 7`, `Community 0`, `Community 3`, `Community 8`, `Community 11`, `Community 24`, `Community 249`, `Community 395`, `Community 138`, `Community 22`, `Community 54`, `Community 49`, `Community 141`, `Community 21`, `Community 53`, `Community 1`, `Community 330`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 6` to `Community 16`, `Community 24`, `Community 9`, `Community 65`, `Community 3`, `Community 0`, `Community 52`, `Community 117`, `Community 8`, `Community 11`, `Community 249`, `Community 255`, `Community 60`, `Community 49`, `Community 137`, `Community 71`, `Community 138`, `Community 21`, `Community 77`, `Community 45`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **Are the 461 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Reservation` has 461 INFERRED edges - model-reasoned connections that need verification._
- **Are the 427 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`HotelConfiguration` has 427 INFERRED edges - model-reasoned connections that need verification._
- **Are the 404 inferred relationships involving `Base` (e.g. with `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` and `Demo-only utilities: seed sample data and reset the database. Exposed only when`) actually correct?**
  _`Base` has 404 INFERRED edges - model-reasoned connections that need verification._
- **Are the 376 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`ReservationStatusEnum` has 376 INFERRED edges - model-reasoned connections that need verification._