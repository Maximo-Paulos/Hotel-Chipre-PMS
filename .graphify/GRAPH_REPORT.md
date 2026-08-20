# Graph Report - .  (2026-08-20)

## Corpus Check
- Large corpus: 1024 files · ~1,641,815 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 9896 nodes · 44700 edges · 360 communities detected
- Extraction: 64% EXTRACTED · 36% INFERRED · 0% AMBIGUOUS · INFERRED: 16136 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 16136 · ON_BRANCH: 9459 · contains: 5831 · calls: 4255 · MODIFIES: 3190 · rationale_for: 2013 · imports: 1078 · imports_from: 829 · PARENT_OF: 653 · inherits: 637 · method: 616 · re_exports: 3


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1024 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 11 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `4ef3eca`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 943 edges
2. `ReservationStatusEnum` - 939 edges
3. `HotelConfiguration` - 915 edges
4. `Room` - 769 edges
5. `Guest` - 725 edges
6. `RoomCategory` - 703 edges
7. `Base` - 534 edges
8. `RoomStatusEnum` - 473 edges
9. `ReservationError` - 437 edges
10. `ReservationSourceEnum` - 367 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati` --uses--> `HotelConfiguration`  [INFERRED]
  tests/perf/explain_probe.py → app/models/hotel_config.py
- `POST /api/checkin/checkout only enforced authentication (get_auth_context),` --uses--> `ReservationStatusEnum`  [INFERRED]
  tests/smoke/test_reservation_operations.py → app/models/reservation.py
- `GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti` --uses--> `ReservationStatusEnum`  [INFERRED]
  tests/smoke/test_reservations_api_roles.py → app/models/reservation.py
- `Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py

## Communities

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (87): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c, master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a, master admin system owner mail and stripe settings  Revision ID: 20260421_master (+79 more)

### Community 1 - "Community 1"
Cohesion: 0.09
Nodes (341): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho, v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event, _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re (+333 more)

