# Graph Report - .  (2026-11-09)

## Corpus Check
- Large corpus: 1959 files · ~2,667,524 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 16111 nodes · 61386 edges · 841 communities detected
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output
- Edge kinds: ON_BRANCH: 30000 · contains: 10902 · calls: 8287 · MODIFIES: 4119 · rationale_for: 2173 · imports: 1887 · imports_from: 1543 · inherits: 1053 · method: 965 · PARENT_OF: 449 · re_exports: 4 · reads_from: 4


## Input Scope
- Requested: auto
- Resolved: committed (source: default-auto)
- Included files: 1959 · Candidates: 2150
- Excluded: 0 untracked · 1913 ignored · 15 sensitive · 0 missing committed
- Recommendation: Use --scope all or graphify.yaml inputs.corpus for a knowledge-base folder.

## Graph Freshness
- Built from Git commit: `9702c0f`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `useSession()` - 78 edges
2. `_client()` - 61 edges
3. `_close()` - 61 edges
4. `hasValidSession()` - 59 edges
5. `apiFetch()` - 56 edges
6. `SessionLike` - 52 edges
7. `ApiError` - 52 edges
8. `useGuardedMutation()` - 42 edges
9. `GemmaService` - 35 edges
10. `BookingAdapter` - 34 edges

## Surprising Connections (you probably didn't know these)
- `login()` --calls--> `_build_login_response()`  [EXTRACTED]
  frontend/src/api/auth.ts → app/api/auth.py
- `register()` --calls--> `_burn_auth_timing_work()`  [EXTRACTED]
  frontend/src/api/auth.ts → app/api/auth.py
- `register()` --calls--> `_issue_email_token()`  [EXTRACTED]
  frontend/src/api/auth.ts → app/api/auth.py
- `register()` --calls--> `_request_source()`  [EXTRACTED]
  frontend/src/api/auth.ts → app/api/auth.py
- `A hotel operator explicitly enters the destination for this receipt.` --rationale_for--> `PaymentReceiptEmailRequest`  [EXTRACTED]
  app/api/payments.py → frontend/src/api/payments.ts

