# Graph Report - .  (2026-10-27)

## Corpus Check
- Large corpus: 1769 files · ~2,569,251 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 18537 nodes · 74288 edges · 712 communities detected
- Extraction: 52% EXTRACTED · 48% INFERRED · 0% AMBIGUOUS · INFERRED: 35538 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 35538 · contains: 10817 · calls: 8466 · MODIFIES: 6170 · rationale_for: 4867 · ON_BRANCH: 2403 · imports: 1931 · imports_from: 1516 · inherits: 1049 · method: 978 · PARENT_OF: 545 · re_exports: 4 · reads_from: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1769 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 15 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `5a603f6`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 1530 edges
2. `HotelConfiguration` - 1450 edges
3. `ReservationStatusEnum` - 1405 edges
4. `Room` - 1145 edges
5. `RoomCategory` - 935 edges
6. `Company` - 803 edges
7. `Guest` - 776 edges
8. `RoomStatusEnum` - 762 edges
9. `AuditActionEnum` - 760 edges
10. `SecurityAuditLog` - 741 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Introspect the real SQLAlchemy metadata: tables, columns, types, indexes, FKs.` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/schema_audit.py → app/database.py
- `Comprueba tres hallazgos de la lectura completa contra la app real (PostgreSQL m` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/verify_misc_findings.py → app/database.py
- `Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/audit_loss_repro.py → app/database.py
- `Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post` --uses--> `AuditLog`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/audit_loss_repro.py → app/models/audit_log.py

## Communities

### Community 497 - "Community 497"
Cohesion: 0.53
Nodes (5): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (179): hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house, _has_unique_hotel_id_id(), upgrade(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs, Separate historical cash receipts from the active drawer and seed access.  Revis, Add a dedicated permission for recording OTA reservations.  Revision ID: 2026092, Add read access for the privacy-safe housekeeping board.  Revision ID: 20260930_, Separate housekeeping state from room availability.  Revision ID: 20260930_house (+171 more)

### Community 635 - "Community 635"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 443 - "Community 443"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table.

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (155): Publish owner-approved monthly subscription prices.  Revision ID: 11be7c9387c4 R, persist missing linen declared on laundry return slips  Revision ID: 20261005_la, Add request correlation keys to durable realtime events.  Revision ID: 20261007_, Notify active PostgreSQL listeners when durable domain events commit.  Revision, Persist idempotent payment receipt email outcomes.  Revision ID: 20261016_paymen, Add a tenant-isolated SQL queue for reservation fact refreshes., Track neutral supplier follow-up for declared laundry shortages.  Revision ID: 2, Add the corporate channel to the analytics fact enum.  Reservation.channel_code (+147 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (290): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho, Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for, correct_payment_transaction(), _reservation_status_label_es(), get_reservation(), rebook_ota_to_direct(), preview_ota_rebook_to_direct(), entry (+282 more)

### Community 636 - "Community 636"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 637 - "Community 637"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 589 - "Community 589"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 638 - "Community 638"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 639 - "Community 639"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 640 - "Community 640"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 641 - "Community 641"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 642 - "Community 642"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 643 - "Community 643"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 644 - "Community 644"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 645 - "Community 645"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 483 - "Community 483"
Cohesion: 0.48
Nodes (5): _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260

### Community 590 - "Community 590"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 646 - "Community 646"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 647 - "Community 647"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 648 - "Community 648"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 649 - "Community 649"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 650 - "Community 650"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (291): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event, _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re, Add transactions.created_by_user_id for payment audit trail.  Transaction had cr (+283 more)

### Community 525 - "Community 525"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 651 - "Community 651"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 652 - "Community 652"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 653 - "Community 653"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 654 - "Community 654"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 655 - "Community 655"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 656 - "Community 656"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 657 - "Community 657"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 658 - "Community 658"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 659 - "Community 659"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 660 - "Community 660"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 661 - "Community 661"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 662 - "Community 662"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 663 - "Community 663"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 664 - "Community 664"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 665 - "Community 665"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 444 - "Community 444"
Cohesion: 0.46
Nodes (7): _sqlite_rebuild_constraints(), _repair_sqlite(), _existing_enum_labels(), _rename_postgres_enum_values(), upgrade(), downgrade(), Align allocation enum storage with the model values.  The original allocation mi

### Community 484 - "Community 484"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat

### Community 526 - "Community 526"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), _drop_successor_reference(), upgrade(), downgrade(), Add zero-balance cash rotation and custody handoffs.

### Community 527 - "Community 527"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio

### Community 528 - "Community 528"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Complete tenant-leading foreign keys outside the core booking domain.  The core

### Community 666 - "Community 666"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 667 - "Community 667"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 485 - "Community 485"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all

### Community 445 - "Community 445"
Cohesion: 0.36
Nodes (6): _has_unique(), _has_fk(), _add_constraint_if_missing(), upgrade(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in

### Community 591 - "Community 591"
Cohesion: 0.60
Nodes (4): _constraint(), upgrade(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could

### Community 668 - "Community 668"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 376 - "Community 376"
Cohesion: 0.31
Nodes (9): upgrade(), _create_linen_tables(), _migrate_linen_data(), _finalize_laundry_vendor_columns(), _drop_kind_column(), downgrade(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li (+1 more)

### Community 669 - "Community 669"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (222): add external-effect mode to payment links  Revision ID: 20260812_external_effect, Staff management endpoints for hotel public API keys., _mercadopago_webhook_impl(), mercadopago_payment_link_webhook(), Public WhatsApp bot hooks authenticated only by hotel API key., Settings, BaseSettings, get_settings() (+214 more)

### Community 283 - "Community 283"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), _install_rls(), _remove_rls(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), upgrade(), downgrade(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill (+5 more)

### Community 297 - "Community 297"
Cohesion: 0.24
Nodes (12): _insert_permission_rows(), _upsert_default(), _backfill_defaults(), _copy_role_overrides(), upgrade(), _install_user_override_rls(), _remove_user_override_rls(), _contract_legacy_rows() (+4 more)

### Community 446 - "Community 446"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 447 - "Community 447"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table.

### Community 670 - "Community 670"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 448 - "Community 448"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state.

### Community 671 - "Community 671"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 592 - "Community 592"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), upgrade(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima

### Community 672 - "Community 672"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 673 - "Community 673"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 674 - "Community 674"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 675 - "Community 675"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 486 - "Community 486"
Cohesion: 0.52
Nodes (6): _columns(), _decode(), _backfill_authoritative_values(), upgrade(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea

### Community 529 - "Community 529"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), seed section visibility permissions and their role defaults  Revision ID: 202608

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (205): store public marketing inquiries and notification state  Revision ID: 20260828_p, add public marketing pricing plans and early-access leads  Revision ID: 20260910, Public contact form endpoint for the marketing site., _request_source(), create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, MARKETING_ROUTES, replaceTag() (+197 more)

### Community 487 - "Community 487"
Cohesion: 0.57
Nodes (6): _index_map(), _ensure_index(), _drop_index_if_present(), upgrade(), downgrade(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar

### Community 530 - "Community 530"
Cohesion: 0.60
Nodes (5): _has_table(), _has_column(), upgrade(), downgrade(), Fold legacy category pricing into seasonal price periods.

### Community 531 - "Community 531"
Cohesion: 0.60
Nodes (5): _set_role_default(), _restore_session_permission(), upgrade(), downgrade(), Align section defaults and remove the self-session catalog permission.  Revision

### Community 676 - "Community 676"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 377 - "Community 377"
Cohesion: 0.29
Nodes (9): _install_rls(), _remove_rls(), _insert_permission_rows(), _insert_default_rows(), upgrade(), downgrade(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects. (+1 more)

### Community 532 - "Community 532"
Cohesion: 0.47
Nodes (5): _set_role_default(), upgrade(), downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns.

### Community 533 - "Community 533"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083

### Community 15 - "Community 15"
Cohesion: 0.01
Nodes (131): _install_rls(), _remove_rls(), upgrade(), downgrade(), add durable realtime domain event outbox  Revision ID: 20260901_domain_event_out, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _has_column() (+123 more)

### Community 406 - "Community 406"
Cohesion: 0.42
Nodes (8): _columns(), _indexes(), _create_index_if_missing(), _drop_index_if_present(), _seed_audit_permission(), upgrade(), downgrade(), Operational audit fields, daily cash indexes, and audit read permission.

### Community 488 - "Community 488"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op

### Community 489 - "Community 489"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat

### Community 490 - "Community 490"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what

### Community 593 - "Community 593"
Cohesion: 0.50
Nodes (3): _columns(), upgrade(), Add hotel-scoped staff aliases and password-login capability state.  Revision ID

### Community 677 - "Community 677"
Cohesion: 0.50
Nodes (1): Persist short-lived MFA step-up ticket use to prevent cross-worker replay.

### Community 449 - "Community 449"
Cohesion: 0.36
Nodes (7): _install_rls(), _remove_rls(), _assert_downgrade_lossless(), upgrade(), downgrade(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins.

### Community 491 - "Community 491"
Cohesion: 0.48
Nodes (6): _enum_labels(), _quote_identifier(), _rename_enum_labels(), upgrade(), downgrade(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:

### Community 12 - "Community 12"
Cohesion: 0.04
Nodes (222): _pg_cron_migration_enabled(), _secure_marketing_leads(), upgrade(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role., Restrict direct execution of the Supabase RLS DDL event trigger.  Revision ID: 2, Add an index for tenant-scoped outbox cursor recovery polling.  Revision ID: 202, Demo-only utilities: seed sample data and reset the database. Exposed only when (+214 more)

### Community 378 - "Community 378"
Cohesion: 0.40
Nodes (9): _cron_is_required(), _create_and_secure_retention_holds(), _upgrade_sqlite(), _downgrade_sqlite(), _install_purge_function(), _reschedule_purge_job(), upgrade(), downgrade() (+1 more)

### Community 534 - "Community 534"
Cohesion: 0.53
Nodes (5): _has_columns(), _indexes(), upgrade(), downgrade(), Add check-in policy, manual receipt references, and auditable refunds.

### Community 407 - "Community 407"
Cohesion: 0.50
Nodes (8): _has_columns(), _set_global_role_defaults(), _set_manager_operational_defaults(), _set_housekeeping_whatsapp_defaults(), _backfill_external_ota_credits(), upgrade(), downgrade(), Backfill legacy OTA credits and operational role defaults.  This data migration

### Community 678 - "Community 678"
Cohesion: 0.50
Nodes (1): Separate payment-proof reading/review from financial reports.  Revision ID: 2026

### Community 679 - "Community 679"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reverting room-movement groups.  Revision ID: 202

### Community 594 - "Community 594"
Cohesion: 0.60
Nodes (4): _install_purge_function(), upgrade(), downgrade(), Backfill the public inquiry retention clock and update the purge function.  Revi

### Community 680 - "Community 680"
Cohesion: 0.50
Nodes (1): Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026

### Community 535 - "Community 535"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), Add tenant-scoped groups for multi-room reservations.

### Community 492 - "Community 492"
Cohesion: 0.43
Nodes (5): _has_unique(), _has_fk(), _enable_tenant_rls(), upgrade(), Harden company nightly charge tenant keys and row level security.

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (216): Store hotel FX market preferences and conversion provenance.  Revision ID: 20261, Add separately guarded, MFA-protected manual cash adjustments.  Revision ID: 202, _enable_tenant_rls(), _disable_tenant_rls(), _disable_silent_rls_filtering(), upgrade(), downgrade(), Add effective-dated company extra-person rates and audited charge corrections. (+208 more)

### Community 681 - "Community 681"
Cohesion: 0.50
Nodes (1): Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv

### Community 682 - "Community 682"
Cohesion: 0.50
Nodes (1): Configure official or blue USD quotes by conversion direction.  Revision ID: 202

### Community 536 - "Community 536"
Cohesion: 0.47
Nodes (4): _existing_table_matches(), _install_tenant_rls(), upgrade(), Persist the local synthetic hotel business date.  Revision ID: 20261017_local_bu

### Community 683 - "Community 683"
Cohesion: 0.50
Nodes (1): Store external OTA payment amounts in their source currency.  Revision ID: 20261

### Community 684 - "Community 684"
Cohesion: 0.50
Nodes (1): Record FX rounding credit and manual credit refunds separately.  Revision ID: 20

### Community 685 - "Community 685"
Cohesion: 0.50
Nodes (1): Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_

### Community 686 - "Community 686"
Cohesion: 0.50
Nodes (1): Track Mercado Pago checkout revocation separately from local cancellation.  Revi

### Community 537 - "Community 537"
Cohesion: 0.47
Nodes (4): _add_transaction_columns_and_check(), _add_group_batch_columns_and_check(), upgrade(), Persist cash received, change, and explicitly retained tip separately.  Revision

### Community 595 - "Community 595"
Cohesion: 0.50
Nodes (3): _enable_tenant_rls(), upgrade(), Persist fixed post-checkout housekeeping checklists.  Revision ID: 20261023_hous

### Community 351 - "Community 351"
Cohesion: 0.31
Nodes (10): _manual_reference_index_exists(), _assert_manual_reference_keys_unique(), _replace_manual_reference_index(), _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Add auditable, idempotent payment corrections.  Revision ID: 20261024_atomic_pay (+2 more)

### Community 687 - "Community 687"
Cohesion: 0.50
Nodes (1): Track auditable voids for open-session cash corrections.  Revision ID: 20261024_

### Community 688 - "Community 688"
Cohesion: 0.50
Nodes (1): Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:

### Community 689 - "Community 689"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reading company vouchers and signatures.  Revisio

### Community 538 - "Community 538"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Snapshot corporate terms per reservation and audit manager review.  Revision ID:

### Community 493 - "Community 493"
Cohesion: 0.43
Nodes (6): _install_tenant_rls(), _remove_tenant_rls(), _status_check(), upgrade(), downgrade(), Add tenant-scoped per-guest arrival records and hotel status policy.  Revision I

### Community 539 - "Community 539"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Track laundry remito discrepancies and explicit linen retirements.  Revision ID:

### Community 540 - "Community 540"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Add audited cancellation review queue and approval permission.  Revision ID: 202

### Community 541 - "Community 541"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Persist general stock counts and require audited approval before adjustment.  Re

### Community 26 - "Community 26"
Cohesion: 0.04
Nodes (88): Add the keyset pagination index for WhatsApp message history.  Revision ID: 2026, _require_plan(), _conversation_access_scope(), channel_status(), complete_channel(), inbox(), conversation_messages(), send_message() (+80 more)

### Community 690 - "Community 690"
Cohesion: 0.50
Nodes (1): Add elevator knowledge and soft allocation preferences by room.  Revision ID: 20

### Community 542 - "Community 542"
Cohesion: 0.47
Nodes (5): _install_history_rls(), _remove_history_rls(), upgrade(), downgrade(), Store comparable published-rate history and pilot recommendation settings.  Revi

### Community 450 - "Community 450"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table.

### Community 543 - "Community 543"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), linen location par levels  Revision ID: 41d66acfb13a Revises: 015f7e36b9cd Creat

### Community 691 - "Community 691"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 692 - "Community 692"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 596 - "Community 596"
Cohesion: 0.60
Nodes (4): _check_clause(), upgrade(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in

### Community 36 - "Community 36"
Cohesion: 0.04
Nodes (51): add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op, APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote (+43 more)

### Community 693 - "Community 693"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 451 - "Community 451"
Cohesion: 0.46
Nodes (7): _user_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _alter_user_column(), upgrade(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2

### Community 452 - "Community 452"
Cohesion: 0.46
Nodes (7): _hotel_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _replace_fk(), upgrade(), downgrade(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs.

### Community 694 - "Community 694"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 695 - "Community 695"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 696 - "Community 696"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 697 - "Community 697"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 698 - "Community 698"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 699 - "Community 699"
Cohesion: 0.50
Nodes (1): track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca

### Community 700 - "Community 700"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 701 - "Community 701"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 408 - "Community 408"
Cohesion: 0.33
Nodes (8): _install_rls(), _remove_rls(), _assert_no_duplicate_remitos(), _guard_day2_downgrade_data(), upgrade(), downgrade(), Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, a, Refuse rollback when it would discard operational data or session state.

### Community 597 - "Community 597"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 544 - "Community 544"
Cohesion: 0.47
Nodes (4): _utcnow(), _seed_ota_providers(), upgrade(), ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l

### Community 453 - "Community 453"
Cohesion: 0.39
Nodes (7): _has_unique(), _ensure_subscription_composite_target(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b

### Community 702 - "Community 702"
Cohesion: 0.50
Nodes (1): reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202

### Community 703 - "Community 703"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 545 - "Community 545"
Cohesion: 0.60
Nodes (5): _policy_name(), _quoted_table(), upgrade(), downgrade(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL

### Community 494 - "Community 494"
Cohesion: 0.43
Nodes (6): _event_id_type(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i

### Community 598 - "Community 598"
Cohesion: 0.50
Nodes (3): _rls(), upgrade(), Add durable job dedupe and worker heartbeat metadata.

### Community 21 - "Community 21"
Cohesion: 0.02
Nodes (74): _DecimalAwareEncoder, _is_database_pool_timeout(), security_headers(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., test_housekeeping_cannot_checkout_reservation(), POST /api/checkin/checkout only enforced authentication (get_auth_context),, _open_session(), test_adjustment_denied_without_grant_while_income_stays_available() (+66 more)

### Community 186 - "Community 186"
Cohesion: 0.10
Nodes (8): CacheStore, Protocol, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, AnalyticsAIProvider, RenderRequester, JsonGetter

### Community 83 - "Community 83"
Cohesion: 0.08
Nodes (31): JobSpec, JobDispatcher, CeleryJobDispatcher, dispatch_once(), Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica, Base, SellableProduct (+23 more)

### Community 298 - "Community 298"
Cohesion: 0.20
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process fields delivered by a Mercado Pago callback without querying         the

### Community 270 - "Community 270"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 100 - "Community 100"
Cohesion: 0.14
Nodes (27): SimpleRateLimiter, MasterAdminSession, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings, _normalize_audit_metadata_key() (+19 more)

### Community 454 - "Community 454"
Cohesion: 0.29
Nodes (3): Telemetry, LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default.

### Community 194 - "Community 194"
Cohesion: 0.19
Nodes (18): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+10 more)

### Community 127 - "Community 127"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_png(), export_analytics_csv(), export_analytics_xlsx()

### Community 20 - "Community 20"
Cohesion: 0.03
Nodes (134): _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _attach_user_session_cookies(), _audit_security_event(), _issue_auth_response(), _build_login_response() (+126 more)

### Community 227 - "Community 227"
Cohesion: 0.22
Nodes (16): _booking_status_label_es(), _require_demo_mode(), _ensure_subscription_active(), _ensure_permission_tier(), _is_manager_context(), _booking_to_read(), _project_booking_graph(), list_bookings() (+8 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (396): availability(), price_quote(), seed_demo_bookings(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses the ca, Quickly seed demo bookings (requires DEMO_MODE=true). (+388 more)

### Community 143 - "Community 143"
Cohesion: 0.12
Nodes (19): _close_report_read(), _cash_expense_read(), _csv_local_datetime(), _csv_local_date(), _csv_decimal(), export_cash_ledger_csv(), latest_cash_close_report(), pending_cash_close_reports() (+11 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (342): _require_cash_difference_approval_when_requested(), Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., CashExpenseStatusEnum, CashExpense, A proposed drawer expense; approved expenses create one cash movement., NotificationSeverityEnum, NotificationChannelEnum (+334 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (194): CheckInRequest, FastAPI routes for Check-in / Check-out., B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir (+186 more)

### Community 13 - "Community 13"
Cohesion: 0.01
Nodes (190): BaseModel, AllocationPolicyVersionCreate, AllocationPolicyVersionRead, ActiveAllocationPolicyRead, AllocationPolicySuggestionCreate, AllocationPolicySuggestionRead, AllocationPolicySuggestionReviewRequest, AllocationPolicySuggestionApplyRequest (+182 more)

### Community 23 - "Community 23"
Cohesion: 0.02
Nodes (83): _ticket_key(), _store_process_ticket(), _require_permission(), _realtime_client_or_503(), create_collaboration_ticket(), _patch_conflict_response(), patch_collaborative_resource(), _consume_ticket() (+75 more)

### Community 19 - "Community 19"
Cohesion: 0.04
Nodes (157): _require_resource_lane(), Keep collaboration permissions aligned with the normal resource API., _until_disconnect(), _build_authorization_check(), recover_domain_events(), stream_domain_events(), Adapt sync and async streams to ASGI disconnects and always close them., Revalidate stream access while tolerating a brief database pool outage.      The (+149 more)

### Community 324 - "Community 324"
Cohesion: 0.33
Nodes (3): CollaborationManager, Process-local peers plus best-effort Redis pub/sub fan-out., Process-local peers plus best-effort Redis pub/sub fan-out.

### Community 18 - "Community 18"
Cohesion: 0.02
Nodes (132): FastAPI routes for the commercial configuration domain., FastAPI routes for Hotel Configuration (Admin Panel)., ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, IssueHotelApiKeyPayload, listApiKeys(), issueApiKey() (+124 more)

### Community 51 - "Community 51"
Cohesion: 0.06
Nodes (48): get_company_hotel_currency(), Company, CompanyPayload, CompanyOption, CompanyHotelCurrency, CompanyNightlyRate, CompanyNightlyRatesResponse, CompanyNightlyRatePayload (+40 more)

### Community 45 - "Community 45"
Cohesion: 0.13
Nodes (60): CompanyOptionRead, get_company_options(), Return only the hotel's configured currency for company screens., Return only the names needed to link a reservation to a company., str, AnalyticsCurrencyDisplayEnum, AnalyticsAlertSetting, AnalyticsAlertSnooze (+52 more)

### Community 325 - "Community 325"
Cohesion: 0.22
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 301 - "Community 301"
Cohesion: 0.24
Nodes (8): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (438): _reject_direct_rate_write(), DailyRateOut, Config, DailyRateFallbackOut, PaymentMethodOptionsOut, DailyRateIn, BulkRateIn, BulkFieldRateIn (+430 more)

### Community 17 - "Community 17"
Cohesion: 0.02
Nodes (159): _require_demo_mode(), seed_demo(), reset_demo(), Guard demo mutations behind both an approved runtime and an explicit flag., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Base, DeclarativeBase (+151 more)

### Community 284 - "Community 284"
Cohesion: 0.19
Nodes (8): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, EmailSendResponse, EmailVerifyResponse, SmtpStatus

### Community 381 - "Community 381"
Cohesion: 0.33
Nodes (7): FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, get_all_rates(), get_usd_oficial_rate(), get_single_rate(), create_fx_snapshot()

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (358): FxSnapshotRead, FxConversionQuoteRequest, FxConversionQuoteRead, get_conversion_quote(), Return the configured official/blue conversion for any supported pair., revenue_report(), booked_value_report(), export_revenue_report_csv() (+350 more)

### Community 214 - "Community 214"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (49): _restriction_error_detail(), _get_tenant_guest(), list_active_restriction_guest_ids(), create_restriction(), list_restrictions(), resolve_restriction(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of (+41 more)

### Community 40 - "Community 40"
Cohesion: 0.04
Nodes (61): _guest_service_error_detail(), _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), get_guest_quick_profile(), get_guest_tags(), create_guest_tag(), resolve_tag() (+53 more)

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (34): add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest., DocumentTypeEnum, GuestCompanion, Companion/additional occupant traveling with a primary guest.     Hotels often n, GuestCompanionBase, GuestCompanionCreate (+26 more)

### Community 52 - "Community 52"
Cohesion: 0.06
Nodes (52): _database_healthcheck(), _postgres_healthcheck(), _redis_healthcheck(), _critical_lock_readiness(), live_healthcheck(), ready_healthcheck(), _clickhouse_healthcheck(), datastores_healthcheck() (+44 more)

### Community 89 - "Community 89"
Cohesion: 0.15
Nodes (33): get_housekeeping_checklists(), complete_housekeeping_checklist_item(), Tenant-scoped API for fixed post-checkout housekeeping checklists., List open checklists for the caller's hotel without guest data., Complete one fixed item; all PostgreSQL state changes commit together., HousekeepingChecklistStatusEnum, HousekeepingChecklistItemCodeEnum, HousekeepingChecklist (+25 more)

### Community 78 - "Community 78"
Cohesion: 0.08
Nodes (39): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _reject_generic_whatsapp_mutation(), _store_oauth_code() (+31 more)

### Community 165 - "Community 165"
Cohesion: 0.20
Nodes (23): _source_key(), _available_invitation(), _activate_invitation_for_user(), _raise_preview_error(), get_invitation_preview(), _pending_invitation_claim(), _build_invitation_mfa_challenge(), _audit_invitation_mfa_challenge() (+15 more)

### Community 122 - "Community 122"
Cohesion: 0.09
Nodes (18): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (56): VendorCreate, VendorUpdate, VendorRead, VendorPriceUpsert, VendorPriceRead, RemitoLineIn, RemitoCreate, RemitoLineRead (+48 more)

### Community 353 - "Community 353"
Cohesion: 0.38
Nodes (9): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+1 more)

### Community 31 - "Community 31"
Cohesion: 0.04
Nodes (65): _schedule_to_read(), get_daily_report_schedule(), update_daily_report_schedule(), FastAPI routes for the notification backend: inbox, push subscriptions, preferen, NotificationSeverity, NotificationItem, NotificationListResponse, listNotifications() (+57 more)

### Community 35 - "Community 35"
Cohesion: 0.03
Nodes (40): FastAPI routes for the onboarding flow used by smoke tests., DepositPolicyRule, DepositPolicyRules, OnboardingProviderSetup, OnboardingStatus, OnboardingSubscription, OwnerPayload, HotelIdentityPayload (+32 more)

### Community 38 - "Community 38"
Cohesion: 0.08
Nodes (68): _can(), _is_operator_scoped(), _can_read_reservation_context(), _report_type_allowed(), _conflict(), get_operational_tasks(), create_operational_task(), patch_operational_task() (+60 more)

### Community 152 - "Community 152"
Cohesion: 0.23
Nodes (24): _log_ota_processing_failure(), _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), _guarded_json_payload(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com. (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (364): PaymentSurchargeCreate, PaymentReceiptEmailRequest, payment_receipt_data(), download_payment_receipt_pdf(), email_payment_receipt(), FastAPI routes for Payments., A hotel operator explicitly enters the destination for this receipt., Reverse a mistaken ledger entry and optionally reassign its payment. (+356 more)

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (97): _temporary_grant_actor(), _temporary_grant_response(), _raise_temporary_grant_http_error(), _validate_role(), _validate_code(), _assert_role_profile_mutation_allowed(), _target_membership_or_404(), _assert_manageable_membership() (+89 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (82): consume_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Keep ownership-role cells immutable except the owner's explicit rate control., Keep permission exceptions aligned with the staff-management boundary., Apply a user-reviewed set of permission changes atomically with one MFA ticket., Ask for one exceptional permission without changing the requester's role., Retired: grants are consumed only inside their protected action., Permission (+74 more)

### Community 72 - "Community 72"
Cohesion: 0.06
Nodes (33): update_promotion(), simulate_promotion_pricing(), Promotions API (v72 mobile-first pricing/promotions task).  CRUD for versioned,, Creates a new immutable version; the previous version is deactivated.     Reserv, Return which promotions would apply and the resulting price breakdown     for a, PromotionBenefitType, PromotionScope, PromotionConditions (+25 more)

### Community 354 - "Community 354"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status()

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (93): Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by id (v72 §16).      Scoped to the API key, ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum, BillingAdjustmentTypeEnum, ReservationAdjustment (+85 more)

### Community 22 - "Community 22"
Cohesion: 0.02
Nodes (104): TariffRecommendationSettings, TariffRecommendationSettingsOut, TariffRecommendationRunIn, TariffRecommendationRunOut, _settings_out(), read_settings(), update_settings(), generate_recommendation() (+96 more)

### Community 81 - "Community 81"
Cohesion: 0.12
Nodes (38): RateChangeItemIn, RateChangeDraftIn, RateChangeDecisionIn, RateChangeDraftEditIn, RateChangeDraftOut, _raise_draft_http(), _safe_rollback(), create_draft() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (44): _safe_csv_cell(), OperationalReservationSummary, OperationalReservationGroup, ArrivalCount, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead, OperationalAlert (+36 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (208): RoleCatalogItem, RoleListResponse, RoleResponse, CreateCustomRoleRequest, RenameCustomRoleRequest, ArchiveCustomRoleRequest, _role_item(), _rollback_and_raise() (+200 more)

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (58): _serialize_allocation_run_details(), _json_dict(), RoomBlockCreate, RoomBlockRead, RoomBlockConflictPreview, RoomBlockAllocationPreviewRead, RoomBlockExtensionConflictPreview, RoomBlockExtensionInput (+50 more)

### Community 355 - "Community 355"
Cohesion: 0.36
Nodes (9): _current_user(), _safe_resource_id(), _validate_audit_timeline_range(), _build_audit_timeline_csv(), _attach_actor_names(), security_overview(), recent_security_events(), audit_timeline() (+1 more)

### Community 42 - "Community 42"
Cohesion: 0.04
Nodes (39): _ensure_adjustment_permission(), StockItemUpdate, StockCountLineRead, create_movement(), _stock_count_line_read(), _stock_count_session_detail(), get_stock_count_session_detail(), record_stock_count_line() (+31 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (42): StockItemCreate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementCreate, StockMovementRead, StockTransferCreate, StockTransferRead (+34 more)

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (29): _remaining_trial_days(), _require_master_admin_write(), _master_admin_hotel_id(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial(), upsert_entitlement_override() (+21 more)

### Community 95 - "Community 95"
Cohesion: 0.10
Nodes (33): _assert_assignable_role(), _assert_manageable_membership(), _assert_manageable_role(), _membership_user_info(), _membership_for_invitation(), list_users(), InviteResponse, _send_invitation_email() (+25 more)

### Community 153 - "Community 153"
Cohesion: 0.10
Nodes (15): API routes for reservation waitlist operations., WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload, WaitlistPromoteResponse, WaitlistPromotionSuggestion, listWaitlistEntries() (+7 more)

### Community 101 - "Community 101"
Cohesion: 0.06
Nodes (34): _record_pool_checkout(), _RequestTelemetryQueuePool, QueuePool, _install_slow_query_listener(), get_engine(), _render_server_default(), _column_fill_value(), _backfill_not_null_nulls() (+26 more)

### Community 713 - "Community 713"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 714 - "Community 714"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 76 - "Community 76"
Cohesion: 0.07
Nodes (38): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change() (+30 more)

### Community 715 - "Community 715"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 196 - "Community 196"
Cohesion: 0.20
Nodes (17): AuthContext, _parse_header_hotel_id(), _parse_token_hotel_id(), _decode_authorization_header(), _authenticate_user(), _resolve_membership(), get_auth_context(), _action_step_up_tickets() (+9 more)

### Community 271 - "Community 271"
Cohesion: 0.18
Nodes (13): redis_namespace(), namespaced_key(), _client_signature(), get_sync_redis_client(), get_async_redis_client(), reset_clients(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Return a process-local sync client, or None for empty configuration.      The op (+5 more)

### Community 546 - "Community 546"
Cohesion: 0.40
Nodes (3): ResponseBodySizeTelemetryMiddleware, Count response bytes after compression without buffering body content., Count response bytes after compression without buffering body content.

### Community 195 - "Community 195"
Cohesion: 0.10
Nodes (20): _seed_permission_matrix_once(), lifespan(), _consume_xlsx_export_queue(), Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Generate queued XLSX reports one at a time to bound local resource use., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup. (+12 more)

### Community 410 - "Community 410"
Cohesion: 0.25
Nodes (7): _InvitationAccessLogFilter, Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs.

### Community 238 - "Community 238"
Cohesion: 0.13
Nodes (16): _safe_request_path_for_logging(), request_telemetry(), Hide invitation/OTA capabilities from application logs., Emit bounded HTTP timing fields and make correlation IDs observable., Hide invitation/OTA capabilities from application logs., Emit bounded HTTP timing fields and make correlation IDs observable., Hide invitation/OTA capabilities from application logs., Emit bounded HTTP timing fields and make correlation IDs observable. (+8 more)

### Community 326 - "Community 326"
Cohesion: 0.18
Nodes (10): SafeStaticFiles, StaticFiles, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on (+2 more)

### Community 154 - "Community 154"
Cohesion: 0.08
Nodes (26): _frontend_placeholder(), serve_frontend(), serve_spa(), Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin (+18 more)

### Community 718 - "Community 718"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 414 - "Community 414"
Cohesion: 0.50
Nodes (7): _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 145 - "Community 145"
Cohesion: 0.26
Nodes (26): BillingDecision, MasterStripeWebhookEvent, put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi, MasterAdminLoginRequest, MasterAdminMfaLoginRequest, MasterAdminMfaEnrollRequest, MasterAdminMfaCodeRequest (+18 more)

### Community 64 - "Community 64"
Cohesion: 0.14
Nodes (47): RuntimeError, NotificationOutboxStatusEnum, Notification, PushSubscription, NotificationPreference, NotificationOutbox, DailyReportSchedule, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+39 more)

### Community 116 - "Community 116"
Cohesion: 0.13
Nodes (24): PrivacyRetentionHold, Current legal-retention exception for one public lead or inquiry.      Changes a, _validate_case_reference(), RetentionHoldCreate, RetentionHoldRelease, RetentionTargetSearch, RetentionHoldRead, RetentionTargetRead (+16 more)

### Community 108 - "Community 108"
Cohesion: 0.14
Nodes (31): MasterAdminContext, _now(), _as_aware(), _hash_value(), _normalize_identifier(), _normalize_pin(), _normalize_http_origin(), _require_master_admin_origin() (+23 more)

### Community 328 - "Community 328"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 146 - "Community 146"
Cohesion: 0.10
Nodes (25): ActionStepUpTicketUse, Tenant-scoped replay ledger for MFA step-up tickets., Persist only the random ticket id and action binding after first use., permissions_requiring_step_up(), permission_requires_step_up(), create_action_step_up_ticket(), is_permission_admin_read_action(), create_permission_admin_read_step_up_ticket() (+17 more)

### Community 228 - "Community 228"
Cohesion: 0.25
Nodes (14): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., GemmaIntent, classify_gemma_intent() (+6 more)

### Community 123 - "Community 123"
Cohesion: 0.16
Nodes (24): LLMPolicySuggestionStatusEnum, ManualOverrideReason, LLMPolicySuggestion, LLMFeedbackEvent, Allocation, solver and LLM policy models.  The deterministic solver remains the, AllocationQuestionnaireDraft, AllocationFeedbackDraft, draft_policy_from_questionnaire() (+16 more)

### Community 47 - "Community 47"
Cohesion: 0.19
Nodes (67): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, AllocationExplanation, SolverMetric (+59 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (94): AnalyticsExportFormatEnum, AnalyticsExportStatusEnum, AnalyticsExportJob, StoredObjectStatusEnum, AnalyticsExportRequest, AnalyticsExportJobRead, _xml_10_text(), _iter_csv_chunks() (+86 more)

### Community 257 - "Community 257"
Cohesion: 0.34
Nodes (15): FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum, ReservationGuestSegmentSourceEnum, ComparisonWindow, ComparisonState, MonetaryTotals, ReservationNightFactDraft, RoomOccupancyNightFactDraft (+7 more)

### Community 59 - "Community 59"
Cohesion: 0.06
Nodes (52): HotelBusinessClock, Persist the latest simulated business date for a single hotel.      The row is i, advance_business_clock(), Business-date read and controlled one-day advancement for local simulation., Advance exactly one business day and append a real-time audit event.      SQLite, get_country_catalog(), get_timezone_catalog(), is_valid_timezone() (+44 more)

### Community 229 - "Community 229"
Cohesion: 0.18
Nodes (17): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., QueuedDomainChange, queue_domain_change(), discard_queued_domain_changes(), _session_transaction_id(), get_domain_event_outbox_metrics(), A safe invalidation signal waiting for the surrounding DB commit. (+9 more)

### Community 60 - "Community 60"
Cohesion: 0.07
Nodes (47): LaundryRemitoDiscrepancy, LaundryDiscrepancyAction, Auditable custody records for linen differences reported on laundry remitos.  Di, Immutable action history and hotel-scoped idempotency for discrepancy decisions., is_duplicate_remito_integrity_error(), create_vendor(), get_vendor(), set_vendor_price() (+39 more)

### Community 499 - "Community 499"
Cohesion: 0.33
Nodes (5): LaundryVendor, LaundryVendorPrice, LaundryRemito, LaundryRemitoLine, Laundry vendor, pricing and remito (delivery note) models.  An outsourced laundr

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (54): LinenItem, LinenLocation, LinenMovement, LinenParLevel, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Configured minimum quantity for one linen item at one hotel location., Raised when an operational follow-up cannot be read or updated., Raised when a shortage line is outside the hotel or does not exist. (+46 more)

### Community 179 - "Community 179"
Cohesion: 0.15
Nodes (19): MarketingPricingPlan, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, _decode_features(), _plan_to_public(), _ordered_plans(), _plan_catalog_fallback(), public_pricing() (+11 more)

### Community 217 - "Community 217"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 58 - "Community 58"
Cohesion: 0.11
Nodes (51): OperationalTaskTypeEnum, OperationalTaskStatusEnum, OperationalTask, OperationalTaskCreate, OperationalTaskUpdate, OperationalTaskEventRead, OperationalTaskAttachmentUpload, OperationalTaskAttachmentRead (+43 more)

### Community 30 - "Community 30"
Cohesion: 0.16
Nodes (83): OTASyncStatusEnum, OTAReservationMapping, OTAWebhookCredential, OTA (Online Travel Agency) reservation mapping. Tracks the link between external, Maps an external OTA reservation to an internal reservation.     Stores the raw, Per-hotel OTA webhook credential. The secret is stored as a hash so the     raw, OTAReservationLifecycleEnum, OTAProvider (+75 more)

### Community 53 - "Community 53"
Cohesion: 0.06
Nodes (22): OTASyncJob, OTASyncEvent, ABC, Foundational OTA adapter interfaces and orchestration services., BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, A provider operation failed before it could return normalized data., Acknowledge processed reservation messages in Booking's queue. (+14 more)

### Community 167 - "Community 167"
Cohesion: 0.20
Nodes (22): PaymentProofStatusEnum, PaymentProof, PaymentProofBlob, Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., PaymentProofError, _delete_uncommitted_object(), _decode_image() (+14 more)

### Community 61 - "Community 61"
Cohesion: 0.08
Nodes (48): PaymentReceiptEmailDelivery, One attempted receipt email, without retaining the guest's email address.      `, ReservationEmailKindEnum, ReservationEmailStatusEnum, ReservationEmailDelivery, Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, HotelOutboundIdentity (+40 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (37): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, mask_to_weekdays(), PromotionConditions, PromotionCreate (+29 more)

### Community 272 - "Community 272"
Cohesion: 0.26
Nodes (13): PublicInquiryNotificationStatus, PublicInquiryRateLimitError, PublicInquiryUnavailableError, _digest_key(), _rate_limit_keys(), _utcnow_naive(), _notification_body(), _notify_inquiry() (+5 more)

### Community 84 - "Community 84"
Cohesion: 0.12
Nodes (39): PublishedRateHistory, One confirmed base rate per category and stay date.      USD values are populate, RateChangeDraft, Auditable, tenant-scoped draft for daily rates or a price period., Capture approved category rates with the currency and comparable season used., Write a history row for each approved base-rate change in the draft.      This i, _decimal(), _utc() (+31 more)

### Community 329 - "Community 329"
Cohesion: 0.27
Nodes (9): RateLimitEvent, Persistent rate-limit events for security-sensitive endpoints., mfa_attempt_key(), check_mfa_attempt(), reset_mfa_attempts(), Shared persistent rate-limit buckets for account MFA proofs., Use one OTP bucket and one reauthentication bucket per account.      Surface-spe, Record and commit one persistent account proof attempt before checking it. (+1 more)

### Community 68 - "Community 68"
Cohesion: 0.11
Nodes (48): SubscriptionEvent, SubscriptionAdjustment, Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, _now(), _as_utc(), _plan_defaults(), plan_catalog() (+40 more)

### Community 168 - "Community 168"
Cohesion: 0.17
Nodes (22): UserMfaSecret, UserMfaRecoveryCode, TOTP MFA secrets and one-time recovery codes for normal user accounts., MfaSecretUnavailableError, get_user_mfa_secret(), get_active_mfa_secret(), encrypt_totp_secret(), decrypt_totp_secret() (+14 more)

### Community 97 - "Community 97"
Cohesion: 0.11
Nodes (34): UserSession, An opaque browser session whose raw token is never persisted., _now(), _as_aware(), _hash_value(), _issue_token(), _issue_rotation_successor(), _session_cookie_secure() (+26 more)

### Community 356 - "Community 356"
Cohesion: 0.20
Nodes (8): CancellationReviewRead, ReservationCancellationResponse, ReservationRead, BookingCancellationResponse, BookingRead, CancellationReviewDecisionRequest, CancellationReviewResolutionResponse, Transport contracts for manual reservation cancellation review.

### Community 138 - "Community 138"
Cohesion: 0.10
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 548 - "Community 548"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 549 - "Community 549"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceResolveRequest, GuestRoomAvoidanceRead, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 239 - "Community 239"
Cohesion: 0.13
Nodes (2): _normalize_currency(), HotelConfigUpdate

### Community 302 - "Community 302"
Cohesion: 0.17
Nodes (9): PublicPricingPlan, PublicPricingResponse, LeadCreateRequest, LeadCreateResponse, MasterPricingPlanPayload, MasterPricingPlanListPayload, MasterLeadPayload, MasterLeadListPayload (+1 more)

### Community 550 - "Community 550"
Cohesion: 0.40
Nodes (1): HotelIdentityPayload

### Community 551 - "Community 551"
Cohesion: 0.40
Nodes (3): PaymentSurchargeQuoteRequest, PaymentSurchargeQuoteRead, Validated payment-surcharge quote contracts.

### Community 273 - "Community 273"
Cohesion: 0.14
Nodes (11): VisibilityWindowUpdate, VisibilityWindowRead, RolePermissionOverrideRequest, UserPermissionOverrideRequest, PermissionOverrideBatchChange, PermissionOverrideBatchRequest, PermissionDecision, PermissionCatalogItem (+3 more)

### Community 285 - "Community 285"
Cohesion: 0.19
Nodes (6): _clean_required(), _clean_optional(), PublicInquiryCreate, PublicInquiryAccepted, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 415 - "Community 415"
Cohesion: 0.25
Nodes (5): ReservationEmailKind, ReservationEmailStatus, ReservationEmailSendRequest, ReservationEmailDeliveryRead, ReservationEmailSendResponse

### Community 358 - "Community 358"
Cohesion: 0.20
Nodes (5): ReservationGroupPaymentAllocationRequest, ReservationGroupPaymentCreate, ReservationGroupPaymentAllocationRead, ReservationGroupPaymentRead, Request and read contracts for one group collection with child allocations.

### Community 274 - "Community 274"
Cohesion: 0.19
Nodes (13): RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryUpdate, RoomBase, RoomCreate, RoomRead, RoomUpdate (+5 more)

### Community 552 - "Community 552"
Cohesion: 0.40
Nodes (5): WhatsAppChannelComplete, Metadata returned by the server-side Embedded Signup exchange., Metadata returned by the server-side Embedded Signup exchange., Metadata returned by the server-side Embedded Signup exchange., Metadata returned by the server-side Embedded Signup exchange.

### Community 459 - "Community 459"
Cohesion: 0.33
Nodes (4): ChatMessage, ChatCompletionRequest, chat_completions(), _extract_latest_user_message()

### Community 187 - "Community 187"
Cohesion: 0.19
Nodes (19): run_persisted_allocation(), get_allocation_run_details(), get_latest_allocation_run_details(), accept_allocation_run(), auto_apply_safe_allocation_run(), reject_allocation_run(), _create_assignment_explanation(), _reservation_state_fingerprint() (+11 more)

### Community 385 - "Community 385"
Cohesion: 0.36
Nodes (8): _pending_proposal_query(), _request_allocation_proposal(), reservation_overlaps_allocation_horizon(), request_reservation_created_allocation(), trigger_reoptimization_bg(), _run_reoptimization_once(), Run one SQL-backed pass, retrying only transient lock contention., Reoptimize once per hotel and coalesce concurrent same-process triggers.      Th

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, GemmaProvider (+12 more)

### Community 159 - "Community 159"
Cohesion: 0.17
Nodes (24): reservation_status_to_outcome(), infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code(), backfill_channel_code(), split_amount_evenly(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact() (+16 more)

### Community 111 - "Community 111"
Cohesion: 0.15
Nodes (30): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _iter_export_payload_rows(), _is_row_collection(), _flatten_payload_rows(), _rows_to_csv_bytes() (+22 more)

### Community 147 - "Community 147"
Cohesion: 0.16
Nodes (24): _load_category_cost_rows(), detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), touch_reservation_fact_window(), touch_room_state_event_fact_window(), calculate_pickup_30d(), _reservation_row_kind() (+16 more)

### Community 286 - "Community 286"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (69): _now(), _facts_data_as_of(), _hotel_local_now(), _ensure_utc(), _money(), _money_str(), _utc_date_range(), _analytics_window() (+61 more)

### Community 275 - "Community 275"
Cohesion: 0.35
Nodes (13): CashExpenseError, _money(), _delete_object_key(), _decode_receipt(), _safe_filename(), _require_open_session(), create_cash_expense(), list_cash_expenses() (+5 more)

### Community 103 - "Community 103"
Cohesion: 0.08
Nodes (31): _StockDraft, _LinenDraft, _LaundryVendorDraft, _CashSessionDraft, ResourceSpec, MergeResult, normalize_resource_type(), get_resource_spec() (+23 more)

### Community 160 - "Community 160"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy(), create_fx_policy() (+12 more)

### Community 305 - "Community 305"
Cohesion: 0.32
Nodes (9): _decode_company_pdf(), _safe_company_filename(), _get_reservation(), _get_company(), _get_reservation_company(), create_document(), upload_company_document(), get_company_document_bytes() (+1 more)

### Community 258 - "Community 258"
Cohesion: 0.30
Nodes (13): _reservation(), _company(), _rate_for_date(), _rates_for_stay_dates(), list_company_nightly_surcharge_rates(), create_company_nightly_surcharge_rate(), _paid_and_pending_by_charge(), get_company_night_charges() (+5 more)

### Community 386 - "Community 386"
Cohesion: 0.47
Nodes (8): _decimal_text(), company_terms_from_profile(), terms_fingerprint(), _reservation_economics(), _parse_pricing_snapshot(), build_company_terms_snapshot(), get_company_terms_review_state(), effective_company_terms()

### Community 417 - "Community 417"
Cohesion: 0.25
Nodes (8): spreadsheet_safe_value(), spreadsheet_safe_row(), Prefix formula-like text so spreadsheet software treats it as text., Apply formula protection consistently to every text cell in a CSV row., Prefix formula-like text so spreadsheet software treats it as text., Apply formula protection consistently to every text cell in a CSV row., Prefix formula-like text so spreadsheet software treats it as text., Apply formula protection consistently to every text cell in a CSV row.

### Community 418 - "Community 418"
Cohesion: 0.36
Nodes (7): DemoResetSafetyError, assert_demo_database_target_is_safe(), assert_demo_reset_is_safe(), Fail-closed safety checks for destructive local demo database resets., The runtime or database target is not explicitly safe for a demo reset., Allow demo data operations only against an explicitly local database., Allow destructive demo resets only in development against a local DB.      The e

### Community 276 - "Community 276"
Cohesion: 0.21
Nodes (13): _settings(), _get_redis_client(), _required(), _try_postgres_advisory_lock(), distributed_lock(), with_distributed_lock(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru (+5 more)

### Community 259 - "Community 259"
Cohesion: 0.19
Nodes (13): DomainEvent, _settings(), _get_redis_client(), _get_realtime_fast_fail_client(), _required(), _unavailable(), publish_domain_event(), get_realtime_client() (+5 more)

### Community 188 - "Community 188"
Cohesion: 0.10
Nodes (20): channel_for_hotel(), revision_key_for_hotel(), validate_event_input(), _validate_hotel_id(), get_domain_event_recovery(), _outbox_sse_payload(), iter_postgres_event_stream(), _PostgresOutboxStreamRow (+12 more)

### Community 230 - "Community 230"
Cohesion: 0.13
Nodes (13): _OutboxPublishAttempt, _OutboxPublishCooldown, publish_queued_domain_changes(), _record_outbox_attempt(), Redis outcome to persist after every publish in the batch has finished., Process-local gate for durable after-commit Redis publishes only., Return a permit, or skip while cooling down / another probe runs., A successful recovery probe closes only the cooldown it owns. (+5 more)

### Community 199 - "Community 199"
Cohesion: 0.11
Nodes (13): _OutboxPublishPermit, coalesce_model_change_family(), shutdown_postgres_event_listeners(), A durable Redis attempt, optionally owning the single recovery probe., Collapse bulk ORM invalidations to one safe signal per domain.      The persiste, Close any lazy PostgreSQL notification connections at app shutdown., listener_connection_string(), parse_domain_event_notification() (+5 more)

### Community 500 - "Community 500"
Cohesion: 0.40
Nodes (6): _scalar_event_value(), _model_hotel_id(), _model_event_payload(), queue_model_changes(), Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends.

### Community 501 - "Community 501"
Cohesion: 0.33
Nodes (6): _outbox_backoff_seconds(), publish_pending_domain_events(), Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th

### Community 198 - "Community 198"
Cohesion: 0.17
Nodes (11): _record_postgres_stream_count(), _record_postgres_fallback_poll(), _PostgresEventStreamHub, _deliver_postgres_notification(), _update_postgres_listener_state(), _get_postgres_event_stream_hub(), _forget_postgres_event_stream_hub(), _stop_postgres_event_listener_if_idle() (+3 more)

### Community 717 - "Community 717"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 287 - "Community 287"
Cohesion: 0.22
Nodes (8): Mailer, send_platform_email(), send_verification_email(), send_reset_password_email(), send_verification_success_email(), send_generic_auth_notice_email(), Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists.

### Community 419 - "Community 419"
Cohesion: 0.46
Nodes (6): _money(), _local_day(), _aggregate_rows(), _validate_report_window(), build_financial_report(), _hotel_bounds()

### Community 98 - "Community 98"
Cohesion: 0.14
Nodes (35): _cache_key(), _cache_key_for_display_rate(), _cached_rate(), _store_rate(), parse_provider_updated_at(), quote_is_fresh(), _quote_matches_supported_market(), _quote_matches_conversion_market() (+27 more)

### Community 502 - "Community 502"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 288 - "Community 288"
Cohesion: 0.45
Nodes (11): GemmaActionRunError, get_action_run(), approve_action_run(), reject_action_run(), review_action_run_draft(), apply_action_run_draft(), _load_json_dict(), _coerce_numeric_dict() (+3 more)

### Community 128 - "Community 128"
Cohesion: 0.13
Nodes (8): GemmaOrchestrator, _build_session_title(), _safe_text(), _coerce_string_list(), _coerce_float(), _coerce_action_list(), _resolve_existing_user_id(), _derive_models_endpoint()

### Community 117 - "Community 117"
Cohesion: 0.15
Nodes (4): GemmaPolicyDraft, GemmaService, Adapter for Gemma-backed policy suggestions.      The service can talk to either, Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 387 - "Community 387"
Cohesion: 0.31
Nodes (3): GemmaServiceError, Raised when a Gemma request cannot be completed safely., Raised when a Gemma request cannot be completed safely.

### Community 503 - "Community 503"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 420 - "Community 420"
Cohesion: 0.54
Nodes (7): GuestRoomAvoidanceNotFoundError, _now(), _get_tenant_guest(), _get_tenant_room(), record_guest_room_avoidance(), get_active_guest_room_avoidances(), resolve_guest_room_avoidance()

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (24): ensure_plans_seeded(), get_or_create_hotel_for_owner(), _ensure_membership_and_subscription(), ensure_all_ota_webhook_secrets(), Hotel helper utilities (ownership + bootstrap)., Seed default plans if missing., Find a hotel configuration owned by the given email, or create a new one.     Al, Create owner membership and starter subscription if missing. (+16 more)

### Community 129 - "Community 129"
Cohesion: 0.15
Nodes (24): redact_integration_error(), _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload(), get_connection_payload() (+16 more)

### Community 460 - "Community 460"
Cohesion: 0.38
Nodes (6): list_missing_follow_ups(), update_missing_follow_up(), _serialize_follow_up(), Neutral operational follow-up for declared laundry remito shortages.  This servi, Return operational details only; deliberately omit all price fields., Return operational details only; deliberately omit all price fields.

### Community 555 - "Community 555"
Cohesion: 0.40
Nodes (3): duplicate_laundry_remitos(), Read-only duplicate detection shared by migration and operator tooling., Return normalized duplicate remito groups, including every row id.      Service

### Community 359 - "Community 359"
Cohesion: 0.29
Nodes (9): _lock_active_owner_memberships(), ensure_active_owner(), validate_membership_change(), transfer_primary_owner(), Atomic invariants and lifecycle operations for hotel memberships., Lock the current owner set for the duration of the caller's transaction., Require at least one active owner while holding the owner-row lock., Validate a role/status mutation before changing the membership row.      The own (+1 more)

### Community 148 - "Community 148"
Cohesion: 0.14
Nodes (21): _utcnow(), _validate_payload(), _insert_ignore(), _redact(), _role_recipient_ids(), _actor_role(), get_effective_notification_preference(), _in_quiet_hours() (+13 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (32): ObjectStat, ObjectStorage, _safe_relative_path(), LocalObjectStorage, GCSObjectStorage, get_object_storage(), Content-addressed-ish blob store: put/get/delete bytes by string key., Upload a seekable file without changing existing bytes-based callers. (+24 more)

### Community 155 - "Community 155"
Cohesion: 0.25
Nodes (25): OnboardingError, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload(), _current_subscription_context() (+17 more)

### Community 289 - "Community 289"
Cohesion: 0.31
Nodes (12): _utc(), _value(), _money(), _bounds(), _date_filter(), _actor_name(), _area_for(), _safe_detail_value() (+4 more)

### Community 174 - "Community 174"
Cohesion: 0.16
Nodes (20): _daily_report_reservation_load_options(), _candidate_summary(), _daily_reservation_candidate_from_row(), _guest_name(), _reservation_summary(), _group(), company_night_extra_balances_by_reservation(), filter_pms_revenue_transactions() (+12 more)

### Community 106 - "Community 106"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 126 - "Community 126"
Cohesion: 0.07
Nodes (4): OTAProviderAdapter, ExpediaAdapter, FakeBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event()

### Community 260 - "Community 260"
Cohesion: 0.32
Nodes (14): create_or_update_manual_ota_reservation(), release_no_guarantee(), _suggest_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean(), _apply_manual_amounts() (+6 more)

### Community 290 - "Community 290"
Cohesion: 0.28
Nodes (12): _json_size_estimate(), _body_size_estimate(), _request_details(), _response_body_size(), _safe_operation(), _fallback_url(), observed_http_call(), observed_async_http_call() (+4 more)

### Community 231 - "Community 231"
Cohesion: 0.18
Nodes (7): _CachedFailure, _PollEntry, CachedOutboxPollFailure, OutboxPollBatchCache, Short-lived singleflight cache for PostgreSQL event-outbox polling.  The Postgre, A same-window poll failed already; wait for the next bounded retry., Deduplicate concurrent per-process polls without extending freshness.

### Community 175 - "Community 175"
Cohesion: 0.17
Nodes (22): _ensure_utc(), _assert_mercadopago_preference_identity(), _mercadopago_preference_expired(), _money(), _is_safe_provider_url(), _signing_secret(), _signature(), sign_external_reference() (+14 more)

### Community 189 - "Community 189"
Cohesion: 0.18
Nodes (19): _validate_email(), _mercadopago_access_token(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email(), _notification_url(), _is_public_webhook_base(), _notification_url_if_public() (+11 more)

### Community 388 - "Community 388"
Cohesion: 0.33
Nodes (8): _pdf_text(), _amount(), _rate(), _local_created_at(), generate_payment_receipt_pdf(), Generate a downloadable PDF from the persisted payment receipt snapshot., Keep core-font text safe while retaining Spanish Latin-1 characters., Render one page from ``get_payment_receipt_data`` output.      The function acce

### Community 232 - "Community 232"
Cohesion: 0.24
Nodes (16): _is_json_scalar(), normalize_webhook_identifier(), _safe_webhook_event_type(), _payload_value(), _normalize_status(), _completed_at(), _is_allowed_status_transition(), _find_existing_event() (+8 more)

### Community 291 - "Community 291"
Cohesion: 0.29
Nodes (12): quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount(), _convert_amount(), _resolve_conversion_quote() (+4 more)

### Community 461 - "Community 461"
Cohesion: 0.67
Nodes (6): _utc(), _decimal(), _published_base_rates(), _comparable_season_key(), get_fresh_ars_per_usd_snapshot(), record_published_rate_history()

### Community 389 - "Community 389"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 130 - "Community 130"
Cohesion: 0.17
Nodes (28): _settings(), _cache_enabled(), _redis_failure_cooldown_seconds(), _redis_timeout_seconds(), _mark_redis_unavailable(), _mark_redis_available(), _get_redis_client(), _load_json() (+20 more)

### Community 176 - "Community 176"
Cohesion: 0.18
Nodes (22): get_reservation_operations_summary(), _get_operations_related_data(), list_pending_reservation_actions(), _load_pending_action_reservations(), _latest_ota_links_by_reservation(), _related_adjustments_by_reservation(), _pending_action_financial_inputs(), _candidate_reservation_ids() (+14 more)

### Community 556 - "Community 556"
Cohesion: 0.70
Nodes (4): _canonical_hash(), _read_batch(), get_group_payment_batch(), create_reservation_group_payment()

### Community 161 - "Community 161"
Cohesion: 0.16
Nodes (24): _room_move_permission_candidates(), _invalidate_availability_cache(), _hotel_default_currency(), _extension_conflicts(), _extension_no_show_reservations(), _is_auto_assignable_future_reservation(), _available_room_for_conflict(), _extension_room_label() (+16 more)

### Community 557 - "Community 557"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 604 - "Community 604"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 306 - "Community 306"
Cohesion: 0.23
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 558 - "Community 558"
Cohesion: 0.40
Nodes (5): consumption_report(), _consumption_totals_by_item(), _hotel_timezone(), Ordinary outbound stock (``out`` only) per item in [date_from,     date_to], plu, Stock consumed (``out``/``adjustment_out``) per item in [date_from,     date_to]

### Community 190 - "Community 190"
Cohesion: 0.24
Nodes (20): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements(), _get_entitlements_for_subscription() (+12 more)

### Community 206 - "Community 206"
Cohesion: 0.16
Nodes (18): _apply_setting(), _remember_setting(), _set_context_value(), reapply_tenant_context_on_connection(), set_tenant_user_context(), set_tenant_hotel_context(), set_invitation_token_hash_context(), set_tenant_context() (+10 more)

### Community 331 - "Community 331"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 559 - "Community 559"
Cohesion: 0.40
Nodes (3): find_user_by_email(), Exact, case-insensitive lookup helpers for user identity fields., Find an exact email match without treating SQL wildcard characters specially.

### Community 233 - "Community 233"
Cohesion: 0.28
Nodes (16): WaitlistError, _get_waitlist_entry(), _lock_waitlist_entry(), _waitlist_entry_fingerprint(), add_to_waitlist(), list_waitlist_entries(), update_waitlist_entry(), promote_from_waitlist() (+8 more)

### Community 462 - "Community 462"
Cohesion: 0.57
Nodes (6): WhatsAppBookingError, availability_lookup(), price_quote(), options_with_prices(), create_reservation(), generate_payment_link()

### Community 292 - "Community 292"
Cohesion: 0.15
Nodes (13): _redis_endpoint(), _sandbox_domain_event_replay_enabled(), build_beat_schedule(), Return a Redis endpoint identity without exposing URL credentials., Allow only internal outbox recovery in a closed sandbox with Redis wired.      T, Return provider work or only safe internal replay for a closed sandbox.      `no, Return a Redis endpoint identity without exposing URL credentials., Allow only internal outbox recovery in a closed sandbox with Redis wired.      T (+5 more)

### Community 465 - "Community 465"
Cohesion: 0.38
Nodes (6): _session(), process_outbox(), generate_daily_reports(), Celery tasks for the notification backend: process the outbox (bounded retry/exp, Deliver each hotel's pending outbox rows under that hotel's RLS     context. not, Same per-hotel RLS-context requirement as process_outbox above --     daily_repo

### Community 361 - "Community 361"
Cohesion: 0.31
Nodes (9): _empty_totals(), _positive_count(), _rotated_hotel_ids(), _process_pending_revocations(), run_payment_link_revocation_tasks(), Durable, tenant-scoped recovery for canceled Mercado Pago checkout links., Rotate two positions every five-minute slot for predictable fairness., Enumerate every hotel regardless of subscription, rotating visits by cycle. (+1 more)

### Community 560 - "Community 560"
Cohesion: 0.40
Nodes (4): generate_daily_tariff_recommendations(), Daily generation of reviewable, never-auto-published tariff drafts., Create human-review drafts for opted-in hotels using persisted PMS data., Create human-review drafts for opted-in hotels using persisted PMS data.

### Community 405 - "Community 405"
Cohesion: 0.31
Nodes (8): _is_example_test_address(), local_synthetic_email_addresses_enabled(), normalize_reservation_email(), is_local_synthetic_reservation_email(), Validation helpers for reservation communication email addresses., Allow reserved synthetic addresses only in isolated local/test modes., Validate and normalize an email, narrowly allowing local ``example.test``., Return whether a validated recipient belongs to the local reserved domain.

### Community 303 - "Community 303"
Cohesion: 0.24
Nodes (6): chain_names(), root_name(), is_db_call(), FuncScan, scan_file(), names of methods in a call chain, outer->inner

### Community 553 - "Community 553"
Cohesion: 0.60
Nodes (4): login(), vu(), run(), Closed-loop load test: N virtual users, each loops over a request mix with think

### Community 416 - "Community 416"
Cohesion: 0.25
Nodes (3): measured(), Mide, sobre PostgreSQL real, el costo de cuatro rutas calientes que la lectura c, Ejecuta ``fn`` ``repeat`` veces en una sesión nueva y devuelve sentencias/commit

### Community 554 - "Community 554"
Cohesion: 0.60
Nodes (4): pipe(), handle(), flush(), main()

### Community 603 - "Community 603"
Cohesion: 0.83
Nodes (3): timing(), outbox_count(), step()

### Community 360 - "Community 360"
Cohesion: 0.24
Nodes (3): _TooLarge, BodyLimitMiddleware, Tope global de tamaño de cuerpo como middleware ASGI puro (hallazgo N13 del info

### Community 504 - "Community 504"
Cohesion: 0.40
Nodes (5): derive_pepper(), hash_code(), verify_code(), Hash de secretos de corta vida con HMAC-SHA256 (hallazgo N8 del informe).  Hoy `, Deriva el pepper de la clave Fernet existente: no agrega una variable de entorno

### Community 505 - "Community 505"
Cohesion: 0.60
Nodes (5): hotel_chipre_private.purge_operational_data(), public.rate_limit_events, public.security_tokens, public.domain_event_outbox, PUBLIC

### Community 383 - "Community 383"
Cohesion: 0.31
Nodes (6): session, jsonResponse(), stepUpRequired(), permissionAdminReadStepUpRequired(), tick(), waitFor()

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (30): credentials, backendURL, StoredSession, SHOTS, VIEWPORTS, login(), toWebp(), capture() (+22 more)

### Community 382 - "Community 382"
Cohesion: 0.22
Nodes (4): backendURL, ownerCredentials, receptionistCredentials, TestSession

### Community 216 - "Community 216"
Cohesion: 0.16
Nodes (14): RouteScenario, Persona, ApiRequestMetric, ApiResponseMetric, UiActionMetric, personas, durationSeconds, normalizePath() (+6 more)

### Community 498 - "Community 498"
Cohesion: 0.40
Nodes (3): credentials, parseMoney(), readStat()

### Community 455 - "Community 455"
Cohesion: 0.29
Nodes (3): backendURL, receptionistCredentials, TestSession

### Community 327 - "Community 327"
Cohesion: 0.18
Nodes (5): manager, owner, ids, fixtures, transactionsByReservation

### Community 547 - "Community 547"
Cohesion: 0.50
Nodes (3): receptionist, localIsoDate(), openReservationForm()

### Community 413 - "Community 413"
Cohesion: 0.29
Nodes (5): frontendRoot, sourceRoot, pluralSuffixes, flattenKeys(), loadKeys()

### Community 215 - "Community 215"
Cohesion: 0.24
Nodes (11): LocalizedDateFieldProps, validCalendarDate(), formatDateInputValue(), formatDateTimeInputValue(), maskDateInputValue(), maskDateTimeInputValue(), parseDateInputValue(), parseDateTimeInputValue() (+3 more)

### Community 25 - "Community 25"
Cohesion: 0.04
Nodes (87): mfaStatusQueryKey(), getMfaStatus(), SessionLike, ActionStepUpChallenge, ActionStepUpTicket, ActionStepUpHandler, normalizeHotelId(), jwtExpMs() (+79 more)

### Community 87 - "Community 87"
Cohesion: 0.09
Nodes (32): AllocationObjective, AllocationPolicyVersion, ActiveAllocationPolicy, AllocationPolicyVersionCreate, AllocationExplanation, AllocationAssignment, AllocationRunDetail, ReservationReassignmentLock (+24 more)

### Community 27 - "Community 27"
Cohesion: 0.03
Nodes (77): MfaEnrollment, AuthResponse, AuthResult, isMfaChallenge(), getAuthProviders(), loginWithGoogle(), completeMfaLogin(), setPasswordWithGoogle() (+69 more)

### Community 39 - "Community 39"
Cohesion: 0.05
Nodes (69): CashSessionStatus, CashMovementType, CashSession, CashSessionPage, CashMovement, CashCloseReport, CashCustodyHandoff, CashSessionSummary (+61 more)

### Community 34 - "Community 34"
Cohesion: 0.03
Nodes (51): ApiError, CompanyReservationTermsReviewAction, getCompanyReservationTermsReview(), reviewCompanyReservationTerms(), Props, termFieldKeys, CompanyTermsReviewPanel(), RequestOptions (+43 more)

### Community 80 - "Community 80"
Cohesion: 0.08
Nodes (34): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+26 more)

### Community 46 - "Community 46"
Cohesion: 0.04
Nodes (56): RemitoDirection, LaundryVendor, LaundryVendorCreate, LaundryVendorUpdate, LaundryVendorPrice, LaundryVendorPriceUpsert, LaundryRemitoLine, LaundryRemito (+48 more)

### Community 144 - "Community 144"
Cohesion: 0.07
Nodes (24): LinenItem, LinenLocation, LinenItemCreate, LinenLocationCreate, LinenMovementCreate, LinenMovement, CurrentLinenStock, LinenSummaryEntry (+16 more)

### Community 115 - "Community 115"
Cohesion: 0.10
Nodes (25): OperationalTaskType, OperationalTaskStatus, OperationalTaskPriority, OperationalTask, OperationalTaskEvent, ShiftHandoff, OperationalTaskAttachment, OperationalTaskCreate (+17 more)

### Community 41 - "Community 41"
Cohesion: 0.05
Nodes (69): RESERVATION_QUERY_PREFIXES, PAYMENT_QUERY_PREFIXES, CASH_QUERY_PREFIXES, RESERVATION_ENTITY_QUERY_PREFIXES, GUEST_QUERY_PREFIXES, ROOM_QUERY_PREFIXES, ReservationRecordRefreshOptions, refreshAfterMutation() (+61 more)

### Community 411 - "Community 411"
Cohesion: 0.25
Nodes (5): CLIENT_ID, REDIRECT_URI, AppleAuthorization, AppleSignInResult, Window

### Community 65 - "Community 65"
Cohesion: 0.06
Nodes (34): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+26 more)

### Community 412 - "Community 412"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 495 - "Community 495"
Cohesion: 0.80
Nodes (5): SharedSandboxBootstrapError, load_env(), _literal(), build_sql(), main()

### Community 496 - "Community 496"
Cohesion: 0.47
Nodes (5): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 299 - "Community 299"
Cohesion: 0.36
Nodes (11): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+3 more)

### Community 352 - "Community 352"
Cohesion: 0.49
Nodes (9): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+1 more)

### Community 379 - "Community 379"
Cohesion: 0.42
Nodes (8): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots.

### Community 704 - "Community 704"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 300 - "Community 300"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 113 - "Community 113"
Cohesion: 0.16
Nodes (29): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+21 more)

### Community 599 - "Community 599"
Cohesion: 0.67
Nodes (3): normalize_instruction_paths(), main(), Replace this repository's absolute root in generated instructions only.

### Community 141 - "Community 141"
Cohesion: 0.13
Nodes (21): OperationalQAError, _utc_now(), _json_bytes(), _write(), _catalog(), initialize(), validate(), main() (+13 more)

### Community 173 - "Community 173"
Cohesion: 0.26
Nodes (20): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+12 more)

### Community 158 - "Community 158"
Cohesion: 0.22
Nodes (23): AttestationError, _sha256(), _canonical_json(), _b64url_encode(), _b64url_decode(), _read_regular_nofollow(), _read_limited(), _json_object() (+15 more)

### Community 409 - "Community 409"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 600 - "Community 600"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 142 - "Community 142"
Cohesion: 0.22
Nodes (16): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+8 more)

### Community 323 - "Community 323"
Cohesion: 0.40
Nodes (10): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+2 more)

### Community 601 - "Community 601"
Cohesion: 0.83
Nodes (3): run(), validate_json(), main()

### Community 226 - "Community 226"
Cohesion: 0.23
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 107 - "Community 107"
Cohesion: 0.21
Nodes (32): VerificationError, _dict(), _list(), _string(), _validate_config(), _decode_lease_entropy(), _validate_baseline_lease_id(), _verify_dedicated_baseline_lease() (+24 more)

### Community 380 - "Community 380"
Cohesion: 0.22
Nodes (6): ReadOnlyJsonApi, VerificationConfig, ProviderClients, _required_env(), main(), Small GET-only API client with bounded retries and redacted failures.

### Community 602 - "Community 602"
Cohesion: 0.83
Nodes (3): _non_empty(), validate_manifest(), main()

### Community 256 - "Community 256"
Cohesion: 0.33
Nodes (14): DrillError, _validate_tables(), _sqlite_path(), _sqlite_counts(), _verify_local_objects(), _run_sqlite(), _postgres_parts(), _pg_command() (+6 more)

### Community 85 - "Community 85"
Cohesion: 0.12
Nodes (39): QABootstrapError, Persona, QABootstrapConfig, QABootstrapResult, ProviderEvidence, _required(), _flag(), _required_port() (+31 more)

### Community 384 - "Community 384"
Cohesion: 0.36
Nodes (8): _required(), load_provider_evidence_private_key(), issue_provider_evidence_token(), _safe_output_path(), write_private_token(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer.

### Community 304 - "Community 304"
Cohesion: 0.21
Nodes (5): _parser(), _hotel_ranges(), _build_dry_run_report(), main(), Idempotently rebuild reservation and room analytics facts for a bounded scope.

### Community 330 - "Community 330"
Cohesion: 0.33
Nodes (8): PhaseMetrics, LoadConfig, percentile(), safe_headers(), run_phase(), _parse_paths(), _run(), main()

### Community 458 - "Community 458"
Cohesion: 0.52
Nodes (5): RealtimeMetrics, validate_target(), run_load(), _run(), main()

### Community 109 - "Community 109"
Cohesion: 0.12
Nodes (29): E2ESafetyError, _enabled(), _postgres_e2e_connection(), _postgres_e2e_seed_connection(), _is_postgres_e2e_target(), _assert_postgres_e2e_database_empty(), prepare_e2e_environment(), reset_e2e_database() (+21 more)

### Community 357 - "Community 357"
Cohesion: 0.31
Nodes (9): reset_projection_clients(), _close_clients(), _enable(), test_mongo_audit_projection_lands_document(), test_neo4j_reservation_assignment_lands_nodes(), _cassandra_probe(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each (+1 more)

### Community 69 - "Community 69"
Cohesion: 0.06
Nodes (42): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), Migration coverage for the deduplication sweep., _run_alembic(), _assert_backfill() (+34 more)

### Community 457 - "Community 457"
Cohesion: 0.48
Nodes (6): _resident_bytes(), _peak_resident_bytes(), _percentile(), _scenario(), main(), Measure allocation solver time and process memory on synthetic hotel data.  Run

### Community 197 - "Community 197"
Cohesion: 0.19
Nodes (19): BenchmarkResult, index_usage_for_operation(), derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure() (+11 more)

### Community 332 - "Community 332"
Cohesion: 0.35
Nodes (10): PostgresTargetSafetyError, _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot (+2 more)

### Community 463 - "Community 463"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 464 - "Community 464"
Cohesion: 0.48
Nodes (6): _receptionist_context(), _open_cash_session(), _create_receptionist_user(), test_receptionist_can_view_and_make_reservation_payments(), test_financial_summary_requires_reservation_read_not_cash_operation(), Front desk can read reservation finances and record payments.

### Community 605 - "Community 605"
Cohesion: 0.67
Nodes (3): _receptionist_context(), test_receptionist_can_view_operations_summary_and_pending_actions(), GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti

### Community 200 - "Community 200"
Cohesion: 0.22
Nodes (17): _auth_context(), step_up_client(), _code_at(), _invalid_code(), _issue_ticket(), test_sensitive_permission_requires_a_matching_ticket_before_handler(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket() (+9 more)

### Community 207 - "Community 207"
Cohesion: 0.19
Nodes (14): _reservation_payload(), _pending_requests(), test_direct_and_inbound_ota_bookings_request_one_coalesced_proposal(), test_waitlisted_or_out_of_horizon_reservation_does_not_request_current_run(), test_background_worker_runs_auto_apply_for_eligible_room_moves(), test_real_background_solver_auto_applies_eligible_moves_and_keeps_locks(), test_pending_proposal_coalesces_different_automatic_triggers(), test_postgres_worker_auto_applies_only_unchecked_in_unlocked_moves() (+6 more)

### Community 118 - "Community 118"
Cohesion: 0.14
Nodes (8): make_rooms(), make_res(), TestOverlap, test_reservation_day_index_clips_to_half_open_horizon(), test_overlapping_reservation_pairs_use_half_open_dates_and_keep_original_indexes(), TestGreedyAllocation, TestCPSATAllocation, Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).

### Community 333 - "Community 333"
Cohesion: 0.55
Nodes (9): _seed_hotel(), _guest(), _reservation(), _slots(), test_slot_builder_does_not_hydrate_unused_reservation_relationships(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_previous_completed_room_signal_requires_the_new_reservation_category(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy() (+1 more)

### Community 334 - "Community 334"
Cohesion: 0.56
Nodes (10): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+2 more)

### Community 466 - "Community 466"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 336 - "Community 336"
Cohesion: 0.29
Nodes (9): _seed_allocation_case(), _run_allocation(), _wait_for_postgres_lock_wait(), test_postgres_autoapply_rejects_room_taken_after_solver_snapshot(), test_postgres_acceptance_rejects_stale_policy_or_fx_configuration(), test_postgres_autoapply_serializes_with_concurrent_reservation_creation(), PostgreSQL regressions for allocation freshness and room-lock serialization.  Th, A competing committed booking between solve and apply must fail closed. (+1 more)

### Community 102 - "Community 102"
Cohesion: 0.13
Nodes (29): _slot(), test_mobility_restriction_prefers_lower_floor_only_if_hotel_has_no_elevator(), test_unknown_or_present_elevator_does_not_apply_floor_preference(), test_score_only_breaks_equivalent_room_tie(), test_room_assignment_rejects_pricing_objectives(), test_solver_only_locks_checked_in_or_explicitly_pinned_reservations(), test_paid_reservation_with_room_is_still_eligible_for_reassignment(), test_allocation_slots_exclude_pricing_data() (+21 more)

### Community 337 - "Community 337"
Cohesion: 0.24
Nodes (4): _Response, _Client, test_provider_receives_only_curated_hotel_analytics_payload(), test_provider_chat_uses_curated_hotel_context_and_controlled_message()

### Community 86 - "Community 86"
Cohesion: 0.09
Nodes (28): assert_freshness_metadata(), _wait_for_xlsx_completion(), _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_company_detail_and_exports_only_include_reservations_overlapping_the_selected_window(), test_streamed_detail_exports_match_materialized_payloads(), test_room_state_events_and_variable_cost_audit() (+20 more)

### Community 561 - "Community 561"
Cohesion: 0.60
Nodes (3): _reservation(), test_reservation_fact_touch_enqueues_and_coalesces_without_materializing(), test_hotel_cron_materializes_and_deletes_only_that_hotels_jobs()

### Community 124 - "Community 124"
Cohesion: 0.10
Nodes (10): test_explicit_fact_refresh_repairs_legacy_currency_fact(), _make_fact_refresh_reservation(), _fact_business_snapshot(), test_targeted_reservation_fact_touch_matches_full_refresh(), test_targeted_refresh_preserves_facts_outside_union_window(), test_targeted_room_refresh_reapplies_events_only_for_affected_rooms(), test_targeted_reservation_fact_touch_isolated_by_hotel(), test_room_state_event_create_and_close_refresh_only_materialized_room_horizon() (+2 more)

### Community 277 - "Community 277"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed(), test_operational_schema_covers_dimensions_and_non_pii_facts()

### Community 112 - "Community 112"
Cohesion: 0.07
Nodes (16): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_add_reservation_guests_matches_existing_document_despite_whitespace(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_n06_cancel_errors_match_between_reservation_and_booking_routes(), test_n06_terminal_edit_and_stale_version_errors_are_localized_on_both_routes(), Spin up the real FastAPI app against an in-memory SQLite database. (+8 more)

### Community 338 - "Community 338"
Cohesion: 0.35
Nodes (7): FakeJwkClient, _token(), _verify(), test_valid_apple_token_is_verified(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch()

### Community 180 - "Community 180"
Cohesion: 0.29
Nodes (21): _post_request(), _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation() (+13 more)

### Community 421 - "Community 421"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 169 - "Community 169"
Cohesion: 0.08
Nodes (16): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_hotel_delete_is_restricted(), test_audit_log_all_actions_persist(), test_transaction_hotel_id_has_fk_constraint(), test_failed_audit_log_insert_does_not_roll_back_callers_change(), TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence. (+8 more)

### Community 131 - "Community 131"
Cohesion: 0.08
Nodes (7): _complete_onboarding(), test_login_prefers_a_completed_hotel_when_multiple_memberships_exist(), _fake_apple_claims(), test_apple_login_creates_account_and_persists_first_authorization_name(), test_apple_login_reclaims_matching_local_email_after_verified_claims(), test_apple_login_rejects_different_subject_claiming_linked_email(), test_apple_unlink_requires_password_and_revokes_session()

### Community 706 - "Community 706"
Cohesion: 0.67
Nodes (1): FakeResponse

### Community 218 - "Community 218"
Cohesion: 0.17
Nodes (17): test_auth_flows_fail_without_connected_mail_provider(), _fake_google_claims(), test_google_login_creates_new_user_when_email_unknown(), test_google_login_treats_email_underscore_as_a_literal_character(), test_google_login_relogin_with_same_sub_preserves_password(), test_google_login_does_not_replace_another_linked_subject(), test_google_account_can_set_password_only_with_linked_google_proof_and_csrf(), test_password_login_rejects_even_a_valid_hash_when_password_login_is_disabled() (+9 more)

### Community 293 - "Community 293"
Cohesion: 0.22
Nodes (13): _register_owner(), _configure_resend(), test_password_policy_requires_twelve_characters_for_register_and_reset(), test_register_verify_and_reset_use_resend_provider(), test_register_is_anti_enumeration_and_does_not_touch_existing_credentials(), test_reset_password_revokes_previously_issued_tokens(), test_google_login_does_not_replace_existing_password_without_mfa(), test_google_account_link_waits_for_mfa_and_preserves_password() (+5 more)

### Community 240 - "Community 240"
Cohesion: 0.22
Nodes (16): _auth_headers(), test_unverified_users_cannot_use_operational_endpoints(), _next_totp_code(), _verified_auth(), _enroll_and_confirm_mfa(), test_mfa_status_reports_only_active_state_for_the_authenticated_user(), test_mfa_enrollment_rejects_active_factor_before_password_verification(), test_google_only_account_can_disable_mfa_with_fresh_linked_google_proof() (+8 more)

### Community 606 - "Community 606"
Cohesion: 0.50
Nodes (4): test_register_rejects_malformed_email(), RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage

### Community 607 - "Community 607"
Cohesion: 0.50
Nodes (4): test_register_rejects_reserved_test_tld_outside_test_mode(), .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by

### Community 608 - "Community 608"
Cohesion: 0.50
Nodes (4): test_register_accepts_reserved_test_tld_in_test_mode(), The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re

### Community 609 - "Community 609"
Cohesion: 0.50
Nodes (4): test_self_registration_cannot_grant_platform_admin_role(), A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j

### Community 390 - "Community 390"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_surfaces_retryable_provider_outage(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue()

### Community 562 - "Community 562"
Cohesion: 0.50
Nodes (3): _override_auth(), test_receptionist_can_get_price_quote(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t

### Community 90 - "Community 90"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+24 more)

### Community 208 - "Community 208"
Cohesion: 0.12
Nodes (5): _fix_operational_clock_time(), test_stock_and_linen_ledger_timestamps_use_hotel_business_clock(), test_laundry_batch_uses_business_date_for_timestamps_and_batch_code(), test_task_events_and_shift_handoffs_use_business_clock(), Local hotel-scoped business clock API and date isolation coverage.

### Community 563 - "Community 563"
Cohesion: 0.60
Nodes (4): _run_alembic(), test_local_business_clock_migration_adds_and_drops_only_its_table(), test_local_business_clock_migration_adopts_existing_bootstrap_table(), Alembic round-trip for the additive local business-clock table.

### Community 79 - "Community 79"
Cohesion: 0.06
Nodes (16): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+8 more)

### Community 156 - "Community 156"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+16 more)

### Community 506 - "Community 506"
Cohesion: 0.60
Nodes (5): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable(), Cancelling a reservation must cancel its still-payable seña links (BR §M).

### Community 362 - "Community 362"
Cohesion: 0.38
Nodes (9): _evaluate(), test_cancellation_inside_saved_free_window_has_no_penalty(), test_cancellation_after_cutoff_requires_approval_for_saved_percentage(), test_non_refundable_saved_plan_uses_full_total_without_creating_a_charge(), test_fixed_penalty_uses_saved_currency(), test_missing_snapshot_requires_manager_review_without_using_current_policy(), test_missing_checkin_time_requires_hotel_configuration(), test_invalid_policy_values_fail_closed_to_manager_review() (+1 more)

### Community 422 - "Community 422"
Cohesion: 0.32
Nodes (3): _load_migration(), FakeInspector, test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 467 - "Community 467"
Cohesion: 0.57
Nodes (6): _load_migration(), _run(), _create_minimal_schema(), test_cash_movement_void_migration_round_trips_without_history(), test_cash_movement_void_migration_refuses_to_drop_void_history(), SQLite regression coverage for auditable cash-movement voids.

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (53): _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_and_currency_is_allowed(), test_cash_movement_requires_open_session(), test_cash_movement_rejects_non_positive_amount_with_spanish_message(), test_close_report_expected_balance_from_confirmed_cash() (+45 more)

### Community 564 - "Community 564"
Cohesion: 0.60
Nodes (4): _load_migration(), _run(), test_cash_tender_change_migration_preserves_legacy_rows_and_validates_pairs(), SQLite migration coverage for separate cash tender, change, and tip amounts.

### Community 566 - "Community 566"
Cohesion: 0.40
Nodes (1): TestGuestValidation

### Community 469 - "Community 469"
Cohesion: 0.33
Nodes (1): TestCheckIn

### Community 162 - "Community 162"
Cohesion: 0.15
Nodes (24): _override_auth(), _client_with_db(), _seed_fully_paid_reservation(), _assert_reservation_response(), test_checkin_without_new_fields_fails_with_clear_message(), test_checkin_captures_missing_fields_in_same_request(), test_partial_checkin_reaches_pre_check_in_then_final_checkin(), test_checkout_room_lock_conflict_returns_409_and_rolls_back() (+16 more)

### Community 294 - "Community 294"
Cohesion: 0.44
Nodes (12): _override_auth(), _test_app(), _guest(), _seed_reservation(), _close(), test_each_guest_arrival_is_idempotent_and_only_first_occupies_room(), test_hotel_can_mark_reservation_checked_in_on_first_guest(), test_missing_guest_profiles_remain_visible_and_do_not_complete_party() (+4 more)

### Community 565 - "Community 565"
Cohesion: 0.70
Nodes (4): _override_auth(), _client_with_db(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 363 - "Community 363"
Cohesion: 0.20
Nodes (9): test_checkin_room_lock_refreshes_room_loaded_before_competing_status_change(), test_checkin_refreshes_concurrent_room_move_and_fails_fast_on_room_lock(), test_checkout_returns_retryable_conflict_when_another_transaction_holds_room(), test_checkout_allows_deferred_company_balance_without_financial_mutation_postgres(), PostgreSQL regressions for the check-in room row lock and ORM identity map., A stale eagerly loaded Room must not pass check-in after another commit., A moved reservation is refreshed before check-in; a busy room returns a conflict, Checkout uses PostgreSQL NOWAIT while holding the reservation lock. (+1 more)

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (37): _make_hotel(), _make_guest(), _make_room(), anchor_hotel_day_to_fixture_arrival(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin() (+29 more)

### Community 209 - "Community 209"
Cohesion: 0.23
Nodes (16): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), test_register_settlement_rolls_back_when_audit_cannot_be_written(), _company_reservation(), test_deferred_company_extension_does_not_calculate_or_record_base_price(), test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(), test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies() (+8 more)

### Community 391 - "Community 391"
Cohesion: 0.64
Nodes (8): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation(), test_company_document_cannot_be_attached_to_unlinked_reservation(), test_uploaded_company_voucher_is_private_signature_aware_and_tenant_scoped()

### Community 423 - "Community 423"
Cohesion: 0.50
Nodes (7): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_requirements_do_not_implicitly_lock_allocation(), test_corporate_reservation_is_allocation_locked()

### Community 191 - "Community 191"
Cohesion: 0.19
Nodes (20): _company_reservation(), _transaction(), test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(), test_company_night_charge_batch_resolves_rate_history_with_bounded_queries(), test_company_night_charges_use_effective_rate_and_extra_person_quantity(), test_company_charge_quantity_cannot_exceed_registered_additional_people(), test_terminal_company_reservations_cannot_receive_new_nightly_charges(), test_legacy_rate_does_not_price_a_night_before_safe_cutover() (+12 more)

### Community 424 - "Community 424"
Cohesion: 0.46
Nodes (6): _run_alembic(), _seed_legacy_company(), test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only(), test_company_nightly_rate_downgrade_refuses_to_discard_user_history(), test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots(), SQLite upgrade coverage for company nightly rate cutover and rollback guard.

### Community 392 - "Community 392"
Cohesion: 0.39
Nodes (8): _seed_company_reservation(), test_company_terms_change_is_reviewed_without_silently_rewriting_booking(), test_manager_accepts_current_terms_without_repricing_and_retry_is_idempotent(), test_stale_company_config_requires_manager_to_reload_before_deciding(), test_legacy_reservation_without_snapshot_cannot_claim_to_keep_unknown_terms(), test_company_terms_review_does_not_disclose_reservation_across_hotels(), test_company_terms_review_rejects_closed_reservations_without_mutation(), Reservation-level review for changes to mutable company configuration.

### Community 470 - "Community 470"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 139 - "Community 139"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 241 - "Community 241"
Cohesion: 0.26
Nodes (14): _create_role(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), _step_up_headers(), test_roles_api_contract_and_owner_co_owner_admin_mutations(), test_role_archive_refuses_active_members_and_pending_invites(), test_expired_pending_invitation_is_not_counted_or_blocking_role_archive(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed() (+6 more)

### Community 393 - "Community 393"
Cohesion: 0.44
Nodes (8): _create_remitos(), _load_migration(), test_remito_preflight_reports_ids_and_trimmed_duplicates(), test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace(), test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved(), test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint(), test_remito_preflight_is_empty_when_no_duplicate_exists(), test_day2_downgrade_refuses_to_discard_persisted_operational_data()

### Community 471 - "Community 471"
Cohesion: 0.33
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 364 - "Community 364"
Cohesion: 0.42
Nodes (9): _legacy_deferred_reservation(), _payment(), test_deferred_reservation_read_and_list_mask_legacy_lodging_money(), test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(), test_pending_company_night_extra_remains_due_until_payment_completes(), test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(), test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(), test_deferred_reservation_group_masks_legacy_group_total() (+1 more)

### Community 201 - "Community 201"
Cohesion: 0.10
Nodes (9): client(), test_seed_and_reset_blocked_by_default(), test_seed_and_reset_allowed_when_demo_enabled(), FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Explicit development environments retain the DEMO_MODE workflow., FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled. (+1 more)

### Community 242 - "Community 242"
Cohesion: 0.21
Nodes (9): FakeRedis, _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_optional_lock_can_degrade_when_redis_is_unavailable(), FakePostgresSession, test_required_lock_uses_postgres_advisory_lock_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 181 - "Community 181"
Cohesion: 0.18
Nodes (16): use_redis_for_redis_outbox_replay_tests(), _seed_hotels(), _outbox_row(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision() (+8 more)

### Community 48 - "Community 48"
Cohesion: 0.05
Nodes (48): _isolate_realtime_configuration(), _event_engine(), _thread_safe_event_engine(), FakeRedis, _settings(), _successful_publisher(), test_realtime_fallback_poll_is_bounded_when_listener_is_unavailable(), test_postgres_event_batch_select_omits_unneeded_outbox_payload() (+40 more)

### Community 234 - "Community 234"
Cohesion: 0.16
Nodes (7): _postgres_e2e_environment(), test_seed_guard_accepts_only_explicit_loopback_postgres_e2e_database(), test_seed_guard_accepts_secondary_ipv4_loopback_for_isolated_postgres(), test_seed_guard_accepts_explicit_high_local_postgres_port(), test_seed_guard_requires_a_distinct_explicit_seed_role_on_the_same_local_database(), test_seed_guard_rejects_postgres_without_the_dedicated_local_test_boundary(), test_reset_e2e_database_never_deletes_postgres_target_files()

### Community 243 - "Community 243"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, test_credential_access_and_email_stop_before_db_or_network(), test_connections_flag_alone_closes_credential_lane(), test_payment_link_test_stops_before_db_or_provider(), test_google_login_stops_before_transport_or_db(), test_apple_login_stops_before_jwks_or_db(), test_provider_callbacks_stop_before_body_parse() (+2 more)

### Community 508 - "Community 508"
Cohesion: 0.60
Nodes (5): _f003_environment(), test_f003_seed_accepts_only_dedicated_local_fixture_target(), test_f003_seed_requires_explicit_opt_in(), test_f003_seed_rejects_sqlite_even_with_opt_in(), test_f003_seed_rejects_database_outside_its_dedicated_namespace()

### Community 210 - "Community 210"
Cohesion: 0.17
Nodes (11): _FakeResponse, _quote(), _seed_expired_conversion_cache(), test_fresh_quote_rejects_crossed_buy_sell_values(), test_blue_equivalent_for_non_usd_currency_is_explicitly_derived(), test_blue_equivalent_fails_closed_when_any_source_quote_is_stale(), test_stale_selected_usd_quote_fails_closed_without_requesting_official_fallback(), test_usd_conversion_rejects_provider_quote_for_wrong_currency_or_market() (+3 more)

### Community 567 - "Community 567"
Cohesion: 0.60
Nodes (4): _load_migration(), _side_columns(), test_fx_conversion_side_migration_backfills_defaults_and_round_trips_safely(), SQLite migration coverage for configurable USD conversion sides.

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (39): _step_up_header(), test_credit_refund_requires_refund_permission_step_up_and_cash_session(), Authorization and API contract checks for FX-credit cash refunds., _add_manager_actor(), _target_reservation(), _payment(), test_manager_can_atomically_reassign_manual_payment_and_replay_idempotently(), test_receptionist_cannot_correct_payment() (+31 more)

### Community 611 - "Community 611"
Cohesion: 0.83
Nodes (3): _load_migration(), _market_columns(), test_fx_direction_market_migration_preserves_global_market_and_guards_downgrade()

### Community 220 - "Community 220"
Cohesion: 0.28
Nodes (16): _reservation(), _open_cash(), _mock_usd_to_ars_quote(), _legacy_rounding_credit_payment(), test_configured_rounding_never_changes_exact_fx_principal_or_issues_credit(), test_arbitrary_fx_overpayment_is_rejected_even_when_rounding_is_configured(), test_same_currency_payment_remains_exact_under_fx_rounding_policy(), test_fx_payment_does_not_collect_a_tender_cent_that_exceeds_balance() (+8 more)

### Community 612 - "Community 612"
Cohesion: 0.67
Nodes (3): _load_migration(), test_credit_ledger_migration_preserves_old_rows_and_constrains_credit_refunds(), SQLite migration coverage for separate FX rounding-credit ledger fields.

### Community 613 - "Community 613"
Cohesion: 0.50
Nodes (1): PostgreSQL regressions for exact non-cash FX settlement amounts.

### Community 614 - "Community 614"
Cohesion: 0.67
Nodes (3): _load_migration(), test_fx_rounding_policy_migration_defaults_existing_hotels_and_checks_allowed_policies(), SQLite coverage for the persisted foreign-payment FX rounding policy.

### Community 166 - "Community 166"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 615 - "Community 615"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_direct_guest_and_companion_audits_exclude_pii(), test_decorator_mongo_projection_excludes_guest_pii()

### Community 308 - "Community 308"
Cohesion: 0.42
Nodes (10): _seed_hotel(), _seed_reservation(), _step_up_headers(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_rejects_invalid_and_overlong_date_ranges(), test_guest_export_excludes_soft_deleted_guest_identity() (+2 more)

### Community 365 - "Community 365"
Cohesion: 0.42
Nodes (9): _isolate_realtime_configuration(), _auth(), _client(), test_restriction_api_permissions_tenant_isolation_and_event(), test_active_restriction_summary_is_batched_tenant_scoped_and_nondisclosing(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_restriction_override_reason_rejects_whitespace() (+1 more)

### Community 340 - "Community 340"
Cohesion: 0.38
Nodes (10): _seed_hotel(), _seed_guest_inventory(), _reservation(), _create_payload(), test_restriction_lifecycle_distinguishes_active_expired_and_resolved(), test_restriction_is_tenant_scoped_for_reads_and_resolution(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override() (+2 more)

### Community 568 - "Community 568"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 261 - "Community 261"
Cohesion: 0.41
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 341 - "Community 341"
Cohesion: 0.18
Nodes (3): utc_server_clock(), The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today

### Community 509 - "Community 509"
Cohesion: 0.53
Nodes (5): _load_migration(), _run(), _create_referenced_tables(), test_housekeeping_checklist_migration_creates_constrained_tenant_tables_and_guards_downgrade(), SQLite migration coverage for the fixed housekeeping checklist schema.

### Community 262 - "Community 262"
Cohesion: 0.23
Nodes (10): _checked_in_reservation(), _checkout(), _complete(), test_checkout_creates_fixed_checklist_and_final_item_releases_cleaning_room(), test_item_completion_is_idempotent_and_does_not_increment_version(), test_completing_checklist_preserves_maintenance_and_blocked_rooms(), test_open_checklist_blocks_direct_release_and_checkin_even_if_room_looks_ready(), test_complete_item_is_tenant_scoped() (+2 more)

### Community 569 - "Community 569"
Cohesion: 0.40
Nodes (3): test_postgres_checkout_checklist_and_room_audit_roll_back_atomically(), PostgreSQL tenant and concurrent item completion regressions., Checkout, checklist creation, and room audit share the caller transaction.

### Community 617 - "Community 617"
Cohesion: 0.83
Nodes (3): _load_migration(), _run_migration(), test_migration_backfills_existing_accounts_and_retains_alias_on_rollback()

### Community 618 - "Community 618"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (53): get_db_override_target(), get_auth_context_target(), _invitation_token(), client_with_db(), owner_ctx(), _manage_users_request(), test_invite_returns_token_and_accepts(), test_atomic_invitation_consumption_rejects_a_rotated_token_hash() (+45 more)

### Community 456 - "Community 456"
Cohesion: 0.33
Nodes (3): _FakeDispatcher, JobDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 342 - "Community 342"
Cohesion: 0.40
Nodes (10): _seed(), _shortage_case(), _approve(), test_shortage_stays_pending_and_does_not_adjust_stock_until_authorized_resolution(), test_missing_linen_resolution_outcomes_keep_custody_and_ledger_consistent(), test_claim_or_replacement_remains_pending_until_physical_receipt(), test_vendor_credit_requires_explicit_negotiated_amount_and_currency(), test_excess_is_pending_identification_until_stock_acceptance_or_return() (+2 more)

### Community 619 - "Community 619"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 132 - "Community 132"
Cohesion: 0.22
Nodes (28): _override_auth(), _client_with_db(), _teardown(), test_duplicate_remito_returns_conflict_but_other_direction_is_allowed(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_vendor_price_write_requires_laundry_price_permission(), test_manager_needs_explicit_vendor_price_permission(), test_owner_can_manage_linen_items_and_receptionist_cannot() (+20 more)

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (31): _seed_hotels(), _seed_house_stock(), _set_test_vendor_price(), test_create_vendor_creates_its_own_linen_location(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_inbound_reverses_the_transfer(), test_remito_number_is_unique_per_hotel_vendor_and_direction(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing() (+23 more)

### Community 343 - "Community 343"
Cohesion: 0.31
Nodes (10): _seed_hotels(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped(), test_linen_opening_count_batch_is_atomic_and_only_applies_before_location_history(), test_linen_summary_marks_zero_balance_as_having_history(), test_linen_transfer_is_atomic_linked_and_idempotent(), test_linen_transfer_rejects_insufficient_source_without_partial_rows(), test_linen_minimums_are_location_specific_and_allow_zero() (+2 more)

### Community 157 - "Community 157"
Cohesion: 0.15
Nodes (17): env_page(), FakeRender, mutations(), acquire_lease(), release_lease(), test_acquire_validates_before_writing_and_commits_id_last(), test_acquire_refuses_every_drift_without_mutation(), test_same_production_and_qa_identity_is_rejected_before_get() (+9 more)

### Community 425 - "Community 425"
Cohesion: 0.43
Nodes (7): _load_migration(), _load_data_migration(), test_migration_backfills_default_policy_and_is_idempotent(), test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(), test_ota_backfill_locks_row_before_recomputing_completed_ledger(), SQLite contract test for the new manual-payment/check-in-policy migration., A payment committed after candidate discovery must be in the backfill snapshot.

### Community 570 - "Community 570"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_schema(), test_manual_rate_policy_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for bounded manual reservation rates.

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (65): FakeResponse, _seed_platform_admin(), _complete_master_login(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_admin_absolute_ttl_expires_recently_active_session(), test_master_login_bootstraps_env_account() (+57 more)

### Community 366 - "Community 366"
Cohesion: 0.31
Nodes (7): _login(), test_owner_sets_a_price_and_the_public_endpoint_serves_it(), test_saving_pricing_writes_an_audit_event(), test_a_plan_dropped_from_the_payload_disappears(), test_negative_price_is_rejected(), test_owner_can_read_captured_leads(), Public pricing is owner-editable from the master-admin console.  Reuses the mast

### Community 394 - "Community 394"
Cohesion: 0.28
Nodes (7): _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it(), test_master_admin_dashboard_reads_hotels_without_outbox_rls_failure(), C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, A master-admin dashboard read may seed a missing subscription safely.      Snaps, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1

### Community 473 - "Community 473"
Cohesion: 0.43
Nodes (5): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), This bool-returning shim delegates to the SAME raising validator every     real

### Community 310 - "Community 310"
Cohesion: 0.17
Nodes (8): TestTransactionModel, Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship., Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship.

### Community 265 - "Community 265"
Cohesion: 0.13
Nodes (11): TestRoomModels, Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify category string representation., Tests for Room and RoomCategory models., Verify categories are created with correct attributes. (+3 more)

### Community 708 - "Community 708"
Cohesion: 0.67
Nodes (2): Verify the hotel has exactly 38 rooms., Verify the hotel has exactly 38 rooms.

### Community 709 - "Community 709"
Cohesion: 0.67
Nodes (2): Same room_number can exist in different hotels without conflict., Same room_number can exist in different hotels without conflict.

### Community 710 - "Community 710"
Cohesion: 0.67
Nodes (2): Verify room string representation., Verify room string representation.

### Community 263 - "Community 263"
Cohesion: 0.13
Nodes (11): TestGuestModel, Tests for Guest and GuestCompanion models., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Create companions and verify relationship., Verify auto-generated timestamps., Tests for Guest and GuestCompanion models., Verify guest with full data. (+3 more)

### Community 264 - "Community 264"
Cohesion: 0.13
Nodes (11): TestReservationModel, Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify can_transition_to method., Verify balance_due computed property., Verify nights calculation., Tests for Reservation model and state machine., Verify the state machine transition map is correct. (+3 more)

### Community 309 - "Community 309"
Cohesion: 0.17
Nodes (9): TestHotelConfigModel, Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies., Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper. (+1 more)

### Community 426 - "Community 426"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 620 - "Community 620"
Cohesion: 0.67
Nodes (3): _alembic(), test_migration_seeds_dedicated_permission_and_safe_role_defaults(), Regression coverage for the additive movement-group permission migration.

### Community 295 - "Community 295"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 133 - "Community 133"
Cohesion: 0.09
Nodes (20): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+12 more)

### Community 311 - "Community 311"
Cohesion: 0.26
Nodes (7): _reservation(), test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(), test_sweep_anchors_configured_no_show_window_to_hotel_checkin_time(), test_sweep_sql_cutoff_filter_matches_elapsed_utc_hours_across_dst(), test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(), test_sweep_excludes_checked_in_and_is_idempotent(), test_sweep_is_tenant_scoped()

### Community 367 - "Community 367"
Cohesion: 0.20
Nodes (9): test_normalizes_generated_instruction_paths_without_touching_external_paths(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized(), Regression coverage for portable Graphify artifact normalization., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+1 more)

### Community 395 - "Community 395"
Cohesion: 0.50
Nodes (8): _auth(), _client(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_push_subscription_register_and_unregister(), test_preferences_crud(), test_daily_report_schedule_is_owner_co_owner_only(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and

### Community 119 - "Community 119"
Cohesion: 0.15
Nodes (30): _hotel(), _member(), test_enqueue_dedupes_same_event_recipient_channel(), test_notification_inbox_event_waits_until_outbox_delivery(), test_enqueue_same_dedupe_key_isolated_per_hotel(), test_enqueue_skips_recipient_without_entity_read_permission(), test_enqueue_skips_recipient_without_active_membership(), test_enqueue_role_based_fanout() (+22 more)

### Community 571 - "Community 571"
Cohesion: 0.60
Nodes (4): _pending_push(), test_permanently_unavailable_push_is_terminal_on_postgres(), test_transient_push_error_keeps_retry_on_postgres(), PostgreSQL-backed delivery-state regression coverage for Web Push.

### Community 621 - "Community 621"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), test_process_outbox_delivers_across_every_active_hotel(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t

### Community 396 - "Community 396"
Cohesion: 0.50
Nodes (8): _owner(), _outbox_event_types(), test_reservation_lifecycle_enqueues_notifications(), test_no_show_enqueues_notification(), test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), Integration coverage: the real domain-event call sites (reservation lifecycle, c

### Community 244 - "Community 244"
Cohesion: 0.18
Nodes (11): _reserve(), test_reservation_spanning_the_window_is_returned_unclipped(), test_reservation_entirely_before_or_after_window_is_excluded(), test_cancelled_reservation_is_excluded(), test_checked_out_reservation_does_not_reduce_free_room_count(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(), test_custom_housekeeping_role_gets_anonymized_occupancy_grid() (+3 more)

### Community 572 - "Community 572"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 177 - "Community 177"
Cohesion: 0.25
Nodes (20): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_today_arrival_count_is_server_side_hotel_local_and_not_page_limited(), test_operational_daily_report_separates_no_shows_from_arrivals(), test_occupancy_report_counts_pre_check_in_reservations(), test_daily_report_is_hotel_scoped() (+12 more)

### Community 344 - "Community 344"
Cohesion: 0.25
Nodes (4): MemoryObjectStorage, _create_task_context(), test_task_photo_is_private_tenant_scoped_and_integrity_checked(), test_task_photo_timestamp_uses_local_business_date()

### Community 221 - "Community 221"
Cohesion: 0.21
Nodes (16): _user(), test_task_lifecycle_history_and_stale_version(), test_task_due_at_round_trips_as_hotel_local_wall_clock(), test_task_comment_appends_history_without_changing_task_status(), test_housekeeping_can_read_all_general_tasks_but_cannot_operate_them(), test_task_author_fallback_is_hotel_scoped_and_used_by_list_create_and_update(), test_task_create_does_not_commit_before_author_resolution(), test_task_author_without_hotel_membership_does_not_expose_global_profile() (+8 more)

### Community 345 - "Community 345"
Cohesion: 0.24
Nodes (9): _booking_cancel_payload(), _wait_for_blocking_backend(), test_ota_cancellation_waits_for_checkin_and_uses_committed_status(), test_ota_modification_locks_reservation_before_room_after_extension(), test_ota_cancellation_does_not_follow_cross_hotel_reservation_mapping(), PostgreSQL regression for OTA cancellation racing with check-in., Cancellation waits for check-in's reservation lock, then requires review., A modification waits for an extension's reservation lock before room selection. (+1 more)

### Community 278 - "Community 278"
Cohesion: 0.36
Nodes (12): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_modify_after_checkin_or_checkout_rejects_stay_or_room_changes(), test_booking_modify_after_checkin_preserves_room_for_same_stay_and_category(), test_booking_modify_rechecks_locked_room_and_falls_back_or_marks_conflict(), test_booking_modify_without_room_keeps_confirmed_stay_and_terms_unchanged(), test_booking_modify_rechecks_current_room_after_lock_and_reassigns_on_conflict() (+4 more)

### Community 202 - "Community 202"
Cohesion: 0.21
Nodes (18): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel() (+10 more)

### Community 510 - "Community 510"
Cohesion: 0.33
Nodes (4): TestOTARaceCondition, Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room.

### Community 235 - "Community 235"
Cohesion: 0.19
Nodes (9): _seed_hotel(), _assert_ota_payload_storage(), test_booking_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_ota_service_marks_unexpected_error_safely_before_caller_transaction_decision(), test_ota_webhook_returns_generic_500_for_unexpected_processing_error() (+1 more)

### Community 346 - "Community 346"
Cohesion: 0.53
Nodes (10): _load_migration(), _run(), _create_minimal_schema(), _manual_reference_index_sql(), test_payment_correction_migration_round_trips_when_history_is_empty(), test_payment_correction_upgrade_creates_target_index_when_legacy_index_is_missing(), test_payment_correction_upgrade_rejects_active_duplicates_before_schema_changes(), test_payment_correction_downgrade_preserves_schema_when_cancelled_duplicates_exist() (+2 more)

### Community 192 - "Community 192"
Cohesion: 0.20
Nodes (17): _GatewayResponse, _preference_identity(), _mock_revocation_http(), _reservation(), _link(), _management_member(), test_cancel_link_queues_only_payable_mercado_pago_preferences(), test_cancel_active_links_queues_revocation_for_eligible_links_only() (+9 more)

### Community 623 - "Community 623"
Cohesion: 0.67
Nodes (3): _load_migration(), test_migration_queues_only_legacy_open_mp_links_for_cancelled_reservations(), SQLite coverage for the legacy payment-link revocation backfill.

### Community 624 - "Community 624"
Cohesion: 0.50
Nodes (1): PostgreSQL coverage for exclusive provider-revocation work claims.

### Community 266 - "Community 266"
Cohesion: 0.15
Nodes (3): _HotelRowsQuery, _FakeSession, test_enabled_task_visits_active_and_inactive_hotels_under_each_context()

### Community 178 - "Community 178"
Cohesion: 0.17
Nodes (19): _enable_external_effects(), _reservation(), test_create_payment_link_persists_link_without_transaction(), test_local_payment_link_rejects_currency_different_from_reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp() (+11 more)

### Community 312 - "Community 312"
Cohesion: 0.29
Nodes (9): _signature(), _post(), test_unsigned_reference_status_and_money_do_not_override_provider_payment(), test_provider_amount_matches_cents_sent_for_payment_link_test(), test_older_provider_snapshot_cannot_regress_a_newer_payment_state(), test_unknown_provider_status_preserves_state_and_records_diagnostic(), test_retryable_provider_fetch_failure_returns_503(), test_unsigned_reference_cannot_redirect_signed_payment_to_another_test_record() (+1 more)

### Community 163 - "Community 163"
Cohesion: 0.15
Nodes (24): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_submit_transfer_proof_validates_image_and_stores_metadata(), test_concurrent_metadata_conflict_deletes_the_uncommitted_upload(), test_failed_commit_after_upload_rolls_back_metadata_and_deletes_object(), test_ambiguous_commit_that_persisted_proof_keeps_its_object(), test_submit_transfer_proof_reencodes_and_removes_exif() (+16 more)

### Community 511 - "Community 511"
Cohesion: 0.33
Nodes (6): ensure_category_pricing_table(), Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata).

### Community 236 - "Community 236"
Cohesion: 0.13
Nodes (15): opened_cash_register(), TestDepositPayment, Payment lifecycle tests explicitly model an operator-opened caja., Tests for deposit (señas) payment flow., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status →, Payment lifecycle tests explicitly model an operator-opened caja., Tests for deposit (señas) payment flow., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status → (+7 more)

### Community 427 - "Community 427"
Cohesion: 0.25
Nodes (4): _assign_hotel(), Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1).

### Community 512 - "Community 512"
Cohesion: 0.33
Nodes (5): Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING.

### Community 313 - "Community 313"
Cohesion: 0.18
Nodes (10): TestFullPayment, Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Tests for full payment flow., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid. (+2 more)

### Community 296 - "Community 296"
Cohesion: 0.15
Nodes (11): TestBalancePaymentAtCheckin, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Critical test: Simulates web booking with deposit, then balance payment at check (+3 more)

### Community 428 - "Community 428"
Cohesion: 0.25
Nodes (6): TestHotelIsolation, Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id.

### Community 193 - "Community 193"
Cohesion: 0.10
Nodes (10): TestPaymentEdgeCases, Edge case tests for the payment engine., Cannot pay more than the outstanding balance., Edge case tests for the payment engine., Cannot pay more than the outstanding balance., Edge case tests for the payment engine., Edge case tests for the payment engine., Cannot pay more than the outstanding balance. (+2 more)

### Community 429 - "Community 429"
Cohesion: 0.25
Nodes (7): Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation.

### Community 430 - "Community 430"
Cohesion: 0.25
Nodes (7): Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method.

### Community 431 - "Community 431"
Cohesion: 0.25
Nodes (7): Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials.

### Community 432 - "Community 432"
Cohesion: 0.25
Nodes (7): A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t

### Community 397 - "Community 397"
Cohesion: 0.22
Nodes (9): TestPaymentActorAudit, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered (+1 more)

### Community 398 - "Community 398"
Cohesion: 0.22
Nodes (8): A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl

### Community 314 - "Community 314"
Cohesion: 0.44
Nodes (9): _override_auth(), _build_client(), _cleanup(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_reactivate_deactivated_surcharge_via_patch(), test_payment_surcharge_quote_endpoint_returns_exact_maximum_and_cash_suggestion() (+1 more)

### Community 474 - "Community 474"
Cohesion: 0.43
Nodes (4): _reservation(), test_payment_link_webhook_uses_the_saved_fixed_surcharge_quote(), test_quote_chooses_maximum_tender_without_exceeding_balance_and_returns_cash_suggestion(), test_signed_payment_quote_keeps_previewed_fx_and_surcharge_when_rate_changes()

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (50): _reservation(), _link(), _provider_result(), _management_member(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key() (+42 more)

### Community 203 - "Community 203"
Cohesion: 0.16
Nodes (17): _seed_hotel(), test_company_night_rate_permission_defaults_allow_management_roles(), test_permission_override_can_deny_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_owner_override_can_grant_permission_missing_from_role_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_resolve_many_preserves_user_role_and_hotel_override_precedence(), test_resolve_many_preserves_legacy_deny_fallback_and_invariants() (+9 more)

### Community 93 - "Community 93"
Cohesion: 0.16
Nodes (36): _override_auth(), _step_up_headers(), _client_with_db(), _enable_whatsapp_plan_for_api_test(), test_permissions_matrix_available_to_permission_manager_only(), test_permissions_matrix_exposes_only_canonical_rows_with_ui_metadata(), test_revoking_each_section_view_permission_blocks_its_read_endpoint(), test_subscription_status_does_not_claim_active_when_source_is_unavailable() (+28 more)

### Community 245 - "Community 245"
Cohesion: 0.26
Nodes (11): _load_migration(), _Result, _RecordingBind, _uppercase_catalog(), test_upgrade_normalizes_only_remaining_enum_labels_and_is_idempotent(), test_downgrade_reverses_only_the_new_migration(), test_upgrade_fails_closed_if_both_enum_labels_exist(), test_upgrade_fails_closed_when_an_expected_label_is_missing() (+3 more)

### Community 104 - "Community 104"
Cohesion: 0.07
Nodes (32): _reset_pg_to_empty_schema(), _reset_pg_to_clean_head(), test_alembic_upgrade_on_empty_database(), test_alembic_downgrade_and_reupgrade(), test_numeric_precision_enforced_on_postgres(), test_enum_types_exist_in_postgres(), test_unique_constraints_enforced_on_postgres(), test_explain_analyze_guest_search_index() (+24 more)

### Community 99 - "Community 99"
Cohesion: 0.10
Nodes (31): _bootstrap_environment(), _provider_manifest(), _local_evidence_payload(), _safe_environment(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_remote_target_rejects_self_attested_json_without_signed_token() (+23 more)

### Community 170 - "Community 170"
Cohesion: 0.21
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 94 - "Community 94"
Cohesion: 0.11
Nodes (26): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+18 more)

### Community 246 - "Community 246"
Cohesion: 0.24
Nodes (15): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_rate_plan_price_extracts_included_taxes_and_fixed_fees(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(), test_all_supported_fx_pairs_use_directional_quotes_via_ars(), test_usd_conversion_uses_configured_side_per_direction_and_records_provenance() (+7 more)

### Community 279 - "Community 279"
Cohesion: 0.38
Nodes (13): _seed_hotel(), _seed_daily_rates(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_extracts_included_tax_from_daily_price(), test_canonical_promotion_pricing_converts_non_ars_currency_with_fx_snapshot() (+5 more)

### Community 247 - "Community 247"
Cohesion: 0.27
Nodes (14): _seed_hotel(), _ctx(), test_create_promotion_rejects_percentage_over_100(), test_create_promotion_rejects_duplicate_code(), test_find_applicable_promotions_matches_typed_conditions(), test_find_applicable_promotions_respects_weekday_and_date_range(), test_find_applicable_promotions_for_nights_batches_rules_and_guest_tags(), test_find_applicable_promotions_matches_guest_tag_type() (+6 more)

### Community 475 - "Community 475"
Cohesion: 0.71
Nodes (6): _override_auth(), _build_client(), _cleanup(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 134 - "Community 134"
Cohesion: 0.17
Nodes (21): manifest(), token_for(), env_page(), FakeRender, HealthResponse, FakeRenderCleanupFailure, FakeRenderPutResponseLost, _mutating_calls() (+13 more)

### Community 315 - "Community 315"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 222 - "Community 222"
Cohesion: 0.29
Nodes (16): _payload(), _configured_settings(), _inquiry_rows(), test_public_inquiry_persists_and_notifies_after_acceptance(), test_public_inquiry_keeps_record_when_notification_fails(), test_public_inquiry_rejects_invalid_required_fields(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_rate_limited_by_source_and_email() (+8 more)

### Community 182 - "Community 182"
Cohesion: 0.10
Nodes (6): _plan(), TestPublicPricing, TestLeadCapture, The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page., A deploy that has not run the migration yet must not 500 the page.

### Community 249 - "Community 249"
Cohesion: 0.23
Nodes (14): tagged(), write_fixture(), test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_unsigned_or_fabricated_attestation_is_rejected(), test_altered_signature_is_rejected(), test_signed_attestation_missing_a_summary_hash_is_rejected() (+6 more)

### Community 250 - "Community 250"
Cohesion: 0.45
Nodes (14): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+6 more)

### Community 251 - "Community 251"
Cohesion: 0.32
Nodes (14): seed_rate_context(), test_rate_draft_requires_confirmation_and_keeps_reservation_price(), test_rate_confirmation_rolls_back_business_change_if_audit_write_fails(), test_stale_rate_draft_cannot_overwrite_a_newer_rate(), test_rate_draft_is_tenant_scoped(), test_rate_draft_rejects_unsafe_fields_and_duplicate_dates(), _period_draft_payload(), _period_values() (+6 more)

### Community 625 - "Community 625"
Cohesion: 0.50
Nodes (4): test_verify_email_code_guessing_is_rate_limited(), Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re

### Community 626 - "Community 626"
Cohesion: 0.50
Nodes (4): test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate(), validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th

### Community 627 - "Community 627"
Cohesion: 0.50
Nodes (4): test_register_is_rate_limited_by_source(), Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun

### Community 628 - "Community 628"
Cohesion: 0.50
Nodes (4): test_concurrent_db_requests_record_each_attempt_before_deciding(), Concurrent attempts share the same budget instead of racing on a pre-count., Concurrent attempts share the same budget instead of racing on a pre-count., Concurrent attempts share the same budget instead of racing on a pre-count.

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (64): _client(), _close(), _patch_legacy_booking(), test_daily_rate_snapshot_retains_original_pricing_channel(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_company_terms_review_requires_reservation_read_even_for_company_managers(), test_reservation_responses_redact_guest_documents_without_guest_view_permission(), test_company_extension_request_records_only_request_metadata_and_audit() (+56 more)

### Community 135 - "Community 135"
Cohesion: 0.13
Nodes (20): FakeRedis, BrokenRedis, isolate_read_model_cache(), _cache_settings(), _reset_cache_client_state(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising() (+12 more)

### Community 399 - "Community 399"
Cohesion: 0.36
Nodes (6): _add_event(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_missing_or_zero_cursor_requires_full_refetch(), test_stale_cursor_requires_full_refetch(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch()

### Community 400 - "Community 400"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 183 - "Community 183"
Cohesion: 0.24
Nodes (17): iso(), write_bundle(), rewrite_summary(), rewrite_manifest(), errors_for(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_short_code_sha_is_rejected(), test_manifest_byte_hash_is_required() (+9 more)

### Community 514 - "Community 514"
Cohesion: 0.60
Nodes (5): _load_workflow(), _job_block(), test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes(), test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled(), Contracts for opting provider-bound PR evidence checks in by label.

### Community 574 - "Community 574"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 368 - "Community 368"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 105 - "Community 105"
Cohesion: 0.10
Nodes (29): test_overdue_checked_in_stay_is_a_serialized_manual_review_action(), test_pending_action_candidate_cap_does_not_hide_later_critical_action(), _mk_reservation(), test_completed_paid_amounts_group_net_completed_transactions_and_scope_hotel(), test_pending_action_adjustment_batch_omits_rows_that_cannot_create_actions(), test_cancelled_reservation_never_offers_collection_action(), test_cancelled_direct_booking_with_net_paid_amount_surfaces_manual_refund_review(), test_no_show_direct_booking_with_legacy_net_paid_amount_surfaces_manual_refund_review() (+21 more)

### Community 575 - "Community 575"
Cohesion: 0.60
Nodes (4): _load_migration(), _run(), test_cancellation_policy_snapshot_migration_is_nullable_reversible_and_does_not_backfill(), SQLite coverage for the reversible cancellation-policy snapshot column.

### Community 267 - "Community 267"
Cohesion: 0.30
Nodes (13): _auth(), cancellation_client(), _seed_reservation(), _set_now(), test_penalty_request_is_pending_idempotent_and_keeps_room_inventory(), test_legacy_bookings_cancel_route_uses_the_same_penalty_review_flow(), test_manager_approval_cancels_but_does_not_create_a_charge(), test_manager_rejection_leaves_reservation_active() (+5 more)

### Community 515 - "Community 515"
Cohesion: 0.53
Nodes (5): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_uses_reservation_currency_and_rejects_mismatch(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), Tests for operator-created reservation consumption charges.

### Community 369 - "Community 369"
Cohesion: 0.38
Nodes (9): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly(), test_invalid_recipient_is_rejected_before_provider(), test_local_example_test_address_is_accepted_but_never_forwarded(), test_production_rejects_example_test_recipient(), test_synthetic_email_does_not_expand_reservation_tenant_scope() (+1 more)

### Community 316 - "Community 316"
Cohesion: 0.39
Nodes (9): _seed_hotel(), _add_reservation(), _rows(), _step_up_headers(), test_reservation_export_requires_dedicated_permission(), test_reservation_export_uses_inclusive_occupancy_dates_and_hotel_scope(), test_reservation_export_neutralizes_formula_like_text(), test_reservation_export_rejects_invalid_and_overlong_date_ranges() (+1 more)

### Community 433 - "Community 433"
Cohesion: 0.25
Nodes (1): One operator-entered collection stays idempotent across grouped reservations.

### Community 516 - "Community 516"
Cohesion: 0.53
Nodes (5): _group_payloads(), test_create_four_room_company_group_and_aggregate_summary(), test_group_rejects_room_count_outside_bounds(), test_group_rejects_inconsistent_company_and_manual_totals(), Atomic multi-room reservation grouping and aggregate balance contracts.

### Community 347 - "Community 347"
Cohesion: 0.36
Nodes (10): _create_sample_reservation(), _completed_transaction(), test_no_show_can_be_marked_without_auto_charge(), test_date_change_without_payments_cancels_and_recreates(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_paid_date_change_refreshes_analytics_facts_once(), test_extension_requires_payment_or_link_action(), test_extension_rejects_checkout_not_after_current_checkout_in_spanish() (+2 more)

### Community 317 - "Community 317"
Cohesion: 0.26
Nodes (9): _make_reservations(), test_default_limit_caps_result_at_50(), test_skip_and_limit_page_through_results(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_listing_uses_one_scalar_reservation_query(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati (+1 more)

### Community 120 - "Community 120"
Cohesion: 0.27
Nodes (30): _override_auth(), _build_client(), _cleanup_client(), _seed_bookable_state(), _payload(), _manual_ota_payload(), test_receptionist_cannot_set_manual_total_amount(), test_co_owner_uses_confirmed_owner_level_manual_rate_access() (+22 more)

### Community 370 - "Community 370"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 576 - "Community 576"
Cohesion: 0.40
Nodes (5): test_move_reservation_room_updates_room_status_for_checked_in_reservation(), Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke

### Community 629 - "Community 629"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 577 - "Community 577"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_permission_defaults(), test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade(), SQLite round-trip for the configurable reservation price permission.

### Community 434 - "Community 434"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 476 - "Community 476"
Cohesion: 0.48
Nodes (6): _reservation(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty(), test_search_does_not_leak_across_hotels(), Tests for the reservation global search filter (B1 header search).  Search is a

### Community 519 - "Community 519"
Cohesion: 0.33
Nodes (4): TestConfirmationCode, Tests for confirmation code generation., Tests for confirmation code generation., Tests for confirmation code generation.

### Community 149 - "Community 149"
Cohesion: 0.07
Nodes (19): TestAvailability, Tests for room availability checking., A room with no reservations should be available., A room with an overlapping reservation should not be available., Check-out day == next check-in day should be allowed (no overlap)., Find available rooms after booking some., Availability checks must not eagerly load room reservation histories., Tests for room availability checking. (+11 more)

### Community 348 - "Community 348"
Cohesion: 0.18
Nodes (4): TestReservationCreation, Tests for reservation creation logic., Tests for reservation creation logic., Tests for reservation creation logic.

### Community 630 - "Community 630"
Cohesion: 0.50
Nodes (3): Create a standard reservation and verify computed fields., Create a standard reservation and verify computed fields., Create a standard reservation and verify computed fields.

### Community 578 - "Community 578"
Cohesion: 0.40
Nodes (4): B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto

### Community 579 - "Community 579"
Cohesion: 0.40
Nodes (4): Reserve a specific room., Reserve a specific room., Reserve a specific room., Reserve a specific room.

### Community 580 - "Community 580"
Cohesion: 0.40
Nodes (4): Should fail for non-existent guest., Should fail for non-existent guest., Should fail for non-existent guest., Should fail for non-existent guest.

### Community 517 - "Community 517"
Cohesion: 0.33
Nodes (5): Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in.

### Community 581 - "Community 581"
Cohesion: 0.40
Nodes (4): Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category.

### Community 518 - "Community 518"
Cohesion: 0.33
Nodes (5): Should fail when room doesn't match the requested category., Cannot book the same room for overlapping dates., Cannot book the same room for overlapping dates., Cannot book the same room for overlapping dates., Cannot book the same room for overlapping dates.

### Community 349 - "Community 349"
Cohesion: 0.18
Nodes (6): TestStateTransitions, Should fail for non-existent guest., Tests for reservation state machine transitions., Tests for reservation state machine transitions., Tests for reservation state machine transitions., Tests for reservation state machine transitions.

### Community 268 - "Community 268"
Cohesion: 0.27
Nodes (11): _RecordingSession, _install_recording_dependencies(), test_manual_total_update_mutation_and_audit_share_one_commit(), test_paid_total_adjustment_keeps_legacy_audit_key(), test_mutator_failure_propagates_without_audit_or_commit(), _authorization(), _reservation_for_preparation(), test_prepare_update_preserves_permission_and_financial_policy_order() (+3 more)

### Community 91 - "Community 91"
Cohesion: 0.09
Nodes (37): _role_connection(), _seed_engine(), _seed_session(), test_invitation_token_resolves_its_custom_role_under_forced_rls(), test_tenant_isolation_blocks_cross_hotel_reads(), test_payment_corrections_enforce_tenant_rls_for_read_and_write(), test_no_tenant_context_hides_all_rows(), test_master_admin_bypass_sees_all_hotels_subscriptions() (+29 more)

### Community 252 - "Community 252"
Cohesion: 0.31
Nodes (14): _seed_room_block_checkin_case(), _hold_room_for_checkin(), _wait_for_worker_blocked_by(), _start_block_mutation(), _cleanup_room_block_case(), test_postgres_create_block_rejects_existing_reservation_during_checkin(), test_postgres_extend_block_waits_for_checkin_then_rechecks_protected_reservation(), test_postgres_create_block_requires_allocation_proposal_to_clear_reservation() (+6 more)

### Community 211 - "Community 211"
Cohesion: 0.37
Nodes (18): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+10 more)

### Community 253 - "Community 253"
Cohesion: 0.31
Nodes (13): _override_auth(), _seed_room(), _seed_reservation(), test_create_and_resolve_room_block_api(), test_room_block_conflict_preview_returns_counts_without_reservation_identity(), test_room_block_conflict_preview_uses_create_permission_and_validates_dates(), test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(), test_room_block_extension_preview_and_mutation_keep_end_exclusive() (+5 more)

### Community 478 - "Community 478"
Cohesion: 0.29
Nodes (3): test_duplicate_room_number_returns_409(), Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro

### Community 212 - "Community 212"
Cohesion: 0.22
Nodes (15): _seed_move_shapes(), _move(), test_room_move_rejects_a_stale_reservation_version(), test_checked_in_room_move_returns_conflict_when_destination_checklist_is_open(), test_manager_can_override_open_checklist_for_checked_in_move_with_audited_reason(), test_reception_cannot_override_open_checklist_even_with_a_reason(), test_room_move_lock_conflict_returns_409_and_rolls_back(), test_receptionist_is_limited_to_same_category_moves() (+7 more)

### Community 371 - "Community 371"
Cohesion: 0.60
Nodes (9): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_receptionist_can_read_but_cannot_revert_room_movement_group(), test_explicit_receptionist_grant_can_revert_group(), test_company_group_revert_denies_reception_even_with_individual_company_manage_override(), test_housekeeping_cannot_read_or_revert_room_movement_group(), test_room_movement_group_cross_hotel_isolation() (+1 more)

### Community 318 - "Community 318"
Cohesion: 0.26
Nodes (10): _override_auth(), test_receptionist_can_list_rooms_without_loading_reservations(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_room_category_rates_are_batched_and_keep_daily_period_and_base_precedence(), test_custom_housekeeping_role_receives_safe_room_projection(), Reception needs to read room data to build reservations (room picker, availabili, GET /api/rooms/categories feeds the category picker on both the     Reservations (+2 more)

### Community 319 - "Community 319"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 583 - "Community 583"
Cohesion: 0.40
Nodes (5): test_company_night_charge_reservation_lock_targets_only_reservation(), Reservation has nullable joined relations, so payment locks must name the row., Reservation has nullable joined relations, so payment locks must name the row., Reservation has nullable joined relations, so payment locks must name the row., Reservation has nullable joined relations, so payment locks must name the row.

### Community 584 - "Community 584"
Cohesion: 0.40
Nodes (5): test_company_night_charge_billing_adjustment_lock_targets_only_adjustment(), BillingAdjustment also eager-loads optional relations used by night-charge corre, BillingAdjustment also eager-loads optional relations used by night-charge corre, BillingAdjustment also eager-loads optional relations used by night-charge corre, BillingAdjustment also eager-loads optional relations used by night-charge corre

### Community 585 - "Community 585"
Cohesion: 0.40
Nodes (5): test_company_night_charge_payment_path_uses_reservation_lock_target(), The payment helper must lock the reservation despite joined optional relations., The payment helper must lock the reservation despite joined optional relations., The payment helper must lock the reservation despite joined optional relations., The payment helper must lock the reservation despite joined optional relations.

### Community 631 - "Community 631"
Cohesion: 0.50
Nodes (4): test_forward_stale_tariff_quote_cannot_persist_reservation(), A tariff revision change invalidates the quote before any write., A tariff revision change invalidates the quote before any write., A tariff revision change invalidates the quote before any write.

### Community 254 - "Community 254"
Cohesion: 0.21
Nodes (14): _headers(), test_security_overview_and_events_are_redacted_and_tenant_scoped(), test_manager_cannot_read_security_settings(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv(), test_security_csv_treats_formula_prefixed_actor_alias_as_text(), test_audit_surfaces_do_not_expose_mutating_methods(), test_unified_audit_timeline_combines_sources_orders_redacts_and_isolates_tenant(), test_unified_audit_timeline_supports_inclusive_date_filters_and_role_guard() (+6 more)

### Community 520 - "Community 520"
Cohesion: 0.53
Nodes (4): _values(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_env_file_requires_owner_only_permissions()

### Community 150 - "Community 150"
Cohesion: 0.09
Nodes (10): Surface, _request_context(), _make_reservation(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _card_value(), _starter_analytics() (+2 more)

### Community 521 - "Community 521"
Cohesion: 0.53
Nodes (5): _migrate(), _unique_column_sets(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi

### Community 479 - "Community 479"
Cohesion: 0.43
Nodes (4): RecordingMailer, test_staff_welcome_notice_contains_access_details_without_capabilities(), test_staff_role_notice_names_the_hotel_and_both_roles(), test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details()

### Community 223 - "Community 223"
Cohesion: 0.27
Nodes (17): _override_auth(), _client_with_db(), _teardown(), _second_hotel(), test_owner_can_delete_item_and_recreate_it_with_the_same_name(), test_duplicate_active_name_returns_clean_409_not_a_500(), test_stock_item_unit_cost_is_exposed_on_create_and_update(), test_stock_item_full_edit_updates_name_sku_unit_and_min_quantity() (+9 more)

### Community 224 - "Community 224"
Cohesion: 0.27
Nodes (17): _seed_hotels(), _movement(), test_consumption_report_totals_and_variation_between_periods(), test_consumption_report_excludes_adjustments_and_location_transfers(), test_consumption_report_is_hotel_scoped(), test_consumption_report_variation_is_none_without_a_previous_baseline(), test_consumption_report_rejects_invalid_group_by(), test_consumption_report_rejects_inverted_range() (+9 more)

### Community 320 - "Community 320"
Cohesion: 0.52
Nodes (11): _override_auth(), _client_with_db(), _teardown(), _create_item(), _start_session(), test_count_recount_after_movement_and_manager_confirmation_are_atomic_and_idempotent(), test_count_confirmation_requires_configurable_permission_and_is_tenant_scoped(), test_count_session_rejects_overlapping_item_and_location_scopes() (+3 more)

### Community 632 - "Community 632"
Cohesion: 0.50
Nodes (3): test_confirmation_waits_for_inflight_movement_then_requires_recount(), PostgreSQL locking regression for stock-count confirmation., An in-flight movement cannot slip between stale-check and adjustment.

### Community 633 - "Community 633"
Cohesion: 0.50
Nodes (1): PostgreSQL-backed contract checks for stock movement idempotency.

### Community 70 - "Community 70"
Cohesion: 0.06
Nodes (50): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_stock_movement_rejects_precision_beyond_persisted_scale(), test_stock_movement_rejects_quantity_beyond_persisted_precision(), test_stock_outbound_cannot_make_quantity_negative(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(), test_stock_adjustment_can_correct_quantity_downward() (+42 more)

### Community 586 - "Community 586"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_transfer_schema(), test_stock_transfer_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for linked stock transfer movements.

### Community 480 - "Community 480"
Cohesion: 0.33
Nodes (2): _Session, test_subscription_session_closes_before_asgi_work()

### Community 522 - "Community 522"
Cohesion: 0.73
Nodes (5): _run_alembic(), _plan_values(), test_publishes_approved_prices_without_overwriting_admin_values(), test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(), test_price_migration_downgrade_restores_preexisting_currency_and_period()

### Community 204 - "Community 204"
Cohesion: 0.18
Nodes (16): _ensure_hotel(), _auth_headers(), _step_up_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_trial_does_not_replace_existing_legacy_paid_plan(), test_comped_override_requires_master_admin_session_before_disclosing_hotel_state(), test_role_gating_for_trial_and_comped_override() (+8 more)

### Community 587 - "Community 587"
Cohesion: 0.40
Nodes (5): test_ensure_subscription_rebuilds_a_missing_legacy_projection(), A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur

### Community 435 - "Community 435"
Cohesion: 0.32
Nodes (3): _direction(), test_direction_requires_matching_occupancy_and_pickup_signals(), test_marked_high_demand_event_always_points_up()

### Community 634 - "Community 634"
Cohesion: 0.67
Nodes (3): _index_names(), test_hot_path_composite_indexes_exist_in_models(), Focused regression tests for the TECH-0063 OLTP audit fixes.

### Community 125 - "Community 125"
Cohesion: 0.23
Nodes (27): _reservation_id(), _create_reservation(), _request(), _approve(), _set_cancel_permission(), _consume(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(), test_owner_can_view_and_revoke_active_grants_without_exposing_token() (+19 more)

### Community 436 - "Community 436"
Cohesion: 0.25
Nodes (3): test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(), C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them.

### Community 82 - "Community 82"
Cohesion: 0.07
Nodes (33): _load_rls_migration(), _load_user_override_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_company_night_charge_tenant_migration(), _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract(), test_tenant_composite_fk_migrations_cover_every_scoped_relationship() (+25 more)

### Community 136 - "Community 136"
Cohesion: 0.14
Nodes (18): iso(), evidence_bytes(), FakeGitHub, prepare(), test_trusted_prepare_and_finalize_accept_only_byte_identical_provider_artifact(), test_finalize_rejects_artifact_with_different_bytes(), test_prepare_rejects_release_change_after_qa_code_sha(), test_prepare_rejects_unsuccessful_provider_workflow() (+10 more)

### Community 225 - "Community 225"
Cohesion: 0.12
Nodes (5): _bearer_headers(), test_postgres_concurrent_refreshes_recover_the_same_successor(), test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_session_listing_individual_revoke_logout_and_revoke_all(), Real row locks serialize overlapping refreshes without losing the cookie.

### Community 67 - "Community 67"
Cohesion: 0.09
Nodes (18): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _http_request(), _make_reservation(), _make_transaction() (+10 more)

### Community 137 - "Community 137"
Cohesion: 0.09
Nodes (28): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_preserves_explicit_negotiated_nightly_rate(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price() (+20 more)

### Community 523 - "Community 523"
Cohesion: 0.33
Nodes (6): opened_cash_register(), Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja.

### Community 171 - "Community 171"
Cohesion: 0.16
Nodes (12): _make_reservation(), _pay_full(), TestCheckinRoomReadiness, Create a PENDING reservation using the first available category., Pay the full amount → FULLY_PAID., Create a PENDING reservation using the first available category., Final check-in requires an assigned, available, ready room., Create a PENDING reservation using the first available category. (+4 more)

### Community 151 - "Community 151"
Cohesion: 0.09
Nodes (15): _pay_deposit(), TestPaymentGateDepositPaid, Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.      Note, Final check-in requires an assigned, available, ready room., Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.      Note, Pay the full amount → FULLY_PAID., A legacy per-hotel setting cannot bypass the full-payment rule., Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.      Note (+7 more)

### Community 255 - "Community 255"
Cohesion: 0.13
Nodes (14): §7.1 positive: paying the remaining balance after deposit allows check-in., Cannot checkout a PENDING reservation., §7.1 positive: paying the remaining balance after deposit allows check-in., Cannot checkout a PENDING reservation., §7.1 positive: paying the remaining balance after deposit allows check-in., Cannot checkout a PENDING reservation., §7.1 positive: paying the remaining balance after deposit allows check-in., Cannot checkout a PENDING reservation. (+6 more)

### Community 172 - "Community 172"
Cohesion: 0.08
Nodes (21): TestPaymentGatePending, The error explains the full amount required by the default policy., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., The default full-payment policy blocks check-in without payment., The error explains the full amount required by the default policy., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., The default full-payment policy blocks check-in without payment., The error explains the full amount required by the default policy. (+13 more)

### Community 164 - "Community 164"
Cohesion: 0.08
Nodes (22): TestConfigFlag, Verify payment and guest-data gates remain separate., Guest data and the default full-payment gate remain independent., Even if document/terms config flags are disabled, payment gate remains active., Verify payment and guest-data gates remain separate., Guest data and the default full-payment gate remain independent., Even if documentterms config flags are disabled, payment gate remains active., Verify payment and guest-data gates remain separate. (+14 more)

### Community 184 - "Community 184"
Cohesion: 0.09
Nodes (20): TestGuestValidationGates, Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Separate coverage of document-not-verified vs terms-not-signed blocks. (+12 more)

### Community 437 - "Community 437"
Cohesion: 0.25
Nodes (7): Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False).

### Community 438 - "Community 438"
Cohesion: 0.25
Nodes (7): When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error.

### Community 439 - "Community 439"
Cohesion: 0.25
Nodes (7): When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error.

### Community 121 - "Community 121"
Cohesion: 0.08
Nodes (26): TestCheckoutGate, Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp., After checkout, the assigned room status is set to CLEANING., Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp. (+18 more)

### Community 401 - "Community 401"
Cohesion: 0.22
Nodes (8): A legacy per-hotel setting cannot bypass the full-payment rule., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in.

### Community 402 - "Community 402"
Cohesion: 0.22
Nodes (8): The default full-payment policy blocks check-in without payment., Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se

### Community 280 - "Community 280"
Cohesion: 0.26
Nodes (13): opened_cash_register(), _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains(), test_checkout_allows_deferred_company_balance_without_changing_financial_records(), test_checkout_still_blocks_company_without_deferred_payment_when_balance_remains() (+5 more)

### Community 269 - "Community 269"
Cohesion: 0.42
Nodes (12): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+4 more)

### Community 440 - "Community 440"
Cohesion: 0.25
Nodes (4): TestPricePeriodOverlap, V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai, Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics).

### Community 372 - "Community 372"
Cohesion: 0.22
Nodes (4): _make_period(), TestResolveRateCalendar, Tier-2: active PricePeriod used when no DailyRate exists., PricePeriod is NOT used for dates outside its range.

### Community 237 - "Community 237"
Cohesion: 0.12
Nodes (9): TestGetPriceForDate, Tier-1: explicit DailyRate row wins over everything else., DailyRate explicit row takes priority over an active PricePeriod., An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used. (+1 more)

### Community 321 - "Community 321"
Cohesion: 0.17
Nodes (6): TestApplyPricePeriod, apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price.

### Community 403 - "Community 403"
Cohesion: 0.22
Nodes (5): TestDailyRateModelConstraints, Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss.

### Community 481 - "Community 481"
Cohesion: 0.29
Nodes (4): TestPricePeriodModel, PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on

### Community 205 - "Community 205"
Cohesion: 0.18
Nodes (19): opened_cash_register(), _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_extension_impact_plan_is_read_only_and_contains_only_operational_fields(), test_extension_rejects_missing_confirmation_without_mutation() (+11 more)

### Community 140 - "Community 140"
Cohesion: 0.11
Nodes (16): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_manual_move_does_not_implicitly_lock_reservation(), test_edit_room_change_does_not_implicitly_lock_reservation(), test_owner_can_explicitly_lock_manual_room_assignment() (+8 more)

### Community 185 - "Community 185"
Cohesion: 0.12
Nodes (20): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_terminal_reservation_allows_only_arrival_metadata_and_audits_values(), test_update_mobility_restriction_triggers_reoptimization(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_room_move_allows_receptionist_within_the_same_category() (+12 more)

### Community 213 - "Community 213"
Cohesion: 0.19
Nodes (16): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_receptionist_can_list_movement_groups_but_cannot_revert_them(), test_housekeeping_cannot_list_read_or_revert_movement_groups(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_aborts_when_origin_room_lock_is_contended(), test_revert_group_service_conflict_does_not_overwrite_original_room() (+8 more)

### Community 373 - "Community 373"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 322 - "Community 322"
Cohesion: 0.17
Nodes (9): TestReoptimizationTrigger, §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the (+1 more)

### Community 281 - "Community 281"
Cohesion: 0.14
Nodes (9): TestReoptimizationIntegration, §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, The background task must commit and close its own DB session., If run_persisted_allocation raises, rollback must be called (not commit)., §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, The background task must commit and close its own DB session. (+1 more)

### Community 71 - "Community 71"
Cohesion: 0.05
Nodes (33): _make_reservation(), TestWaitlistModelFields, TestWaitlistListing, TestWaitlistResolveLogic, TestWaitlistIsolation, Helper — create a reservation through the service layer., The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room. (+25 more)

### Community 441 - "Community 441"
Cohesion: 0.25
Nodes (5): TestOverbookingBlocked, When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., Six physical Twin rooms hold six overlapping stays; the seventh is         rejec

### Community 404 - "Community 404"
Cohesion: 0.22
Nodes (7): TestWaitlistCreation, When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable.

### Community 350 - "Community 350"
Cohesion: 0.29
Nodes (6): _context(), _reserve(), _hotel_today(), test_visibility_window_filters_far_future_and_null_is_unlimited(), test_in_house_guest_remains_visible_when_check_in_predates_window(), Regression tests for tenant-scoped, per-role reservation visibility.

### Community 482 - "Community 482"
Cohesion: 0.48
Nodes (5): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation(), test_waitlist_suggestion_is_feasibility_only_and_does_not_promote(), test_waitlist_promotion_rejects_entry_changed_after_suggestion()

### Community 374 - "Community 374"
Cohesion: 0.38
Nodes (8): _hotel_id(), _race_two_sessions(), _seed_payment_target(), test_same_payment_webhook_is_idempotent_under_two_postgres_sessions(), test_distinct_payment_events_share_one_payment_and_transaction_under_postgres_lock(), test_same_ota_reservation_is_materialized_once_under_two_postgres_sessions(), Two-session idempotency regressions for inbound payment and OTA webhooks.  These, Hold the first real PostgreSQL lock until the second session is waiting.

### Community 524 - "Community 524"
Cohesion: 0.60
Nodes (5): _request(), test_rejects_oversized_content_length_before_reading_body(), test_rejects_chunked_body_that_exceeds_limit(), test_accepts_body_at_exact_limit(), test_rejects_malformed_content_length()

### Community 442 - "Community 442"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 375 - "Community 375"
Cohesion: 0.53
Nodes (8): _seed_hotel(), _issue_key(), _headers(), _whatsapp_quote(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

### Community 282 - "Community 282"
Cohesion: 0.31
Nodes (12): _signature(), _post(), _message(), _delivery(), test_rejects_a_delivery_whose_signature_does_not_match(), test_ingests_a_signed_inbound_message(), test_one_unusable_message_does_not_discard_the_rest_of_the_batch(), test_tolerates_a_payload_whose_nested_fields_are_not_objects() (+4 more)

### Community 747 - "Community 747"
Cohesion: 1.00
Nodes (1): Observe the exact PostgreSQL lock dependency, without SQL-text filters.

### Community 748 - "Community 748"
Cohesion: 1.00
Nodes (1): Hold the first real PostgreSQL lock until the second session is waiting.

### Community 746 - "Community 746"
Cohesion: 1.00
Nodes (1): Observe the exact PostgreSQL lock dependency, without SQL-text filters.

### Community 743 - "Community 743"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 739 - "Community 739"
Cohesion: 1.00
Nodes (1): A moved reservation is refreshed before check-in; a busy room returns a conflict

### Community 741 - "Community 741"
Cohesion: 1.00
Nodes (1): Checkout uses PostgreSQL NOWAIT while holding the reservation lock.

### Community 742 - "Community 742"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 738 - "Community 738"
Cohesion: 1.00
Nodes (1): A moved reservation is refreshed before check-in; a busy room returns a conflict

### Community 740 - "Community 740"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 745 - "Community 745"
Cohesion: 1.00
Nodes (1): Replace requests at the adapter boundary; never permit a real request.

### Community 744 - "Community 744"
Cohesion: 1.00
Nodes (1): Replace requests at the adapter boundary; never permit a real request.

### Community 733 - "Community 733"
Cohesion: 1.00
Nodes (1): An immutable view of the effective fields in a reservation PATCH.

### Community 734 - "Community 734"
Cohesion: 1.00
Nodes (1): Return operational fields blocked for a terminal reservation.          The two P

### Community 735 - "Community 735"
Cohesion: 1.00
Nodes (1): Classify a validated PATCH payload without changing the reservation.

## Knowledge Gaps
- **2726 isolated node(s):** `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.` (+2721 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 635`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 636`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 637`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 638`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 639`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 640`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 641`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 642`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 643`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 644`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 645`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 646`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 647`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 648`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 649`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 650`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 651`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 652`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 653`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 654`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 655`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 656`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 657`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 658`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 659`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 660`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 661`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 662`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 663`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 664`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 665`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 666`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 667`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 668`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 669`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 670`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 671`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 672`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 673`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 674`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 675`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 676`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 677`** (1 nodes): `Persist short-lived MFA step-up ticket use to prevent cross-worker replay.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 678`** (1 nodes): `Separate payment-proof reading/review from financial reports.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 679`** (1 nodes): `Add a dedicated permission for reverting room-movement groups.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 680`** (1 nodes): `Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 681`** (1 nodes): `Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 682`** (1 nodes): `Configure official or blue USD quotes by conversion direction.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 683`** (1 nodes): `Store external OTA payment amounts in their source currency.  Revision ID: 20261`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 684`** (1 nodes): `Record FX rounding credit and manual credit refunds separately.  Revision ID: 20`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 685`** (1 nodes): `Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 686`** (1 nodes): `Track Mercado Pago checkout revocation separately from local cancellation.  Revi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 687`** (1 nodes): `Track auditable voids for open-session cash corrections.  Revision ID: 20261024_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 688`** (1 nodes): `Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 689`** (1 nodes): `Add a dedicated permission for reading company vouchers and signatures.  Revisio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 690`** (1 nodes): `Add elevator knowledge and soft allocation preferences by room.  Revision ID: 20`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 691`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 692`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 693`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 694`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 695`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 696`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 697`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 698`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 699`** (1 nodes): `track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 700`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 701`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 702`** (1 nodes): `reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 703`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 713`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 714`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 715`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 718`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 217`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 239`** (2 nodes): `_normalize_currency()`, `HotelConfigUpdate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 550`** (1 nodes): `HotelIdentityPayload`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 717`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 704`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 706`** (1 nodes): `FakeResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 566`** (1 nodes): `TestGuestValidation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 469`** (1 nodes): `TestCheckIn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 471`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 613`** (1 nodes): `PostgreSQL regressions for exact non-cash FX settlement amounts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 618`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 708`** (2 nodes): `Verify the hotel has exactly 38 rooms.`, `Verify the hotel has exactly 38 rooms.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 709`** (2 nodes): `Same room_number can exist in different hotels without conflict.`, `Same room_number can exist in different hotels without conflict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 710`** (2 nodes): `Verify room string representation.`, `Verify room string representation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 624`** (1 nodes): `PostgreSQL coverage for exclusive provider-revocation work claims.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 400`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 433`** (1 nodes): `One operator-entered collection stays idempotent across grouped reservations.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 633`** (1 nodes): `PostgreSQL-backed contract checks for stock movement idempotency.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 480`** (2 nodes): `_Session`, `test_subscription_session_closes_before_asgi_work()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 747`** (1 nodes): `Observe the exact PostgreSQL lock dependency, without SQL-text filters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 748`** (1 nodes): `Hold the first real PostgreSQL lock until the second session is waiting.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 746`** (1 nodes): `Observe the exact PostgreSQL lock dependency, without SQL-text filters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 743`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 739`** (1 nodes): `A moved reservation is refreshed before check-in; a busy room returns a conflict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 741`** (1 nodes): `Checkout uses PostgreSQL NOWAIT while holding the reservation lock.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 742`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 738`** (1 nodes): `A moved reservation is refreshed before check-in; a busy room returns a conflict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 740`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 745`** (1 nodes): `Replace requests at the adapter boundary; never permit a real request.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 744`** (1 nodes): `Replace requests at the adapter boundary; never permit a real request.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 733`** (1 nodes): `An immutable view of the effective fields in a reservation PATCH.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 734`** (1 nodes): `Return operational fields blocked for a terminal reservation.          The two P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 735`** (1 nodes): `Classify a validated PATCH payload without changing the reservation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 17` to `Community 497`, `Community 12`, `Community 1`, `Community 76`, `Community 100`, `Community 145`, `Community 116`, `Community 146`, `Community 228`, `Community 47`, `Community 123`, `Community 8`, `Community 45`, `Community 28`, `Community 257`, `Community 2`, `Community 59`, `Community 15`, `Community 10`, `Community 83`, `Community 9`, `Community 16`, `Community 301`, `Community 0`, `Community 229`, `Community 88`, `Community 57`, `Community 36`, `Community 5`, `Community 19`, `Community 14`, `Community 89`, `Community 26`, `Community 60`, `Community 499`, `Community 55`, `Community 179`, `Community 64`, `Community 217`, `Community 58`, `Community 38`, `Community 29`, `Community 30`, `Community 53`, `Community 167`, `Community 61`, `Community 4`, `Community 32`, `Community 74`, `Community 272`, `Community 84`, `Community 329`, `Community 3`, `Community 6`, `Community 68`, `Community 168`, `Community 97`, `Community 416`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 0` to `Community 2`, `Community 10`, `Community 45`, `Community 18`, `Community 19`, `Community 35`, `Community 8`, `Community 22`, `Community 95`, `Community 5`, `Community 145`, `Community 1`, `Community 17`, `Community 83`, `Community 416`, `Community 47`, `Community 257`, `Community 28`, `Community 9`, `Community 16`, `Community 103`, `Community 4`, `Community 61`, `Community 62`, `Community 33`, `Community 60`, `Community 359`, `Community 64`, `Community 155`, `Community 152`, `Community 30`, `Community 84`, `Community 29`, `Community 75`, `Community 68`, `Community 190`, `Community 15`, `Community 59`, `Community 361`, `Community 58`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 16` to `Community 2`, `Community 10`, `Community 88`, `Community 9`, `Community 29`, `Community 8`, `Community 58`, `Community 38`, `Community 1`, `Community 17`, `Community 83`, `Community 47`, `Community 257`, `Community 45`, `Community 103`, `Community 57`, `Community 155`, `Community 0`, `Community 152`, `Community 62`, `Community 30`, `Community 167`, `Community 81`, `Community 61`, `Community 44`, `Community 84`, `Community 32`, `Community 233`, `Community 462`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 1519 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Reservation` has 1519 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1442 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`HotelConfiguration` has 1442 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1403 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`ReservationStatusEnum` has 1403 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1139 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Room` has 1139 INFERRED edges - model-reasoned connections that need verification._