### Community 31 - "Community 31"
Cohesion: 0.06
Nodes (30): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2, add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio, add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D, _remaining_trial_days(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial() (+22 more)

### Community 316 - "Community 316"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (68): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em, reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif, ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026, ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026, ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d, baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7, _DecimalAwareEncoder, Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files. (+60 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (41): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard, add trial and comped fields to subscriptions  Revision ID: 20260419_subscription, FastAPI routes for the onboarding flow used by smoke tests., Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr, OnboardingProviderSetup, OnboardingStatus, OwnerPayload, HotelIdentityPayload (+33 more)

### Community 317 - "Community 317"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 337 - "Community 337"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 338 - "Community 338"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 339 - "Community 339"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 340 - "Community 340"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 293 - "Community 293"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 341 - "Community 341"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 342 - "Community 342"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 343 - "Community 343"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 344 - "Community 344"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 345 - "Community 345"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 346 - "Community 346"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 347 - "Community 347"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 348 - "Community 348"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 349 - "Community 349"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 350 - "Community 350"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 351 - "Community 351"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 352 - "Community 352"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 353 - "Community 353"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 354 - "Community 354"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 355 - "Community 355"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 249 - "Community 249"
Cohesion: 0.46
Nodes (7): _sqlite_rebuild_constraints(), _repair_sqlite(), _existing_enum_labels(), _rename_postgres_enum_values(), upgrade(), downgrade(), Align allocation enum storage with the model values.  The original allocation mi

### Community 271 - "Community 271"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat

### Community 294 - "Community 294"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), _drop_successor_reference(), upgrade(), downgrade(), Add zero-balance cash rotation and custody handoffs.

### Community 295 - "Community 295"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio

### Community 296 - "Community 296"
Cohesion: 0.47
Nodes (4): _has_unique(), _has_fk(), upgrade(), Complete tenant-leading foreign keys outside the core booking domain.  The core

### Community 356 - "Community 356"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 357 - "Community 357"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 272 - "Community 272"
Cohesion: 0.52
Nodes (6): _constraint(), _repair_sqlite(), _rename_postgres_values(), upgrade(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all

### Community 250 - "Community 250"
Cohesion: 0.36
Nodes (6): _has_unique(), _has_fk(), _add_constraint_if_missing(), upgrade(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in

### Community 318 - "Community 318"
Cohesion: 0.60
Nodes (4): _constraint(), upgrade(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could

### Community 358 - "Community 358"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 196 - "Community 196"
Cohesion: 0.29
Nodes (10): upgrade(), _create_linen_tables(), _migrate_linen_data(), _finalize_laundry_vendor_columns(), _drop_kind_column(), downgrade(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li (+2 more)

### Community 359 - "Community 359"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 360 - "Community 360"
Cohesion: 0.50
Nodes (1): stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (169): add external-effect mode to payment links  Revision ID: 20260812_external_effect, Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, _generate_code(), _mask_email(), _build_auth_response(), _issue_email_token(), register(), request_verify() (+161 more)

### Community 159 - "Community 159"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), _install_rls(), _remove_rls(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), upgrade(), downgrade(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill (+5 more)

### Community 174 - "Community 174"
Cohesion: 0.24
Nodes (12): _insert_permission_rows(), _upsert_default(), _backfill_defaults(), _copy_role_overrides(), upgrade(), _install_user_override_rls(), _remove_user_override_rls(), _contract_legacy_rows() (+4 more)

### Community 251 - "Community 251"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table.

### Community 252 - "Community 252"
Cohesion: 0.32
Nodes (7): _install_rls(), _remove_rls(), upgrade(), downgrade(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table.

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (20): repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/, add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide, Build the canonical quote shared by reservation-facing surfaces., ExampleInstrumentedTest, MainActivity, BridgeActivity, ExampleUnitTest, config (+12 more)

### Community 361 - "Community 361"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 319 - "Community 319"
Cohesion: 0.60
Nodes (4): _check_clause(), upgrade(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in

### Community 362 - "Community 362"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 119 - "Community 119"
Cohesion: 0.14
Nodes (11): _hotel_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), _replace_fk(), upgrade(), downgrade(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs., test_audit_log_hotel_delete_is_restricted() (+3 more)

### Community 363 - "Community 363"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 320 - "Community 320"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 364 - "Community 364"
Cohesion: 0.50
Nodes (1): laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7

### Community 365 - "Community 365"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 297 - "Community 297"
Cohesion: 0.60
Nodes (5): _policy_name(), _quoted_table(), upgrade(), downgrade(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL

### Community 134 - "Community 134"
Cohesion: 0.15
Nodes (11): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer (+3 more)

### Community 117 - "Community 117"
Cohesion: 0.12
Nodes (13): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification. (+5 more)

### Community 81 - "Community 81"
Cohesion: 0.10
Nodes (17): SimpleRateLimiter, Staff management endpoints for hotel public API keys., require_public_api_purpose(), Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val, HotelAPIKeyError, _hash_secret(), _generate_secret() (+9 more)

### Community 129 - "Community 129"
Cohesion: 0.24
Nodes (16): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+8 more)

### Community 77 - "Community 77"
Cohesion: 0.11
Nodes (29): _pick_default_hotel_id(), google_login(), validate_reset(), Auth endpoints: register, login, email verification and password reset. Verifica, Prefer a hotel whose onboarding is already complete.      When a user belongs to, "Sign in with Google" via Google Identity Services' ID-token flow: the     front, Validate reset code without changing password (paso previo en UI)., MasterEmailConnectionError (+21 more)

### Community 175 - "Community 175"
Cohesion: 0.29
Nodes (10): _require_demo_mode(), _booking_to_read(), _project_booking_graph(), list_bookings(), create_booking(), get_booking(), cancel_booking(), checkin_booking() (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (171): availability(), price_quote(), seed_demo_bookings(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true). (+163 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (204): CheckInRequest, FastAPI routes for Check-in / Check-out., _to_read(), _is_manager_context(), _ensure_action_permission(), _trigger_reoptimization_bg(), occupancy_grid(), register_settlement() (+196 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (145): BaseModel, VendorCreate, VendorUpdate, VendorRead, VendorPriceUpsert, VendorPriceRead, RemitoLineIn, RemitoCreate (+137 more)

### Community 53 - "Community 53"
Cohesion: 0.09
Nodes (21): FastAPI routes for the commercial configuration domain., CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy() (+13 more)

### Community 58 - "Community 58"
Cohesion: 0.10
Nodes (28): Company, CompanyPayload, CompanyDocumentType, CompanyDocumentStatus, CompanyDocument, CompanyDocumentPayload, listCompanies(), createCompany() (+20 more)

### Community 238 - "Community 238"
Cohesion: 0.32
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (67): email_status(), FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., _housekeeping_room(), list_categories(), get_category(), list_rooms(), get_room() (+59 more)

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection. (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (323): DailyRateOut, Config, DailyRateFallbackOut, DailyRateIn, BulkRateIn, BulkFieldRateIn, BulkRateOut, PricePeriodIn (+315 more)

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (351): Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest., Subscription status and entitlements endpoints. (+343 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (138): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, _ensure_enabled(), _connection_error_message(), _origin_for_popup() (+130 more)

### Community 42 - "Community 42"
Cohesion: 0.06
Nodes (27): _postgres_healthcheck(), _redis_healthcheck(), _clickhouse_healthcheck(), datastores_healthcheck(), E2ESafetyError, prepare_e2e_environment(), reset_e2e_database(), _credentials() (+19 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (43): stream_domain_events(), Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, _get_tenant_guest(), create_restriction(), list_restrictions(), resolve_restriction(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of (+35 more)

### Community 176 - "Community 176"
Cohesion: 0.27
Nodes (9): FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, get_all_rates(), get_usd_oficial_rate(), get_single_rate(), create_fx_snapshot() (+1 more)

### Community 125 - "Community 125"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (44): _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), Guest, GuestTagType, GuestTag, GuestTagPayload, GuestStaySummary (+36 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (50): AcceptPayload, LoginRequest, _current_user(), _safe_resource_id(), security_overview(), recent_security_events(), revoke_current_user_sessions(), Tenant-scoped security overview and current-user session revocation. (+42 more)

### Community 80 - "Community 80"
Cohesion: 0.09
Nodes (21): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+13 more)

### Community 130 - "Community 130"
Cohesion: 0.21
Nodes (15): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+7 more)

### Community 18 - "Community 18"
Cohesion: 0.05
Nodes (49): _schedule_to_read(), get_daily_report_schedule(), update_daily_report_schedule(), FastAPI routes for the notification backend: inbox, push subscriptions, preferen, NotificationSeverity, NotificationItem, NotificationListResponse, listNotifications() (+41 more)

### Community 198 - "Community 198"
Cohesion: 0.33
Nodes (8): _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), _guarded_json_payload(), Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar.

### Community 35 - "Community 35"
Cohesion: 0.20
Nodes (44): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., OTASyncStatusEnum, OTAWebhookCredential, Per-hotel OTA webhook credential. The secret is stored as a hash so the     raw, OTAReservationLifecycleEnum (+36 more)

### Community 253 - "Community 253"
Cohesion: 0.33
Nodes (2): _mercadopago_webhook_impl(), mercadopago_payment_link_webhook()

### Community 254 - "Community 254"
Cohesion: 0.48
Nodes (5): _has_per_method_nightly_price(), _get_surcharge_or_404(), create_payment_surcharge(), update_payment_surcharge(), deactivate_payment_surcharge()

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (283): PaymentSurchargeCreate, daily_report(), occupancy_report(), revenue_report(), FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Occupancy report for a date range (default: last 30 days)., Revenue report for a date range. (+275 more)

### Community 67 - "Community 67"
Cohesion: 0.09
Nodes (29): _validate_role(), _validate_code(), _target_membership_or_404(), read_effective_permissions(), _update_role_override(), update_permission_override(), restore_role_permission_defaults(), read_user_overrides() (+21 more)

### Community 45 - "Community 45"
Cohesion: 0.07
Nodes (28): Promotions API (v72 mobile-first pricing/promotions task).  CRUD for versioned,, PromotionBenefitType, PromotionScope, PromotionConditions, Promotion, PromotionCreatePayload, PromotionUpdatePayload, PromotionSimulateParams (+20 more)

### Community 83 - "Community 83"
Cohesion: 0.12
Nodes (25): update_promotion(), simulate_promotion_pricing(), Creates a new immutable version; the previous version is deactivated.     Reserv, Return which promotions would apply and the resulting price breakdown     for a, Promotion, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, PromotionError, _quantize() (+17 more)

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (50): RateCalendarChannelRestrictions, RateCalendarMeta, RateCalendarResponse, GetRateCalendarDailyParams, getRateCalendarDaily(), DailyRatePrices, DailyRateOut, DailyRateRangeRow (+42 more)

### Community 322 - "Community 322"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 62 - "Community 62"
Cohesion: 0.09
Nodes (28): OperationalReservationSummary, OperationalReservationGroup, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead, OperationalAlert, DailyOperationalReport, NightlyOperationalSummary (+20 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (60): _ensure_manual_rate_permission(), _project_reservation_graph(), create_new_reservation(), create_or_update_manual_ota(), list_reservations(), get_reservation(), add_reservation_guests(), room_move() (+52 more)

### Community 118 - "Community 118"
Cohesion: 0.17
Nodes (12): RoomBlockCreate, RoomBlockRead, RoomBlockError, _invalidate_availability_cache(), _validate_range(), room_block_overlap_filter(), blocked_room_ids_for_range(), room_has_active_block() (+4 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (48): _ensure_adjustment_permission(), StockItemCreate, StockItemUpdate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementCreate, StockMovementRead (+40 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (193): User management per hotel (owners/co-owners)., CashSessionStatusEnum, CashMovementTypeEnum, CashCustodyStatusEnum, CashSession, CashMovement, CashCloseReport, CashCustodyHandoff (+185 more)

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (15): API routes for reservation waitlist operations., Reservation, WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload, WaitlistPromoteResponse, listWaitlistEntries() (+7 more)

### Community 135 - "Community 135"
Cohesion: 0.18
Nodes (8): Public WhatsApp bot hooks authenticated only by hotel API key., WhatsAppBookingError, availability_lookup(), price_quote(), options_with_prices(), create_reservation(), generate_payment_link(), handle_payment_confirmation()

### Community 54 - "Community 54"
Cohesion: 0.07
Nodes (38): Settings, BaseSettings, get_settings(), _normalized_env_value(), _has_value(), _is_public_https_url(), _mercadopago_is_active(), _paypal_is_active() (+30 more)

### Community 74 - "Community 74"
Cohesion: 0.07
Nodes (32): get_engine(), _render_server_default(), _column_fill_value(), _backfill_not_null_nulls(), _sync_missing_columns(), init_db(), get_session_factory(), get_db() (+24 more)

### Community 8 - "Community 8"
Cohesion: 0.06
Nodes (196): Defensive datastore clients for optional infrastructure., Application decorators., Pydantic schemas for HotelConfiguration., mockCategories, mockCalendar, mockDailyRates, Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati, 0737a5a feat(frontend): V72 Wave A/B/C — companies, cash, reports, waitlist, laundry, stock, api-keys, permissions, whatsapp (+188 more)

### Community 323 - "Community 323"
Cohesion: 0.83
Nodes (3): _contact_points(), get_cassandra_session(), cassandra_healthcheck()

### Community 366 - "Community 366"
Cohesion: 1.00
Nodes (2): get_mongo_db(), mongo_healthcheck()

### Community 367 - "Community 367"
Cohesion: 1.00
Nodes (2): get_neo4j_driver(), neo4j_healthcheck()

### Community 177 - "Community 177"
Cohesion: 0.24
Nodes (7): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity()

### Community 371 - "Community 371"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 93 - "Community 93"
Cohesion: 0.17
Nodes (22): _decode_authorization_header(), _authenticate_user(), get_current_user_optional(), get_current_user(), is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value() (+14 more)

### Community 220 - "Community 220"
Cohesion: 0.22
Nodes (9): _is_demo_mode_enabled(), _require_demo_mode(), Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed. (+1 more)

### Community 162 - "Community 162"
Cohesion: 0.15
Nodes (13): _seed_permission_matrix_once(), lifespan(), Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup. (+5 more)

### Community 72 - "Community 72"
Cohesion: 0.07
Nodes (32): SafeStaticFiles, StaticFiles, _frontend_placeholder(), serve_frontend(), serve_spa(), StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin (+24 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (50): Master admin panel backend package., _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings() (+42 more)

### Community 222 - "Community 222"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (27): RuntimeError, SystemEmailStatus, _mask_email(), _mask_recipients(), _normalize_display_from(), EmailProviderError, EmailProvider, ABC (+19 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (40): MasterAdminSession, Base, MasterAdminAuthLockout, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings, MasterAdminContext, SellableProduct (+32 more)

### Community 59 - "Community 59"
Cohesion: 0.11
Nodes (33): MasterAdminAuditEvent, MasterStripeWebhookEvent, Subscription, FakeResponse, _seed_platform_admin(), _seed_hotel(), _seed_subscription(), _configure_resend() (+25 more)

### Community 86 - "Community 86"
Cohesion: 0.18
Nodes (25): _now(), _as_aware(), _hash_value(), _normalize_identifier(), _normalize_pin(), _bootstrap_master_credentials_match(), _pin_matches(), _session_cookie_secure() (+17 more)

### Community 41 - "Community 41"
Cohesion: 0.10
Nodes (21): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., GemmaIntent, classify_gemma_intent() (+13 more)

### Community 75 - "Community 75"
Cohesion: 0.16
Nodes (29): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, AllocationExplanation (+21 more)

### Community 100 - "Community 100"
Cohesion: 0.20
Nodes (24): str, AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum, OTAConnectionStatusEnum, OTASyncJobStatusEnum, PaymentProviderEnum (+16 more)

### Community 60 - "Community 60"
Cohesion: 0.20
Nodes (27): AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsAIUsageMonthly, HotelAuditEvent, RoomStateEventTypeEnum, RoomStateEventReasonCodeEnum, RoomStateEvent, FactRoomOccupancyDaily (+19 more)

### Community 68 - "Community 68"
Cohesion: 0.16
Nodes (30): AnalyticsExportStatusEnum, AnalyticsExportJob, FactReservationDaily, _date_window(), _decimal_total(), _project_operational_window(), _parse_datetime(), detect_no_shows() (+22 more)

### Community 49 - "Community 49"
Cohesion: 0.10
Nodes (40): AuditLog, Append-only record of every significant mutation within a hotel tenant.     Do N, PaymentProofStatusEnum, PaymentProof, PaymentProofBlob, Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., PaymentProofError (+32 more)

### Community 113 - "Community 113"
Cohesion: 0.18
Nodes (14): CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentStatusUpdate, CompanyDocumentRead (+6 more)

### Community 324 - "Community 324"
Cohesion: 0.50
Nodes (3): _LenientDateTime, TypeDecorator, DateTime that also accepts ISO-formatted strings on bind.      Callers occasiona

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (41): APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote, PublicReservationCreate (+33 more)

### Community 199 - "Community 199"
Cohesion: 0.42
Nodes (9): LinenItem, LinenLocation, LinenMovement, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Hotel-scoped linen (ropa blanca) inventory service.  Mirrors app/services/stock_, Raised when a linen inventory operation is invalid., Every active linen item's current balance in one query pair, instead     of the, Balance of one linen item for a hotel, optionally narrowed to one     location - (+1 more)

### Community 55 - "Community 55"
Cohesion: 0.16
Nodes (32): NotificationChannelEnum, NotificationOutboxStatusEnum, Notification, PushSubscription, NotificationPreference, NotificationOutbox, DailyReportSchedule, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+24 more)

### Community 136 - "Community 136"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (18): OTASyncJob, OTASyncEvent, Foundational OTA adapter interfaces and orchestration services., OTAProviderAdapter, ExpediaAdapter, OTAAdapterContext, OTAOperationResult, NormalizedOTAReservation (+10 more)

### Community 223 - "Community 223"
Cohesion: 0.22
Nodes (8): UserPermissionOverride, Configurable permission matrix models., An employee-specific permission decision within one hotel membership., publish_permission_invalidation(), Tenant-scoped permission catalog, resolution, mutation, and audit services., Explicit invalidation boundary for callers and future cache adapters.      Effec, Best-effort tenant signal after commit; never roll back the RBAC write., Best-effort tenant signal after commit; never roll back the RBAC write.

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (68): Permission, RolePermissionDefault, HotelPermissionOverride, SecurityAuditLog, _insert_if_missing(), seed_default_permissions(), _engine_key(), ensure_permission_matrix_seeded() (+60 more)

### Community 120 - "Community 120"
Cohesion: 0.20
Nodes (12): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, mask_to_weekdays(), PromotionConditions, PromotionCreate, PromotionUpdate, PromotionRead (+4 more)

### Community 200 - "Community 200"
Cohesion: 0.31
Nodes (9): ReportableOriginEnum, v72 §16.2 reportable origin — the 7 business-level booking origins.      Derived, _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception() (+1 more)

### Community 300 - "Community 300"
Cohesion: 0.40
Nodes (4): StockItem, StockLocation, StockMovement, Stock and inventory movement models.

### Community 87 - "Community 87"
Cohesion: 0.20
Nodes (26): SubscriptionEvent, _now(), _as_utc(), _plan_defaults(), plan_catalog(), _is_enforcement_enabled(), _compute_can_write(), _sync_legacy_tables() (+18 more)

### Community 278 - "Community 278"
Cohesion: 0.33
Nodes (4): WaitlistStatusEnum, WaitlistEntry, Waitlist / overbooking list model — v72 §9.  When the hotel is at capacity for a, Single guest waiting for a room in a given category for a date range.     Priori

### Community 101 - "Community 101"
Cohesion: 0.12
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 301 - "Community 301"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 224 - "Community 224"
Cohesion: 0.33
Nodes (8): GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead, Pydantic schemas for Guest and companions.

### Community 178 - "Community 178"
Cohesion: 0.17
Nodes (10): NotificationRead, NotificationListResponse, NotificationMarkReadRequest, PushSubscriptionRegisterRequest, PushSubscriptionUnregisterRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, DailyReportScheduleRead (+2 more)

### Community 114 - "Community 114"
Cohesion: 0.10
Nodes (14): OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, ProviderSetupPayload, PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, CategoriesPayload (+6 more)

### Community 255 - "Community 255"
Cohesion: 0.29
Nodes (6): SecurityCurrentUserRead, SecurityOverviewRead, SecurityEventRead, SecurityEventsRead, RevokeAllSessionsResponse, Public, redacted contracts for hotel security settings.

### Community 256 - "Community 256"
Cohesion: 0.29
Nodes (6): WaitlistEntryCreate, WaitlistEntryUpdate, WaitlistEntryRead, WaitlistPromoteRequest, WaitlistPromoteResponse, Schemas for hotel-scoped waitlist entries.

### Community 88 - "Community 88"
Cohesion: 0.10
Nodes (21): CashHandoffSchemaRepairError, repair_cash_handoff_schema(), missing_model_tables(), main(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it. (+13 more)

### Community 137 - "Community 137"
Cohesion: 0.28
Nodes (12): AllocationPolicyError, ensure_default_policy_profile(), ensure_default_policy_version(), get_active_policy_settings(), list_policy_versions(), create_policy_version(), publish_policy_version(), get_policy_suggestion() (+4 more)

### Community 78 - "Community 78"
Cohesion: 0.13
Nodes (18): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, OpenAIProvider, get_analytics_ai_provider() (+10 more)

### Community 236 - "Community 236"
Cohesion: 0.25
Nodes (3): AnalyticsAIProvider, Protocol, RenderRequester

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (24): reservation_status_to_outcome(), infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code(), backfill_channel_code(), split_amount_evenly(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact() (+16 more)

### Community 91 - "Community 91"
Cohesion: 0.15
Nodes (22): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _flatten_payload_rows(), _rows_to_csv_bytes(), _png_from_rows(), _sheet_xml_from_table() (+14 more)

### Community 102 - "Community 102"
Cohesion: 0.17
Nodes (21): detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), touch_reservation_fact_window(), calculate_pickup_30d(), _reservation_row_kind(), _resolve_no_show_policy(), _reservation_monetary_totals() (+13 more)

### Community 279 - "Community 279"
Cohesion: 0.40
Nodes (5): _as_utc_datetime(), annotate_analytics_payload(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL, Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 164 - "Community 164"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (53): _now(), _facts_data_as_of(), _hotel_local_now(), _ensure_utc(), _money(), _money_str(), _utc_date_range(), _analytics_window() (+45 more)

### Community 38 - "Community 38"
Cohesion: 0.07
Nodes (39): AnalyticsWarehouseUnavailable, ReconciliationResult, WarehouseSyncResult, FactReconciliationResult, _settings(), _required(), _validate_hotel_id(), _date_value() (+31 more)

### Community 201 - "Community 201"
Cohesion: 0.33
Nodes (8): model_snapshot(), sanitize_audit_payload(), payload_json(), create_audit_log(), queue_audit_log(), safe_create_audit_log(), Allow-list guest audit context before persistence or external projection., Best-effort audit log: a failure here must never discard the caller's     real,

### Community 165 - "Community 165"
Cohesion: 0.23
Nodes (12): _settings(), _get_redis_client(), _required(), _try_postgres_advisory_lock(), distributed_lock(), with_distributed_lock(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru (+4 more)

### Community 112 - "Community 112"
Cohesion: 0.19
Nodes (18): DomainEvent, _settings(), channel_for_hotel(), revision_key_for_hotel(), validate_event_input(), _validate_hotel_id(), _get_redis_client(), _required() (+10 more)

### Community 202 - "Community 202"
Cohesion: 0.38
Nodes (9): _is_cache_fresh(), _get_async(), fetch_all_rates(), fetch_rate(), get_usd_official_rate(), get_usd_rate_for_type(), get_all_rates_snapshot(), get_cached_rates() (+1 more)

### Community 280 - "Community 280"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 166 - "Community 166"
Cohesion: 0.45
Nodes (11): GemmaActionRunError, get_action_run(), approve_action_run(), reject_action_run(), review_action_run_draft(), apply_action_run_draft(), _load_json_dict(), _coerce_numeric_dict() (+3 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaServiceError, GemmaService, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 281 - "Community 281"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 179 - "Community 179"
Cohesion: 0.36
Nodes (10): _now(), _audit(), _get_guest(), _active_tag_filter(), list_active_tags(), _serialize_stay(), quick_profile(), add_tag() (+2 more)

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (22): _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload(), get_connection_payload(), derive_expires_at() (+14 more)

### Community 302 - "Community 302"
Cohesion: 0.50
Nodes (4): JurisdictionProfile, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 66 - "Community 66"
Cohesion: 0.06
Nodes (30): create_vendor(), get_vendor(), set_vendor_price(), create_remito(), vendor_balance(), vendor_spend(), _quarter_bounds(), vendor_settlements() (+22 more)

### Community 188 - "Community 188"
Cohesion: 0.27
Nodes (9): list_linen_items(), create_linen_item(), delete_linen_item(), get_linen_item(), create_location(), get_location(), register_movement(), linen_summary() (+1 more)

### Community 79 - "Community 79"
Cohesion: 0.13
Nodes (24): _utcnow(), _validate_payload(), _insert_ignore(), _redact(), _role_recipient_ids(), _actor_role(), get_effective_notification_preference(), _in_quiet_hours() (+16 more)

### Community 103 - "Community 103"
Cohesion: 0.28
Nodes (23): OnboardingError, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _merge_extra_policies(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload() (+15 more)

### Community 138 - "Community 138"
Cohesion: 0.20
Nodes (13): _guest_name(), _reservation_summary(), _group(), _active_room_blocks(), _available_with_review(), _cash_session(), _alerts(), daily_report() (+5 more)

### Community 143 - "Community 143"
Cohesion: 0.15
Nodes (1): BookingAdapter

### Community 144 - "Community 144"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 76 - "Community 76"
Cohesion: 0.14
Nodes (3): _hotel_default_currency(), OTAIntegrationService, TestBookingWebhook

### Community 115 - "Community 115"
Cohesion: 0.19
Nodes (19): _money(), _is_safe_provider_url(), _signing_secret(), _signature(), sign_external_reference(), resolve_signed_external_reference(), _get_reservation_for_hotel(), _unique_link_code() (+11 more)

### Community 107 - "Community 107"
Cohesion: 0.21
Nodes (22): PaymentLinkTestError, _validate_email(), _mercadopago_access_token(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email(), _notification_url(), _is_public_webhook_base() (+14 more)

### Community 189 - "Community 189"
Cohesion: 0.31
Nodes (9): _decode_image(), _safe_filename(), _reservation(), submit_transfer_proof(), get_transfer_proof(), approve_transfer_proof(), reject_transfer_proof(), _proof_path() (+1 more)

### Community 132 - "Community 132"
Cohesion: 0.17
Nodes (16): get_hotel_config(), validate_payment_method_enabled(), _resolve_reservation_hotel(), _resolve_payment_currency(), _payment_method_value(), calculate_payment_surcharge(), calculate_base_amount_before_surcharge(), process_payment() (+8 more)

### Community 180 - "Community 180"
Cohesion: 0.35
Nodes (11): validate_mercadopago_webhook_signature(), _payload_value(), _normalize_status(), _completed_at(), _is_allowed_status_transition(), _find_existing_event(), _insert_event(), _transaction_exists() (+3 more)

### Community 104 - "Community 104"
Cohesion: 0.17
Nodes (22): canonical_permission_code(), _role_permissions(), immutable_permission_decision(), can_role_hold_permission(), invalidate_effective_permission_cache(), get_effective_permission_details(), _audit(), _validate_mutable() (+14 more)

### Community 203 - "Community 203"
Cohesion: 0.38
Nodes (9): quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount(), _convert_amount(), _select_fx_policy() (+1 more)

### Community 282 - "Community 282"
Cohesion: 0.53
Nodes (4): _quantize(), _hotel_default_currency(), CanonicalPricingResult, compute_canonical_stay_pricing()

### Community 226 - "Community 226"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 121 - "Community 121"
Cohesion: 0.24
Nodes (18): _publish_cache_event(), _settings(), _cache_enabled(), _get_redis_client(), _load_json(), _store_json(), _get_cached_or_compute(), _date_token() (+10 more)

### Community 122 - "Community 122"
Cohesion: 0.22
Nodes (18): get_reservation_operations_summary(), list_pending_reservation_actions(), _candidate_reservation_ids(), _row_could_generate_action(), resolve_external_channel_follow_up(), clear_reservation_manual_review(), _guest_display_name(), _fmt_date() (+10 more)

### Community 167 - "Community 167"
Cohesion: 0.21
Nodes (9): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi (+1 more)

### Community 95 - "Community 95"
Cohesion: 0.11
Nodes (20): list_stock_items(), create_stock_item(), update_stock_item(), delete_stock_item(), _notify_if_low_stock(), register_movement(), current_stock(), stock_summary() (+12 more)

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (26): _apply_setting(), _remember_setting(), _set_context_value(), reapply_tenant_context_on_connection(), set_tenant_user_context(), set_tenant_hotel_context(), set_tenant_context(), set_master_admin_context() (+18 more)

### Community 190 - "Community 190"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 240 - "Community 240"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 204 - "Community 204"
Cohesion: 0.44
Nodes (8): WaitlistError, _get_waitlist_entry(), add_to_waitlist(), update_waitlist_entry(), promote_from_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), request_payment_link_for_waitlist()

### Community 304 - "Community 304"
Cohesion: 0.60
Nodes (4): _session(), process_outbox(), generate_daily_reports(), Celery tasks for the notification backend: process the outbox (bounded retry/exp

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (130): credentials, credentials, PAGES, revealCollapsedNavLink(), clientNavigate(), frontendDir, repoRoot, pythonCandidates (+122 more)

### Community 163 - "Community 163"
Cohesion: 0.26
Nodes (8): emailOutboxPath, resetEmailOutbox(), cleanupEmailOutbox(), readLatestCode(), waitForCode(), emailOutboxPath, readLatestCode(), waitForCode()

### Community 275 - "Community 275"
Cohesion: 0.33
Nodes (3): credentials, backendURL, StoredSession

### Community 299 - "Community 299"
Cohesion: 0.40
Nodes (1): credentials

### Community 50 - "Community 50"
Cohesion: 0.08
Nodes (28): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., graphify_state(), main(), run() (+20 more)

### Community 221 - "Community 221"
Cohesion: 0.28
Nodes (5): owner, localIsoDate(), parseMoney(), createReservation(), readStat()

### Community 368 - "Community 368"
Cohesion: 0.67
Nodes (1): owner

### Community 276 - "Community 276"
Cohesion: 0.33
Nodes (1): credentials

### Community 369 - "Community 369"
Cohesion: 0.67
Nodes (1): credentials

### Community 277 - "Community 277"
Cohesion: 0.40
Nodes (3): hotelId, authHeaders(), ensureOnboarding()

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (64): PermissionGate(), LoginPage, RegisterOwnerPage, ForgotPasswordPage, ResetPasswordPage, AcceptInvitationPage, VerifyEmailPage, CashRegisterPage (+56 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (53): AllocationRunPayload, AllocationRunResponse, RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), listRoomMovementGroups(), revertRoomMovementGroup(), ReservationPendingAction (+45 more)

### Community 57 - "Community 57"
Cohesion: 0.10
Nodes (33): CashSessionStatus, CashMovementType, CashSession, CashMovement, CashCloseReport, CashCustodyHandoff, CashSessionSummary, CashSessionOpenPayload (+25 more)

### Community 64 - "Community 64"
Cohesion: 0.10
Nodes (30): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+22 more)

### Community 109 - "Community 109"
Cohesion: 0.14
Nodes (18): GuestRestrictionStatus, GuestRestriction, GuestRestrictionCreatePayload, GuestRestrictionResolvePayload, RestrictionOverride, listGuestRestrictions(), createGuestRestriction(), resolveGuestRestriction() (+10 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (65): RemitoDirection, LaundryVendor, LaundryVendorCreate, LaundryVendorUpdate, LaundryVendorPrice, LaundryVendorPriceUpsert, LaundryRemitoLine, LaundryRemito (+57 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (25): PaymentMethod, ReservationStatus, ConfirmDialogProps, Props, GuestRestrictionBadge(), Props, IntegrationHelpDrawer(), CheckinCaptureForm (+17 more)

### Community 85 - "Community 85"
Cohesion: 0.09
Nodes (18): RateCalendarChannelPrice, RateCalendarChannelDay, RateCalendarDay, InfoTipProps, PopoverPosition, InfoTip(), RateCalendarGridProps, ChannelSummary (+10 more)

### Community 65 - "Community 65"
Cohesion: 0.07
Nodes (18): OccupancyGridRoom, OccupancyGridReservation, OccupancyGridBlock, OccupancyGridResponse, DATE_LABEL, OccupancyGridProps, CategoryGroup, OccupancyGrid() (+10 more)

### Community 46 - "Community 46"
Cohesion: 0.14
Nodes (30): StructuredData, SeoProps, Seo(), navItems, MarketingShellProps, MarketingShell(), PublicButtonLinkProps, isExternal() (+22 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (38): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+30 more)

### Community 131 - "Community 131"
Cohesion: 0.17
Nodes (15): trimTrailingSlash(), ensureLeadingSlash(), normalizeUrl(), PUBLIC_SITE_URL, PUBLIC_APP_URL, APP_URL_HOSTNAME, SITE_URL_HOSTNAME, PREVIEW_APP_HOST_SUFFIXES (+7 more)

### Community 239 - "Community 239"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 273 - "Community 273"
Cohesion: 0.80
Nodes (5): SharedSandboxBootstrapError, load_env(), _literal(), build_sql(), main()

### Community 28 - "Community 28"
Cohesion: 0.08
Nodes (52): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+44 more)

### Community 73 - "Community 73"
Cohesion: 0.16
Nodes (26): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+18 more)

### Community 127 - "Community 127"
Cohesion: 0.20
Nodes (14): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots. (+6 more)

### Community 160 - "Community 160"
Cohesion: 0.32
Nodes (12): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+4 more)

### Community 70 - "Community 70"
Cohesion: 0.16
Nodes (30): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+22 more)

### Community 298 - "Community 298"
Cohesion: 0.80
Nodes (4): _write_json(), _archive_historical(), _build_cases(), main()

### Community 219 - "Community 219"
Cohesion: 0.44
Nodes (8): OperationalQAError, _utc_now(), _json_bytes(), _write(), _catalog(), initialize(), validate(), main()

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (44): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+36 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (32): BootstrapConfigurationError, bootstrap_configuration_fingerprint(), Hash the exact provider-observed values without exposing them individually., JsonGetter, ReadOnlyJsonApi, _decode_lease_entropy(), Safe failure whose message never contains provider response bodies., Small GET-only API client with bounded retries and redacted failures. (+24 more)

### Community 237 - "Community 237"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 321 - "Community 321"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (36): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+28 more)

### Community 161 - "Community 161"
Cohesion: 0.35
Nodes (12): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+4 more)

### Community 128 - "Community 128"
Cohesion: 0.24
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 51 - "Community 51"
Cohesion: 0.16
Nodes (38): VerificationError, VerificationConfig, ProviderClients, _dict(), _list(), _string(), _validate_config(), _validate_baseline_lease_id() (+30 more)

### Community 40 - "Community 40"
Cohesion: 0.10
Nodes (46): QABootstrapError, Persona, QABootstrapConfig, ProviderEvidence, _required(), _flag(), _required_port(), _validate_email() (+38 more)

### Community 225 - "Community 225"
Cohesion: 0.36
Nodes (8): _required(), load_provider_evidence_private_key(), issue_provider_evidence_token(), _safe_output_path(), write_private_token(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer.

### Community 187 - "Community 187"
Cohesion: 0.33
Nodes (8): PhaseMetrics, LoadConfig, percentile(), safe_headers(), run_phase(), _parse_paths(), _run(), main()

### Community 186 - "Community 186"
Cohesion: 0.35
Nodes (10): derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure(), explain(), print_results() (+2 more)

### Community 181 - "Community 181"
Cohesion: 0.27
Nodes (11): _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+3 more)

### Community 257 - "Community 257"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 303 - "Community 303"
Cohesion: 0.70
Nodes (4): _receptionist_context(), _open_cash_session(), _create_receptionist_user(), test_receptionist_can_view_and_make_reservation_payments()

### Community 139 - "Community 139"
Cohesion: 0.17
Nodes (6): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), Regression contracts for the repository's agent-operations setup.

### Community 105 - "Community 105"
Cohesion: 0.18
Nodes (5): make_rooms(), make_res(), TestOverlap, TestGreedyAllocation, TestCPSATAllocation

### Community 191 - "Community 191"
Cohesion: 0.56
Nodes (10): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+2 more)

### Community 258 - "Community 258"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 241 - "Community 241"
Cohesion: 0.46
Nodes (7): _slot(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(), test_allocation_run_creates_movement_group_and_events(), _seed_hotel_rooms_guests(), _reservation()

### Community 150 - "Community 150"
Cohesion: 0.30
Nodes (11): assert_freshness_metadata(), _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads() (+3 more)

### Community 151 - "Community 151"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed(), test_operational_schema_covers_dimensions_and_non_pii_facts()

### Community 123 - "Community 123"
Cohesion: 0.35
Nodes (18): _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation(), _audit_for() (+10 more)

### Community 242 - "Community 242"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (18): FakeResponse, _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend(), test_password_policy_requires_twelve_characters_for_register_and_reset(), test_register_verify_and_reset_use_resend_provider(), test_auth_flows_fail_without_connected_mail_provider() (+10 more)

### Community 326 - "Community 326"
Cohesion: 0.67
Nodes (2): _override_auth(), test_receptionist_can_get_price_quote()

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+29 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (14): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+6 more)

### Community 96 - "Community 96"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+15 more)

### Community 305 - "Community 305"
Cohesion: 0.80
Nodes (4): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 243 - "Community 243"
Cohesion: 0.32
Nodes (3): _load_migration(), FakeInspector, test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 146 - "Community 146"
Cohesion: 0.14
Nodes (4): opened_cash_register(), TestGuestValidation, TestCheckIn, TestCheckOut

### Community 206 - "Community 206"
Cohesion: 0.49
Nodes (9): _override_auth(), _client_with_db(), _seed_fully_paid_reservation(), test_checkin_without_new_fields_fails_with_clear_message(), test_checkin_captures_missing_fields_in_same_request(), test_partial_checkin_reaches_pre_check_in_then_final_checkin(), test_partial_checkin_requires_fully_paid(), test_add_companion_during_checkin_flow_appears_in_additional_guests() (+1 more)

### Community 306 - "Community 306"
Cohesion: 0.70
Nodes (4): _override_auth(), _client_with_db(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 145 - "Community 145"
Cohesion: 0.51
Nodes (14): _make_hotel(), _make_guest(), _make_room(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin(), test_prohibido_tag_from_different_hotel_does_not_block() (+6 more)

### Community 207 - "Community 207"
Cohesion: 0.58
Nodes (9): _get_db_override_target(), _override_auth(), _seed_hotel(), _build_client(), _cleanup_client(), test_owner_can_create_and_update_commercial_configuration(), test_manager_has_no_access_to_commercial_configuration(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories() (+1 more)

### Community 283 - "Community 283"
Cohesion: 0.47
Nodes (4): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi

### Community 259 - "Community 259"
Cohesion: 0.71
Nodes (6): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation()

### Community 260 - "Community 260"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_reservation_is_allocation_locked()

### Community 140 - "Community 140"
Cohesion: 0.21
Nodes (9): FakeRedis, _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_optional_lock_can_degrade_when_redis_is_unavailable(), FakePostgresSession, test_required_lock_uses_postgres_advisory_lock_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 182 - "Community 182"
Cohesion: 0.26
Nodes (6): FakeRedis, _settings(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_optional_backend_degrades_without_fabricating_an_event(), test_required_backend_raises_when_unavailable(), test_stream_endpoint_sets_no_cache_headers_and_tenant_stream()

### Community 284 - "Community 284"
Cohesion: 0.53
Nodes (5): _alembic(), _seed_legacy_links(), _assert_migrated(), test_payment_link_migration_backfills_provider_history_and_reupgrades(), Data-contract regression for the payment-link execution-mode migration.

### Community 285 - "Community 285"
Cohesion: 0.47
Nodes (4): _make_completed_transaction(), test_daily_report_totals_a_completed_transaction_without_crashing(), test_revenue_report_totals_multiple_completed_transactions_without_crashing(), Regression coverage for app/api/reports.py's financial endpoints (/api/reports/d

### Community 99 - "Community 99"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 327 - "Community 327"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_direct_guest_and_companion_audits_exclude_pii(), test_decorator_mongo_projection_excludes_guest_pii()

### Community 328 - "Community 328"
Cohesion: 0.67
Nodes (3): _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite(), B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio

### Community 244 - "Community 244"
Cohesion: 0.46
Nodes (6): _seed_hotel(), _seed_reservation(), test_guest_export_permission_ceiling_cannot_be_overridden_for_reception(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_permission_defaults_and_override_are_hotel_scoped()

### Community 307 - "Community 307"
Cohesion: 0.80
Nodes (4): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 261 - "Community 261"
Cohesion: 0.67
Nodes (6): _auth(), _client(), test_restriction_api_permissions_tenant_isolation_and_event(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_restriction_override_reason_rejects_whitespace()

### Community 262 - "Community 262"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_legacy_tags(), _load_migration(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls()

### Community 192 - "Community 192"
Cohesion: 0.38
Nodes (10): _seed_hotel(), _seed_guest_inventory(), _reservation(), _create_payload(), test_restriction_lifecycle_distinguishes_active_expired_and_resolved(), test_restriction_is_tenant_scoped_for_reads_and_resolution(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override() (+2 more)

### Community 152 - "Community 152"
Cohesion: 0.46
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 331 - "Community 331"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 147 - "Community 147"
Cohesion: 0.42
Nodes (14): _override_auth(), _client_with_db(), _teardown(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_owner_can_manage_linen_items_and_receptionist_cannot(), test_owner_can_register_a_linen_movement_and_load_an_opening_balance(), test_housekeeping_can_operate_remitos_but_not_manage_vendors(), test_remito_rejects_insufficient_house_stock_via_api() (+6 more)

### Community 124 - "Community 124"
Cohesion: 0.26
Nodes (18): _seed_hotels(), _seed_house_stock(), test_create_vendor_creates_its_own_linen_location(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_remito_line_snapshots_price_and_flags_missing_price() (+10 more)

### Community 308 - "Community 308"
Cohesion: 0.60
Nodes (4): _seed_hotels(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped(), Same per-location bug as stock_service: an 'out' at location B must be     valid

### Community 263 - "Community 263"
Cohesion: 0.43
Nodes (6): _run_alembic(), _seed_pre_split_data(), test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade(), _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly, Hand-insert a real 'linen' StockItem plus movements and a laundry     vendor/pri

### Community 116 - "Community 116"
Cohesion: 0.22
Nodes (15): env_page(), FakeRender, mutations(), acquire_lease(), release_lease(), test_acquire_validates_before_writing_and_commits_id_last(), test_acquire_refuses_every_drift_without_mutation(), test_same_production_and_qa_identity_is_rejected_before_get() (+7 more)

### Community 309 - "Community 309"
Cohesion: 0.40
Nodes (1): Response

### Community 193 - "Community 193"
Cohesion: 0.42
Nodes (8): _reservation(), _create_link(), _sign(), _post_webhook(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_duplicate_webhook_delivery_does_not_double_charge(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing()

### Community 264 - "Community 264"
Cohesion: 0.43
Nodes (5): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), This bool-returning shim delegates to the SAME raising validator every     real

### Community 245 - "Community 245"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 246 - "Community 246"
Cohesion: 0.43
Nodes (7): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_reset_endpoint_allows_testing_env()

### Community 141 - "Community 141"
Cohesion: 0.26
Nodes (13): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+5 more)

### Community 108 - "Community 108"
Cohesion: 0.12
Nodes (14): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 153 - "Community 153"
Cohesion: 0.14
Nodes (13): test_normalizes_generated_instruction_paths_without_touching_external_paths(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized(), Regression coverage for portable Graphify artifact normalization., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+5 more)

### Community 227 - "Community 227"
Cohesion: 0.50
Nodes (8): _auth(), _client(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_push_subscription_register_and_unregister(), test_preferences_crud(), test_daily_report_schedule_is_owner_co_owner_only(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and

### Community 106 - "Community 106"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), test_enqueue_dedupes_same_event_recipient_channel(), test_enqueue_same_dedupe_key_isolated_per_hotel(), test_enqueue_skips_recipient_without_entity_read_permission(), test_enqueue_skips_recipient_without_active_membership(), test_enqueue_role_based_fanout(), test_enqueue_respects_channel_preference() (+15 more)

### Community 228 - "Community 228"
Cohesion: 0.50
Nodes (8): _owner(), _outbox_event_types(), test_reservation_lifecycle_enqueues_notifications(), test_no_show_enqueues_notification(), test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), Integration coverage: the real domain-event call sites (reservation lifecycle, c

### Community 194 - "Community 194"
Cohesion: 0.27
Nodes (6): _reserve(), test_reservation_spanning_the_window_is_returned_unclipped(), test_reservation_entirely_before_or_after_window_is_excluded(), test_cancelled_reservation_is_excluded(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations()

### Community 229 - "Community 229"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database.

### Community 310 - "Community 310"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 230 - "Community 230"
Cohesion: 0.36
Nodes (7): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records(), API coverage for the expanded onboarding wizard.

### Community 247 - "Community 247"
Cohesion: 0.54
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 168 - "Community 168"
Cohesion: 0.38
Nodes (11): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel() (+3 more)

### Community 148 - "Community 148"
Cohesion: 0.33
Nodes (13): _enable_external_effects(), _reservation(), test_create_payment_link_persists_link_without_transaction(), test_connections_flag_closed_forces_local_only_before_gateway(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_link_best_effort_when_gateway_fails() (+5 more)

### Community 286 - "Community 286"
Cohesion: 0.53
Nodes (4): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation(), test_payment_links_api_rejects_manager_without_cash_operate()

### Community 169 - "Community 169"
Cohesion: 0.35
Nodes (12): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_submit_transfer_proof_validates_image_and_stores_metadata(), test_submit_transfer_proof_reencodes_and_removes_exif(), test_submit_transfer_proof_rejects_non_image_disguised_as_png(), test_submit_transfer_proof_rejects_oversized_payload(), test_proof_bytes_are_tenant_scoped() (+4 more)

### Community 209 - "Community 209"
Cohesion: 0.47
Nodes (7): _override_auth(), _build_client(), _cleanup(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_reactivate_deactivated_surcharge_via_patch()

### Community 195 - "Community 195"
Cohesion: 0.42
Nodes (9): _reservation(), _link(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key(), test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(), test_rejected_payment_cannot_be_flipped_to_completed_by_later_webhook() (+1 more)

### Community 231 - "Community 231"
Cohesion: 0.39
Nodes (5): _auth(), _client(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_user_override_rejects_self_elevation_and_cross_hotel_id_without_disclosure()

### Community 170 - "Community 170"
Cohesion: 0.24
Nodes (10): _seed_hotel(), test_permission_override_can_deny_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_role_ceiling_ignores_a_stale_privilege_escalating_override(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_get_matrix_includes_hotel_overrides(), test_resolve_seeds_the_matrix_once_per_engine_not_per_call(), A1: resolve() used to call seed_default_permissions() on every invocation      ( (+2 more)

### Community 154 - "Community 154"
Cohesion: 0.38
Nodes (13): _override_auth(), _client_with_db(), test_permissions_matrix_available_to_permission_manager_only(), test_effective_permissions_returns_only_current_role_capabilities(), test_permission_override_can_deny_receptionist_guest_edit(), test_permission_denied_is_audited(), test_permission_override_rejects_grant_above_role_ceiling(), test_override_in_hotel_a_does_not_affect_hotel_b() (+5 more)

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (38): _bootstrap_environment(), _provider_manifest(), _local_evidence_payload(), _safe_environment(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_remote_target_rejects_self_attested_json_without_signed_token() (+30 more)

### Community 97 - "Community 97"
Cohesion: 0.19
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 52 - "Community 52"
Cohesion: 0.11
Nodes (28): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+20 more)

### Community 311 - "Community 311"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread()

### Community 183 - "Community 183"
Cohesion: 0.44
Nodes (11): _seed_hotel(), _seed_daily_rates(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_missing_fx_rate_raises() (+3 more)

### Community 155 - "Community 155"
Cohesion: 0.29
Nodes (12): _seed_hotel(), _ctx(), test_create_promotion_rejects_percentage_over_100(), test_create_promotion_rejects_duplicate_code(), test_find_applicable_promotions_matches_typed_conditions(), test_find_applicable_promotions_respects_weekday_and_date_range(), test_find_applicable_promotions_matches_guest_tag_type(), test_apply_promotions_never_goes_negative() (+4 more)

### Community 265 - "Community 265"
Cohesion: 0.71
Nodes (6): _override_auth(), _build_client(), _cleanup(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 266 - "Community 266"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _seed_pre_migration_surcharge(), _load_migration(), test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data(), test_promotions_migration_owns_reversible_postgresql_rls()

### Community 184 - "Community 184"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 312 - "Community 312"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 156 - "Community 156"
Cohesion: 0.48
Nodes (12): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+4 more)

### Community 232 - "Community 232"
Cohesion: 0.56
Nodes (8): _client(), _close(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_stock_read_movement_and_admin_are_independently_enforced_without_mutation(), test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(), test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation(), test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation(), test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation()

### Community 267 - "Community 267"
Cohesion: 0.48
Nodes (6): _load_migration(), _alembic(), _engine(), _seed_pre_revision(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal()

### Community 142 - "Community 142"
Cohesion: 0.17
Nodes (8): FakeRedis, BrokenRedis, test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip(), test_operational_invalidation_clears_availability_and_analytics(), test_analytics_home_cache_key_varies_by_filter()

### Community 233 - "Community 233"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 210 - "Community 210"
Cohesion: 0.38
Nodes (7): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors()

### Community 313 - "Community 313"
Cohesion: 0.60
Nodes (4): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), Tests for operator-created reservation consumption charges.

### Community 234 - "Community 234"
Cohesion: 0.33
Nodes (7): _make_reservations(), test_default_limit_caps_result_at_50(), test_skip_and_limit_page_through_results(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele

### Community 171 - "Community 171"
Cohesion: 0.58
Nodes (12): _override_auth(), _build_client(), _cleanup_client(), _seed_bookable_state(), _payload(), test_receptionist_cannot_set_manual_total_amount(), test_co_owner_cannot_set_manual_total_amount_by_default(), test_manager_cannot_set_manual_total_amount_by_default() (+4 more)

### Community 211 - "Community 211"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 332 - "Community 332"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 314 - "Community 314"
Cohesion: 0.60
Nodes (3): _quote(), test_reservation_rejects_quote_after_pricing_revision_changes(), test_confirmed_reservation_stores_pricing_revision()

### Community 287 - "Community 287"
Cohesion: 0.60
Nodes (5): _reservation(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty(), test_search_does_not_leak_across_hotels()

### Community 126 - "Community 126"
Cohesion: 0.11
Nodes (9): TestConfirmationCode, TestStateTransitions, Tests for Reservation Service — booking creation, availability checks, state tra, Tests for confirmation code generation., Tests for reservation state machine transitions., Tests for confirmation code generation., Tests for reservation state machine transitions., Tests for confirmation code generation. (+1 more)

### Community 235 - "Community 235"
Cohesion: 0.56
Nodes (7): _role_connection(), _seed_engine(), _seed_session(), test_tenant_isolation_blocks_cross_hotel_reads(), test_no_tenant_context_hides_all_rows(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_after_commit_listener_reapplies_hotel_context()

### Community 172 - "Community 172"
Cohesion: 0.44
Nodes (12): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+4 more)

### Community 212 - "Community 212"
Cohesion: 0.42
Nodes (7): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_housekeeping_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped(), test_receptionist_cannot_create_room_block_by_default()

### Community 288 - "Community 288"
Cohesion: 0.73
Nodes (5): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation(), _seed_group()

### Community 289 - "Community 289"
Cohesion: 0.53
Nodes (4): _override_auth(), test_receptionist_can_list_rooms(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories()

### Community 185 - "Community 185"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 333 - "Community 333"
Cohesion: 0.50
Nodes (4): test_validate_runtime_security_ignores_incomplete_optional_integrations(), Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup.

### Community 334 - "Community 334"
Cohesion: 0.50
Nodes (4): test_validate_runtime_security_rejects_localhost_redirect_when_service_configured(), OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential

### Community 268 - "Community 268"
Cohesion: 0.29
Nodes (3): _no_real_db(), Every response must carry baseline security headers so the SPA and API are not m, The unmatched-path SPA fallback still depends on get_db; stub it so this     tes

### Community 290 - "Community 290"
Cohesion: 0.53
Nodes (4): _headers(), test_security_overview_and_events_are_redacted_and_tenant_scoped(), test_manager_cannot_read_security_settings(), test_revoke_all_invalidates_the_callers_previous_token()

### Community 291 - "Community 291"
Cohesion: 0.53
Nodes (4): _values(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_env_file_requires_owner_only_permissions()

### Community 269 - "Community 269"
Cohesion: 0.57
Nodes (5): _seed_category(), _delete_audit(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits(), test_price_period_delete_soft_deletes_hides_and_audits()

### Community 157 - "Community 157"
Cohesion: 0.33
Nodes (13): _override_auth(), _client_with_db(), _teardown(), _second_hotel(), test_owner_can_delete_item_and_recreate_it_with_the_same_name(), test_duplicate_active_name_returns_clean_409_not_a_500(), test_stock_item_unit_cost_is_exposed_on_create_and_update(), test_stock_item_full_edit_updates_name_sku_unit_and_min_quantity() (+5 more)

### Community 149 - "Community 149"
Cohesion: 0.31
Nodes (14): _seed_hotels(), _movement(), test_consumption_report_totals_and_variation_between_periods(), test_consumption_report_only_counts_out_and_adjustment_out(), test_consumption_report_is_hotel_scoped(), test_consumption_report_variation_is_none_without_a_previous_baseline(), test_consumption_report_rejects_invalid_group_by(), test_consumption_report_rejects_inverted_range() (+6 more)

### Community 61 - "Community 61"
Cohesion: 0.08
Nodes (36): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_stock_outbound_cannot_make_quantity_negative(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited(), test_stock_adjustment_can_correct_quantity_downward(), test_stock_adjustment_downward_cannot_make_quantity_negative(), test_current_stock_location_filter_is_additive_and_hotel_wide_total_unchanged() (+28 more)

### Community 213 - "Community 213"
Cohesion: 0.38
Nodes (7): _ensure_hotel(), _auth_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_records_audit_event(), test_comped_override_rejects_unknown_hotel_without_subscription_state(), test_role_gating_for_trial_and_comped_override(), test_manual_transitions_emit_events()

### Community 173 - "Community 173"
Cohesion: 0.15
Nodes (4): test_sqlite_commit_with_no_tenant_context_is_a_clean_noop(), C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., Most sessions never call set_tenant_*; the listener must not touch them.

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (19): _load_rls_migration(), _load_user_override_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract(), test_extended_composite_fk_migration_covers_every_remaining_scoped_fk(), test_extended_composite_fk_migration_has_unique_target_for_every_parent() (+11 more)

### Community 84 - "Community 84"
Cohesion: 0.14
Nodes (7): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _make_reservation(), _make_transaction()

### Community 214 - "Community 214"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 270 - "Community 270"
Cohesion: 0.57
Nodes (6): opened_cash_register(), _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 158 - "Community 158"
Cohesion: 0.47
Nodes (11): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+3 more)

### Community 248 - "Community 248"
Cohesion: 0.50
Nodes (7): opened_cash_register(), _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_no_future_conflict_extends_normally()

### Community 110 - "Community 110"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_reservation_is_motor_protected_set_on_manual_move(), test_reservation_is_wait_listed_field(), test_extend_stay_basic() (+3 more)

### Community 215 - "Community 215"
Cohesion: 0.33
Nodes (8): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_update_mobility_restriction_triggers_reoptimization(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_room_move_rejects_receptionist_without_room_move_permission(), test_room_move_endpoint_rejects_capacity_overflow_and_returns_delta_on_reprice()

### Community 216 - "Community 216"
Cohesion: 0.36
Nodes (8): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_movement_group_hotel_isolation(), test_revert_already_reverted_group_returns_400(), _seed_group()

### Community 217 - "Community 217"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 336 - "Community 336"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation()

### Community 292 - "Community 292"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link(), test_whatsapp_payment_confirmation_is_idempotent()

### Community 218 - "Community 218"
Cohesion: 0.53
Nodes (8): _seed_hotel(), _issue_key(), _headers(), _whatsapp_quote(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

## Knowledge Gaps
- **795 isolated node(s):** `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`, `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em` (+790 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 337`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 338`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 339`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 340`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 341`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 342`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 343`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 344`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 345`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 346`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 347`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 348`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 349`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 350`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 351`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 352`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 353`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 354`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 355`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 356`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 357`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 358`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 359`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 360`** (1 nodes): `stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 361`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 362`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 363`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 364`** (1 nodes): `laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 365`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 253`** (2 nodes): `_mercadopago_webhook_impl()`, `mercadopago_payment_link_webhook()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 366`** (2 nodes): `get_mongo_db()`, `mongo_healthcheck()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 367`** (2 nodes): `get_neo4j_driver()`, `neo4j_healthcheck()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 371`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 136`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 143`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 144`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 299`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 368`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 276`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 369`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 326`** (2 nodes): `_override_auth()`, `test_receptionist_can_get_price_quote()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 309`** (1 nodes): `Response`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 233`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 0` to `Community 9`, `Community 5`, `Community 162`, `Community 72`, `Community 220`, `Community 7`, `Community 59`, `Community 39`, `Community 41`, `Community 75`, `Community 2`, `Community 60`, `Community 100`, `Community 68`, `Community 49`, `Community 6`, `Community 113`, `Community 111`, `Community 176`, `Community 11`, `Community 324`, `Community 34`, `Community 32`, `Community 33`, `Community 3`, `Community 199`, `Community 55`, `Community 136`, `Community 14`, `Community 4`, `Community 35`, `Community 24`, `Community 22`, `Community 223`, `Community 83`, `Community 120`, `Community 200`, `Community 300`, `Community 31`, `Community 87`, `Community 278`, `Community 88`, `Community 69`, `Community 99`, `Community 229`, `Community 230`, `Community 170`, `Community 149`, `Community 92`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 0` to `Community 15`, `Community 33`, `Community 7`, `Community 3`, `Community 6`, `Community 10`, `Community 2`, `Community 81`, `Community 9`, `Community 39`, `Community 100`, `Community 60`, `Community 11`, `Community 48`, `Community 66`, `Community 55`, `Community 103`, `Community 35`, `Community 76`, `Community 107`, `Community 4`, `Community 282`, `Community 87`, `Community 68`, `Community 8`, `Community 49`, `Community 69`, `Community 99`, `Community 5`, `Community 17`, `Community 263`, `Community 59`, `Community 24`, `Community 170`, `Community 149`, `Community 61`?**
  _High betweenness centrality (0.067) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 4` to `Community 11`, `Community 0`, `Community 2`, `Community 7`, `Community 9`, `Community 39`, `Community 75`, `Community 100`, `Community 60`, `Community 113`, `Community 34`, `Community 6`, `Community 35`, `Community 76`, `Community 49`, `Community 118`, `Community 130`, `Community 135`, `Community 146`, `Community 126`?**
  _High betweenness centrality (0.034) - this node is a cross-community bridge._
- **Are the 936 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 936 INFERRED edges - model-reasoned connections that need verification._
- **Are the 937 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 937 INFERRED edges - model-reasoned connections that need verification._
- **Are the 908 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 908 INFERRED edges - model-reasoned connections that need verification._
- **Are the 764 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Room` has 764 INFERRED edges - model-reasoned connections that need verification._