## Communities

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (143): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Read and resolve the guest room-rejection lifecycle., Staff management endpoints for hotel public API keys. (+135 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (275): hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house, _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, Separate historical cash receipts from the active drawer and seed access.  Revis, Add a dedicated permission for recording OTA reservations.  Revision ID: 2026092 (+267 more)

### Community 733 - "Community 733"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 498 - "Community 498"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table.

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (191): Publish owner-approved monthly subscription prices.  Revision ID: 11be7c9387c4 R, persist missing linen declared on laundry return slips  Revision ID: 20261005_la, Add request correlation keys to durable realtime events.  Revision ID: 20261007_, Notify active PostgreSQL listeners when durable domain events commit.  Revision, Persist idempotent payment receipt email outcomes.  Revision ID: 20261016_paymen, Add a tenant-isolated SQL queue for reservation fact refreshes., Track neutral supplier follow-up for declared laundry shortages.  Revision ID: 2, merge domain event migration branches  Revision ID: 3942765e8560 Revises: 202610 (+183 more)

### Community 734 - "Community 734"
Cohesion: 0.50
Nodes (1): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho

### Community 735 - "Community 735"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 736 - "Community 736"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 669 - "Community 669"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 737 - "Community 737"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 738 - "Community 738"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 739 - "Community 739"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 740 - "Community 740"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 741 - "Community 741"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 742 - "Community 742"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 743 - "Community 743"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 744 - "Community 744"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 561 - "Community 561"
Cohesion: 0.48
Nodes (5): _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260

### Community 670 - "Community 670"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 745 - "Community 745"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 746 - "Community 746"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 747 - "Community 747"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 748 - "Community 748"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 749 - "Community 749"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 750 - "Community 750"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 605 - "Community 605"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 751 - "Community 751"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 752 - "Community 752"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 753 - "Community 753"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 754 - "Community 754"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 755 - "Community 755"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 756 - "Community 756"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 757 - "Community 757"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 758 - "Community 758"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 759 - "Community 759"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 760 - "Community 760"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 761 - "Community 761"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 762 - "Community 762"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 763 - "Community 763"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 764 - "Community 764"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 765 - "Community 765"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 499 - "Community 499"
Cohesion: 0.46
Nodes (7): _sqlite_rebuild_constraints(), _repair_sqlite(), _existing_enum_labels(), _rename_postgres_enum_values(), upgrade(), downgrade(), Align allocation enum storage with the model values.  The original allocation mi

### Community 562 - "Community 562"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat

### Community 606 - "Community 606"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), _drop_successor_reference(), upgrade(), downgrade(), Add zero-balance cash rotation and custody handoffs.

### Community 607 - "Community 607"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio

### Community 608 - "Community 608"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Complete tenant-leading foreign keys outside the core booking domain.  The core

### Community 766 - "Community 766"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 767 - "Community 767"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 563 - "Community 563"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all

### Community 500 - "Community 500"
Cohesion: 0.36
Nodes (6): _has_unique(), _has_fk(), _add_constraint_if_missing(), upgrade(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in

### Community 768 - "Community 768"
Cohesion: 0.50
Nodes (1): Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re

### Community 769 - "Community 769"
Cohesion: 0.50
Nodes (1): Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for

### Community 671 - "Community 671"
Cohesion: 0.60
Nodes (4): _constraint(), upgrade(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could

### Community 770 - "Community 770"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 771 - "Community 771"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 426 - "Community 426"
Cohesion: 0.31
Nodes (9): upgrade(), _create_linen_tables(), _migrate_linen_data(), _finalize_laundry_vendor_columns(), _drop_kind_column(), downgrade(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li (+1 more)

### Community 772 - "Community 772"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 773 - "Community 773"
Cohesion: 0.50
Nodes (1): stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision

### Community 774 - "Community 774"
Cohesion: 0.50
Nodes (1): add external-effect mode to payment links  Revision ID: 20260812_external_effect

### Community 306 - "Community 306"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), _install_rls(), _remove_rls(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), upgrade(), downgrade(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill (+5 more)

### Community 326 - "Community 326"
Cohesion: 0.24
Nodes (12): _insert_permission_rows(), _upsert_default(), _backfill_defaults(), _copy_role_overrides(), upgrade(), _install_user_override_rls(), _remove_user_override_rls(), _contract_legacy_rows() (+4 more)

### Community 501 - "Community 501"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 502 - "Community 502"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table.

### Community 775 - "Community 775"
Cohesion: 0.50
Nodes (1): repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/

### Community 776 - "Community 776"
Cohesion: 0.50
Nodes (1): add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide

### Community 777 - "Community 777"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 503 - "Community 503"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state.

### Community 778 - "Community 778"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 672 - "Community 672"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), upgrade(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima

### Community 779 - "Community 779"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 780 - "Community 780"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 781 - "Community 781"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 782 - "Community 782"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 564 - "Community 564"
Cohesion: 0.52
Nodes (6): _columns(), _decode(), _backfill_authoritative_values(), upgrade(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea

### Community 609 - "Community 609"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), seed section visibility permissions and their role defaults  Revision ID: 202608

### Community 148 - "Community 148"
Cohesion: 0.09
Nodes (17): store public marketing inquiries and notification state  Revision ID: 20260828_p, _pg_cron_migration_enabled(), _secure_marketing_leads(), upgrade(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role., Public marketing inquiries submitted through the website., publicSiteBaseURL (+9 more)

### Community 565 - "Community 565"
Cohesion: 0.57
Nodes (6): _index_map(), _ensure_index(), _drop_index_if_present(), upgrade(), downgrade(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar

### Community 610 - "Community 610"
Cohesion: 0.60
Nodes (5): _has_table(), _has_column(), upgrade(), downgrade(), Fold legacy category pricing into seasonal price periods.

### Community 611 - "Community 611"
Cohesion: 0.60
Nodes (5): _set_role_default(), _restore_session_permission(), upgrade(), downgrade(), Align section defaults and remove the self-session catalog permission.  Revision

### Community 783 - "Community 783"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 427 - "Community 427"
Cohesion: 0.29
Nodes (9): _install_rls(), _remove_rls(), _insert_permission_rows(), _insert_default_rows(), upgrade(), downgrade(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects. (+1 more)

### Community 612 - "Community 612"
Cohesion: 0.47
Nodes (5): _set_role_default(), upgrade(), downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns.

### Community 613 - "Community 613"
Cohesion: 0.47
Nodes (4): _insert_permission_rows(), _insert_default_rows(), upgrade(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083

### Community 504 - "Community 504"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add durable realtime domain event outbox  Revision ID: 20260901_domain_event_out, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 673 - "Community 673"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), Add the per-hotel application interface language.  The existing ``languages`` co

### Community 674 - "Community 674"
Cohesion: 0.50
Nodes (3): _columns(), upgrade(), Move payment-proof bytes off Postgres, into object storage.  `payment_proof_blob

### Community 784 - "Community 784"
Cohesion: 0.50
Nodes (1): Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  `

### Community 461 - "Community 461"
Cohesion: 0.42
Nodes (8): _columns(), _indexes(), _create_index_if_missing(), _drop_index_if_present(), _seed_audit_permission(), upgrade(), downgrade(), Operational audit fields, daily cash indexes, and audit read permission.

### Community 785 - "Community 785"
Cohesion: 0.50
Nodes (1): add public marketing pricing plans and early-access leads  Revision ID: 20260910

### Community 566 - "Community 566"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op

### Community 567 - "Community 567"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat

### Community 568 - "Community 568"
Cohesion: 0.43
Nodes (6): _enum(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what

### Community 675 - "Community 675"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), upgrade(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs

### Community 676 - "Community 676"
Cohesion: 0.50
Nodes (3): _columns(), upgrade(), Add hotel-scoped staff aliases and password-login capability state.  Revision ID

### Community 21 - "Community 21"
Cohesion: 0.03
Nodes (53): Persist short-lived MFA step-up ticket use to prevent cross-worker replay., Tenant-scoped replay ledger for MFA step-up tickets., HotelMembership, HotelMembership model: many-to-many between users and hotels with roles. Roles:, Tenant-scoped custom roles layered over a built-in permission profile., Per-role reservation visibility windows for one hotel., StepUpTicketAction, permissions_requiring_step_up() (+45 more)

### Community 505 - "Community 505"
Cohesion: 0.36
Nodes (7): _install_rls(), _remove_rls(), _assert_downgrade_lossless(), upgrade(), downgrade(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins.

### Community 569 - "Community 569"
Cohesion: 0.48
Nodes (6): _enum_labels(), _quote_identifier(), _rename_enum_labels(), upgrade(), downgrade(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:

### Community 428 - "Community 428"
Cohesion: 0.40
Nodes (9): _cron_is_required(), _create_and_secure_retention_holds(), _upgrade_sqlite(), _downgrade_sqlite(), _install_purge_function(), _reschedule_purge_job(), upgrade(), downgrade() (+1 more)

### Community 614 - "Community 614"
Cohesion: 0.53
Nodes (5): _has_columns(), _indexes(), upgrade(), downgrade(), Add check-in policy, manual receipt references, and auditable refunds.

### Community 462 - "Community 462"
Cohesion: 0.50
Nodes (8): _has_columns(), _set_global_role_defaults(), _set_manager_operational_defaults(), _set_housekeeping_whatsapp_defaults(), _backfill_external_ota_credits(), upgrade(), downgrade(), Backfill legacy OTA credits and operational role defaults.  This data migration

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (38): Separate payment-proof reading/review from financial reports.  Revision ID: 2026, _log_ota_processing_failure(), _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), _guarded_json_payload(), FastAPI Webhook endpoints for OTA integrations. (+30 more)

### Community 23 - "Community 23"
Cohesion: 0.03
Nodes (27): Restrict direct execution of the Supabase RLS DDL event trigger.  Revision ID: 2, spreadsheet_safe_value(), spreadsheet_safe_row(), Spreadsheet-safe serialization helpers for user-controlled CSV cells., Prefix formula-like text so spreadsheet software treats it as text., Apply formula protection consistently to every text cell in a CSV row., FakeTicketRedis, collaboration_client() (+19 more)

### Community 786 - "Community 786"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reverting room-movement groups.  Revision ID: 202

### Community 677 - "Community 677"
Cohesion: 0.60
Nodes (4): _install_purge_function(), upgrade(), downgrade(), Backfill the public inquiry retention clock and update the purge function.  Revi

### Community 787 - "Community 787"
Cohesion: 0.50
Nodes (1): Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026

### Community 615 - "Community 615"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), Add tenant-scoped groups for multi-room reservations.

### Community 788 - "Community 788"
Cohesion: 0.50
Nodes (1): Add an index for tenant-scoped outbox cursor recovery polling.  Revision ID: 202

### Community 570 - "Community 570"
Cohesion: 0.43
Nodes (5): _has_unique(), _has_fk(), _enable_tenant_rls(), upgrade(), Harden company nightly charge tenant keys and row level security.

### Community 789 - "Community 789"
Cohesion: 0.50
Nodes (1): Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv

### Community 790 - "Community 790"
Cohesion: 0.50
Nodes (1): Configure official or blue USD quotes by conversion direction.  Revision ID: 202

### Community 616 - "Community 616"
Cohesion: 0.47
Nodes (4): _existing_table_matches(), _install_tenant_rls(), upgrade(), Persist the local synthetic hotel business date.  Revision ID: 20261017_local_bu

### Community 791 - "Community 791"
Cohesion: 0.50
Nodes (1): Store external OTA payment amounts in their source currency.  Revision ID: 20261

### Community 792 - "Community 792"
Cohesion: 0.50
Nodes (1): Add the corporate channel to the analytics fact enum.  Reservation.channel_code

### Community 793 - "Community 793"
Cohesion: 0.50
Nodes (1): Persist configurable deposit bands and stay-night counts.  Revision ID: 20261018

### Community 794 - "Community 794"
Cohesion: 0.50
Nodes (1): Record FX rounding credit and manual credit refunds separately.  Revision ID: 20

### Community 795 - "Community 795"
Cohesion: 0.50
Nodes (1): Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_

### Community 796 - "Community 796"
Cohesion: 0.50
Nodes (1): Track Mercado Pago checkout revocation separately from local cancellation.  Revi

### Community 617 - "Community 617"
Cohesion: 0.47
Nodes (4): _add_transaction_columns_and_check(), _add_group_batch_columns_and_check(), upgrade(), Persist cash received, change, and explicitly retained tip separately.  Revision

### Community 678 - "Community 678"
Cohesion: 0.50
Nodes (3): _enable_tenant_rls(), upgrade(), Persist fixed post-checkout housekeeping checklists.  Revision ID: 20261023_hous

### Community 388 - "Community 388"
Cohesion: 0.31
Nodes (10): _manual_reference_index_exists(), _assert_manual_reference_keys_unique(), _replace_manual_reference_index(), _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Add auditable, idempotent payment corrections.  Revision ID: 20261024_atomic_pay (+2 more)

### Community 797 - "Community 797"
Cohesion: 0.50
Nodes (1): Track auditable voids for open-session cash corrections.  Revision ID: 20261024_

### Community 798 - "Community 798"
Cohesion: 0.50
Nodes (1): Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:

### Community 799 - "Community 799"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reading company vouchers and signatures.  Revisio

### Community 618 - "Community 618"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Snapshot corporate terms per reservation and audit manager review.  Revision ID:

### Community 571 - "Community 571"
Cohesion: 0.43
Nodes (6): _install_tenant_rls(), _remove_tenant_rls(), _status_check(), upgrade(), downgrade(), Add tenant-scoped per-guest arrival records and hotel status policy.  Revision I

### Community 619 - "Community 619"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Track laundry remito discrepancies and explicit linen retirements.  Revision ID:

### Community 620 - "Community 620"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Add audited cancellation review queue and approval permission.  Revision ID: 202

### Community 621 - "Community 621"
Cohesion: 0.47
Nodes (5): _install_tenant_rls(), _remove_tenant_rls(), upgrade(), downgrade(), Persist general stock counts and require audited approval before adjustment.  Re

### Community 800 - "Community 800"
Cohesion: 0.50
Nodes (1): Add the keyset pagination index for WhatsApp message history.  Revision ID: 2026

### Community 801 - "Community 801"
Cohesion: 0.50
Nodes (1): Add elevator knowledge and soft allocation preferences by room.  Revision ID: 20

### Community 622 - "Community 622"
Cohesion: 0.47
Nodes (5): _install_history_rls(), _remove_history_rls(), upgrade(), downgrade(), Store comparable published-rate history and pilot recommendation settings.  Revi

### Community 802 - "Community 802"
Cohesion: 0.50
Nodes (1): Persist the latest shared DolarAPI rates for bounded outage fallback.  Revision

### Community 803 - "Community 803"
Cohesion: 0.50
Nodes (1): Persist authorized manual FX payment amounts per reservation.  Revision ID: 2026

### Community 506 - "Community 506"
Cohesion: 0.39
Nodes (7): _columns_to_change(), _assert_prices_fit_cents(), _change_column_types(), upgrade(), downgrade(), Store active nightly and seasonal rate prices as exact cents.  Revision ID: 2026, Refuse silent rounding or overflow before converting existing prices.

### Community 804 - "Community 804"
Cohesion: 0.50
Nodes (1): Record cash change currency and support paired cash movement corrections.  Revis

### Community 40 - "Community 40"
Cohesion: 0.06
Nodes (37): Queue manual room-allocation runs instead of blocking the API request.  Revision, receptionist, AllocationObjective, AllocationPolicyVersion, ActiveAllocationPolicy, AllocationPolicyVersionCreate, AllocationExplanation, AllocationAssignment (+29 more)

### Community 507 - "Community 507"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table.

### Community 623 - "Community 623"
Cohesion: 0.40
Nodes (4): _restore_reservations_hotel_index(), downgrade(), sync_model_drift_missing_columns  Revision ID: 3eaf48a79290 Revises: 20260419_on, Restore the legacy index even if a later downgrade already did so.

### Community 624 - "Community 624"
Cohesion: 0.47
Nodes (5): upgrade(), downgrade(), _install_rls(), _remove_rls(), linen location par levels  Revision ID: 41d66acfb13a Revises: 015f7e36b9cd Creat

### Community 805 - "Community 805"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 806 - "Community 806"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 679 - "Community 679"
Cohesion: 0.60
Nodes (4): _check_clause(), upgrade(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in

### Community 807 - "Community 807"
Cohesion: 0.50
Nodes (1): add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op

### Community 808 - "Community 808"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 508 - "Community 508"
Cohesion: 0.46
Nodes (7): _user_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _alter_user_column(), upgrade(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2

### Community 809 - "Community 809"
Cohesion: 0.50
Nodes (1): laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre

### Community 509 - "Community 509"
Cohesion: 0.46
Nodes (7): _hotel_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _replace_fk(), upgrade(), downgrade(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs.

### Community 810 - "Community 810"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 811 - "Community 811"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 812 - "Community 812"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 813 - "Community 813"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 814 - "Community 814"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 815 - "Community 815"
Cohesion: 0.50
Nodes (1): track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca

### Community 816 - "Community 816"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 817 - "Community 817"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 463 - "Community 463"
Cohesion: 0.33
Nodes (8): _install_rls(), _remove_rls(), _assert_no_duplicate_remitos(), _guard_day2_downgrade_data(), upgrade(), downgrade(), Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, a, Refuse rollback when it would discard operational data or session state.

### Community 680 - "Community 680"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 625 - "Community 625"
Cohesion: 0.47
Nodes (4): _utcnow(), _seed_ota_providers(), upgrade(), ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l

### Community 818 - "Community 818"
Cohesion: 0.50
Nodes (1): laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7

### Community 510 - "Community 510"
Cohesion: 0.39
Nodes (7): _has_unique(), _ensure_subscription_composite_target(), _install_rls(), _remove_rls(), upgrade(), downgrade(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b

### Community 819 - "Community 819"
Cohesion: 0.50
Nodes (1): reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202

### Community 820 - "Community 820"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 626 - "Community 626"
Cohesion: 0.60
Nodes (5): _policy_name(), _quoted_table(), upgrade(), downgrade(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL

### Community 572 - "Community 572"
Cohesion: 0.43
Nodes (6): _event_id_type(), _install_rls(), _remove_rls(), upgrade(), downgrade(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i

### Community 681 - "Community 681"
Cohesion: 0.50
Nodes (3): _rls(), upgrade(), Add durable job dedupe and worker heartbeat metadata.

### Community 821 - "Community 821"
Cohesion: 0.50
Nodes (1): Add tenant-scoped object metadata without deleting legacy file references.

### Community 394 - "Community 394"
Cohesion: 0.24
Nodes (3): _render_service_block(), _env_value(), test_render_pool_budget_is_bounded_for_one_api_and_one_cron()

### Community 170 - "Community 170"
Cohesion: 0.10
Nodes (9): CacheStore, Protocol, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, AnalyticsAIProvider, _DeferredCompanyReservation, RenderRequester (+1 more)

### Community 389 - "Community 389"
Cohesion: 0.24
Nodes (6): JobSpec, JobDispatcher, CeleryJobDispatcher, dispatch_once(), Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica

### Community 327 - "Community 327"
Cohesion: 0.20
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process fields delivered by a Mercado Pago callback without querying         the

### Community 289 - "Community 289"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 511 - "Community 511"
Cohesion: 0.52
Nodes (1): SimpleRateLimiter

### Community 512 - "Community 512"
Cohesion: 0.29
Nodes (3): Telemetry, LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default.

### Community 182 - "Community 182"
Cohesion: 0.19
Nodes (18): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+10 more)

### Community 108 - "Community 108"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_png(), export_analytics_csv(), export_analytics_xlsx()

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (121): _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _attach_user_session_cookies(), _audit_security_event(), _issue_auth_response(), _build_login_response() (+113 more)

### Community 154 - "Community 154"
Cohesion: 0.14
Nodes (23): _booking_status_label_es(), _require_demo_mode(), _ensure_subscription_active(), _ensure_permission_tier(), _is_manager_context(), _booking_to_read(), _project_booking_graph(), availability() (+15 more)

### Community 109 - "Community 109"
Cohesion: 0.11
Nodes (21): _close_report_read(), _cash_expense_read(), _csv_local_datetime(), _csv_local_date(), _csv_decimal(), _require_cash_difference_approval_when_requested(), export_cash_ledger_csv(), latest_cash_close_report() (+13 more)

### Community 330 - "Community 330"
Cohesion: 0.26
Nodes (9): CheckInRequest, _reservation_read(), _authorize_override(), checkin(), checkin_guest(), checkin_partial(), checkout(), FastAPI routes for Check-in / Check-out. (+1 more)

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (450): BaseModel, VendorCreate, VendorUpdate, VendorRead, VendorPriceUpsert, VendorPriceRead, RemitoLineIn, RemitoCreate (+442 more)

### Community 70 - "Community 70"
Cohesion: 0.08
Nodes (35): _ticket_key(), _store_process_ticket(), _require_permission(), _require_resource_lane(), _realtime_client_or_503(), create_collaboration_ticket(), _patch_conflict_response(), patch_collaborative_resource() (+27 more)

### Community 360 - "Community 360"
Cohesion: 0.33
Nodes (3): _RoomTransport, CollaborationManager, Process-local peers plus best-effort Redis pub/sub fan-out.

### Community 128 - "Community 128"
Cohesion: 0.09
Nodes (9): FastAPI routes for the commercial configuration domain., TaxRule, TaxPolicy, TaxPolicyWrite, listTaxPolicies(), createTaxPolicy(), updateTaxPolicy(), RuleDraft (+1 more)

### Community 30 - "Community 30"
Cohesion: 0.05
Nodes (54): CompanyOptionRead, get_company_hotel_currency(), get_company_options(), Return only the hotel's configured currency for company screens., Return only the names needed to link a reservation to a company., Company, CompanyPayload, CompanyOption (+46 more)

### Community 361 - "Community 361"
Cohesion: 0.22
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (29): _reject_direct_rate_write(), DailyRateOut, Config, DailyRateFallbackOut, PaymentMethodOptionsOut, DailyRateIn, BulkRateIn, BulkFieldRateIn (+21 more)

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (89): _require_demo_mode(), seed_demo(), reset_demo(), Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard demo mutations behind both an approved runtime and an explicit flag., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Settings (+81 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (91): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, Category, listCategories(), SessionLike (+83 more)

### Community 106 - "Community 106"
Cohesion: 0.08
Nodes (14): _fx_display_quote_status(), FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, FxConversionQuoteRequest, FxConversionQuoteRead, get_all_rates() (+6 more)

### Community 212 - "Community 212"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 391 - "Community 391"
Cohesion: 0.29
Nodes (9): _restriction_error_detail(), _get_tenant_guest(), list_active_restriction_guest_ids(), create_restriction(), list_restrictions(), resolve_restriction(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of (+1 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (101): _guest_service_error_detail(), _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), get_guest_quick_profile(), get_guest_tags(), create_guest_tag(), resolve_tag() (+93 more)

### Community 331 - "Community 331"
Cohesion: 0.30
Nodes (11): _database_healthcheck(), _postgres_healthcheck(), _redis_healthcheck(), _critical_lock_readiness(), live_healthcheck(), ready_healthcheck(), _clickhouse_healthcheck(), datastores_healthcheck() (+3 more)

### Community 52 - "Community 52"
Cohesion: 0.08
Nodes (39): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _reject_generic_whatsapp_mutation(), _store_oauth_code() (+31 more)

### Community 80 - "Community 80"
Cohesion: 0.11
Nodes (35): _source_key(), _available_invitation(), _activate_invitation_for_user(), InvitationTokenPayload, _raise_preview_error(), get_invitation_preview(), AcceptPayload, LoginRequest (+27 more)

### Community 196 - "Community 196"
Cohesion: 0.11
Nodes (9): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryStatus, LaundryItem (+1 more)

### Community 392 - "Community 392"
Cohesion: 0.38
Nodes (9): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+1 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (75): _schedule_to_read(), get_daily_report_schedule(), update_daily_report_schedule(), FastAPI routes for the notification backend: inbox, push subscriptions, preferen, ownerCredentials, ownerCredentials, receptionistCredentials, NotificationSeverity (+67 more)

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (45): FastAPI routes for the onboarding flow used by smoke tests., requestVerification(), verifyEmail(), DepositPolicyRule, DepositPolicyRules, OnboardingProviderSetup, OnboardingStatus, OnboardingSubscription (+37 more)

### Community 183 - "Community 183"
Cohesion: 0.21
Nodes (17): _can(), _is_operator_scoped(), _can_read_reservation_context(), _report_type_allowed(), _conflict(), get_operational_tasks(), create_operational_task(), patch_operational_task() (+9 more)

### Community 184 - "Community 184"
Cohesion: 0.12
Nodes (15): _has_per_method_nightly_price(), PaymentSurchargeRead, PaymentSurchargeCreate, PaymentSurchargeUpdate, _get_surcharge_or_404(), quote_payment_surcharge(), create_manual_fx_quote(), get_manual_fx_quote() (+7 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (132): PaymentReceiptEmailRequest, correct_payment_transaction(), payment_receipt_data(), download_payment_receipt_pdf(), email_payment_receipt(), FastAPI routes for Payments., A hotel operator explicitly enters the destination for this receipt., Reverse a mistaken ledger entry and optionally reassign its payment. (+124 more)

### Community 27 - "Community 27"
Cohesion: 0.04
Nodes (56): consume_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Retired: grants are consumed only inside their protected action., BuiltinPermissionRole, PermissionRole, PermissionCatalogItem, PermissionDetail, PermissionCell (+48 more)

### Community 393 - "Community 393"
Cohesion: 0.33
Nodes (10): _temporary_grant_actor(), _temporary_grant_response(), _raise_temporary_grant_http_error(), create_temporary_action_grant(), read_pending_temporary_action_grants(), read_active_temporary_action_grants(), approve_temporary_action_grant(), deny_temporary_action_grant() (+2 more)

### Community 176 - "Community 176"
Cohesion: 0.15
Nodes (21): _validate_role(), _validate_code(), _assert_role_profile_mutation_allowed(), _target_membership_or_404(), _assert_manageable_membership(), _update_role_override(), update_permission_override(), _visibility_window_response() (+13 more)

### Community 50 - "Community 50"
Cohesion: 0.06
Nodes (33): update_promotion(), simulate_promotion_pricing(), Promotions API (v72 mobile-first pricing/promotions task).  CRUD for versioned,, Creates a new immutable version; the previous version is deactivated.     Reserv, Return which promotions would apply and the resulting price breakdown     for a, PromotionBenefitType, PromotionScope, PromotionConditions (+25 more)

### Community 290 - "Community 290"
Cohesion: 0.18
Nodes (8): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status(), Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by id (v72 §16).      Scoped to the API key

### Community 823 - "Community 823"
Cohesion: 0.67
Nodes (1): Public contact form endpoint for the marketing site.

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (99): TariffRecommendationSettings, TariffRecommendationSettingsOut, TariffRecommendationRunIn, TariffRecommendationRunOut, _settings_out(), read_settings(), update_settings(), generate_recommendation() (+91 more)

### Community 291 - "Community 291"
Cohesion: 0.24
Nodes (12): RateChangeItemIn, RateChangeDraftIn, RateChangeDecisionIn, RateChangeDraftEditIn, RateChangeDraftOut, _raise_draft_http(), _safe_rollback(), create_draft() (+4 more)

### Community 515 - "Community 515"
Cohesion: 0.29
Nodes (6): ReferenceCountry, list_timezones(), list_countries(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog., Return the curated country -> primary IANA timezone catalog.

### Community 31 - "Community 31"
Cohesion: 0.05
Nodes (51): daily_report(), occupancy_report(), revenue_report(), booked_value_report(), _safe_csv_cell(), export_revenue_report_csv(), FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c (+43 more)

### Community 4 - "Community 4"
Cohesion: 0.01
Nodes (224): _company_terms_review_response(), read_company_terms_review(), decide_company_terms_review(), _reservation_status_label_es(), _can_view_guest_documents(), _to_read(), _is_manager_context(), _ensure_manual_rate_permission() (+216 more)

### Community 171 - "Community 171"
Cohesion: 0.14
Nodes (21): RoleCatalogItem, RoleListResponse, RoleResponse, CreateCustomRoleRequest, RenameCustomRoleRequest, ArchiveCustomRoleRequest, _role_item(), _rollback_and_raise() (+13 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (125): _require_manager_room_lane(), RoomStatusUpdate, _serialize_reallocation_result(), _validate_room_allocation_preferences(), _attach_current_rate(), _housekeeping_room(), get_category(), create_room() (+117 more)

### Community 265 - "Community 265"
Cohesion: 0.21
Nodes (14): _current_user(), _safe_resource_id(), _validate_audit_timeline_range(), _build_audit_timeline_csv(), _attach_actor_names(), security_overview(), recent_security_events(), audit_timeline() (+6 more)

### Community 18 - "Community 18"
Cohesion: 0.03
Nodes (61): _ensure_adjustment_permission(), StockItemCreate, StockItemUpdate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementCreate, StockMovementRead (+53 more)

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (27): _remaining_trial_days(), _require_master_admin_write(), _master_admin_hotel_id(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial(), upsert_entitlement_override() (+19 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (45): _assert_assignable_role(), _assert_manageable_membership(), _assert_manageable_role(), _membership_user_info(), _membership_for_invitation(), list_users(), InvitePayload, InviteResponse (+37 more)

### Community 138 - "Community 138"
Cohesion: 0.10
Nodes (15): API routes for reservation waitlist operations., WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload, WaitlistPromoteResponse, WaitlistPromotionSuggestion, listWaitlistEntries() (+7 more)

### Community 266 - "Community 266"
Cohesion: 0.27
Nodes (14): _require_plan(), _conversation_access_scope(), channel_status(), complete_channel(), inbox(), conversation_messages(), send_message(), create_note() (+6 more)

### Community 465 - "Community 465"
Cohesion: 0.25
Nodes (1): Public WhatsApp bot hooks authenticated only by hotel API key.

### Community 857 - "Community 857"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 858 - "Community 858"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 308 - "Community 308"
Cohesion: 0.22
Nodes (9): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change() (+1 more)

### Community 859 - "Community 859"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 517 - "Community 517"
Cohesion: 0.38
Nodes (6): PublicAPIContext, get_public_api_context(), require_public_api_purpose(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val

### Community 64 - "Community 64"
Cohesion: 0.08
Nodes (37): AuthContext, _parse_header_hotel_id(), _parse_token_hotel_id(), _decode_authorization_header(), _authenticate_user(), _resolve_membership(), get_auth_context(), _action_step_up_tickets() (+29 more)

### Community 365 - "Community 365"
Cohesion: 0.24
Nodes (10): redis_namespace(), namespaced_key(), _client_signature(), get_sync_redis_client(), get_async_redis_client(), reset_clients(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Return a process-local sync client, or None for empty configuration.      The op (+2 more)

### Community 864 - "Community 864"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 433 - "Community 433"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 229 - "Community 229"
Cohesion: 0.21
Nodes (13): MasterEmailConnectionError, _dev_outbox_path(), _record_dev_email(), SystemEmailStatus, _normalize_account_email(), _sender_parts(), _build_unavailable_message(), _current_status() (+5 more)

### Community 140 - "Community 140"
Cohesion: 0.13
Nodes (24): RuntimeError, ExternalEffectsDisabled, DolarApiRatesDisabled, InboundProviderEventsDisabled, GoogleLoginDisabled, AppleLoginDisabled, external_effects_enabled(), inbound_provider_events_enabled() (+16 more)

### Community 16 - "Community 16"
Cohesion: 0.02
Nodes (97): MasterAdminSession, Base, MasterAdminAuditEvent, MasterAdminAuthLockout, PrivacyRetentionHold, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings (+89 more)

### Community 166 - "Community 166"
Cohesion: 0.13
Nodes (16): _validate_case_reference(), RetentionHoldCreate, RetentionHoldRelease, RetentionTargetSearch, RetentionHoldRead, RetentionTargetRead, PublicInquiryRead, _lock_hold_table_for_write() (+8 more)

### Community 129 - "Community 129"
Cohesion: 0.09
Nodes (7): _serialize_user(), login(), complete_mfa_login(), me(), dashboard_summary(), put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi

### Community 54 - "Community 54"
Cohesion: 0.10
Nodes (40): MasterAdminContext, _now(), _as_aware(), _hash_value(), _normalize_identifier(), _normalize_pin(), _normalize_http_origin(), _require_master_admin_origin() (+32 more)

### Community 366 - "Community 366"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 269 - "Community 269"
Cohesion: 0.13
Nodes (14): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, ReservationAllocationLock (+6 more)

### Community 25 - "Community 25"
Cohesion: 0.03
Nodes (65): str, CashSessionStatusEnum, CashMovementTypeEnum, CashCustodyStatusEnum, CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac (+57 more)

### Community 198 - "Community 198"
Cohesion: 0.11
Nodes (17): AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, AnalyticsExportStatusEnum, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsExportJob, AnalyticsAIUsageMonthly, AnalyticsFactRefreshJob (+9 more)

### Community 51 - "Community 51"
Cohesion: 0.04
Nodes (33): AuditActionEnum, AuditLog, Tenant-scoped audit log for tracking mutations across core tables. Every write t, Append-only record of every significant mutation within a hotel tenant.     Do N, CashExpenseStatusEnum, CashExpense, Hotel-scoped manual cash expenses awaiting explicit approval., A proposed drawer expense; approved expenses create one cash movement. (+25 more)

### Community 690 - "Community 690"
Cohesion: 0.50
Nodes (3): HotelBusinessClock, Opt-in local business date for one synthetic hotel., Persist the latest simulated business date for a single hotel.      The row is i

### Community 831 - "Community 831"
Cohesion: 0.67
Nodes (2): CashSession, Single currency-specific cash-register shift. A hotel may keep one open     sess

### Community 830 - "Community 830"
Cohesion: 0.67
Nodes (2): CashMovement, Individual money movement within an open cash session.     Linked optionally to

### Community 522 - "Community 522"
Cohesion: 0.29
Nodes (4): CashCloseReport, Arqueo de caja: expected vs actual cash at session close.     Differences are fl, Currency of the cash session represented by this close report., Opening float recorded for the next session, when one exists.

### Community 691 - "Community 691"
Cohesion: 0.50
Nodes (2): Connection, Connection model for external provider integrations. Stores credentials/settings

### Community 832 - "Community 832"
Cohesion: 0.67
Nodes (2): DailyRate, Explicit nightly price for a specific category and date.

### Community 833 - "Community 833"
Cohesion: 0.67
Nodes (2): PricePeriod, Named date-range season/period for bulk rate loading.      Higher ``priority`` w

### Community 631 - "Community 631"
Cohesion: 0.40
Nodes (3): DomainEventOutbox, Durable, tenant-scoped outbox for realtime domain invalidations.  The row is com, One durable delivery attempt for one hotel/domain invalidation.

### Community 834 - "Community 834"
Cohesion: 0.67
Nodes (2): DomainEventRetentionWatermark, Tenant-scoped cursor watermarks used by outbox retention cleanup.

### Community 576 - "Community 576"
Cohesion: 0.33
Nodes (3): Guest, Primary guest record. Contains all fields required for check-in     and legal co, Check if guest has provided required identity documents for check-in.

### Community 577 - "Community 577"
Cohesion: 0.33
Nodes (4): APIKeyPurposeEnum, HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia, Per-hotel API credential. `key_hash` stores a hashed version of the secret;

### Community 434 - "Community 434"
Cohesion: 0.22
Nodes (5): HotelConfiguration, Configuration table scoped by hotel (id == hotel_id)., Parse and return extra_policies as a dictionary., Serialize policies dict to JSON string., Check if a specific payment method is enabled.

### Community 523 - "Community 523"
Cohesion: 0.29
Nodes (6): HousekeepingChecklistStatusEnum, HousekeepingChecklistItemCodeEnum, HousekeepingChecklist, HousekeepingChecklistItem, Fixed, auditable housekeeping checklists created at reservation checkout., Stable item codes consumed by the housekeeping API and frontend.

### Community 692 - "Community 692"
Cohesion: 0.50
Nodes (2): StaffInvitation, Persisted staff invitations and their one-time acceptance state.

### Community 693 - "Community 693"
Cohesion: 0.50
Nodes (3): LaundryBatch, LaundryItem, Laundry operations models.

### Community 632 - "Community 632"
Cohesion: 0.40
Nodes (4): LaundryRemitoDiscrepancy, LaundryDiscrepancyAction, Auditable custody records for linen differences reported on laundry remitos.  Di, Immutable action history and hotel-scoped idempotency for discrepancy decisions.

### Community 524 - "Community 524"
Cohesion: 0.29
Nodes (6): LinenItem, LinenLocation, LinenMovement, LinenParLevel, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Configured minimum quantity for one linen item at one hotel location.

### Community 525 - "Community 525"
Cohesion: 0.29
Nodes (5): MarketingPricingPlan, MarketingLead, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, Someone who asked for access from the public site.      Email is unique so a rep

### Community 247 - "Community 247"
Cohesion: 0.13
Nodes (14): NotificationSeverityEnum, NotificationChannelEnum, NotificationOutboxStatusEnum, Notification, PushSubscription, NotificationPreference, NotificationOutbox, DailyReportSchedule (+6 more)

### Community 215 - "Community 215"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 309 - "Community 309"
Cohesion: 0.15
Nodes (11): ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum, RoomMoveTypeEnum, BillingAdjustmentTypeEnum, ReservationAdjustment, RoomMovementGroup, RoomMoveEvent, BillingAdjustment (+3 more)

### Community 435 - "Community 435"
Cohesion: 0.22
Nodes (6): OTASyncStatusEnum, OTAReservationMapping, OTAWebhookCredential, OTA (Online Travel Agency) reservation mapping. Tracks the link between external, Maps an external OTA reservation to an internal reservation.     Stores the raw, Per-hotel OTA webhook credential. The secret is stored as a hash so the     raw

### Community 835 - "Community 835"
Cohesion: 0.67
Nodes (1): PaymentLinkTest

### Community 526 - "Community 526"
Cohesion: 0.29
Nodes (6): PaymentProofStatusEnum, PaymentProof, PaymentProofBlob, Manual bank-transfer evidence and approval lifecycle., Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata.

### Community 694 - "Community 694"
Cohesion: 0.50
Nodes (2): CategoryPricing, Archived legacy pricing shape kept for migration/test compatibility.      Runtim

### Community 471 - "Community 471"
Cohesion: 0.25
Nodes (5): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl

### Community 695 - "Community 695"
Cohesion: 0.50
Nodes (3): PublishedRateHistory, Auditable facts for category rates that were explicitly published., One confirmed base rate per category and stay date.      USD values are populate

### Community 836 - "Community 836"
Cohesion: 0.67
Nodes (2): RateLimitEvent, Persistent rate-limit events for security-sensitive endpoints.

### Community 527 - "Community 527"
Cohesion: 0.29
Nodes (5): RefundPathEnum, RefundStatusEnum, RefundRequest, RefundRequest model — tracks the three-path refund lifecycle per product §8.7., Tracks a refund from request through resolution.     Partial refunds are allowed

### Community 397 - "Community 397"
Cohesion: 0.20
Nodes (5): Reservation, Core reservation entity.     Tracks the full lifecycle from booking to checkout,, Outstanding balance on the reservation., Number of nights for the stay., Check if a state transition is valid.

### Community 528 - "Community 528"
Cohesion: 0.29
Nodes (5): ReservationEmailKindEnum, ReservationEmailStatusEnum, ReservationEmailDelivery, Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m

### Community 398 - "Community 398"
Cohesion: 0.20
Nodes (7): RoomStatusEnum, RoomHousekeepingStatusEnum, RoomCategory, Room, Room and RoomCategory models., Room category/type â€” e.g. Standard, Superior, Suite, Penthouse., Physical room in the hotel.

### Community 529 - "Community 529"
Cohesion: 0.29
Nodes (4): RoomBlockReasonEnum, RoomBlock, RoomBlock — date-ranged blocks on a specific room (v72 §14). Blocks affect avail, Date-ranged block on a room. NULL ends_at means indefinite.     resolved_at popu

### Community 837 - "Community 837"
Cohesion: 0.67
Nodes (2): SecurityAuditLog, Security / access audit log — free-form operational security events.  Distinct f

### Community 436 - "Community 436"
Cohesion: 0.22
Nodes (8): StockItem, StockLocation, StockMovement, StockCountSession, StockCountLine, Stock and inventory movement models., Hotel-scoped physical count awaiting authorized confirmation., One observed quantity for an item, either hotel-wide or by location.

### Community 472 - "Community 472"
Cohesion: 0.25
Nodes (7): SubscriptionPlan, HotelSubscription, SubscriptionEntitlement, HotelEntitlementOverride, Subscription models: plans and per-hotel subscription status., Entitlement linked to a subscription plan (e.g., room limits, feature toggles)., Per-hotel entitlement override to tweak limits/features without cloning plans.

### Community 530 - "Community 530"
Cohesion: 0.29
Nodes (5): Subscription, SubscriptionEvent, SubscriptionAdjustment, Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table

### Community 838 - "Community 838"
Cohesion: 0.67
Nodes (2): Transaction, Financial transaction linked to a reservation.     Every money movement is recor

### Community 697 - "Community 697"
Cohesion: 0.50
Nodes (2): User, User accounts for authentication. Stores hashed passwords and basic profile flag

### Community 696 - "Community 696"
Cohesion: 0.50
Nodes (3): UserMfaSecret, UserMfaRecoveryCode, TOTP MFA secrets and one-time recovery codes for normal user accounts.

### Community 437 - "Community 437"
Cohesion: 0.22
Nodes (6): VoucherStatusEnum, HotelVoucher, VoucherRedemption, Hotel voucher (credit) models — refund path 2 per product §8.7.  A HotelVoucher, Hotel credit issued to a guest (typically as a refund alternative).     The code, Records each partial or full redemption of a HotelVoucher on a reservation.

### Community 578 - "Community 578"
Cohesion: 0.33
Nodes (4): WaitlistStatusEnum, WaitlistEntry, Waitlist / overbooking list model — v72 §9.  When the hotel is at capacity for a, Single guest waiting for a room in a given category for a date range.     Priori

### Community 230 - "Community 230"
Cohesion: 0.12
Nodes (15): WhatsAppChannelStatusEnum, WhatsAppConversationStatusEnum, WhatsAppMessageDirectionEnum, WhatsAppMessageStatusEnum, WhatsAppChannel, WhatsAppProviderRoute, WhatsAppContact, WhatsAppConversation (+7 more)

### Community 395 - "Community 395"
Cohesion: 0.20
Nodes (8): CancellationReviewRead, ReservationCancellationResponse, ReservationRead, BookingCancellationResponse, BookingRead, CancellationReviewDecisionRequest, CancellationReviewResolutionResponse, Transport contracts for manual reservation cancellation review.

### Community 121 - "Community 121"
Cohesion: 0.10
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 473 - "Community 473"
Cohesion: 0.29
Nodes (6): DepositPolicyRule, validate_deposit_policy_rules(), normalize_deposit_policy_rules(), Validated, ordered deposit rules shared by onboarding and hotel settings., Rule applies through ``max_nights``; ``None`` means no upper bound.      Rules a, Return JSON-ready rules, mapping legacy percentage settings safely.

### Community 438 - "Community 438"
Cohesion: 0.33
Nodes (8): GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead, Pydantic schemas for Guest and companions.

### Community 248 - "Community 248"
Cohesion: 0.13
Nodes (2): _normalize_currency(), HotelConfigUpdate

### Community 633 - "Community 633"
Cohesion: 0.40
Nodes (1): HotelIdentityPayload

### Community 579 - "Community 579"
Cohesion: 0.33
Nodes (1): ManualOTAReservationCreate

### Community 439 - "Community 439"
Cohesion: 0.22
Nodes (5): PaymentSurchargeQuoteRequest, ManualFxPaymentQuoteCreate, PaymentSurchargeQuoteRead, Validated payment-surcharge quote contracts., Authorized reservation-specific FX amount after automatic quotes expire.

### Community 295 - "Community 295"
Cohesion: 0.16
Nodes (9): mask_to_weekdays(), PromotionConditions, PromotionCreate, PromotionUpdate, PromotionRead, PromotionSimulateRequest, Pydantic schemas for the Promotion CRUD API and the simulation endpoint., Typed condition set. Every field is a wildcard when omitted/None. (+1 more)

### Community 311 - "Community 311"
Cohesion: 0.19
Nodes (6): _clean_required(), _clean_optional(), PublicInquiryCreate, PublicInquiryAccepted, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 399 - "Community 399"
Cohesion: 0.20
Nodes (5): ReservationGroupPaymentAllocationRequest, ReservationGroupPaymentCreate, ReservationGroupPaymentAllocationRead, ReservationGroupPaymentRead, Request and read contracts for one group collection with child allocations.

### Community 699 - "Community 699"
Cohesion: 0.50
Nodes (2): ReservationChargeCreate, Operator-created consumption or extra charge for an active stay.

### Community 634 - "Community 634"
Cohesion: 0.40
Nodes (2): PaymentCorrectionRequest, Reverse an erroneous payment record and optionally reassign it.

### Community 580 - "Community 580"
Cohesion: 0.33
Nodes (2): PaymentRequest, Client-facing payment request (e.g. from booking cart).

### Community 532 - "Community 532"
Cohesion: 0.33
Nodes (4): ChatMessage, ChatCompletionRequest, chat_completions(), _extract_latest_user_message()

### Community 441 - "Community 441"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, repair_cash_handoff_schema(), missing_model_tables(), main(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it.

### Community 701 - "Community 701"
Cohesion: 0.50
Nodes (3): resolve_hotel_actor_labels(), Tenant-scoped actor display labels for operational read projections., Resolve current per-hotel aliases, falling back to email, in bounded batches.

### Community 81 - "Community 81"
Cohesion: 0.08
Nodes (31): ReservationSlot, RoomSlot, _reservation_indexes_by_horizon_day(), AllocationResult, _check_overlap(), _overlapping_reservation_pairs(), _one_night_gap_penalty_for_room(), _adjacency_bonus_for_room() (+23 more)

### Community 186 - "Community 186"
Cohesion: 0.14
Nodes (18): AllocationError, Exception, apply_allocation_result(), Custom exception for allocation engine errors., Apply the solver's assignments to the database.     Updates room_id on each rese, ConnectionError, _validate_payload(), upsert_connection() (+10 more)

### Community 638 - "Community 638"
Cohesion: 0.60
Nodes (4): AllocationQuestionnaireDraft, AllocationFeedbackDraft, draft_policy_from_questionnaire(), draft_policy_from_feedback()

### Community 199 - "Community 199"
Cohesion: 0.22
Nodes (15): AllocationPolicySettings, AllocationPolicyError, ensure_default_policy_profile(), ensure_default_policy_version(), get_active_policy_settings(), list_policy_versions(), create_policy_version(), publish_policy_version() (+7 more)

### Community 59 - "Community 59"
Cohesion: 0.12
Nodes (37): ValueError, redact_integration_error(), _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload() (+29 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (34): AllocationRuntimeError, PersistedAllocationResult, AllocationRunDetails, reservation_overlaps_default_horizon(), run_persisted_allocation(), _primary_objective_label(), _lock_and_validate_initial_assignments(), _active_policy_version_id_for_acceptance() (+26 more)

### Community 185 - "Community 185"
Cohesion: 0.15
Nodes (19): AllocationRequestInProgress, pending_allocation_stale_after(), _pending_proposal_query(), fail_stale_pending_allocation_requests(), _request_allocation_proposal(), request_manual_allocation(), reservation_overlaps_allocation_horizon(), request_reservation_created_allocation() (+11 more)

### Community 95 - "Community 95"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, GemmaProvider (+12 more)

### Community 110 - "Community 110"
Cohesion: 0.15
Nodes (28): ComparisonWindow, ComparisonState, MonetaryTotals, ReservationNightFactDraft, RoomOccupancyNightFactDraft, infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code() (+20 more)

### Community 45 - "Community 45"
Cohesion: 0.07
Nodes (46): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _xml_10_text(), _iter_export_payload_rows(), _is_row_collection(), _flatten_payload_rows() (+38 more)

### Community 76 - "Community 76"
Cohesion: 0.10
Nodes (33): NoShowDetectionResult, _load_category_cost_rows(), FactRefreshResult, detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), touch_reservation_fact_window(), touch_room_state_event_fact_window() (+25 more)

### Community 312 - "Community 312"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 122 - "Community 122"
Cohesion: 0.14
Nodes (23): _hotel_local_now(), _plan_rank(), require_analytics_plan(), _serialize_company(), _serialize_alert_settings(), _serialize_alert_snooze(), _record_audit_event(), record_hotel_audit_event() (+15 more)

### Community 702 - "Community 702"
Cohesion: 0.50
Nodes (2): _MappedQueryRows, Re-iterable, bounded-memory projection over a SQLAlchemy query.

### Community 157 - "Community 157"
Cohesion: 0.16
Nodes (24): DateWindow, _now(), _ensure_utc(), _utc_date_range(), _analytics_window(), _comparison_read(), metric_card(), _serialize_room_state_event() (+16 more)

### Community 270 - "Community 270"
Cohesion: 0.23
Nodes (15): _facts_data_as_of(), _money(), get_company_fact_detail(), _company_reservation_read(), _sum_money(), _currency_unavailable_for(), _currency_unavailable_aggregate(), _reservation_fact_breakdown() (+7 more)

### Community 296 - "Community 296"
Cohesion: 0.20
Nodes (14): _money_str(), _company_fact_read(), _group_rows(), _room_lookup_map(), _load_room_facts(), _unavailable_currencies(), _unavailable_currency_metadata(), _room_detail_fact_read() (+6 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (32): AnalyticsWarehouseUnavailable, ReconciliationResult, WarehouseSyncResult, FactReconciliationResult, _settings(), _required(), _validate_hotel_id(), _date_value() (+24 more)

### Community 400 - "Community 400"
Cohesion: 0.29
Nodes (8): AppleTokenError, verify_apple_id_token(), _read_private_key(), create_apple_client_secret(), exchange_apple_code(), Apple OIDC verification and authorization-code helpers.  The identity token is a, Raised when an Apple token or provider response is not trustworthy., Verify Apple signature, issuer, audience, expiry and optional nonce.

### Community 313 - "Community 313"
Cohesion: 0.23
Nodes (11): model_snapshot(), sanitize_audit_payload(), payload_json(), create_audit_log(), create_required_audit_log(), queue_audit_log(), safe_create_audit_log(), Allow-list guest audit context before persistence or external projection. (+3 more)

### Community 335 - "Community 335"
Cohesion: 0.29
Nodes (11): _redact_text(), _redact_value(), _parse_redacted_json(), _source_filters(), _safe_resource_id(), _summary(), _details_for_row(), list_audit_timeline() (+3 more)

### Community 533 - "Community 533"
Cohesion: 0.29
Nodes (5): BusinessClockDisabledError, advance_business_clock(), Business-date read and controlled one-day advancement for local simulation., The local-only clock gate is not open for this hotel and runtime., Advance exactly one business day and append a real-time audit event.      SQLite

### Community 442 - "Community 442"
Cohesion: 0.39
Nodes (8): CancellationEvaluation, evaluate_cancellation_policy(), _parse_hotel_time(), _decimal_amount(), _currency(), _review(), Pure cancellation-policy evaluation from the immutable booking snapshot., Calculate a proposed cancellation penalty without applying it.      Missing hist

### Community 232 - "Community 232"
Cohesion: 0.26
Nodes (16): CashExpenseError, _money(), _delete_object_key(), _decode_receipt(), _safe_filename(), _require_open_session(), create_cash_expense(), list_cash_expenses() (+8 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (33): CashRegisterError, _money(), _require_open_session(), open_session(), list_pending_close_reports(), list_pending_cash_custody_reports(), enqueue_pending_difference_notification(), add_movement() (+25 more)

### Community 66 - "Community 66"
Cohesion: 0.11
Nodes (39): CheckInError, CheckInConflictError, CheckOutConflictError, _is_postgres_lock_not_available(), _notify_reservation_event(), _resolve_jurisdiction_code(), validate_guest_for_checkin(), _load_reservation() (+31 more)

### Community 123 - "Community 123"
Cohesion: 0.11
Nodes (25): _StockDraft, _LinenDraft, _LaundryVendorDraft, _CashSessionDraft, ResourceSpec, MergeResult, normalize_resource_type(), get_resource_spec() (+17 more)

### Community 149 - "Community 149"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy(), create_fx_policy() (+12 more)

### Community 271 - "Community 271"
Cohesion: 0.29
Nodes (12): CompanyDocumentError, _decode_company_pdf(), _safe_company_filename(), _get_reservation(), _get_company(), _get_reservation_company(), create_document(), upload_company_document() (+4 more)

### Community 167 - "Community 167"
Cohesion: 0.19
Nodes (21): CompanyNightChargeError, _reservation(), _company(), _rate_for_date(), _rates_for_stay_dates(), list_company_nightly_surcharge_rates(), create_company_nightly_surcharge_rate(), _paid_and_pending_by_charge() (+13 more)

### Community 297 - "Community 297"
Cohesion: 0.24
Nodes (13): _decimal_text(), company_terms_from_profile(), terms_fingerprint(), _reservation_economics(), _parse_pricing_snapshot(), build_company_terms_snapshot(), get_company_terms_review_state(), effective_company_terms() (+5 more)

### Community 401 - "Community 401"
Cohesion: 0.36
Nodes (9): CompanyTermsReviewError, CompanyTermsReviewNotFound, CompanyTermsReviewConflict, get_company_terms_review(), review_company_reservation_terms(), Transactional review service for mutable company terms attached to bookings., Expected validation, tenant, or stale-write failure for a review action., The reservation is outside this tenant or does not exist. (+1 more)

### Community 703 - "Community 703"
Cohesion: 0.50
Nodes (3): build_daily_report(), Build the legacy financial daily-report projection used by its API route., Return the established daily financial report for the caller's hotel.      The A

### Community 272 - "Community 272"
Cohesion: 0.21
Nodes (14): DistributedLockBusy, DistributedLockUnavailable, _settings(), _get_redis_client(), _required(), _try_postgres_advisory_lock(), distributed_lock(), with_distributed_lock() (+6 more)

### Community 178 - "Community 178"
Cohesion: 0.13
Nodes (18): coalesce_model_change_family(), discard_queued_domain_changes(), _PostgresOutboxStreamRow, _read_postgres_event_batch(), _notification_to_stream_row(), _session_factory_database_url(), _postgres_event_listener_database_url(), _get_postgres_event_listener() (+10 more)

### Community 200 - "Community 200"
Cohesion: 0.15
Nodes (17): RealtimeEventsUnavailable, DomainEvent, _settings(), _get_redis_client(), _get_realtime_fast_fail_client(), _required(), _unavailable(), publish_domain_event() (+9 more)

### Community 314 - "Community 314"
Cohesion: 0.17
Nodes (12): channel_for_hotel(), revision_key_for_hotel(), _validate_hotel_id(), get_domain_event_outbox_metrics(), get_domain_event_recovery(), iter_postgres_event_stream(), format_sse(), iter_event_stream() (+4 more)

### Community 298 - "Community 298"
Cohesion: 0.16
Nodes (14): QueuedDomainChange, _scalar_event_value(), _model_hotel_id(), _model_event_payload(), queue_model_changes(), queue_domain_change(), _session_transaction_id(), validate_event_input() (+6 more)

### Community 233 - "Community 233"
Cohesion: 0.13
Nodes (13): _OutboxPublishAttempt, _OutboxPublishPermit, _OutboxPublishCooldown, publish_queued_domain_changes(), _record_outbox_attempt(), Redis outcome to persist after every publish in the batch has finished., A durable Redis attempt, optionally owning the single recovery probe., Process-local gate for durable after-commit Redis publishes only. (+5 more)

### Community 273 - "Community 273"
Cohesion: 0.24
Nodes (6): _record_postgres_stream_count(), _record_postgres_fallback_poll(), _PostgresEventStreamHub, _deliver_postgres_notification(), _update_postgres_listener_state(), Share PostgreSQL notifications and a bounded poll fallback per hotel.

### Community 862 - "Community 862"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 226 - "Community 226"
Cohesion: 0.20
Nodes (9): _mask_email(), _mask_recipients(), _normalize_display_from(), EmailProviderError, EmailProvider, ABC, ResendEmailProvider, NullEmailProvider (+1 more)

### Community 315 - "Community 315"
Cohesion: 0.22
Nodes (8): Mailer, send_platform_email(), send_verification_email(), send_reset_password_email(), send_verification_success_email(), send_generic_auth_notice_email(), Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists.

### Community 216 - "Community 216"
Cohesion: 0.12
Nodes (18): completed_paid_amounts_by_reservation(), completed_paid_amount(), external_paid_balance_credit(), paid_amounts_by_reservation(), reconciled_paid_amounts_by_reservation(), paid_amount_with_legacy_fallback(), has_payment_history_for_cancellation(), billing_adjustment_totals_by_reservation() (+10 more)

### Community 274 - "Community 274"
Cohesion: 0.26
Nodes (13): _money(), _local_day(), _aggregate_rows(), _booked_nights_in_window(), _booked_amount_in_window(), _validate_report_window(), _build_booked_value_projection(), build_booked_value_report() (+5 more)

### Community 368 - "Community 368"
Cohesion: 0.33
Nodes (10): _as_utc(), _cache_identity(), _expected_market(), _quote_for_cache_row(), get_fx_rate_cache_quote(), _row_values(), store_supported_fx_rates(), Persistence helpers for the public DolarAPI quote cache. (+2 more)

### Community 85 - "Community 85"
Cohesion: 0.15
Nodes (34): _cache_key(), _cache_key_for_display_rate(), _cached_rate(), _store_rate(), parse_provider_updated_at(), quote_is_fresh(), _with_observed_at(), _quote_matches_supported_market() (+26 more)

### Community 639 - "Community 639"
Cohesion: 0.50
Nodes (3): FxSnapshotError, create_hotel_fx_snapshot(), Fetch one live snapshot and mark the hotel's configured ARS-to-USD quote.

### Community 581 - "Community 581"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 299 - "Community 299"
Cohesion: 0.40
Nodes (12): GemmaActionRunError, get_action_run(), approve_action_run(), reject_action_run(), review_action_run_draft(), apply_action_run_draft(), _load_json_dict(), _coerce_numeric_dict() (+4 more)

### Community 842 - "Community 842"
Cohesion: 1.00
Nodes (2): build_gemma_hotel_context(), _enum_value()

### Community 640 - "Community 640"
Cohesion: 0.70
Nodes (4): GemmaIntent, classify_gemma_intent(), _normalize(), _extract_keywords()

### Community 96 - "Community 96"
Cohesion: 0.12
Nodes (11): GemmaChatError, GemmaChatResult, GemmaOrchestrator, _build_session_title(), _safe_text(), _coerce_string_list(), _coerce_float(), _coerce_action_list() (+3 more)

### Community 72 - "Community 72"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaServiceError, GemmaService, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 582 - "Community 582"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 475 - "Community 475"
Cohesion: 0.32
Nodes (7): GuestProfile, GuestProfileError, get_guest_profile(), _enum_value(), validate_primary_guest_record(), Jurisdiction-agnostic guest profile rules.  The profile layer keeps legal-field, Raised when a requested guest profile is not available.

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (26): GuestRestrictionServiceError, GuestRestrictionNotFoundError, GuestRestrictionConflictError, GuestProhibitedError, RestrictionOverridePermissionError, _now(), get_active_guest_restrictions(), get_active_guest_restriction_guest_ids() (+18 more)

### Community 316 - "Community 316"
Cohesion: 0.29
Nodes (12): GuestRoomAvoidanceServiceError, GuestRoomAvoidanceNotFoundError, GuestRoomAvoidanceConflictError, _now(), _get_tenant_guest(), _get_tenant_room(), record_guest_room_avoidance(), get_active_guest_room_avoidances() (+4 more)

### Community 120 - "Community 120"
Cohesion: 0.12
Nodes (25): GuestServiceError, _now(), _audit(), _get_guest(), _active_tag_filter(), GuestCreatePayload, find_or_create_guest(), _escape_like_term() (+17 more)

### Community 317 - "Community 317"
Cohesion: 0.23
Nodes (11): HotelAPIKeyError, _hash_secret(), _generate_secret(), issue_key(), verify_key(), revoke_key(), list_keys(), Hotel-scoped public API key lifecycle. (+3 more)

### Community 318 - "Community 318"
Cohesion: 0.31
Nodes (12): HotelOutboundEmailError, HotelOutboundIdentity, HotelOutboundSendResult, HotelEmailAttachment, ensure_hotel_gmail_ready(), _build_email_message(), _build_message(), _dev_outbox_path() (+4 more)

### Community 234 - "Community 234"
Cohesion: 0.19
Nodes (16): HousekeepingChecklistError, HousekeepingChecklistNotFound, HousekeepingChecklistConflict, HousekeepingChecklistCompletionResult, create_checkout_checklist(), _read_checklist(), _build_checklist_read(), list_open_checklists() (+8 more)

### Community 300 - "Community 300"
Cohesion: 0.20
Nodes (13): utcnow(), hash_invitation_token(), issue_invitation(), find_by_token(), is_expired(), consume_invitation(), invitation_snapshot(), Domain helpers for secure, auditable staff invitation lifecycle. (+5 more)

### Community 534 - "Community 534"
Cohesion: 0.38
Nodes (6): JurisdictionProfile, UnsupportedJurisdictionError, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch, Raised when a hotel is configured for a jurisdiction without a profile.

### Community 402 - "Community 402"
Cohesion: 0.31
Nodes (9): LaundryMissingFollowUpError, LaundryMissingFollowUpNotFound, list_missing_follow_ups(), update_missing_follow_up(), _serialize_follow_up(), Neutral operational follow-up for declared laundry remito shortages.  This servi, Raised when an operational follow-up cannot be read or updated., Raised when a shortage line is outside the hotel or does not exist. (+1 more)

### Community 641 - "Community 641"
Cohesion: 0.40
Nodes (3): duplicate_laundry_remitos(), Read-only duplicate detection shared by migration and operator tooling., Return normalized duplicate remito groups, including every row id.      Service

### Community 403 - "Community 403"
Cohesion: 0.29
Nodes (8): LaundryError, create_batch(), add_item(), transition_status(), get_batch(), _next_batch_code(), Hotel-scoped laundry service., Raised when a laundry operation is invalid.

### Community 49 - "Community 49"
Cohesion: 0.07
Nodes (42): LaundryVendorError, DuplicateLaundryRemitoError, LaundryDiscrepancyNotFound, LaundryDiscrepancyConflict, is_duplicate_remito_integrity_error(), create_vendor(), get_vendor(), set_vendor_price() (+34 more)

### Community 82 - "Community 82"
Cohesion: 0.11
Nodes (34): LinenError, LinenNotFoundError, LinenOpeningCountConflict, LinenIdempotencyConflict, LinenTransferHistoryEntry, list_linen_items(), create_linen_item(), delete_linen_item() (+26 more)

### Community 235 - "Community 235"
Cohesion: 0.18
Nodes (16): _decode_features(), _plan_to_public(), _ordered_plans(), _plan_catalog_fallback(), public_pricing(), admin_pricing(), replace_pricing(), hash_source() (+8 more)

### Community 336 - "Community 336"
Cohesion: 0.27
Nodes (11): MembershipInvariantError, _lock_active_owner_memberships(), ensure_active_owner(), validate_membership_change(), transfer_primary_owner(), Atomic invariants and lifecycle operations for hotel memberships., Raised when a membership mutation would violate hotel ownership rules., Lock the current owner set for the duration of the caller's transaction. (+3 more)

### Community 189 - "Community 189"
Cohesion: 0.19
Nodes (19): MfaSecretUnavailableError, get_user_mfa_secret(), get_active_mfa_secret(), encrypt_totp_secret(), decrypt_totp_secret(), _totp_step_for_code(), _consume_totp_code(), _normalize_recovery_code() (+11 more)

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (31): NotificationServiceError, _utcnow(), _validate_payload(), _insert_ignore(), _redact(), _role_recipient_ids(), _actor_role(), get_effective_notification_preference() (+23 more)

### Community 642 - "Community 642"
Cohesion: 0.40
Nodes (4): ObjectStat, get_object_storage(), Minimal object-storage abstraction for bytes and seekable-file transfers.  Why t, Backend picked by `settings.OBJECT_STORAGE_BACKEND` (default: local).      `loca

### Community 275 - "Community 275"
Cohesion: 0.34
Nodes (6): ObjectStorageError, _safe_relative_path(), GCSObjectStorage, Raised when a storage backend cannot complete an operation., Reject any key that could escape the storage root (no `..`, no leading `/`)., Google Cloud Storage adapter with lazy optional dependency loading.

### Community 370 - "Community 370"
Cohesion: 0.18
Nodes (4): ObjectStorage, Content-addressed-ish blob store: put/get/delete bytes by string key., Upload a seekable file without changing existing bytes-based callers., Open an object for reading; storage adapters should stream where possible.

### Community 369 - "Community 369"
Cohesion: 0.29
Nodes (2): LocalObjectStorage, Stores objects as files under a local directory root.      Generalizes the patte

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (31): OnboardingError, StaffOnboardingResult, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload() (+23 more)

### Community 301 - "Community 301"
Cohesion: 0.27
Nodes (13): _utc(), _value(), _money(), _bounds(), _date_filter(), _actor_name(), _area_for(), _safe_detail_value() (+5 more)

### Community 68 - "Community 68"
Cohesion: 0.08
Nodes (36): _daily_report_reservation_load_options(), _DailyReservationCandidate, _candidate_summary(), _daily_reservation_candidate_from_row(), _guest_name(), _reservation_summary(), _group(), company_night_extra_balances_by_reservation() (+28 more)

### Community 73 - "Community 73"
Cohesion: 0.11
Nodes (31): OperationalTaskError, _decode_task_photo(), _safe_task_photo_name(), TaskVersionConflict, HandoffVersionConflict, _now(), _validate_hotel_local_due_at(), _enum_value() (+23 more)

### Community 865 - "Community 865"
Cohesion: 1.00
Nodes (1): Foundational OTA adapter interfaces and orchestration services.

### Community 307 - "Community 307"
Cohesion: 0.15
Nodes (3): BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, A provider operation failed before it could return normalized data.

### Community 146 - "Community 146"
Cohesion: 0.18
Nodes (2): BookingAdapter, Acknowledge processed reservation messages in Booking's queue.

### Community 187 - "Community 187"
Cohesion: 0.12
Nodes (5): OTAProviderAdapter, FakeBookingAdapter, FailingBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event(), test_ota_orchestrator_records_failed_verification()

### Community 263 - "Community 263"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 264 - "Community 264"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 231 - "Community 231"
Cohesion: 0.12
Nodes (5): OTAAdapterContext, OTAOperationResult, NormalizedOTAReservation, OTAProviderAdapter, Common contracts for OTA provider adapters.  The goal is to keep Booking, Expedi

### Community 310 - "Community 310"
Cohesion: 0.27
Nodes (3): OTAOrchestratorError, OTAOrchestratorService, OTA orchestrator service.  This layer coordinates provider adapters, persistent

### Community 698 - "Community 698"
Cohesion: 0.67
Nodes (3): build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 249 - "Community 249"
Cohesion: 0.30
Nodes (15): OTAManualReservationError, create_or_update_manual_ota_reservation(), release_no_guarantee(), _suggest_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean() (+7 more)

### Community 39 - "Community 39"
Cohesion: 0.07
Nodes (21): OTAError, OTAAuthError, OTAProcessingError, _ota_reconciliation_payload_projection(), _serialize_ota_reconciliation_payload(), _encrypt_ota_payload(), _hotel_default_currency(), _ota_fact_input_snapshot() (+13 more)

### Community 319 - "Community 319"
Cohesion: 0.28
Nodes (12): _json_size_estimate(), _body_size_estimate(), _request_details(), _response_body_size(), _safe_operation(), _fallback_url(), observed_http_call(), observed_async_http_call() (+4 more)

### Community 236 - "Community 236"
Cohesion: 0.18
Nodes (7): _CachedFailure, _PollEntry, CachedOutboxPollFailure, OutboxPollBatchCache, Short-lived singleflight cache for PostgreSQL event-outbox polling.  The Postgre, A same-window poll failed already; wait for the next bounded retry., Deduplicate concurrent per-process polls without extending freshness.

### Community 294 - "Community 294"
Cohesion: 0.24
Nodes (13): PaymentCorrectionError, PaymentCorrectionNotFound, PaymentNotFoundError, PaymentCorrectionConflict, PaymentCorrectionOutcome, _request_matches(), _find_idempotent_replay(), correct_payment() (+5 more)

### Community 60 - "Community 60"
Cohesion: 0.10
Nodes (40): PaymentLinkError, _create_mercadopago_preference(), _ensure_utc(), _assert_mercadopago_preference_identity(), _mercadopago_preference_expired(), _default_email_delivery(), _money(), _is_safe_provider_url() (+32 more)

### Community 107 - "Community 107"
Cohesion: 0.13
Nodes (28): PaymentLinkTestError, mercadopago_checkout_url(), _validate_email(), _mercadopago_access_token(), _mercadopago_connection_payload(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email() (+20 more)

### Community 237 - "Community 237"
Cohesion: 0.23
Nodes (15): PaymentProofError, _delete_uncommitted_object(), _decode_image(), _safe_filename(), _reservation(), submit_transfer_proof(), recover_failed_transfer_proof_commit(), get_transfer_proof() (+7 more)

### Community 250 - "Community 250"
Cohesion: 0.23
Nodes (14): PaymentReceiptEmailError, _normalize_email(), _key_hash(), _recipient_fingerprint(), _load_receipt(), _local_simulation_enabled(), _is_reserved_test_recipient(), _format_money() (+6 more)

### Community 443 - "Community 443"
Cohesion: 0.33
Nodes (8): _pdf_text(), _amount(), _rate(), _local_created_at(), generate_payment_receipt_pdf(), Generate a downloadable PDF from the persisted payment receipt snapshot., Keep core-font text safe while retaining Spanish Latin-1 characters., Render one page from ``get_payment_receipt_data`` output.      The function acce

### Community 41 - "Community 41"
Cohesion: 0.09
Nodes (50): PaymentError, PaymentNotFoundError, _cash_tender_breakdown(), _same_idempotent_payment(), get_hotel_config(), validate_payment_method_enabled(), _resolve_reservation_hotel(), _resolve_payment_currency() (+42 more)

### Community 86 - "Community 86"
Cohesion: 0.10
Nodes (34): PaymentWebhookError, RetryablePaymentWebhookError, _is_json_scalar(), normalize_webhook_identifier(), _safe_webhook_event_type(), _payment_response_projection(), _webhook_event_payload_projection(), fetch_mercadopago_payment() (+26 more)

### Community 22 - "Community 22"
Cohesion: 0.06
Nodes (79): PermissionVersionConflict, HotelRoleNotFound, LookupError, HotelRoleVersionConflict, HotelRoleNameConflict, HotelRoleInUse, canonical_permission_code(), _permission_help_es() (+71 more)

### Community 302 - "Community 302"
Cohesion: 0.15
Nodes (7): listener_connection_string(), parse_domain_event_notification(), PostgresEventNotificationListener, Return a psycopg2 URL only when session-level LISTEN can work.      Supabase's s, Validate and project a bounded, privacy-safe PostgreSQL notification., One reconnecting LISTEN connection shared by all SSE streams in a process., Stop the listener and wait briefly for its socket loop to exit.

### Community 238 - "Community 238"
Cohesion: 0.26
Nodes (16): PricingPolicyError, StayPricingQuote, quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount() (+8 more)

### Community 251 - "Community 251"
Cohesion: 0.17
Nodes (15): _price_with_payment_method_override(), _period_price(), get_price_for_date(), resolve_rate_calendar(), resolve_current_rates_for_categories(), get_prices_for_range(), apply_price_period(), build_pricing_revision() (+7 more)

### Community 404 - "Community 404"
Cohesion: 0.29
Nodes (8): CanonicalPricingError, _quantize(), _hotel_default_currency(), CanonicalPricingResult, compute_canonical_stay_pricing(), Canonical stay pricing pipeline (v72 mobile-first pricing/promotions task).  App, Raised when the canonical pricing pipeline cannot produce a quote., JSON-serialisable breakdown, frozen into a reservation's         pricing_snapsho

### Community 158 - "Community 158"
Cohesion: 0.13
Nodes (22): PromotionError, _quantize(), _get_active_or_404(), get_promotion(), create_promotion(), _conditions_kwargs(), update_promotion(), deactivate_promotion() (+14 more)

### Community 320 - "Community 320"
Cohesion: 0.23
Nodes (12): PublicInquiryRateLimitError, PublicInquiryUnavailableError, _digest_key(), _rate_limit_keys(), _utcnow_naive(), _notification_body(), _notify_inquiry(), create_public_inquiry() (+4 more)

### Community 444 - "Community 444"
Cohesion: 0.44
Nodes (8): _utc(), _decimal(), _published_base_rates(), _comparable_season_key(), get_fresh_ars_per_usd_snapshot(), record_published_rate_history(), Capture approved category rates with the currency and comparable season used., Write a history row for each approved base-rate change in the draft.      This i

### Community 217 - "Community 217"
Cohesion: 0.15
Nodes (14): WebPushSendError, WebPushUnavailableError, WebPushSubscriptionInvalid, WebPushAdapter, NullWebPushAdapter, RealWebPushAdapter, get_web_push_adapter(), Web Push channel adapter.  Deliberately a thin, swappable interface rather than (+6 more)

### Community 445 - "Community 445"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 84 - "Community 84"
Cohesion: 0.15
Nodes (30): RateDraftError, _money(), _effective_value(), _load_rate_state(), _validate_changes(), _period_values(), _validate_period_values(), _period_from_values() (+22 more)

### Community 112 - "Community 112"
Cohesion: 0.17
Nodes (28): _settings(), _cache_enabled(), _redis_failure_cooldown_seconds(), _redis_timeout_seconds(), _mark_redis_unavailable(), _mark_redis_available(), _get_redis_client(), _load_json() (+20 more)

### Community 104 - "Community 104"
Cohesion: 0.11
Nodes (29): ReservationActionError, _ActionCandidate, get_reservation_operations_summary(), _get_operations_related_data(), list_pending_reservation_actions(), _load_pending_action_reservations(), _latest_ota_links_by_reservation(), _related_adjustments_by_reservation() (+21 more)

### Community 141 - "Community 141"
Cohesion: 0.14
Nodes (22): CancellationReviewError, CancellationConfigurationRequired, CancellationReviewNotFound, CancellationReviewConflict, CancellationPreparation, CancellationRequestResult, utc_now(), get_pending_cancellation_review() (+14 more)

### Community 371 - "Community 371"
Cohesion: 0.33
Nodes (9): ReservationCommunicationError, ReservationEmailSendOutcome, _clean_email(), _kind_value(), _money(), build_reservation_email(), send_reservation_email(), Guest-facing reservation confirmation and voucher delivery. (+1 more)

### Community 535 - "Community 535"
Cohesion: 0.43
Nodes (6): _canonical_hash(), _read_batch(), get_group_payment_batch(), create_reservation_group_payment(), Atomic idempotent collection and explicit allocations for reservation groups., Create one batch and its child payment transactions as one DB operation.      Re

### Community 44 - "Community 44"
Cohesion: 0.08
Nodes (48): ReservationOperationsError, ReservationError, RoomMovePermissionError, ReservationExtensionImpactConfirmationError, _validate_direct_individual_extension_target(), _invalidate_availability_cache(), _touch_facts(), _hotel_default_currency() (+40 more)

### Community 536 - "Community 536"
Cohesion: 0.29
Nodes (7): required_room_move_permission(), _room_move_permission_candidates(), _room_move_categories(), enforce_room_move_permission(), Return the minimum permission tier for this category-to-category move., Load source and destination categories through tenant-scoped rows., Classify a move and enforce its tier for a user-initiated operation.      The ca

### Community 46 - "Community 46"
Cohesion: 0.09
Nodes (49): ReservationError, _direct_manual_rate_reference_quote(), active_reservations_select(), _active_reservations_without_hotel(), ReservationPricingResult, generate_confirmation_code(), _resolve_hotel_id(), _validate_stay_dates() (+41 more)

### Community 321 - "Community 321"
Cohesion: 0.18
Nodes (13): ReservationVersionConflict, _invalidate_availability_cache(), _touch_facts(), _notify_reservation_event(), transition_reservation_status(), lock_reservation_version(), mark_reservation_no_show(), A reservation changed after the caller last read its version. (+5 more)

### Community 150 - "Community 150"
Cohesion: 0.13
Nodes (25): ManualRatePolicyError, ConfirmedReservationPriceLocked, requires_large_total_adjustment_confirmation(), validate_direct_individual_manual_rate_target(), validate_bounded_manual_rate_correction(), _resolve_reservation_company(), _pricing_with_total(), _apply_manual_total_override() (+17 more)

### Community 276 - "Community 276"
Cohesion: 0.15
Nodes (13): _ReservationGuestProjection, _ReservationListProjection, active_reservations(), _hotel_today_and_timezone(), visible_reservations(), list_reservations(), get_occupancy_grid(), get_reservation_by_id() (+5 more)

### Community 843 - "Community 843"
Cohesion: 0.67
Nodes (3): deferred_company_reservation_ids(), reservation_has_deferred_company_billing(), Return reservations whose lodging is billed outside this PMS.      The persisted

### Community 337 - "Community 337"
Cohesion: 0.18
Nodes (6): ReservationUpdatePlan, build_reservation_update_plan(), Pure planning helpers for reservation PATCH endpoints.  The primary reservations, An immutable view of the effective fields in a reservation PATCH., Return fields blocked by a status-restricted reservation edit.          The two, Classify a validated PATCH payload without changing the reservation.

### Community 293 - "Community 293"
Cohesion: 0.16
Nodes (12): ReservationUpdateAuthorization, ReservationUpdatePreparationError, PreparedReservationUpdate, prepare_reservation_update(), apply_reservation_update(), Application service for the reservations API PATCH mutation and audit., Transport-provided permission checks used by the PATCH use case.      The callba, Business/precondition failure raised before a reservation is mutated. (+4 more)

### Community 38 - "Community 38"
Cohesion: 0.08
Nodes (49): _load_json_dict(), RoomBlockError, ProtectedReservationConflictError, RoomBlockReservationConflictError, RoomBlockAlreadyExistsError, RoomBlockReleaseConflictError, _protected_reservation_filter(), _invalidate_availability_cache() (+41 more)

### Community 583 - "Community 583"
Cohesion: 0.47
Nodes (5): create_category(), create_room(), upsert_categories(), upsert_rooms(), Canonical room category and room catalog write operations.

### Community 704 - "Community 704"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 338 - "Community 338"
Cohesion: 0.23
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 339 - "Community 339"
Cohesion: 0.24
Nodes (11): StaffInvitationProvision, StaffAliasConflict, normalize_staff_role(), normalize_staff_alias(), set_membership_alias(), provision_staff_invitation(), Shared staff membership and invitation provisioning path., The requested hotel alias is already in use by another membership. (+3 more)

### Community 42 - "Community 42"
Cohesion: 0.08
Nodes (46): StockError, StockIdempotencyConflict, StockCountRecountRequired, list_stock_items(), create_stock_item(), update_stock_item(), delete_stock_item(), list_locations() (+38 more)

### Community 476 - "Community 476"
Cohesion: 0.25
Nodes (5): register_uploaded_object(), register_uploaded_object_file(), Upload/verify/register object-storage bytes without exposing them in events., Persist pending metadata, upload, stat and mark ready after verification., Upload and verify a seekable file while keeping memory bounded.

### Community 61 - "Community 61"
Cohesion: 0.13
Nodes (40): _now(), _as_utc(), _plan_defaults(), plan_catalog(), plan_has_feature(), _is_enforcement_enabled(), _compute_can_write(), _sync_legacy_tables() (+32 more)

### Community 100 - "Community 100"
Cohesion: 0.11
Nodes (31): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements(), _get_entitlements_for_subscription() (+23 more)

### Community 159 - "Community 159"
Cohesion: 0.16
Nodes (23): _decimal(), _utc(), _naive_utc(), _season_period_for_date(), _high_demand_event_for_date(), _consecutive_date_runs(), _latest_comparable_rates(), _historical_pickups_by_date() (+15 more)

### Community 67 - "Community 67"
Cohesion: 0.10
Nodes (39): TemporaryGrantActor, TemporaryGrantError, TemporaryGrantNotFoundError, TemporaryGrantAuthorizationError, TemporaryGrantStateError, TemporaryGrantMfaError, TemporaryGrantRateLimitError, _utcnow() (+31 more)

### Community 201 - "Community 201"
Cohesion: 0.16
Nodes (18): _apply_setting(), _remember_setting(), _set_context_value(), reapply_tenant_context_on_connection(), set_tenant_user_context(), set_tenant_hotel_context(), set_invitation_token_hash_context(), set_tenant_context() (+10 more)

### Community 372 - "Community 372"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 160 - "Community 160"
Cohesion: 0.12
Nodes (23): get_country_catalog(), get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), hotel_local_date_bounds(), local_today(), business_clock_enabled_for_hotel(), hotel_timezone_name() (+15 more)

### Community 228 - "Community 228"
Cohesion: 0.13
Nodes (9): find_user_by_email(), Exact, case-insensitive lookup helpers for user identity fields., Find an exact email match without treating SQL wildcard characters specially., _function(), test_migrated_route_keeps_legacy_role_contract(), test_rate_calendar_read_contract_allows_only_owner_co_owner_and_manager(), Regression contracts for routes migrated from the legacy role dependency.  These, API regression coverage for section visibility permissions. (+1 more)

### Community 131 - "Community 131"
Cohesion: 0.12
Nodes (25): _now(), _as_aware(), _hash_value(), _issue_token(), _issue_rotation_successor(), _session_cookie_secure(), _session_cookie_samesite(), _device_label_from_request() (+17 more)

### Community 165 - "Community 165"
Cohesion: 0.16
Nodes (20): WaitlistError, _get_waitlist_entry(), _lock_waitlist_entry(), _waitlist_entry_fingerprint(), add_to_waitlist(), list_waitlist_entries(), update_waitlist_entry(), promote_from_waitlist() (+12 more)

### Community 202 - "Community 202"
Cohesion: 0.23
Nodes (17): WhatsAppCRMError, InboundMessageResult, WhatsAppMessagePage, normalize_phone(), complete_embedded_signup(), _channel(), _conversation(), _event() (+9 more)

### Community 268 - "Community 268"
Cohesion: 0.18
Nodes (14): _rotate_active_hotel_ids(), _session(), _active_hotel_count(), _claim_request(), _process_hotel_request(), process_recalculation_requests(), Background processing for durable room-optimization requests., Start each durable five-minute scan at the next page of three hotels. (+6 more)

### Community 190 - "Community 190"
Cohesion: 0.14
Nodes (16): _date_window(), _decimal_total(), _project_operational_window(), _parse_datetime(), detect_no_shows(), project_reservation_facts_to_clickhouse(), project_operational_facts_to_clickhouse(), _project_all_hotels_window() (+8 more)

### Community 406 - "Community 406"
Cohesion: 0.31
Nodes (9): _empty_totals(), _positive_count(), _rotated_hotel_ids(), _process_pending_revocations(), run_payment_link_revocation_tasks(), Durable, tenant-scoped recovery for canceled Mercado Pago checkout links., Rotate two positions every five-minute slot for predictable fairness., Enumerate every hotel regardless of subscription, rotating visits by cycle. (+1 more)

### Community 477 - "Community 477"
Cohesion: 0.39
Nodes (7): _active_hotel_ids(), _send_report_for_hotel(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports(), Celery tasks for scheduled operational reports (BRM §15.1).  Two beat-driven tas, Build and email the report for a single hotel. Returns True on send.      Best-e

### Community 460 - "Community 460"
Cohesion: 0.31
Nodes (8): _is_example_test_address(), local_synthetic_email_addresses_enabled(), normalize_reservation_email(), is_local_synthetic_reservation_email(), Validation helpers for reservation communication email addresses., Allow reserved synthetic addresses only in isolated local/test modes., Validate and normalize an email, narrowly allowing local ``example.test``., Return whether a validated recipient belongs to the local reserved domain.

### Community 333 - "Community 333"
Cohesion: 0.24
Nodes (6): chain_names(), root_name(), is_db_call(), FuncScan, scan_file(), names of methods in a call chain, outer->inner

### Community 635 - "Community 635"
Cohesion: 0.60
Nodes (4): login(), vu(), run(), Closed-loop load test: N virtual users, each loops over a request mix with think

### Community 474 - "Community 474"
Cohesion: 0.25
Nodes (3): measured(), Mide, sobre PostgreSQL real, el costo de cuatro rutas calientes que la lectura c, Ejecuta ``fn`` ``repeat`` veces en una sesión nueva y devuelve sentencias/commit

### Community 2 - "Community 2"
Cohesion: 0.27
Nodes (457): 0174f49 Document post-deploy read-only smoke results, 019336c Add internal linen transfer history, 02102f9 docs(audit): incorpora la verificación por un segundo lector (262 afirmaciones: 198 confirmadas, 64 corregidas), 0458fcc Show stock movements in operational audit, 049af9d Add local simulation clock and payment receipt workflows, 0503c7f docs: clarify supported login and privacy terms, 074902a Stabilize cash receipt E2E response reads, 07f931f Label agreed company rates in reservation quotes (+449 more)

### Community 637 - "Community 637"
Cohesion: 0.60
Nodes (4): pipe(), handle(), flush(), main()

### Community 700 - "Community 700"
Cohesion: 0.83
Nodes (3): timing(), outbox_count(), step()

### Community 405 - "Community 405"
Cohesion: 0.24
Nodes (3): _TooLarge, BodyLimitMiddleware, Tope global de tamaño de cuerpo como middleware ASGI puro (hallazgo N13 del info

### Community 584 - "Community 584"
Cohesion: 0.40
Nodes (5): derive_pepper(), hash_code(), verify_code(), Hash de secretos de corta vida con HMAC-SHA256 (hallazgo N8 del informe).  Hoy `, Deriva el pepper de la clave Fernet existente: no agrega una variable de entorno

### Community 585 - "Community 585"
Cohesion: 0.60
Nodes (5): hotel_chipre_private.purge_operational_data(), public.rate_limit_events, public.security_tokens, public.domain_event_outbox, PUBLIC

### Community 363 - "Community 363"
Cohesion: 0.20
Nodes (9): module, AnalyticsValueLabels, AnalyticsCurrencyDisplay, ANALYTICS_ROOM_FIELD_LABELS, ANALYTICS_ROOM_VALUE_LABELS, visibleAnalyticsCurrencyFields(), formatAnalyticsTableValue(), 72c4c38 Align analytics tables with selected currency (+1 more)

### Community 839 - "Community 839"
Cohesion: 0.67
Nodes (1): ExampleInstrumentedTest

### Community 824 - "Community 824"
Cohesion: 1.00
Nodes (2): MainActivity, BridgeActivity

### Community 840 - "Community 840"
Cohesion: 0.67
Nodes (1): ExampleUnitTest

### Community 90 - "Community 90"
Cohesion: 0.08
Nodes (18): validatedSha(), resolveCodeSha(), buildMetaPlugin(), MARKETING_ROUTES, replaceTag(), renderRouteHtml(), marketingHtmlPlugin(), indexHtml (+10 more)

### Community 863 - "Community 863"
Cohesion: 1.00
Nodes (1): config

### Community 94 - "Community 94"
Cohesion: 0.07
Nodes (23): source, { code }, CashMovement, CashCloseReport, CashDailyEntry, CashMovementPayload, downloadCashLedgerCsv(), downloadCashExpensesCsv() (+15 more)

### Community 829 - "Community 829"
Cohesion: 0.67
Nodes (2): source, { code }

### Community 826 - "Community 826"
Cohesion: 0.67
Nodes (1): 2f1f92f Show cached analytics report freshness

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (80): credentials, receptionistCredentials, manager, receptionist, Persona, personas, backendURL, credentials (+72 more)

### Community 467 - "Community 467"
Cohesion: 0.29
Nodes (5): 84a8b44 Localize analytics room event values, 8d2cfba Clarify analytics freshness timestamp label, 9857754 Render analytics period comparisons across reports, 9fa52c8 Fix analytics E2E preconditions, bcf12bc Translate analytics room event labels

### Community 47 - "Community 47"
Cohesion: 0.07
Nodes (37): managerCredentials, GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse (+29 more)

### Community 687 - "Community 687"
Cohesion: 0.50
Nodes (1): receptionistCredentials

### Community 214 - "Community 214"
Cohesion: 0.16
Nodes (14): RouteScenario, Persona, ApiRequestMetric, ApiResponseMetric, UiActionMetric, personas, durationSeconds, normalizePath() (+6 more)

### Community 575 - "Community 575"
Cohesion: 0.33
Nodes (3): credentials, backendURL, StoredSession

### Community 432 - "Community 432"
Cohesion: 0.22
Nodes (4): backendURL, owner, receptionist, ApiSession

### Community 518 - "Community 518"
Cohesion: 0.43
Nodes (6): SHOTS, VIEWPORTS, login(), toWebp(), capture(), main()

### Community 688 - "Community 688"
Cohesion: 0.67
Nodes (2): totpAt(), login()

### Community 516 - "Community 516"
Cohesion: 0.33
Nodes (4): credentials, parseMoney(), readStat(), f20706d Skip payment quotes when balance is settled

### Community 519 - "Community 519"
Cohesion: 0.29
Nodes (3): backendURL, receptionistCredentials, TestSession

### Community 364 - "Community 364"
Cohesion: 0.31
Nodes (8): escapeRegExp(), localizedName(), localizedText(), manager, receptionist, localIsoDate(), ensureCashSessionOpen(), createReservation()

### Community 88 - "Community 88"
Cohesion: 0.08
Nodes (23): PublicPricingPlan, PublicPricing, LeadPayload, fetchPublicPricing(), submitLead(), EarlyAccessFormProps, Status, MESSAGES (+15 more)

### Community 689 - "Community 689"
Cohesion: 0.50
Nodes (1): owner

### Community 827 - "Community 827"
Cohesion: 0.67
Nodes (1): credentials

### Community 630 - "Community 630"
Cohesion: 0.50
Nodes (2): mobileNavigationDialog(), openMobileMenu()

### Community 828 - "Community 828"
Cohesion: 0.67
Nodes (1): owner

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (39): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, IssueHotelApiKeyPayload, listApiKeys(), issueApiKey(), revokeApiKey(), PaymentLinkTest (+31 more)

### Community 470 - "Community 470"
Cohesion: 0.29
Nodes (5): frontendRoot, sourceRoot, pluralSuffixes, flattenKeys(), loadKeys()

### Community 213 - "Community 213"
Cohesion: 0.24
Nodes (11): LocalizedDateFieldProps, validCalendarDate(), formatDateInputValue(), formatDateTimeInputValue(), maskDateInputValue(), maskDateTimeInputValue(), parseDateInputValue(), parseDateTimeInputValue() (+3 more)

### Community 466 - "Community 466"
Cohesion: 0.25
Nodes (7): es, en, 344c234 Clarify operational total in reservation editor, 5e02914 Drain allocation queue after scheduler errors, 6ea5623 Rotate allocation processing across hotels, a138bfd Refresh generated maps for QA fixes, fa1728a Clarify operational total in reservation editor

### Community 825 - "Community 825"
Cohesion: 0.67
Nodes (2): frontendRoot, 25f23f7 Clarify missing room event history details

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (53): CashSessionStatus, CashMovementType, CashMovementExclusionReason, CashSession, CashSessionPage, CashCustodyHandoff, CashSessionSummary, CashDailyPaymentMethod (+45 more)

### Community 29 - "Community 29"
Cohesion: 0.04
Nodes (42): ApiError, RequestOptions, readCookie(), setMasterAdminCsrfToken(), clearMasterAdminCsrfToken(), safeJson(), masterAdminFetch(), MasterAdminUser (+34 more)

### Community 17 - "Community 17"
Cohesion: 0.03
Nodes (83): RemitoDirection, LaundryVendor, LaundryVendorCreate, LaundryVendorUpdate, LaundryVendorPrice, LaundryVendorPriceUpsert, LaundryRemitoLine, LaundryRemito (+75 more)

### Community 103 - "Community 103"
Cohesion: 0.10
Nodes (25): OperationalTaskType, OperationalTaskStatus, OperationalTaskPriority, OperationalTask, OperationalTaskEvent, ShiftHandoff, OperationalTaskAttachment, OperationalTaskCreate (+17 more)

### Community 362 - "Community 362"
Cohesion: 0.24
Nodes (10): fetchActiveTemporaryActionGrants(), approveTemporaryActionGrant(), denyTemporaryActionGrant(), revokeTemporaryActionGrant(), TemporaryGrantApprovalPanelProps, IssuedToken, grantsQueryKey(), errorText() (+2 more)

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (31): PublicInquiryPayload, PublicInquiryResponse, submitPublicInquiry(), StructuredData, SeoProps, socialImage, Seo(), BreadcrumbItem (+23 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (65): RESERVATION_QUERY_PREFIXES, PAYMENT_QUERY_PREFIXES, CASH_QUERY_PREFIXES, RESERVATION_ENTITY_QUERY_PREFIXES, GUEST_QUERY_PREFIXES, ROOM_QUERY_PREFIXES, ReservationRecordRefreshOptions, refreshAfterMutation() (+57 more)

### Community 468 - "Community 468"
Cohesion: 0.25
Nodes (5): CLIENT_ID, REDIRECT_URI, AppleAuthorization, AppleSignInResult, Window

### Community 686 - "Community 686"
Cohesion: 0.50
Nodes (3): StatCardProps, toneClasses, StatCard()

### Community 57 - "Community 57"
Cohesion: 0.12
Nodes (26): SectionProps, tones, Section(), SectionHeadingProps, SectionHeading(), DifferentiatorsSection(), FaqSection(), FounderSection() (+18 more)

### Community 197 - "Community 197"
Cohesion: 0.15
Nodes (16): trimTrailingSlash(), ensureLeadingSlash(), normalizeUrl(), PUBLIC_SITE_URL, PUBLIC_APP_URL, APP_URL_HOSTNAME, SITE_URL_HOSTNAME, PREVIEW_APP_HOST_SUFFIXES (+8 more)

### Community 469 - "Community 469"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 332 - "Community 332"
Cohesion: 0.18
Nodes (5): Lead, SOURCE_LABELS, DATE, HEADERS, toCsvCell()

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (73): AppShell, ContactPage, FaqPage, FunctionsPage, MarketingHomePage, MarketingNotFoundPage, PmsHoteleroPage, PricingPageView (+65 more)

### Community 55 - "Community 55"
Cohesion: 0.05
Nodes (23): AnalyticsEnvelope, AnalyticsMetric, AnalyticsComparisonWindow, AnalyticsComparisonState, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+15 more)

### Community 513 - "Community 513"
Cohesion: 0.38
Nodes (7): localDateIso(), usePersistedAnalyticsFilters(), useAnalyticsQuery(), ReportScreen(), analyticsErrorMessage(), StarterLandingScreen(), AnalyticsAIChatPage()

### Community 514 - "Community 514"
Cohesion: 0.43
Nodes (7): usePlan(), planRankFor(), PlanGuard(), UltraGuard(), AnalyticsHomePage(), CompaniesSettingsPage(), RoomStateEventsPage()

### Community 573 - "Community 573"
Cohesion: 0.80
Nodes (5): SharedSandboxBootstrapError, load_env(), _literal(), build_sql(), main()

### Community 574 - "Community 574"
Cohesion: 0.47
Nodes (5): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 328 - "Community 328"
Cohesion: 0.36
Nodes (11): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+3 more)

### Community 390 - "Community 390"
Cohesion: 0.49
Nodes (9): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+1 more)

### Community 429 - "Community 429"
Cohesion: 0.42
Nodes (8): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots.

### Community 822 - "Community 822"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 329 - "Community 329"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 98 - "Community 98"
Cohesion: 0.16
Nodes (29): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+21 more)

### Community 682 - "Community 682"
Cohesion: 0.67
Nodes (3): normalize_instruction_paths(), main(), Replace this repository's absolute root in generated instructions only.

### Community 627 - "Community 627"
Cohesion: 0.80
Nodes (4): _write_json(), _archive_historical(), _build_cases(), main()

### Community 430 - "Community 430"
Cohesion: 0.44
Nodes (8): OperationalQAError, _utc_now(), _json_bytes(), _write(), _catalog(), initialize(), validate(), main()

### Community 164 - "Community 164"
Cohesion: 0.26
Nodes (20): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+12 more)

### Community 628 - "Community 628"
Cohesion: 0.50
Nodes (4): BootstrapConfigurationError, bootstrap_configuration_fingerprint(), Shared, secret-safe binding for the Render QA bootstrap configuration., Hash the exact provider-observed values without exposing them individually.

### Community 147 - "Community 147"
Cohesion: 0.22
Nodes (23): AttestationError, _sha256(), _canonical_json(), _b64url_encode(), _b64url_decode(), _read_regular_nofollow(), _read_limited(), _json_object() (+15 more)

### Community 464 - "Community 464"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 683 - "Community 683"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 127 - "Community 127"
Cohesion: 0.22
Nodes (16): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+8 more)

### Community 359 - "Community 359"
Cohesion: 0.40
Nodes (10): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+2 more)

### Community 684 - "Community 684"
Cohesion: 0.83
Nodes (3): run(), validate_json(), main()

### Community 227 - "Community 227"
Cohesion: 0.23
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 93 - "Community 93"
Cohesion: 0.21
Nodes (32): VerificationError, _dict(), _list(), _string(), _validate_config(), _decode_lease_entropy(), _validate_baseline_lease_id(), _verify_dedicated_baseline_lease() (+24 more)

### Community 431 - "Community 431"
Cohesion: 0.22
Nodes (6): ReadOnlyJsonApi, VerificationConfig, ProviderClients, _required_env(), main(), Small GET-only API client with bounded retries and redacted failures.

### Community 685 - "Community 685"
Cohesion: 0.83
Nodes (3): _non_empty(), validate_manifest(), main()

### Community 267 - "Community 267"
Cohesion: 0.33
Nodes (14): DrillError, _validate_tables(), _sqlite_path(), _sqlite_counts(), _verify_local_objects(), _run_sqlite(), _postgres_parts(), _pg_command() (+6 more)

### Community 65 - "Community 65"
Cohesion: 0.12
Nodes (39): QABootstrapError, Persona, QABootstrapConfig, QABootstrapResult, ProviderEvidence, _required(), _flag(), _required_port() (+31 more)

### Community 440 - "Community 440"
Cohesion: 0.36
Nodes (8): _required(), load_provider_evidence_private_key(), issue_provider_evidence_token(), _safe_output_path(), write_private_token(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer.

### Community 521 - "Community 521"
Cohesion: 0.57
Nodes (6): command(), heading(), fenced(), frontend_routes(), write(), main()

### Community 334 - "Community 334"
Cohesion: 0.21
Nodes (5): _parser(), _hotel_ranges(), _build_dry_run_report(), main(), Idempotently rebuild reservation and room analytics facts for a bounded scope.

### Community 367 - "Community 367"
Cohesion: 0.33
Nodes (8): PhaseMetrics, LoadConfig, percentile(), safe_headers(), run_phase(), _parse_paths(), _run(), main()

### Community 531 - "Community 531"
Cohesion: 0.52
Nodes (5): RealtimeMetrics, validate_target(), run_load(), _run(), main()

### Community 130 - "Community 130"
Cohesion: 0.15
Nodes (23): E2ESafetyError, _enabled(), _postgres_e2e_connection(), _postgres_e2e_seed_connection(), _assert_postgres_e2e_database_empty(), prepare_e2e_environment(), _credentials(), _role_credentials() (+15 more)

### Community 636 - "Community 636"
Cohesion: 0.50
Nodes (3): _prepare_environment(), seed(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2

### Community 56 - "Community 56"
Cohesion: 0.05
Nodes (39): _reject_unqualified_postgres_locks_over_outer_joins(), _reset_durable_realtime_publish_cooldown(), _validated_pg_dsn_or_skip(), pg_engine(), _stub_transactional_auth_email(), _isolate_object_storage(), _reset_permission_seed_cache(), db_engine() (+31 more)

### Community 396 - "Community 396"
Cohesion: 0.31
Nodes (9): reset_projection_clients(), _close_clients(), _enable(), test_mongo_audit_projection_lands_document(), test_neo4j_reservation_assignment_lands_nodes(), _cassandra_probe(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each (+1 more)

### Community 246 - "Community 246"
Cohesion: 0.22
Nodes (14): _migration_dsn(), _run_alembic(), test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips(), Disposable PostgreSQL proof for the forward Alembic release path.  The release c, PostgresTargetSafetyError, _enabled(), _canonical_identity(), _identity_contains() (+6 more)

### Community 478 - "Community 478"
Cohesion: 0.29
Nodes (6): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), Migration coverage for the deduplication sweep.

### Community 188 - "Community 188"
Cohesion: 0.19
Nodes (19): BenchmarkResult, index_usage_for_operation(), derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure() (+11 more)

### Community 841 - "Community 841"
Cohesion: 0.67
Nodes (1): Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati

### Community 537 - "Community 537"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 538 - "Community 538"
Cohesion: 0.48
Nodes (6): _receptionist_context(), _open_cash_session(), _create_receptionist_user(), test_receptionist_can_view_and_make_reservation_payments(), test_financial_summary_requires_reservation_read_not_cash_operation(), Front desk can read reservation finances and record payments.

### Community 203 - "Community 203"
Cohesion: 0.23
Nodes (16): _auth_context(), step_up_client(), _code_at(), _invalid_code(), _issue_ticket(), test_sensitive_permission_requires_a_matching_ticket_before_handler(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket() (+8 more)

### Community 705 - "Community 705"
Cohesion: 0.50
Nodes (1): Current hotel membership aliases label historical actor projections.

### Community 204 - "Community 204"
Cohesion: 0.15
Nodes (9): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), _tracked_files(), test_raw_graphify_graph_is_not_tracked(), test_tracked_graphify_artifacts_stay_small() (+1 more)

### Community 124 - "Community 124"
Cohesion: 0.12
Nodes (18): _reservation_payload(), _pending_requests(), test_direct_and_inbound_ota_bookings_request_one_coalesced_proposal(), test_waitlisted_or_out_of_horizon_reservation_does_not_request_current_run(), test_background_worker_leaves_initial_assignment_unchanged(), test_real_background_solver_leaves_existing_moves_for_reception_review(), test_pending_proposal_coalesces_different_automatic_triggers(), test_postgres_worker_requires_reception_approval_for_existing_moves() (+10 more)

### Community 97 - "Community 97"
Cohesion: 0.13
Nodes (8): make_rooms(), make_res(), TestOverlap, test_reservation_day_index_clips_to_half_open_horizon(), test_overlapping_reservation_pairs_use_half_open_dates_and_keep_original_indexes(), TestGreedyAllocation, TestCPSATAllocation, Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback).

### Community 340 - "Community 340"
Cohesion: 0.53
Nodes (10): _seed_hotel(), _guest(), _reservation(), _slots(), test_slot_builder_does_not_hydrate_unused_reservation_relationships(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_previous_completed_room_signal_requires_the_new_reservation_category(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy() (+2 more)

### Community 292 - "Community 292"
Cohesion: 0.40
Nodes (13): _override_auth(), _build_client(), _cleanup_client(), test_manual_allocation_is_queued_without_running_solver_in_request(), test_manual_allocation_rejects_duplicate_pending_request(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion() (+5 more)

### Community 539 - "Community 539"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 373 - "Community 373"
Cohesion: 0.29
Nodes (9): _seed_allocation_case(), _run_allocation(), _wait_for_postgres_lock_wait(), test_postgres_autoapply_rejects_room_taken_after_solver_snapshot(), test_postgres_acceptance_rejects_stale_policy_or_fx_configuration(), test_postgres_autoapply_serializes_with_concurrent_reservation_creation(), PostgreSQL regressions for allocation freshness and room-lock serialization.  Th, A competing committed booking between solve and apply must fail closed. (+1 more)

### Community 151 - "Community 151"
Cohesion: 0.18
Nodes (21): _slot(), test_mobility_restriction_prefers_lower_floor_only_if_hotel_has_no_elevator(), test_unknown_or_present_elevator_does_not_apply_floor_preference(), test_score_only_breaks_equivalent_room_tie(), test_room_assignment_rejects_pricing_objectives(), test_solver_only_locks_checked_in_or_explicitly_pinned_reservations(), test_paid_reservation_with_room_is_still_eligible_for_reassignment(), test_allocation_slots_exclude_pricing_data() (+13 more)

### Community 374 - "Community 374"
Cohesion: 0.24
Nodes (4): _Response, _Client, test_provider_receives_only_curated_hotel_analytics_payload(), test_provider_chat_uses_curated_hotel_context_and_controlled_message()

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (27): assert_freshness_metadata(), _wait_for_xlsx_completion(), _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_company_detail_and_exports_only_include_reservations_overlapping_the_selected_window(), test_streamed_detail_exports_match_materialized_payloads(), test_room_state_events_and_variable_cost_audit() (+19 more)

### Community 139 - "Community 139"
Cohesion: 0.08
Nodes (4): _SessionStub, test_checkout_transition_marks_reservation_outcome_completed(), 42c1aef Derive analytics outcomes from reservation status, 695afec Sync reservation outcome with lifecycle status

### Community 132 - "Community 132"
Cohesion: 0.11
Nodes (10): test_explicit_fact_refresh_repairs_legacy_currency_fact(), _make_fact_refresh_reservation(), _fact_business_snapshot(), test_targeted_reservation_fact_touch_matches_full_refresh(), test_targeted_refresh_preserves_facts_outside_union_window(), test_targeted_room_refresh_reapplies_events_only_for_affected_rooms(), test_targeted_reservation_fact_touch_isolated_by_hotel(), test_room_state_event_create_and_close_refresh_only_materialized_room_horizon() (+2 more)

### Community 303 - "Community 303"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed(), test_operational_schema_covers_dimensions_and_non_pii_facts()

### Community 142 - "Community 142"
Cohesion: 0.09
Nodes (9): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_add_reservation_guests_matches_existing_document_despite_whitespace(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_n06_cancel_errors_match_between_reservation_and_booking_routes(), test_n06_terminal_edit_and_stale_version_errors_are_localized_on_both_routes(), Spin up the real FastAPI app against an in-memory SQLite database. (+1 more)

### Community 375 - "Community 375"
Cohesion: 0.35
Nodes (7): FakeJwkClient, _token(), _verify(), test_valid_apple_token_is_verified(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch()

### Community 191 - "Community 191"
Cohesion: 0.31
Nodes (19): _post_request(), _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation() (+11 more)

### Community 479 - "Community 479"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 205 - "Community 205"
Cohesion: 0.11
Nodes (11): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_hotel_delete_is_restricted(), test_audit_log_all_actions_persist(), test_transaction_hotel_id_has_fk_constraint(), test_failed_audit_log_insert_does_not_roll_back_callers_change(), TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence. (+3 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (60): FakeResponse, _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend(), test_password_policy_requires_twelve_characters_for_register_and_reset(), test_register_verify_and_reset_use_resend_provider(), test_register_is_anti_enumeration_and_does_not_touch_existing_credentials() (+52 more)

### Community 446 - "Community 446"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_surfaces_retryable_provider_outage(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue()

### Community 643 - "Community 643"
Cohesion: 0.50
Nodes (3): _override_auth(), test_receptionist_can_get_price_quote(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+24 more)

### Community 206 - "Community 206"
Cohesion: 0.12
Nodes (5): _fix_operational_clock_time(), test_stock_and_linen_ledger_timestamps_use_hotel_business_clock(), test_laundry_batch_uses_business_date_for_timestamps_and_batch_code(), test_task_events_and_shift_handoffs_use_business_clock(), Local hotel-scoped business clock API and date isolation coverage.

### Community 644 - "Community 644"
Cohesion: 0.60
Nodes (4): _run_alembic(), test_local_business_clock_migration_adds_and_drops_only_its_table(), test_local_business_clock_migration_adopts_existing_bootstrap_table(), Alembic round-trip for the additive local business-clock table.

### Community 53 - "Community 53"
Cohesion: 0.06
Nodes (16): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+8 more)

### Community 143 - "Community 143"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+16 more)

### Community 586 - "Community 586"
Cohesion: 0.60
Nodes (5): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable(), Cancelling a reservation must cancel its still-payable seña links (BR §M).

### Community 408 - "Community 408"
Cohesion: 0.38
Nodes (9): _evaluate(), test_cancellation_inside_saved_free_window_has_no_penalty(), test_cancellation_after_cutoff_requires_approval_for_saved_percentage(), test_non_refundable_saved_plan_uses_full_total_without_creating_a_charge(), test_fixed_penalty_uses_saved_currency(), test_missing_snapshot_requires_manager_review_without_using_current_policy(), test_missing_checkin_time_requires_hotel_configuration(), test_invalid_policy_values_fail_closed_to_manager_review() (+1 more)

### Community 480 - "Community 480"
Cohesion: 0.32
Nodes (3): _load_migration(), FakeInspector, test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 540 - "Community 540"
Cohesion: 0.57
Nodes (6): _load_migration(), _run(), _create_minimal_schema(), test_cash_movement_void_migration_round_trips_without_history(), test_cash_movement_void_migration_refuses_to_drop_void_history(), SQLite regression coverage for auditable cash-movement voids.

### Community 63 - "Community 63"
Cohesion: 0.13
Nodes (39): _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_and_currency_is_allowed(), test_cash_movement_requires_open_session(), test_cash_movement_rejects_non_positive_amount_with_spanish_message(), test_close_report_expected_balance_from_confirmed_cash() (+31 more)

### Community 645 - "Community 645"
Cohesion: 0.60
Nodes (4): _load_migration(), _run(), test_cash_tender_change_migration_preserves_legacy_rows_and_validates_pairs(), SQLite migration coverage for separate cash tender, change, and tip amounts.

### Community 646 - "Community 646"
Cohesion: 0.40
Nodes (1): TestGuestValidation

### Community 542 - "Community 542"
Cohesion: 0.33
Nodes (1): TestCheckIn

### Community 277 - "Community 277"
Cohesion: 0.30
Nodes (14): _override_auth(), _client_with_db(), _seed_fully_paid_reservation(), _assert_reservation_response(), test_checkin_without_new_fields_fails_with_clear_message(), test_checkin_captures_missing_fields_in_same_request(), test_partial_checkin_reaches_pre_check_in_then_final_checkin(), test_checkout_room_lock_conflict_returns_409_and_rolls_back() (+6 more)

### Community 322 - "Community 322"
Cohesion: 0.44
Nodes (12): _override_auth(), _test_app(), _guest(), _seed_reservation(), _close(), test_each_guest_arrival_is_idempotent_and_only_first_occupies_room(), test_hotel_can_mark_reservation_checked_in_on_first_guest(), test_missing_guest_profiles_remain_visible_and_do_not_complete_party() (+4 more)

### Community 409 - "Community 409"
Cohesion: 0.20
Nodes (9): test_checkin_room_lock_refreshes_room_loaded_before_competing_status_change(), test_checkin_refreshes_concurrent_room_move_and_fails_fast_on_room_lock(), test_checkout_returns_retryable_conflict_when_another_transaction_holds_room(), test_checkout_allows_deferred_company_balance_without_financial_mutation_postgres(), PostgreSQL regressions for the check-in room row lock and ORM identity map., A stale eagerly loaded Room must not pass check-in after another commit., A moved reservation is refreshed before check-in; a busy room returns a conflict, Checkout uses PostgreSQL NOWAIT while holding the reservation lock. (+1 more)

### Community 125 - "Community 125"
Cohesion: 0.18
Nodes (27): _make_hotel(), _make_guest(), _make_room(), anchor_hotel_day_to_fixture_arrival(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin() (+19 more)

### Community 447 - "Community 447"
Cohesion: 0.58
Nodes (8): _get_db_override_target(), _override_auth(), _seed_hotel(), _build_client(), _cleanup_client(), test_owner_can_create_and_update_commercial_configuration(), test_manager_has_no_access_to_commercial_configuration(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories()

### Community 207 - "Community 207"
Cohesion: 0.23
Nodes (16): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), test_register_settlement_rolls_back_when_audit_cannot_be_written(), _company_reservation(), test_deferred_company_extension_does_not_calculate_or_record_base_price(), test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(), test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies() (+8 more)

### Community 448 - "Community 448"
Cohesion: 0.64
Nodes (8): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation(), test_company_document_cannot_be_attached_to_unlinked_reservation(), test_uploaded_company_voucher_is_private_signature_aware_and_tenant_scoped()

### Community 543 - "Community 543"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_requirements_do_not_implicitly_lock_allocation()

### Community 647 - "Community 647"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_columns(), test_company_extension_request_migration_upgrade_downgrade_upgrade(), SQLite round-trip for company extension request fields.

### Community 192 - "Community 192"
Cohesion: 0.20
Nodes (19): _company_reservation(), _transaction(), test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(), test_company_night_charge_batch_resolves_rate_history_with_bounded_queries(), test_company_night_charges_use_effective_rate_and_extra_person_quantity(), test_company_charge_quantity_cannot_exceed_registered_additional_people(), test_terminal_company_reservations_cannot_receive_new_nightly_charges(), test_legacy_rate_does_not_price_a_night_before_safe_cutover() (+11 more)

### Community 481 - "Community 481"
Cohesion: 0.46
Nodes (6): _run_alembic(), _seed_legacy_company(), test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only(), test_company_nightly_rate_downgrade_refuses_to_discard_user_history(), test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots(), SQLite upgrade coverage for company nightly rate cutover and rollback guard.

### Community 449 - "Community 449"
Cohesion: 0.39
Nodes (8): _seed_company_reservation(), test_company_terms_change_is_reviewed_without_silently_rewriting_booking(), test_manager_accepts_current_terms_without_repricing_and_retry_is_idempotent(), test_stale_company_config_requires_manager_to_reload_before_deciding(), test_legacy_reservation_without_snapshot_cannot_claim_to_keep_unknown_terms(), test_company_terms_review_does_not_disclose_reservation_across_hotels(), test_company_terms_review_rejects_closed_reservations_without_mutation(), Reservation-level review for changes to mutable company configuration.

### Community 482 - "Community 482"
Cohesion: 0.39
Nodes (6): example(), test_only_a_newer_observation_timestamp_may_change(), test_any_provider_subject_drift_is_rejected(), test_final_observation_cannot_predate_probes(), test_cli_rejects_symlinked_manifest(), Regression tests for final provider-evidence continuity.

### Community 87 - "Community 87"
Cohesion: 0.08
Nodes (15): get_db_override_target(), get_auth_context_target(), client_with_db(), ctx(), test_company_terms_checkin_bypass_toggle_requires_manager_authority(), test_config_read_permission_allows_get_without_allowing_updates(), test_co_owner_can_change_fx_market_after_step_up(), _override_role() (+7 more)

### Community 544 - "Community 544"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 126 - "Community 126"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 278 - "Community 278"
Cohesion: 0.28
Nodes (13): _create_role(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), _step_up_headers(), test_roles_api_contract_and_owner_co_owner_admin_mutations(), test_role_archive_refuses_active_members_and_pending_invites(), test_expired_pending_invitation_is_not_counted_or_blocking_role_archive(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed() (+5 more)

### Community 707 - "Community 707"
Cohesion: 0.83
Nodes (3): _cash_session(), test_cash_session_serialization_marks_legacy_naive_timestamp_as_utc(), test_cash_session_serialization_normalizes_aware_offset_to_utc()

### Community 450 - "Community 450"
Cohesion: 0.44
Nodes (8): _create_remitos(), _load_migration(), test_remito_preflight_reports_ids_and_trimmed_duplicates(), test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace(), test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved(), test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint(), test_remito_preflight_is_empty_when_no_duplicate_exists(), test_day2_downgrade_refuses_to_discard_persisted_operational_data()

### Community 545 - "Community 545"
Cohesion: 0.33
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 410 - "Community 410"
Cohesion: 0.42
Nodes (9): _legacy_deferred_reservation(), _payment(), test_deferred_reservation_read_and_list_mask_legacy_lodging_money(), test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(), test_pending_company_night_extra_remains_due_until_payment_completes(), test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(), test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(), test_deferred_reservation_group_masks_legacy_group_total() (+1 more)

### Community 239 - "Community 239"
Cohesion: 0.12
Nodes (6): client(), test_seed_and_reset_blocked_by_default(), test_seed_and_reset_allowed_when_demo_enabled(), FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Explicit development environments retain the DEMO_MODE workflow.

### Community 253 - "Community 253"
Cohesion: 0.21
Nodes (9): FakeRedis, _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_optional_lock_can_degrade_when_redis_is_unavailable(), FakePostgresSession, test_required_lock_uses_postgres_advisory_lock_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 172 - "Community 172"
Cohesion: 0.18
Nodes (16): use_redis_for_redis_outbox_replay_tests(), _seed_hotels(), _outbox_row(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision() (+8 more)

### Community 708 - "Community 708"
Cohesion: 0.67
Nodes (2): _alembic(), test_domain_event_outbox_migration_round_trips_on_fresh_sqlite()

### Community 161 - "Community 161"
Cohesion: 0.10
Nodes (7): _thread_safe_event_engine(), test_async_postgres_fallback_preserves_cursor_payload_and_tenant_isolation(), test_async_postgres_fallback_shares_poll_queries_across_streams(), test_async_postgres_listener_fans_out_without_idle_outbox_polls(), test_async_postgres_fallback_idle_wait_keeps_loop_responsive_and_cancels(), test_async_postgres_fallback_revalidates_membership_and_emits_control(), Share the in-memory SQLite connection with async iterator worker threads.

### Community 872 - "Community 872"
Cohesion: 1.00
Nodes (2): _isolate_realtime_configuration(), Keep Redis-default event tests independent of other test modules.

### Community 168 - "Community 168"
Cohesion: 0.11
Nodes (23): _event_engine(), _successful_publisher(), test_postgres_event_batch_select_omits_unneeded_outbox_payload(), test_outbox_cooldown_skips_later_durable_transaction_without_touching_row_metadata(), test_queued_domain_change_publishes_once_after_commit(), test_failed_durable_publish_leaves_later_durable_rows_pending_but_attempts_ephemeral_events(), test_successful_batch_publishes_each_durable_and_ephemeral_event(), test_outbox_rows_are_read_after_redis_with_their_hotel_context() (+15 more)

### Community 240 - "Community 240"
Cohesion: 0.13
Nodes (13): FakeRedis, _settings(), test_realtime_fallback_poll_is_bounded_when_listener_is_unavailable(), test_disabled_realtime_skips_model_outbox_work(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_permission_invalidation_publishes_without_error_logging(), test_optional_backend_degrades_without_fabricating_an_event(), test_required_backend_raises_when_unavailable() (+5 more)

### Community 279 - "Community 279"
Cohesion: 0.18
Nodes (6): _postgres_e2e_environment(), test_seed_guard_accepts_only_explicit_loopback_postgres_e2e_database(), test_seed_guard_accepts_secondary_ipv4_loopback_for_isolated_postgres(), test_seed_guard_accepts_explicit_high_local_postgres_port(), test_seed_guard_requires_a_distinct_explicit_seed_role_on_the_same_local_database(), test_seed_guard_rejects_postgres_without_the_dedicated_local_test_boundary()

### Community 254 - "Community 254"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, test_credential_access_and_email_stop_before_db_or_network(), test_connections_flag_alone_closes_credential_lane(), test_payment_link_test_stops_before_db_or_provider(), test_google_login_stops_before_transport_or_db(), test_apple_login_stops_before_jwks_or_db(), test_provider_callbacks_stop_before_body_parse() (+2 more)

### Community 588 - "Community 588"
Cohesion: 0.53
Nodes (5): _alembic(), _seed_legacy_links(), _assert_migrated(), test_payment_link_migration_backfills_provider_history_and_reupgrades(), Data-contract regression for the payment-link execution-mode migration.

### Community 589 - "Community 589"
Cohesion: 0.60
Nodes (5): _f003_environment(), test_f003_seed_accepts_only_dedicated_local_fixture_target(), test_f003_seed_requires_explicit_opt_in(), test_f003_seed_rejects_sqlite_even_with_opt_in(), test_f003_seed_rejects_database_outside_its_dedicated_namespace()

### Community 218 - "Community 218"
Cohesion: 0.19
Nodes (13): _make_completed_transaction(), test_daily_report_totals_a_completed_transaction_without_crashing(), test_revenue_report_totals_multiple_completed_transactions_without_crashing(), test_deferred_company_revenue_uses_scalar_reservation_projection(), test_revenue_report_projects_category_scalars_without_loading_rooms(), test_revenue_refunds_and_transaction_bounds_use_hotel_local_days(), test_booked_value_includes_and_prorates_stays_overlapping_the_report_window(), test_booked_value_endpoint_matches_full_report_with_bounded_query_count() (+5 more)

### Community 173 - "Community 173"
Cohesion: 0.15
Nodes (14): _FakeResponse, _quote(), _seed_expired_conversion_cache(), test_conversion_checks_provider_even_when_process_cache_is_recent(), test_fresh_quote_rejects_crossed_buy_sell_values(), test_recent_provider_response_with_friday_market_timestamp_is_current(), test_provider_response_cannot_supply_its_own_receipt_timestamp(), test_blue_equivalent_for_non_usd_currency_is_explicitly_derived() (+6 more)

### Community 648 - "Community 648"
Cohesion: 0.60
Nodes (4): _load_migration(), _side_columns(), test_fx_conversion_side_migration_backfills_defaults_and_round_trips_safely(), SQLite migration coverage for configurable USD conversion sides.

### Community 208 - "Community 208"
Cohesion: 0.13
Nodes (8): _step_up_header(), test_credit_refund_requires_refund_permission_step_up_and_cash_session(), Authorization and API contract checks for FX-credit cash refunds., _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_rejects_cancelled_reservations(), test_payment_links_api_cross_hotel_isolation(), test_payment_links_api_respects_explicit_manager_cash_operate_denial()

### Community 709 - "Community 709"
Cohesion: 0.83
Nodes (3): _load_migration(), _market_columns(), test_fx_direction_market_migration_preserves_global_market_and_guards_downgrade()

### Community 411 - "Community 411"
Cohesion: 0.33
Nodes (7): _quote(), test_daily_cache_upsert_keeps_one_row_and_never_replaces_newer_observation(), test_daily_snapshot_stores_each_supported_currency_and_derived_blue_rate(), test_reservation_conversion_reuses_recent_global_cache_without_provider_call(), test_reservation_conversion_refreshes_cache_after_three_hours(), test_provider_outage_uses_last_saved_quote_up_to_24_hours(), test_successful_provider_response_with_friday_timestamp_becomes_current_cache()

### Community 219 - "Community 219"
Cohesion: 0.28
Nodes (16): _reservation(), _open_cash(), _mock_usd_to_ars_quote(), _legacy_rounding_credit_payment(), test_configured_rounding_never_changes_exact_fx_principal_or_issues_credit(), test_arbitrary_fx_overpayment_is_rejected_even_when_rounding_is_configured(), test_same_currency_payment_remains_exact_under_fx_rounding_policy(), test_fx_payment_does_not_collect_a_tender_cent_that_exceeds_balance() (+8 more)

### Community 710 - "Community 710"
Cohesion: 0.67
Nodes (3): _load_migration(), test_credit_ledger_migration_preserves_old_rows_and_constrains_credit_refunds(), SQLite migration coverage for separate FX rounding-credit ledger fields.

### Community 711 - "Community 711"
Cohesion: 0.67
Nodes (3): _load_migration(), test_fx_rounding_policy_migration_defaults_existing_hotels_and_checks_allowed_policies(), SQLite coverage for the persisted foreign-payment FX rounding policy.

### Community 156 - "Community 156"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 451 - "Community 451"
Cohesion: 0.28
Nodes (3): _read(), test_generates_only_allowed_synthetic_values_with_private_permissions(), test_explicit_rotation_replaces_values_and_preserves_mode()

### Community 323 - "Community 323"
Cohesion: 0.19
Nodes (4): _Response, test_validate_provider_credentials_keeps_gmail_provider_validation(), test_validate_gmail_credentials_requires_send_scope(), test_verify_connection_health_for_gmail_updates_connection()

### Community 712 - "Community 712"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_direct_guest_and_companion_audits_exclude_pii(), test_decorator_mongo_projection_excludes_guest_pii()

### Community 713 - "Community 713"
Cohesion: 0.67
Nodes (3): _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite(), B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio

### Community 341 - "Community 341"
Cohesion: 0.42
Nodes (10): _seed_hotel(), _seed_reservation(), _step_up_headers(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_rejects_invalid_and_overlong_date_ranges(), test_guest_export_excludes_soft_deleted_guest_identity() (+2 more)

### Community 547 - "Community 547"
Cohesion: 0.52
Nodes (6): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) -- skip/

### Community 412 - "Community 412"
Cohesion: 0.42
Nodes (9): _isolate_realtime_configuration(), _auth(), _client(), test_restriction_api_permissions_tenant_isolation_and_event(), test_active_restriction_summary_is_batched_tenant_scoped_and_nondisclosing(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_restriction_override_reason_rejects_whitespace() (+1 more)

### Community 548 - "Community 548"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_legacy_tags(), _load_migration(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls()

### Community 376 - "Community 376"
Cohesion: 0.38
Nodes (10): _seed_hotel(), _seed_guest_inventory(), _reservation(), _create_payload(), test_restriction_lifecycle_distinguishes_active_expired_and_resolved(), test_restriction_is_tenant_scoped_for_reads_and_resolution(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override() (+2 more)

### Community 649 - "Community 649"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 280 - "Community 280"
Cohesion: 0.41
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 377 - "Community 377"
Cohesion: 0.18
Nodes (3): utc_server_clock(), The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today

### Community 378 - "Community 378"
Cohesion: 0.25
Nodes (6): _Response, _seed_gmail_connection(), _seed_mercadopago_connection(), test_send_hotel_email_uses_connected_gmail(), test_send_hotel_email_preserves_pdf_attachment_bytes_in_gmail_mime(), test_payment_link_test_requires_hotel_gmail_connection()

### Community 715 - "Community 715"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_hotel_schedule_migration_preserves_existing_settings_and_round_trips(), SQLite migration round-trip for hotel-local check-in and check-out times.

### Community 590 - "Community 590"
Cohesion: 0.53
Nodes (5): _load_migration(), _run(), _create_referenced_tables(), test_housekeeping_checklist_migration_creates_constrained_tenant_tables_and_guards_downgrade(), SQLite migration coverage for the fixed housekeeping checklist schema.

### Community 281 - "Community 281"
Cohesion: 0.23
Nodes (10): _checked_in_reservation(), _checkout(), _complete(), test_checkout_creates_fixed_checklist_and_final_item_releases_cleaning_room(), test_item_completion_is_idempotent_and_does_not_increment_version(), test_completing_checklist_preserves_maintenance_and_blocked_rooms(), test_open_checklist_blocks_direct_release_and_checkin_even_if_room_looks_ready(), test_complete_item_is_tenant_scoped() (+2 more)

### Community 650 - "Community 650"
Cohesion: 0.40
Nodes (3): test_postgres_checkout_checklist_and_room_audit_roll_back_atomically(), PostgreSQL tenant and concurrent item completion regressions., Checkout, checklist creation, and room audit share the caller transaction.

### Community 591 - "Community 591"
Cohesion: 0.53
Nodes (5): _run_alembic(), _assert_backfill(), test_housekeeping_status_migration_backfills_and_reverses_cleanly(), test_housekeeping_board_permission_migration_seeds_only_intended_roles(), Data migration guard for separating housekeeping state from room status.

### Community 716 - "Community 716"
Cohesion: 0.83
Nodes (3): _load_migration(), _run_migration(), test_migration_backfills_existing_accounts_and_retains_alias_on_rollback()

### Community 717 - "Community 717"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 651 - "Community 651"
Cohesion: 0.50
Nodes (2): RecordingMailer, test_staff_invitation_email_uses_human_role_labels()

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (53): get_db_override_target(), get_auth_context_target(), _invitation_token(), client_with_db(), owner_ctx(), _manage_users_request(), test_invite_returns_token_and_accepts(), test_atomic_invitation_consumption_rejects_a_rotated_token_hash() (+45 more)

### Community 520 - "Community 520"
Cohesion: 0.33
Nodes (3): _FakeDispatcher, JobDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 379 - "Community 379"
Cohesion: 0.40
Nodes (10): _seed(), _shortage_case(), _approve(), test_shortage_stays_pending_and_does_not_adjust_stock_until_authorized_resolution(), test_missing_linen_resolution_outcomes_keep_custody_and_ledger_consistent(), test_claim_or_replacement_remains_pending_until_physical_receipt(), test_vendor_credit_requires_explicit_negotiated_amount_and_currency(), test_excess_is_pending_identification_until_stock_acceptance_or_return() (+2 more)

### Community 718 - "Community 718"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_missing_follow_up_migration_backfills_shorts_and_guards_downgrade(), Backfill and preserve neutral follow-up for declared laundry shortages.

### Community 719 - "Community 719"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_missing_quantity_migration_defaults_existing_lines_and_round_trips(), Persist declared laundry losses without changing historical remito lines.

### Community 720 - "Community 720"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_house_location_migration_preserves_old_remitos_and_round_trips(), Add a nullable hotel-side location to new laundry remitos safely.

### Community 721 - "Community 721"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 133 - "Community 133"
Cohesion: 0.25
Nodes (26): _override_auth(), _client_with_db(), _teardown(), test_duplicate_remito_returns_conflict_but_other_direction_is_allowed(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_vendor_price_write_requires_laundry_price_permission(), test_manager_needs_explicit_vendor_price_permission(), test_owner_can_manage_linen_items_and_receptionist_cannot() (+18 more)

### Community 134 - "Community 134"
Cohesion: 0.21
Nodes (26): _seed_hotels(), _seed_house_stock(), _set_test_vendor_price(), test_create_vendor_creates_its_own_linen_location(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_inbound_reverses_the_transfer(), test_remito_number_is_unique_per_hotel_vendor_and_direction(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing() (+18 more)

### Community 722 - "Community 722"
Cohesion: 0.67
Nodes (3): _run_alembic(), test_linen_par_level_migration_constraints_and_upgrade_downgrade_upgrade(), Migration contract and SQLite round trip for location-specific linen minima.

### Community 549 - "Community 549"
Cohesion: 0.43
Nodes (6): _run_alembic(), _seed_pre_split_data(), test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade(), _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly, Hand-insert a real 'linen' StockItem plus movements and a laundry     vendor/pri

### Community 144 - "Community 144"
Cohesion: 0.15
Nodes (17): env_page(), FakeRender, mutations(), acquire_lease(), release_lease(), test_acquire_validates_before_writing_and_commits_id_last(), test_acquire_refuses_every_drift_without_mutation(), test_same_production_and_qa_identity_is_rejected_before_get() (+9 more)

### Community 483 - "Community 483"
Cohesion: 0.43
Nodes (7): _load_migration(), _load_data_migration(), test_migration_backfills_default_policy_and_is_idempotent(), test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(), test_ota_backfill_locks_row_before_recomputing_completed_ledger(), SQLite contract test for the new manual-payment/check-in-policy migration., A payment committed after candidate discovery must be in the backfill snapshot.

### Community 484 - "Community 484"
Cohesion: 0.43
Nodes (6): _scenario(), _simulate_expired_fx(), test_manual_fx_amount_is_reserved_once_then_cashier_records_that_exact_amount(), test_manual_fx_is_denied_while_a_current_automatic_quote_exists(), test_manual_fx_amount_cannot_exceed_reservation_balance_or_be_unaudited(), PostgreSQL regressions for manager-approved, reservation-specific FX amounts.

### Community 652 - "Community 652"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_schema(), test_manual_rate_policy_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for bounded manual reservation rates.

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (58): FakeResponse, _seed_platform_admin(), _complete_master_login(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_admin_absolute_ttl_expires_recently_active_session(), test_master_login_bootstraps_env_account() (+50 more)

### Community 485 - "Community 485"
Cohesion: 0.32
Nodes (6): _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it(), test_master_admin_dashboard_reads_hotels_without_outbox_rls_failure(), C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, A master-admin dashboard read may seed a missing subscription safely.      Snaps

### Community 342 - "Community 342"
Cohesion: 0.38
Nodes (12): _reservation(), _create_link(), _sign(), _post_webhook(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_duplicate_webhook_delivery_does_not_double_charge(), test_retryable_provider_failure_returns_503_without_persisting_then_redelivery_is_idempotent() (+4 more)

### Community 550 - "Community 550"
Cohesion: 0.43
Nodes (5): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), This bool-returning shim delegates to the SAME raising validator every     real

### Community 452 - "Community 452"
Cohesion: 0.22
Nodes (5): TestTransactionModel, Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship.

### Community 255 - "Community 255"
Cohesion: 0.13
Nodes (9): TestRoomModels, Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify the hotel has exactly 38 rooms., Same room_number can exist in different hotels without conflict., Verify room string representation. (+1 more)

### Community 413 - "Community 413"
Cohesion: 0.20
Nodes (6): TestGuestModel, Tests for Guest and GuestCompanion models., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Create companions and verify relationship., Verify auto-generated timestamps.

### Community 414 - "Community 414"
Cohesion: 0.20
Nodes (6): TestReservationModel, Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify can_transition_to method., Verify balance_due computed property., Verify nights calculation.

### Community 486 - "Community 486"
Cohesion: 0.25
Nodes (5): TestHotelConfigModel, Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies.

### Community 487 - "Community 487"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 723 - "Community 723"
Cohesion: 0.67
Nodes (3): _alembic(), test_migration_seeds_dedicated_permission_and_safe_role_defaults(), Regression coverage for the additive movement-group permission migration.

### Community 453 - "Community 453"
Cohesion: 0.39
Nodes (8): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel(), test_reset_endpoint_allows_testing_env()

### Community 324 - "Community 324"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 113 - "Community 113"
Cohesion: 0.09
Nodes (20): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+12 more)

### Community 343 - "Community 343"
Cohesion: 0.26
Nodes (7): _reservation(), test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(), test_sweep_anchors_configured_no_show_window_to_hotel_checkin_time(), test_sweep_sql_cutoff_filter_matches_elapsed_utc_hours_across_dst(), test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(), test_sweep_excludes_checked_in_and_is_idempotent(), test_sweep_is_tenant_scoped()

### Community 415 - "Community 415"
Cohesion: 0.20
Nodes (9): test_normalizes_generated_instruction_paths_without_touching_external_paths(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized(), Regression coverage for portable Graphify artifact normalization., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+1 more)

### Community 454 - "Community 454"
Cohesion: 0.50
Nodes (8): _auth(), _client(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_push_subscription_register_and_unregister(), test_preferences_crud(), test_daily_report_schedule_is_owner_co_owner_only(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and

### Community 848 - "Community 848"
Cohesion: 0.67
Nodes (1): Regression guard: verify the notification backend migration against a REAL `alem

### Community 135 - "Community 135"
Cohesion: 0.19
Nodes (26): _hotel(), _member(), test_enqueue_dedupes_same_event_recipient_channel(), test_notification_inbox_event_waits_until_outbox_delivery(), test_enqueue_same_dedupe_key_isolated_per_hotel(), test_enqueue_skips_recipient_without_entity_read_permission(), test_enqueue_skips_recipient_without_active_membership(), test_enqueue_role_based_fanout() (+18 more)

### Community 724 - "Community 724"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), test_process_outbox_delivers_across_every_active_hotel(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t

### Community 455 - "Community 455"
Cohesion: 0.50
Nodes (8): _owner(), _outbox_event_types(), test_reservation_lifecycle_enqueues_notifications(), test_no_show_enqueues_notification(), test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), Integration coverage: the real domain-event call sites (reservation lifecycle, c

### Community 380 - "Community 380"
Cohesion: 0.27
Nodes (9): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_owner_registration_without_outbox_override_does_not_return_503(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers. (+1 more)

### Community 653 - "Community 653"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 381 - "Community 381"
Cohesion: 0.31
Nodes (9): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_new_hotel_starts_with_cash_only(), test_onboarding_cannot_activate_paid_plan_without_checkout(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records() (+1 more)

### Community 345 - "Community 345"
Cohesion: 0.26
Nodes (7): _user(), _reservation(), _transaction(), test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(), test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(), test_operational_audit_filters_only_successful_logins(), Focused coverage for the operational audit and hotel-local cash projection.

### Community 849 - "Community 849"
Cohesion: 0.67
Nodes (1): PostgreSQL regression coverage for the stock movement audit projection.

### Community 174 - "Community 174"
Cohesion: 0.27
Nodes (19): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_today_arrival_count_is_server_side_hotel_local_and_not_page_limited(), test_operational_daily_report_separates_no_shows_from_arrivals(), test_occupancy_report_counts_pre_check_in_reservations(), test_daily_report_is_hotel_scoped() (+11 more)

### Community 382 - "Community 382"
Cohesion: 0.25
Nodes (4): MemoryObjectStorage, _create_task_context(), test_task_photo_is_private_tenant_scoped_and_integrity_checked(), test_task_photo_timestamp_uses_local_business_date()

### Community 220 - "Community 220"
Cohesion: 0.21
Nodes (16): _user(), test_task_lifecycle_history_and_stale_version(), test_task_due_at_round_trips_as_hotel_local_wall_clock(), test_task_comment_appends_history_without_changing_task_status(), test_housekeeping_can_read_all_general_tasks_but_cannot_operate_them(), test_task_author_fallback_is_hotel_scoped_and_used_by_list_create_and_update(), test_task_create_does_not_commit_before_author_resolution(), test_task_author_without_hotel_membership_does_not_expose_global_profile() (+8 more)

### Community 383 - "Community 383"
Cohesion: 0.24
Nodes (9): _booking_cancel_payload(), _wait_for_blocking_backend(), test_ota_cancellation_waits_for_checkin_and_uses_committed_status(), test_ota_modification_locks_reservation_before_room_after_extension(), test_ota_cancellation_does_not_follow_cross_hotel_reservation_mapping(), PostgreSQL regression for OTA cancellation racing with check-in., Cancellation waits for check-in's reservation lock, then requires review., A modification waits for an extension's reservation lock before room selection. (+1 more)

### Community 304 - "Community 304"
Cohesion: 0.36
Nodes (12): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_modify_after_checkin_or_checkout_rejects_stay_or_room_changes(), test_booking_modify_after_checkin_preserves_room_for_same_stay_and_category(), test_booking_modify_rechecks_locked_room_and_falls_back_or_marks_conflict(), test_booking_modify_without_room_keeps_confirmed_stay_and_terms_unchanged(), test_booking_modify_rechecks_current_room_after_lock_and_reassigns_on_conflict() (+4 more)

### Community 850 - "Community 850"
Cohesion: 0.67
Nodes (1): Regression guard for a real bug: `dee1bd0660f6_ota_allocation_foundation` create

### Community 256 - "Community 256"
Cohesion: 0.28
Nodes (14): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel() (+6 more)

### Community 241 - "Community 241"
Cohesion: 0.12
Nodes (8): TestBookingWebhook, TestExpediaWebhook, TestOTARaceCondition, TestAvailabilityUpdate, Tests for OTA Integration — Race condition handling and webhook processing., Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room.

### Community 242 - "Community 242"
Cohesion: 0.19
Nodes (9): _seed_hotel(), _assert_ota_payload_storage(), test_booking_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_ota_service_marks_unexpected_error_safely_before_caller_transaction_decision(), test_ota_webhook_returns_generic_500_for_unexpected_processing_error() (+1 more)

### Community 384 - "Community 384"
Cohesion: 0.53
Nodes (10): _load_migration(), _run(), _create_minimal_schema(), _manual_reference_index_sql(), test_payment_correction_migration_round_trips_when_history_is_empty(), test_payment_correction_upgrade_creates_target_index_when_legacy_index_is_missing(), test_payment_correction_upgrade_rejects_active_duplicates_before_schema_changes(), test_payment_correction_downgrade_preserves_schema_when_cancelled_duplicates_exist() (+2 more)

### Community 346 - "Community 346"
Cohesion: 0.42
Nodes (11): _add_manager_actor(), _target_reservation(), _payment(), test_manager_can_atomically_reassign_manual_payment_and_replay_idempotently(), test_receptionist_cannot_correct_payment(), test_duplicate_reversal_keeps_history_without_creating_a_replacement(), test_cash_reassignment_moves_existing_movement_and_preserves_drawer_totals(), test_cash_duplicate_reversal_voids_movement_and_excludes_it_from_drawer_totals() (+3 more)

### Community 179 - "Community 179"
Cohesion: 0.20
Nodes (17): _GatewayResponse, _preference_identity(), _mock_revocation_http(), _reservation(), _link(), _management_member(), test_cancel_link_queues_only_payable_mercado_pago_preferences(), test_cancel_active_links_queues_revocation_for_eligible_links_only() (+9 more)

### Community 726 - "Community 726"
Cohesion: 0.67
Nodes (3): _load_migration(), test_migration_queues_only_legacy_open_mp_links_for_cancelled_reservations(), SQLite coverage for the legacy payment-link revocation backfill.

### Community 727 - "Community 727"
Cohesion: 0.50
Nodes (1): PostgreSQL coverage for exclusive provider-revocation work claims.

### Community 243 - "Community 243"
Cohesion: 0.13
Nodes (3): _HotelRowsQuery, _FakeSession, test_enabled_task_visits_active_and_inactive_hotels_under_each_context()

### Community 193 - "Community 193"
Cohesion: 0.22
Nodes (16): _enable_external_effects(), _reservation(), test_create_payment_link_persists_link_without_transaction(), test_local_payment_link_rejects_currency_different_from_reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp() (+8 more)

### Community 347 - "Community 347"
Cohesion: 0.29
Nodes (9): _signature(), _post(), test_unsigned_reference_status_and_money_do_not_override_provider_payment(), test_provider_amount_matches_cents_sent_for_payment_link_test(), test_older_provider_snapshot_cannot_regress_a_newer_payment_state(), test_unknown_provider_status_preserves_state_and_records_diagnostic(), test_retryable_provider_fetch_failure_returns_503(), test_unsigned_reference_cannot_redirect_signed_payment_to_another_test_record() (+1 more)

### Community 180 - "Community 180"
Cohesion: 0.20
Nodes (20): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_submit_transfer_proof_validates_image_and_stores_metadata(), test_concurrent_metadata_conflict_deletes_the_uncommitted_upload(), test_failed_commit_after_upload_rolls_back_metadata_and_deletes_object(), test_ambiguous_commit_that_persisted_proof_keeps_its_object(), test_submit_transfer_proof_reencodes_and_removes_exif() (+12 more)

### Community 181 - "Community 181"
Cohesion: 0.26
Nodes (18): _completed_payment(), _mock_receipt_email(), _receipt_headers(), test_receipt_email_sends_persisted_receipt_once_and_records_auditable_outcome(), test_receipt_pdf_download_has_safe_headers_and_email_reuses_exact_pdf_bytes(), test_receipt_pdf_is_hidden_across_tenants_and_denied_without_cash_permission(), test_local_simulation_captures_test_email_and_pdf_without_provider_calls(), test_local_simulation_rejects_non_test_recipient_and_never_falls_back_to_gmail() (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.05
Nodes (18): _assign_hotel(), TestDepositPayment, TestHotelIsolation, TestPaymentEdgeCases, TestPaymentActorAudit, Assign hotel scope to reservation (hotel_id column provided by A1)., Tests for deposit (señas) payment flow., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status → (+10 more)

### Community 656 - "Community 656"
Cohesion: 0.40
Nodes (3): TestFullPayment, Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid.

### Community 657 - "Community 657"
Cohesion: 0.40
Nodes (3): TestBalancePaymentAtCheckin, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi

### Community 348 - "Community 348"
Cohesion: 0.44
Nodes (9): _override_auth(), _build_client(), _cleanup(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_reactivate_deactivated_surcharge_via_patch(), test_payment_surcharge_quote_endpoint_returns_exact_maximum_and_cash_suggestion() (+1 more)

### Community 551 - "Community 551"
Cohesion: 0.43
Nodes (4): _reservation(), test_payment_link_webhook_uses_the_saved_fixed_surcharge_quote(), test_quote_chooses_maximum_tender_without_exceeding_balance_and_returns_cash_suggestion(), test_signed_payment_quote_keeps_previewed_fx_and_surcharge_when_rate_changes()

### Community 91 - "Community 91"
Cohesion: 0.16
Nodes (32): _reservation(), _link(), _provider_result(), _management_member(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key() (+24 more)

### Community 416 - "Community 416"
Cohesion: 0.33
Nodes (9): _alembic(), test_permission_catalog_migration_is_additive_and_reversible(), test_operational_audit_cash_migration_is_safe_on_existing_schema(), test_housekeeping_occupancy_default_migration_tightens_without_touching_grant(), test_room_move_tier_migration_is_additive_idempotent_and_preserves_overrides(), test_permission_enforcement_migration_backfills_defaults_and_removes_sessions(), test_migrated_defaults_match_the_code_default_matrix(), Regression coverage for the additive permission-catalog migration. (+1 more)

### Community 152 - "Community 152"
Cohesion: 0.16
Nodes (12): _step_up_headers(), _auth(), _client(), test_owner_and_co_owner_can_use_administration_catalog_but_manager_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_owner_cannot_change_or_restore_another_owners_user_overrides(), test_owner_can_restore_one_role_override_to_catalog_default_with_audit(), test_owner_can_restore_one_user_override_to_role_default_with_audit() (+4 more)

### Community 244 - "Community 244"
Cohesion: 0.21
Nodes (14): _seed_hotel(), test_company_night_rate_permission_defaults_allow_management_roles(), test_permission_override_can_deny_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_owner_override_can_grant_permission_missing_from_role_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_resolve_many_preserves_user_role_and_hotel_override_precedence(), test_resolve_many_preserves_legacy_deny_fallback_and_invariants() (+6 more)

### Community 105 - "Community 105"
Cohesion: 0.20
Nodes (30): _override_auth(), _step_up_headers(), _client_with_db(), _enable_whatsapp_plan_for_api_test(), test_permissions_matrix_available_to_permission_manager_only(), test_permissions_matrix_exposes_only_canonical_rows_with_ui_metadata(), test_revoking_each_section_view_permission_blocks_its_read_endpoint(), test_subscription_status_does_not_claim_active_when_source_is_unavailable() (+22 more)

### Community 257 - "Community 257"
Cohesion: 0.26
Nodes (11): _load_migration(), _Result, _RecordingBind, _uppercase_catalog(), test_upgrade_normalizes_only_remaining_enum_labels_and_is_idempotent(), test_downgrade_reverses_only_the_new_migration(), test_upgrade_fails_closed_if_both_enum_labels_exist(), test_upgrade_fails_closed_when_an_expected_label_is_missing() (+3 more)

### Community 153 - "Community 153"
Cohesion: 0.09
Nodes (23): _reset_pg_to_empty_schema(), _reset_pg_to_clean_head(), test_alembic_upgrade_on_empty_database(), test_alembic_downgrade_and_reupgrade(), test_numeric_precision_enforced_on_postgres(), test_enum_types_exist_in_postgres(), test_unique_constraints_enforced_on_postgres(), test_explain_analyze_guest_search_index() (+15 more)

### Community 83 - "Community 83"
Cohesion: 0.10
Nodes (31): _bootstrap_environment(), _provider_manifest(), _local_evidence_payload(), _safe_environment(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_remote_target_rejects_self_attested_json_without_signed_token() (+23 more)

### Community 593 - "Community 593"
Cohesion: 0.47
Nodes (4): safe_preview_settings(), test_preview_runtime_accepts_explicitly_disabled_external_effects(), test_preview_runtime_rejects_external_effects_configuration(), Fail-closed safeguards for cloud QA external integrations.

### Community 162 - "Community 162"
Cohesion: 0.21
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (26): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+18 more)

### Community 282 - "Community 282"
Cohesion: 0.26
Nodes (14): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_rate_plan_price_extracts_included_taxes_and_fixed_fees(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(), test_all_supported_fx_pairs_use_directional_quotes_via_ars(), test_usd_conversion_uses_configured_side_per_direction_and_records_provenance() (+6 more)

### Community 325 - "Community 325"
Cohesion: 0.41
Nodes (12): _seed_hotel(), _seed_daily_rates(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_extracts_included_tax_from_daily_price(), test_canonical_promotion_pricing_converts_non_ars_currency_with_fx_snapshot() (+4 more)

### Community 258 - "Community 258"
Cohesion: 0.27
Nodes (14): _seed_hotel(), _ctx(), test_create_promotion_rejects_percentage_over_100(), test_create_promotion_rejects_duplicate_code(), test_find_applicable_promotions_matches_typed_conditions(), test_find_applicable_promotions_respects_weekday_and_date_range(), test_find_applicable_promotions_for_nights_batches_rules_and_guest_tags(), test_find_applicable_promotions_matches_guest_tag_type() (+6 more)

### Community 552 - "Community 552"
Cohesion: 0.71
Nodes (6): _override_auth(), _build_client(), _cleanup(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 553 - "Community 553"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_pre_migration_surcharge(), _load_migration(), test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data(), test_promotions_migration_owns_reversible_postgresql_rls()

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (21): manifest(), token_for(), env_page(), FakeRender, HealthResponse, FakeRenderCleanupFailure, FakeRenderPutResponseLost, _mutating_calls() (+13 more)

### Community 349 - "Community 349"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 221 - "Community 221"
Cohesion: 0.29
Nodes (16): _payload(), _configured_settings(), _inquiry_rows(), test_public_inquiry_persists_and_notifies_after_acceptance(), test_public_inquiry_keeps_record_when_notification_fails(), test_public_inquiry_rejects_invalid_required_fields(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_rate_limited_by_source_and_email() (+8 more)

### Community 488 - "Community 488"
Cohesion: 0.32
Nodes (3): _plan(), TestPublicPricing, A deploy that has not run the migration yet must not 500 the page.

### Community 456 - "Community 456"
Cohesion: 0.22
Nodes (1): TestLeadCapture

### Community 658 - "Community 658"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 259 - "Community 259"
Cohesion: 0.23
Nodes (14): tagged(), write_fixture(), test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_unsigned_or_fabricated_attestation_is_rejected(), test_altered_signature_is_rejected(), test_signed_attestation_missing_a_summary_hash_is_rejected() (+6 more)

### Community 283 - "Community 283"
Cohesion: 0.47
Nodes (13): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+5 more)

### Community 260 - "Community 260"
Cohesion: 0.32
Nodes (14): seed_rate_context(), test_rate_draft_requires_confirmation_and_keeps_reservation_price(), test_rate_confirmation_rolls_back_business_change_if_audit_write_fails(), test_stale_rate_draft_cannot_overwrite_a_newer_rate(), test_rate_draft_is_tenant_scoped(), test_rate_draft_rejects_unsafe_fields_and_duplicate_dates(), _period_draft_payload(), _period_values() (+6 more)

### Community 209 - "Community 209"
Cohesion: 0.12
Nodes (12): get_db_override_target(), get_auth_context_target(), client_with_db(), authed_client(), test_verify_email_code_guessing_is_rate_limited(), test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate(), test_register_is_rate_limited_by_source(), test_concurrent_db_requests_record_each_attempt_before_deciding() (+4 more)

### Community 659 - "Community 659"
Cohesion: 0.50
Nodes (3): _rate_price_migration(), test_postgres_rate_price_migration_refuses_rounding_and_reverses(), PostgreSQL behavior checks for exact money in active nightly rate tables.

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (63): _client(), _close(), _patch_legacy_booking(), test_daily_rate_snapshot_retains_original_pricing_channel(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_company_terms_review_requires_reservation_read_even_for_company_managers(), test_reservation_responses_redact_guest_documents_without_guest_view_permission(), test_company_extension_request_records_only_request_metadata_and_audit() (+55 more)

### Community 554 - "Community 554"
Cohesion: 0.48
Nodes (6): _load_migration(), _alembic(), _engine(), _seed_pre_revision(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal()

### Community 115 - "Community 115"
Cohesion: 0.13
Nodes (20): FakeRedis, BrokenRedis, isolate_read_model_cache(), _cache_settings(), _reset_cache_client_state(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising() (+12 more)

### Community 457 - "Community 457"
Cohesion: 0.36
Nodes (6): _add_event(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_missing_or_zero_cursor_requires_full_refetch(), test_stale_cursor_requires_full_refetch(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch()

### Community 458 - "Community 458"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 175 - "Community 175"
Cohesion: 0.24
Nodes (17): iso(), write_bundle(), rewrite_summary(), rewrite_manifest(), errors_for(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_short_code_sha_is_rejected(), test_manifest_byte_hash_is_required() (+9 more)

### Community 595 - "Community 595"
Cohesion: 0.60
Nodes (5): _load_workflow(), _job_block(), test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes(), test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled(), Contracts for opting provider-bound PR evidence checks in by label.

### Community 660 - "Community 660"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 417 - "Community 417"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 385 - "Community 385"
Cohesion: 0.33
Nodes (8): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors(), R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).  No real em

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (27): test_overdue_checked_in_stay_is_a_serialized_manual_review_action(), test_pending_action_candidate_cap_does_not_hide_later_critical_action(), _mk_reservation(), test_completed_paid_amounts_group_net_completed_transactions_and_scope_hotel(), test_pending_action_adjustment_batch_omits_rows_that_cannot_create_actions(), test_cancelled_reservation_never_offers_collection_action(), test_cancelled_direct_booking_with_net_paid_amount_surfaces_manual_refund_review(), test_no_show_direct_booking_with_legacy_net_paid_amount_surfaces_manual_refund_review() (+19 more)

### Community 596 - "Community 596"
Cohesion: 0.33
Nodes (1): Regression coverage for reservation arrival metadata and internal comments.

### Community 661 - "Community 661"
Cohesion: 0.60
Nodes (4): _load_migration(), _run(), test_cancellation_policy_snapshot_migration_is_nullable_reversible_and_does_not_backfill(), SQLite coverage for the reversible cancellation-policy snapshot column.

### Community 284 - "Community 284"
Cohesion: 0.30
Nodes (13): _auth(), cancellation_client(), _seed_reservation(), _set_now(), test_penalty_request_is_pending_idempotent_and_keeps_room_inventory(), test_legacy_bookings_cancel_route_uses_the_same_penalty_review_flow(), test_manager_approval_cancels_but_does_not_create_a_charge(), test_manager_rejection_leaves_reservation_active() (+5 more)

### Community 597 - "Community 597"
Cohesion: 0.53
Nodes (5): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_uses_reservation_currency_and_rejects_mismatch(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), Tests for operator-created reservation consumption charges.

### Community 418 - "Community 418"
Cohesion: 0.38
Nodes (9): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly(), test_invalid_recipient_is_rejected_before_provider(), test_local_example_test_address_is_accepted_but_never_forwarded(), test_production_rejects_example_test_recipient(), test_synthetic_email_does_not_expand_reservation_tenant_scope() (+1 more)

### Community 351 - "Community 351"
Cohesion: 0.39
Nodes (9): _seed_hotel(), _add_reservation(), _rows(), _step_up_headers(), test_reservation_export_requires_dedicated_permission(), test_reservation_export_uses_inclusive_occupancy_dates_and_hotel_scope(), test_reservation_export_neutralizes_formula_like_text(), test_reservation_export_rejects_invalid_and_overlong_date_ranges() (+1 more)

### Community 489 - "Community 489"
Cohesion: 0.43
Nodes (7): _paid_reservation(), test_postgres_paid_extension_preserves_booked_nightly_rate_when_no_active_rate(), test_postgres_paid_extension_still_rejects_other_pricing_errors(), test_postgres_paid_edit_keeps_booked_nightly_rate_when_no_active_rate(), test_postgres_collaborative_edit_recalculates_manual_total_for_shortened_stay(), test_postgres_paid_edit_keeps_dates_and_total_when_pricing_error_is_not_missing_rate(), PostgreSQL regressions for stay-extension pricing.

### Community 490 - "Community 490"
Cohesion: 0.25
Nodes (1): One operator-entered collection stays idempotent across grouped reservations.

### Community 598 - "Community 598"
Cohesion: 0.53
Nodes (5): _group_payloads(), test_create_four_room_company_group_and_aggregate_summary(), test_group_rejects_room_count_outside_bounds(), test_group_rejects_inconsistent_company_and_manual_totals(), Atomic multi-room reservation grouping and aggregate balance contracts.

### Community 386 - "Community 386"
Cohesion: 0.36
Nodes (10): _create_sample_reservation(), _completed_transaction(), test_no_show_can_be_marked_without_auto_charge(), test_date_change_without_payments_cancels_and_recreates(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_paid_date_change_refreshes_analytics_facts_once(), test_extension_requires_payment_or_link_action(), test_extension_rejects_checkout_not_after_current_checkout_in_spanish() (+2 more)

### Community 352 - "Community 352"
Cohesion: 0.26
Nodes (9): _make_reservations(), test_default_limit_caps_result_at_50(), test_skip_and_limit_page_through_results(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_listing_uses_one_scalar_reservation_query(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati (+1 more)

### Community 136 - "Community 136"
Cohesion: 0.32
Nodes (26): _override_auth(), _build_client(), _cleanup_client(), _seed_bookable_state(), _payload(), _manual_ota_payload(), test_receptionist_cannot_set_manual_total_amount(), test_co_owner_uses_confirmed_owner_level_manual_rate_access() (+18 more)

### Community 419 - "Community 419"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 728 - "Community 728"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 662 - "Community 662"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_permission_defaults(), test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade(), SQLite round-trip for the configurable reservation price permission.

### Community 491 - "Community 491"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 555 - "Community 555"
Cohesion: 0.48
Nodes (6): _reservation(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty(), test_search_does_not_leak_across_hotels(), Tests for the reservation global search filter (B1 header search).  Search is a

### Community 729 - "Community 729"
Cohesion: 0.50
Nodes (2): TestConfirmationCode, Tests for confirmation code generation.

### Community 285 - "Community 285"
Cohesion: 0.13
Nodes (7): TestAvailability, Tests for room availability checking., A room with no reservations should be available., A room with an overlapping reservation should not be available., Check-out day == next check-in day should be allowed (no overlap)., Find available rooms after booking some., Availability checks must not eagerly load room reservation histories.

### Community 169 - "Community 169"
Cohesion: 0.09
Nodes (9): TestReservationCreation, Tests for reservation creation logic., Create a standard reservation and verify computed fields., B4: manual tarifa on a direct reservation with no company_id -- the         auto, Reserve a specific room., Should fail for non-existent guest., Should fail when check-out is before check-in., Should fail when room doesn't match the requested category. (+1 more)

### Community 599 - "Community 599"
Cohesion: 0.33
Nodes (2): TestStateTransitions, Tests for reservation state machine transitions.

### Community 177 - "Community 177"
Cohesion: 0.18
Nodes (14): _RecordingSession, _install_recording_dependencies(), test_manual_total_update_mutation_and_audit_share_one_commit(), test_checkout_change_recalculates_manual_nightly_price_without_touching_paid_ledger(), test_checkout_extension_does_not_reprice_non_manual_reservation(), test_paid_total_adjustment_keeps_legacy_audit_key(), test_mutator_failure_propagates_without_audit_or_commit(), _authorization() (+6 more)

### Community 163 - "Community 163"
Cohesion: 0.18
Nodes (22): _role_connection(), _seed_engine(), _seed_session(), test_invitation_token_resolves_its_custom_role_under_forced_rls(), test_tenant_isolation_blocks_cross_hotel_reads(), test_payment_corrections_enforce_tenant_rls_for_read_and_write(), test_no_tenant_context_hides_all_rows(), test_master_admin_bypass_sees_all_hotels_subscriptions() (+14 more)

### Community 261 - "Community 261"
Cohesion: 0.31
Nodes (14): _seed_room_block_checkin_case(), _hold_room_for_checkin(), _wait_for_worker_blocked_by(), _start_block_mutation(), _cleanup_room_block_case(), test_postgres_create_block_rejects_existing_reservation_during_checkin(), test_postgres_extend_block_waits_for_checkin_then_rechecks_protected_reservation(), test_postgres_create_block_requires_allocation_proposal_to_clear_reservation() (+6 more)

### Community 222 - "Community 222"
Cohesion: 0.39
Nodes (17): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+9 more)

### Community 262 - "Community 262"
Cohesion: 0.31
Nodes (13): _override_auth(), _seed_room(), _seed_reservation(), test_create_and_resolve_room_block_api(), test_room_block_conflict_preview_returns_counts_without_reservation_identity(), test_room_block_conflict_preview_uses_create_permission_and_validates_dates(), test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(), test_room_block_extension_preview_and_mutation_keep_end_exclusive() (+5 more)

### Community 556 - "Community 556"
Cohesion: 0.29
Nodes (3): test_duplicate_room_number_returns_409(), Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro

### Community 210 - "Community 210"
Cohesion: 0.22
Nodes (15): _seed_move_shapes(), _move(), test_room_move_rejects_a_stale_reservation_version(), test_checked_in_room_move_returns_conflict_when_destination_checklist_is_open(), test_manager_can_override_open_checklist_for_checked_in_move_with_audited_reason(), test_reception_cannot_override_open_checklist_even_with_a_reason(), test_room_move_lock_conflict_returns_409_and_rolls_back(), test_receptionist_is_limited_to_same_category_moves() (+7 more)

### Community 420 - "Community 420"
Cohesion: 0.60
Nodes (9): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_receptionist_can_read_but_cannot_revert_room_movement_group(), test_explicit_receptionist_grant_can_revert_group(), test_company_group_revert_denies_reception_even_with_individual_company_manage_override(), test_housekeeping_cannot_read_or_revert_room_movement_group(), test_room_movement_group_cross_hotel_isolation() (+1 more)

### Community 421 - "Community 421"
Cohesion: 0.31
Nodes (8): _override_auth(), test_receptionist_can_list_rooms_without_loading_reservations(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_room_category_rates_are_batched_and_keep_daily_period_and_base_precedence(), test_custom_housekeeping_role_receives_safe_room_projection(), Reception needs to read room data to build reservations (room picker, availabili, GET /api/rooms/categories feeds the category picker on both the     Reservations

### Community 353 - "Community 353"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 194 - "Community 194"
Cohesion: 0.10
Nodes (6): test_company_night_charge_reservation_lock_targets_only_reservation(), test_company_night_charge_billing_adjustment_lock_targets_only_adjustment(), test_company_night_charge_payment_path_uses_reservation_lock_target(), Reservation has nullable joined relations, so payment locks must name the row., BillingAdjustment also eager-loads optional relations used by night-charge corre, The payment helper must lock the reservation despite joined optional relations.

### Community 116 - "Community 116"
Cohesion: 0.07
Nodes (8): test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured(), test_validate_runtime_security_ignores_incomplete_optional_integrations(), test_validate_runtime_security_rejects_localhost_redirect_when_service_configured(), test_validate_runtime_security_rejects_weak_master_admin_password_in_production(), MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., Partial integration env vars should not block production startup., OAuth redirect URIs are only validated when the corresponding service credential, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc

### Community 286 - "Community 286"
Cohesion: 0.23
Nodes (13): _headers(), test_security_overview_and_events_are_redacted_and_tenant_scoped(), test_manager_cannot_read_security_settings(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv(), test_security_csv_treats_formula_prefixed_actor_alias_as_text(), test_audit_surfaces_do_not_expose_mutating_methods(), test_unified_audit_timeline_combines_sources_orders_redacts_and_isolates_tenant(), test_unified_audit_timeline_supports_inclusive_date_filters_and_role_guard() (+5 more)

### Community 600 - "Community 600"
Cohesion: 0.53
Nodes (4): _values(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_env_file_requires_owner_only_permissions()

### Community 137 - "Community 137"
Cohesion: 0.09
Nodes (10): Surface, _request_context(), _make_reservation(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _card_value(), _starter_analytics() (+2 more)

### Community 601 - "Community 601"
Cohesion: 0.53
Nodes (5): _migrate(), _unique_column_sets(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi

### Community 557 - "Community 557"
Cohesion: 0.43
Nodes (4): RecordingMailer, test_staff_welcome_notice_contains_access_details_without_capabilities(), test_staff_role_notice_names_the_hotel_and_both_roles(), test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details()

### Community 853 - "Community 853"
Cohesion: 0.67
Nodes (1): SQLite contract test for persisted stay counts and deposit rule backfill.

### Community 223 - "Community 223"
Cohesion: 0.27
Nodes (17): _override_auth(), _client_with_db(), _teardown(), _second_hotel(), test_owner_can_delete_item_and_recreate_it_with_the_same_name(), test_duplicate_active_name_returns_clean_409_not_a_500(), test_stock_item_unit_cost_is_exposed_on_create_and_update(), test_stock_item_full_edit_updates_name_sku_unit_and_min_quantity() (+9 more)

### Community 245 - "Community 245"
Cohesion: 0.29
Nodes (16): _seed_hotels(), _movement(), test_consumption_report_totals_and_variation_between_periods(), test_consumption_report_excludes_adjustments_and_location_transfers(), test_consumption_report_is_hotel_scoped(), test_consumption_report_variation_is_none_without_a_previous_baseline(), test_consumption_report_rejects_invalid_group_by(), test_consumption_report_rejects_inverted_range() (+8 more)

### Community 664 - "Community 664"
Cohesion: 0.60
Nodes (4): _alembic(), _assert_revision_schema(), test_stock_count_migration_backfills_safe_defaults_and_round_trips(), SQLite migration round-trip for audited, hotel-scoped stock count sessions.

### Community 354 - "Community 354"
Cohesion: 0.52
Nodes (11): _override_auth(), _client_with_db(), _teardown(), _create_item(), _start_session(), test_count_recount_after_movement_and_manager_confirmation_are_atomic_and_idempotent(), test_count_confirmation_requires_configurable_permission_and_is_tenant_scoped(), test_count_session_rejects_overlapping_item_and_location_scopes() (+3 more)

### Community 730 - "Community 730"
Cohesion: 0.50
Nodes (3): test_confirmation_waits_for_inflight_movement_then_requires_recount(), PostgreSQL locking regression for stock-count confirmation., An in-flight movement cannot slip between stale-check and adjustment.

### Community 731 - "Community 731"
Cohesion: 0.50
Nodes (1): PostgreSQL-backed contract checks for stock movement idempotency.

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (33): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_stock_movement_rejects_precision_beyond_persisted_scale(), test_stock_movement_rejects_quantity_beyond_persisted_precision(), test_stock_outbound_cannot_make_quantity_negative(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(), test_stock_adjustment_can_correct_quantity_downward() (+25 more)

### Community 665 - "Community 665"
Cohesion: 0.60
Nodes (4): _run_alembic(), _assert_transfer_schema(), test_stock_transfer_migration_upgrade_downgrade_upgrade(), SQLite migration round-trip for linked stock transfer movements.

### Community 558 - "Community 558"
Cohesion: 0.33
Nodes (2): _Session, test_subscription_session_closes_before_asgi_work()

### Community 602 - "Community 602"
Cohesion: 0.73
Nodes (5): _run_alembic(), _plan_values(), test_publishes_approved_prices_without_overwriting_admin_values(), test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(), test_price_migration_downgrade_restores_preexisting_currency_and_period()

### Community 195 - "Community 195"
Cohesion: 0.17
Nodes (16): _ensure_hotel(), _auth_headers(), _step_up_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_trial_does_not_replace_existing_legacy_paid_plan(), test_comped_override_requires_master_admin_session_before_disclosing_hotel_state(), test_role_gating_for_trial_and_comped_override() (+8 more)

### Community 492 - "Community 492"
Cohesion: 0.32
Nodes (3): _direction(), test_direction_requires_matching_occupancy_and_pickup_signals(), test_marked_high_demand_event_always_points_up()

### Community 732 - "Community 732"
Cohesion: 0.67
Nodes (3): _index_names(), test_hot_path_composite_indexes_exist_in_models(), Focused regression tests for the TECH-0063 OLTP audit fixes.

### Community 117 - "Community 117"
Cohesion: 0.24
Nodes (26): _reservation_id(), _create_reservation(), _request(), _approve(), _set_cancel_permission(), _consume(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(), test_owner_can_view_and_revoke_active_grants_without_exposing_token() (+18 more)

### Community 493 - "Community 493"
Cohesion: 0.25
Nodes (3): test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(), C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them.

### Community 118 - "Community 118"
Cohesion: 0.11
Nodes (19): _load_rls_migration(), _load_user_override_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_company_night_charge_tenant_migration(), _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract(), test_tenant_composite_fk_migrations_cover_every_scoped_relationship() (+11 more)

### Community 119 - "Community 119"
Cohesion: 0.14
Nodes (18): iso(), evidence_bytes(), FakeGitHub, prepare(), test_trusted_prepare_and_finalize_accept_only_byte_identical_provider_artifact(), test_finalize_rejects_artifact_with_different_bytes(), test_prepare_rejects_release_change_after_qa_code_sha(), test_prepare_rejects_unsuccessful_provider_workflow() (+10 more)

### Community 224 - "Community 224"
Cohesion: 0.12
Nodes (5): _bearer_headers(), test_postgres_concurrent_refreshes_recover_the_same_successor(), test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_session_listing_individual_revoke_logout_and_revoke_all(), Real row locks serialize overlapping refreshes without losing the cookie.

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (18): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _http_request(), _make_reservation(), _make_transaction() (+10 more)

### Community 155 - "Community 155"
Cohesion: 0.12
Nodes (23): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_preserves_explicit_negotiated_nightly_rate(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_downgrades_fully_paid_when_recalculated_total_exceeds_paid() (+15 more)

### Community 35 - "Community 35"
Cohesion: 0.06
Nodes (27): _make_reservation(), _pay_deposit(), _pay_full(), TestCheckinRoomReadiness, TestPaymentGateDepositPaid, TestPaymentGatePending, TestConfigFlag, TestCheckoutGate (+19 more)

### Community 356 - "Community 356"
Cohesion: 0.17
Nodes (7): TestGuestValidationGates, Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest who has NOT accepted terms is blocked (terms_accepted=False)., When require_document_for_checkin=False, missing document is not an error., When require_terms_acceptance=False, missing terms is not an error.

### Community 357 - "Community 357"
Cohesion: 0.33
Nodes (11): opened_cash_register(), _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains(), test_checkout_allows_deferred_company_balance_without_changing_financial_records(), test_checkout_still_blocks_company_without_deferred_payment_when_balance_remains() (+3 more)

### Community 287 - "Community 287"
Cohesion: 0.42
Nodes (12): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+4 more)

### Community 494 - "Community 494"
Cohesion: 0.29
Nodes (3): _make_period(), TestResolveRateCalendar, Tier-2: active PricePeriod used when no DailyRate exists.

### Community 288 - "Community 288"
Cohesion: 0.13
Nodes (8): TestGetPriceForDate, Tier-1: explicit DailyRate row wins over everything else., An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used., When two PricePeriods overlap, the one with higher priority is returned.

### Community 876 - "Community 876"
Cohesion: 1.00
Nodes (1): DailyRate explicit row takes priority over an active PricePeriod.

### Community 875 - "Community 875"
Cohesion: 1.00
Nodes (1): PricePeriod is NOT used for dates outside its range.

### Community 358 - "Community 358"
Cohesion: 0.17
Nodes (6): TestApplyPricePeriod, apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price.

### Community 666 - "Community 666"
Cohesion: 0.40
Nodes (3): TestPricePeriodOverlap, Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics).

### Community 459 - "Community 459"
Cohesion: 0.22
Nodes (5): TestDailyRateModelConstraints, Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss.

### Community 559 - "Community 559"
Cohesion: 0.29
Nodes (4): TestPricePeriodModel, PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on

### Community 225 - "Community 225"
Cohesion: 0.22
Nodes (17): opened_cash_register(), _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_extension_impact_plan_is_read_only_and_contains_only_operational_fields(), test_extension_rejects_missing_confirmation_without_mutation() (+9 more)

### Community 145 - "Community 145"
Cohesion: 0.11
Nodes (14): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_manual_move_does_not_implicitly_lock_reservation(), test_edit_room_change_does_not_implicitly_lock_reservation(), test_owner_can_explicitly_lock_manual_room_assignment() (+6 more)

### Community 211 - "Community 211"
Cohesion: 0.19
Nodes (16): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_receptionist_can_list_movement_groups_but_cannot_revert_them(), test_housekeeping_cannot_list_read_or_revert_movement_groups(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_aborts_when_origin_room_lock_is_contended(), test_revert_group_service_conflict_does_not_overwrite_original_room() (+8 more)

### Community 422 - "Community 422"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 495 - "Community 495"
Cohesion: 0.25
Nodes (5): TestReoptimizationTrigger, §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect.

### Community 423 - "Community 423"
Cohesion: 0.20
Nodes (5): TestReoptimizationIntegration, §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, The background task must commit and close its own DB session., If run_persisted_allocation raises, rollback must be called (not commit).

### Community 79 - "Community 79"
Cohesion: 0.06
Nodes (21): _make_reservation(), TestWaitlistModelFields, TestWaitlistListing, TestWaitlistResolveLogic, TestWaitlistIsolation, Helper — create a reservation through the service layer., The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room. (+13 more)

### Community 496 - "Community 496"
Cohesion: 0.25
Nodes (5): TestOverbookingBlocked, When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., Six physical Twin rooms hold six overlapping stays; the seventh is         rejec

### Community 603 - "Community 603"
Cohesion: 0.33
Nodes (4): TestWaitlistCreation, When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable.

### Community 387 - "Community 387"
Cohesion: 0.29
Nodes (6): _context(), _reserve(), _hotel_today(), test_visibility_window_filters_far_future_and_null_is_unlimited(), test_in_house_guest_remains_visible_when_check_in_predates_window(), Regression tests for tenant-scoped, per-role reservation visibility.

### Community 560 - "Community 560"
Cohesion: 0.48
Nodes (5): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation(), test_waitlist_suggestion_is_feasibility_only_and_does_not_promote(), test_waitlist_promotion_rejects_entry_changed_after_suggestion()

### Community 424 - "Community 424"
Cohesion: 0.38
Nodes (8): _hotel_id(), _race_two_sessions(), _seed_payment_target(), test_same_payment_webhook_is_idempotent_under_two_postgres_sessions(), test_distinct_payment_events_share_one_payment_and_transaction_under_postgres_lock(), test_same_ota_reservation_is_materialized_once_under_two_postgres_sessions(), Two-session idempotency regressions for inbound payment and OTA webhooks.  These, Hold the first real PostgreSQL lock until the second session is waiting.

### Community 604 - "Community 604"
Cohesion: 0.60
Nodes (5): _request(), test_rejects_oversized_content_length_before_reading_body(), test_rejects_chunked_body_that_exceeds_limit(), test_accepts_body_at_exact_limit(), test_rejects_malformed_content_length()

### Community 668 - "Community 668"
Cohesion: 0.70
Nodes (4): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 497 - "Community 497"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 425 - "Community 425"
Cohesion: 0.53
Nodes (8): _seed_hotel(), _issue_key(), _headers(), _whatsapp_quote(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

### Community 305 - "Community 305"
Cohesion: 0.31
Nodes (12): _signature(), _post(), _message(), _delivery(), test_rejects_a_delivery_whose_signature_does_not_match(), test_ingests_a_signed_inbound_message(), test_one_unusable_message_does_not_discard_the_rest_of_the_batch(), test_tolerates_a_payload_whose_nested_fields_are_not_objects() (+4 more)

### Community 629 - "Community 629"
Cohesion: 0.40
Nodes (5): 0c4b2d1 Refresh Graphify and generated inventories, 6e9297c Prevent allocation starvation across hotels, 7650c16 Fix allocation queue tenant rotation and stale TTL, 9702c0f Polish room status summary hierarchy, b4d2a10 Refine room status summary hierarchy

## Knowledge Gaps
- **2965 isolated node(s):** `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som`, `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.` (+2960 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 733`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 734`** (1 nodes): `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 735`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 736`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 737`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 738`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 739`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 740`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 741`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 742`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 743`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 744`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 745`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 746`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 747`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 748`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 749`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 750`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 751`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 752`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 753`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 754`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 755`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 756`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 757`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 758`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 759`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 760`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 761`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 762`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 763`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 764`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 765`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 766`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 767`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 768`** (1 nodes): `Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 769`** (1 nodes): `Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 770`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 771`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 772`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 773`** (1 nodes): `stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 774`** (1 nodes): `add external-effect mode to payment links  Revision ID: 20260812_external_effect`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 775`** (1 nodes): `repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 776`** (1 nodes): `add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 777`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 778`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 779`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 780`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 781`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 782`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 783`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 784`** (1 nodes): `Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  ``
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 785`** (1 nodes): `add public marketing pricing plans and early-access leads  Revision ID: 20260910`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 786`** (1 nodes): `Add a dedicated permission for reverting room-movement groups.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 787`** (1 nodes): `Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 788`** (1 nodes): `Add an index for tenant-scoped outbox cursor recovery polling.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 789`** (1 nodes): `Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 790`** (1 nodes): `Configure official or blue USD quotes by conversion direction.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 791`** (1 nodes): `Store external OTA payment amounts in their source currency.  Revision ID: 20261`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 792`** (1 nodes): `Add the corporate channel to the analytics fact enum.  Reservation.channel_code`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 793`** (1 nodes): `Persist configurable deposit bands and stay-night counts.  Revision ID: 20261018`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 794`** (1 nodes): `Record FX rounding credit and manual credit refunds separately.  Revision ID: 20`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 795`** (1 nodes): `Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 796`** (1 nodes): `Track Mercado Pago checkout revocation separately from local cancellation.  Revi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 797`** (1 nodes): `Track auditable voids for open-session cash corrections.  Revision ID: 20261024_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 798`** (1 nodes): `Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 799`** (1 nodes): `Add a dedicated permission for reading company vouchers and signatures.  Revisio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 800`** (1 nodes): `Add the keyset pagination index for WhatsApp message history.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 801`** (1 nodes): `Add elevator knowledge and soft allocation preferences by room.  Revision ID: 20`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 802`** (1 nodes): `Persist the latest shared DolarAPI rates for bounded outage fallback.  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 803`** (1 nodes): `Persist authorized manual FX payment amounts per reservation.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 804`** (1 nodes): `Record cash change currency and support paired cash movement corrections.  Revis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 805`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 806`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 807`** (1 nodes): `add reservation internal comment  Revision ID: 63f2a956b2b2 Revises: 20260904_op`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 808`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 809`** (1 nodes): `laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 810`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 811`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 812`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 813`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 814`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 815`** (1 nodes): `track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 816`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 817`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 818`** (1 nodes): `laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 819`** (1 nodes): `reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 820`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 821`** (1 nodes): `Add tenant-scoped object metadata without deleting legacy file references.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 511`** (1 nodes): `SimpleRateLimiter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 823`** (1 nodes): `Public contact form endpoint for the marketing site.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 465`** (1 nodes): `Public WhatsApp bot hooks authenticated only by hotel API key.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 857`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 858`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 859`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 864`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 831`** (2 nodes): `CashSession`, `Single currency-specific cash-register shift. A hotel may keep one open     sess`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 830`** (2 nodes): `CashMovement`, `Individual money movement within an open cash session.     Linked optionally to`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 691`** (2 nodes): `Connection`, `Connection model for external provider integrations. Stores credentials/settings`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 832`** (2 nodes): `DailyRate`, `Explicit nightly price for a specific category and date.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 833`** (2 nodes): `PricePeriod`, `Named date-range season/period for bulk rate loading.      Higher ``priority`` w`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 834`** (2 nodes): `DomainEventRetentionWatermark`, `Tenant-scoped cursor watermarks used by outbox retention cleanup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 692`** (2 nodes): `StaffInvitation`, `Persisted staff invitations and their one-time acceptance state.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 215`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 835`** (1 nodes): `PaymentLinkTest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 694`** (2 nodes): `CategoryPricing`, `Archived legacy pricing shape kept for migration/test compatibility.      Runtim`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 836`** (2 nodes): `RateLimitEvent`, `Persistent rate-limit events for security-sensitive endpoints.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 837`** (2 nodes): `SecurityAuditLog`, `Security / access audit log — free-form operational security events.  Distinct f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 838`** (2 nodes): `Transaction`, `Financial transaction linked to a reservation.     Every money movement is recor`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 697`** (2 nodes): `User`, `User accounts for authentication. Stores hashed passwords and basic profile flag`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 248`** (2 nodes): `_normalize_currency()`, `HotelConfigUpdate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 633`** (1 nodes): `HotelIdentityPayload`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 579`** (1 nodes): `ManualOTAReservationCreate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 699`** (2 nodes): `ReservationChargeCreate`, `Operator-created consumption or extra charge for an active stay.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 634`** (2 nodes): `PaymentCorrectionRequest`, `Reverse an erroneous payment record and optionally reassign it.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 580`** (2 nodes): `PaymentRequest`, `Client-facing payment request (e.g. from booking cart).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 702`** (2 nodes): `_MappedQueryRows`, `Re-iterable, bounded-memory projection over a SQLAlchemy query.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 862`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 842`** (2 nodes): `build_gemma_hotel_context()`, `_enum_value()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 369`** (2 nodes): `LocalObjectStorage`, `Stores objects as files under a local directory root.      Generalizes the patte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 865`** (1 nodes): `Foundational OTA adapter interfaces and orchestration services.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 146`** (2 nodes): `BookingAdapter`, `Acknowledge processed reservation messages in Booking's queue.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 263`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 264`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 839`** (1 nodes): `ExampleInstrumentedTest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 824`** (2 nodes): `MainActivity`, `BridgeActivity`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 840`** (1 nodes): `ExampleUnitTest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 863`** (1 nodes): `config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 829`** (2 nodes): `source`, `{ code }`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 826`** (1 nodes): `2f1f92f Show cached analytics report freshness`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 687`** (1 nodes): `receptionistCredentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 688`** (2 nodes): `totpAt()`, `login()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 689`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 827`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 630`** (2 nodes): `mobileNavigationDialog()`, `openMobileMenu()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 828`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 825`** (2 nodes): `frontendRoot`, `25f23f7 Clarify missing room event history details`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 822`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 841`** (1 nodes): `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 705`** (1 nodes): `Current hotel membership aliases label historical actor projections.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 646`** (1 nodes): `TestGuestValidation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 542`** (1 nodes): `TestCheckIn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 545`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 708`** (2 nodes): `_alembic()`, `test_domain_event_outbox_migration_round_trips_on_fresh_sqlite()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 872`** (2 nodes): `_isolate_realtime_configuration()`, `Keep Redis-default event tests independent of other test modules.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 717`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 651`** (2 nodes): `RecordingMailer`, `test_staff_invitation_email_uses_human_role_labels()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 848`** (1 nodes): `Regression guard: verify the notification backend migration against a REAL `alem`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 849`** (1 nodes): `PostgreSQL regression coverage for the stock movement audit projection.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 850`** (1 nodes): `Regression guard for a real bug: `dee1bd0660f6_ota_allocation_foundation` create`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 727`** (1 nodes): `PostgreSQL coverage for exclusive provider-revocation work claims.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 456`** (1 nodes): `TestLeadCapture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 458`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 596`** (1 nodes): `Regression coverage for reservation arrival metadata and internal comments.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 490`** (1 nodes): `One operator-entered collection stays idempotent across grouped reservations.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 729`** (2 nodes): `TestConfirmationCode`, `Tests for confirmation code generation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 599`** (2 nodes): `TestStateTransitions`, `Tests for reservation state machine transitions.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 853`** (1 nodes): `SQLite contract test for persisted stay counts and deposit rule backfill.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 731`** (1 nodes): `PostgreSQL-backed contract checks for stock movement idempotency.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 558`** (2 nodes): `_Session`, `test_subscription_session_closes_before_asgi_work()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 876`** (1 nodes): `DailyRate explicit row takes priority over an active PricePeriod.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 875`** (1 nodes): `PricePeriod is NOT used for dates outside its range.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BookingAdapter` connect `Community 146` to `Community 307`, `Community 187`?**
  _High betweenness centrality (0.006) - this node is a cross-community bridge._
- **Why does `VerificationError` connect `Community 93` to `Community 431`, `Community 140`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **Why does `OTAIntegrationService` connect `Community 39` to `Community 1`?**
  _High betweenness centrality (0.004) - this node is a cross-community bridge._
- **What connects `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som`, `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082` to the rest of the system?**
  _2965 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 5` be split into smaller, more focused modules?**
  _Cohesion score 0.009603211363285472 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.005584542094236646 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.006373929853631594 - nodes in this community are weakly interconnected._