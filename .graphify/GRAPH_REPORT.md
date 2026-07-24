# Graph Report - .  (2026-07-24)

## Corpus Check
- Large corpus: 720 files · ~472,051 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 6362 nodes · 20332 edges · 298 communities detected
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 6679 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 6679 · contains: 4146 · calls: 3177 · MODIFIES: 1651 · ON_BRANCH: 1248 · rationale_for: 836 · imports: 698 · imports_from: 560 · method: 554 · inherits: 525 · PARENT_OF: 258


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 720 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 7 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `a733848`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `ReservationStatusEnum` - 452 edges
2. `Reservation` - 450 edges
3. `HotelConfiguration` - 397 edges
4. `Room` - 338 edges
5. `Base` - 327 edges
6. `Guest` - 325 edges
7. `RoomCategory` - 317 edges
8. `RoomStatusEnum` - 252 edges
9. `ReservationError` - 206 edges
10. `ReservationSourceEnum` - 199 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati` --uses--> `HotelConfiguration`  [INFERRED]
  tests/perf/explain_probe.py → app/models/hotel_config.py
- `Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py
- `Return ``dsn`` only when provider evidence proves a disposable QA target.      E` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py
- `The PostgreSQL test target cannot be proven isolated and disposable.` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py

## Communities

### Community 234 - "Community 234"
Cohesion: 0.53
Nodes (5): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (10): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c, extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard, add trial and comped fields to subscriptions  Revision ID: 20260419_subscription, test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured(), test_validate_runtime_security_ignores_incomplete_optional_integrations(), test_validate_runtime_security_rejects_localhost_redirect_when_service_configured(), MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., Partial integration env vars should not block production startup. (+2 more)

### Community 278 - "Community 278"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 265 - "Community 265"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 279 - "Community 279"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 13 - "Community 13"
Cohesion: 0.04
Nodes (18): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif, ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026, ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026, chat_completions(), _extract_latest_user_message(), build_gemma_hotel_context(), _enum_value(), Gemma-aware policy suggestion service.  This module keeps the PMS safe by treati (+10 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (20): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a, master admin system owner mail and stripe settings  Revision ID: 20260421_master, sync_model_drift_missing_columns  Revision ID: 3eaf48a79290 Revises: 20260419_on, guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date, AnalyticsComparisonWindowRead, AnalyticsComparisonStateRead, AnalyticsMetricCardRead, AnalyticsStarterSummaryDataRead (+12 more)

### Community 232 - "Community 232"
Cohesion: 0.48
Nodes (5): _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260

### Community 266 - "Community 266"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), upgrade(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t

### Community 280 - "Community 280"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 281 - "Community 281"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 282 - "Community 282"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 283 - "Community 283"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 284 - "Community 284"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 285 - "Community 285"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 245 - "Community 245"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 286 - "Community 286"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 287 - "Community 287"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 288 - "Community 288"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 289 - "Community 289"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 290 - "Community 290"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 291 - "Community 291"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 292 - "Community 292"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (20): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc, _DecimalAwareEncoder, _is_demo_mode_enabled(), _require_demo_mode(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., Check whether demo-only utilities should be exposed., get_group(), list_groups() (+12 more)

### Community 293 - "Community 293"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 294 - "Community 294"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 295 - "Community 295"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 296 - "Community 296"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 297 - "Community 297"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 298 - "Community 298"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (65): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi, email_status(), FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., FastAPI routes for Payments., AllocationRunPayload, AllocationRunResponse, RoomMoveEvent (+57 more)

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (27): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs, Manual bank-transfer evidence and approval lifecycle., _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_is_allowed(), test_cash_movement_requires_open_session() (+19 more)

### Community 150 - "Community 150"
Cohesion: 0.27
Nodes (9): _policy_name(), _quoted_table(), upgrade(), downgrade(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, get_public_api_context(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth. (+1 more)

### Community 299 - "Community 299"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 300 - "Community 300"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 301 - "Community 301"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 302 - "Community 302"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 267 - "Community 267"
Cohesion: 0.60
Nodes (4): _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d

### Community 246 - "Community 246"
Cohesion: 0.47
Nodes (4): _utcnow(), _seed_ota_providers(), upgrade(), ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l

### Community 146 - "Community 146"
Cohesion: 0.21
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process an IPN (Instant Payment Notification) from MercadoPago.         Queries

### Community 127 - "Community 127"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (43): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _issue_email_token(), register(), request_verify() (+35 more)

### Community 233 - "Community 233"
Cohesion: 0.53
Nodes (1): SimpleRateLimiter

### Community 103 - "Community 103"
Cohesion: 0.24
Nodes (16): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+8 more)

### Community 37 - "Community 37"
Cohesion: 0.09
Nodes (38): validate_reset(), Prefer a hotel whose onboarding is already complete.      When a user belongs to, Validate reset code without changing password (paso previo en UI)., AcceptPayload, LoginRequest, InvitePayload, InviteResponse, UpdateRolePayload (+30 more)

### Community 34 - "Community 34"
Cohesion: 0.10
Nodes (29): RoomBlockCreate, RoomBlockRead, _validate_block_dates(), _exclusive_end(), _inclusive_end(), _existing_user_id(), _read_block(), create_room_block() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (83): BaseModel, MasterAdminLoginRequest, MasterAdminUserPayload, MasterAdminLoginResponse, MasterAdminSessionResponse, BillingPolicyUpdateRequest, BillingPolicyPayload, EmailTestRequest (+75 more)

### Community 118 - "Community 118"
Cohesion: 0.22
Nodes (13): _require_demo_mode(), _booking_to_read(), _project_booking_graph(), availability(), price_quote(), list_bookings(), create_booking(), get_booking() (+5 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (70): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped (+62 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (35): _postgres_healthcheck(), _redis_healthcheck(), datastores_healthcheck(), _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), get_engine() (+27 more)

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (57): CheckInRequest, FastAPI routes for Check-in / Check-out., FastAPI routes for Guest management., Add new companions to an existing guest., GuestRatingEnum, GuestTagTypeEnum, GuestTag, Guest and GuestCompanion models. Exhaustive fields for check-in panel: identity (+49 more)

### Community 129 - "Community 129"
Cohesion: 0.14
Nodes (1): FastAPI routes for the commercial configuration domain.

### Community 44 - "Community 44"
Cohesion: 0.10
Nodes (28): Company, CompanyPayload, CompanyDocumentType, CompanyDocumentStatus, CompanyDocument, CompanyDocumentPayload, listCompanies(), createCompany() (+20 more)

### Community 202 - "Community 202"
Cohesion: 0.32
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 86 - "Community 86"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection. (+4 more)

### Community 2 - "Community 2"
Cohesion: 0.04
Nodes (130): DailyRateOut, Config, DailyRateFallbackOut, DailyRateIn, BulkRateIn, BulkFieldRateIn, BulkRateOut, PricePeriodIn (+122 more)

### Community 203 - "Community 203"
Cohesion: 0.32
Nodes (7): _require_demo_mode(), seed_demo(), reset_demo(), Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for

### Community 136 - "Community 136"
Cohesion: 0.19
Nodes (8): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, EmailSendResponse, EmailVerifyResponse, SmtpStatus

### Community 137 - "Community 137"
Cohesion: 0.24
Nodes (9): FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, get_all_rates(), get_usd_oficial_rate(), get_single_rate(), create_fx_snapshot() (+1 more)

### Community 98 - "Community 98"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 87 - "Community 87"
Cohesion: 0.10
Nodes (8): _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), add_companions(), GuestStaySummary, GuestQuickProfile, GuestCheckInReservation, GuestCompanion

### Community 82 - "Community 82"
Cohesion: 0.13
Nodes (15): Staff management endpoints for hotel public API keys., HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia, Per-hotel API credential. `key_hash` stores a hashed version of the secret;, HotelAPIKeyError, _hash_secret(), _generate_secret(), issue_key() (+7 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (21): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _store_oauth_code(), get_status() (+13 more)

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (27): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+19 more)

### Community 163 - "Community 163"
Cohesion: 0.38
Nodes (9): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+1 more)

### Community 72 - "Community 72"
Cohesion: 0.08
Nodes (12): FastAPI routes for the onboarding flow used by smoke tests., OnboardingProviderSetup, OnboardingStatus, OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, CategoryPayload, RoomPayload (+4 more)

### Community 6 - "Community 6"
Cohesion: 0.08
Nodes (53): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., OTASyncStatusEnum, OTAReservationMapping, OTAWebhookCredential, OTA (Online Travel Agency) reservation mapping. Tracks the link between external (+45 more)

### Community 218 - "Community 218"
Cohesion: 0.33
Nodes (2): _mercadopago_webhook_impl(), mercadopago_payment_link_webhook()

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (33): PaymentSurchargeRead, PaymentSurchargeCreate, PaymentSurchargeUpdate, _get_surcharge_or_404(), update_payment_surcharge(), deactivate_payment_surcharge(), Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, ReservationStatusHistory (+25 more)

### Community 93 - "Community 93"
Cohesion: 0.14
Nodes (15): PermissionOverrideRequest, FastAPI routes for hotel permission matrix management., PermissionRole, PermissionCell, PermissionMatrix, PermissionMatrixResponse, PermissionOverridePayload, PermissionOverrideResponse (+7 more)

### Community 164 - "Community 164"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status()

### Community 83 - "Community 83"
Cohesion: 0.15
Nodes (19): RateCalendarChannelRestrictions, RateCalendarMeta, GetRateCalendarDailyParams, getRateCalendarDaily(), DailyRatePrices, DailyRateOut, getCategoryDailyRates(), BulkRateResult (+11 more)

### Community 272 - "Community 272"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (22): daily_report(), occupancy_report(), revenue_report(), OperationalReservationSummary, OperationalReservationGroup, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead (+14 more)

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (211): FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Occupancy report for a date range (default: last 30 days)., Revenue report for a date range., RoomStatusUpdate, RoomCategoryAssignmentUpdate, Soft-delete a room when no active reservations are attached., DocumentTypeEnum (+203 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (52): _to_read(), _is_manager_context(), _trigger_reoptimization_bg(), _project_reservation_graph(), create_new_reservation(), create_or_update_manual_ota(), list_reservations(), get_reservation() (+44 more)

### Community 53 - "Community 53"
Cohesion: 0.46
Nodes (29): register_settlement(), FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend, §5.2 — Run allocation engine in background after reservation changes.     Create, Register the deferred corporate collection (v72 §3.5): settled., Cancel a reservation. Post check-in cancellations are not allowed., §10.2 — Internally release a no-guarantee OTA reservation (no provider cancel ca, Mark a reservation as no-show without automatic charge., Modify a reservation (dates, notes, room). Only allowed for pre-check-in states. (+21 more)

### Community 14 - "Community 14"
Cohesion: 0.04
Nodes (52): _serialize_reallocation_result(), _attach_current_rate(), list_categories(), get_category(), room_availability(), update_room(), update_room_status(), update_room_category() (+44 more)

### Community 94 - "Community 94"
Cohesion: 0.11
Nodes (5): DecimalValue, StockItem, StockLocation, StockMovement, CurrentStock

### Community 177 - "Community 177"
Cohesion: 0.22
Nodes (9): StockItemCreate, StockItemUpdate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementRead, FastAPI routes for stock and inventory operations., StockError (+1 more)

### Community 108 - "Community 108"
Cohesion: 0.13
Nodes (14): StockMovementCreate, StockMovementType, listStockItems(), listLowStockItems(), createStockItem(), listStockLocations(), createStockLocation(), createStockMovement() (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (95): _remaining_trial_days(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial(), admin_comped_override(), Subscription status and entitlements endpoints., _decode_authorization_header() (+87 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (15): API routes for reservation waitlist operations., listGuests(), WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload, WaitlistPromoteResponse, listWaitlistEntries() (+7 more)

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (8): Public WhatsApp bot hooks authenticated only by hotel API key., WhatsAppBookingError, availability_lookup(), price_quote(), options_with_prices(), create_reservation(), generate_payment_link(), handle_payment_confirmation()

### Community 24 - "Community 24"
Cohesion: 0.06
Nodes (36): Settings, BaseSettings, get_settings(), _normalized_env_value(), _has_value(), _is_public_https_url(), _mercadopago_is_active(), _paypal_is_active() (+28 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (108): Base, DeclarativeBase, Base class for all ORM models., Record an AuditLog row for a successful entity mutation., str, AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, AnalyticsExportStatusEnum (+100 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (183): Application decorators., Reservation model with strict state machine. States: pending â†’ deposit_paid â†, Transaction and PaymentMethod models. Supports: Efectivo (Cash), MercadoPago, Pa, mockCategories, mockCalendar, mockDailyRates, Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati, 01498d0 Harden password reset flow (verified-only, dev code return) (+175 more)

### Community 139 - "Community 139"
Cohesion: 0.22
Nodes (8): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change()

### Community 305 - "Community 305"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 303 - "Community 303"
Cohesion: 0.67
Nodes (3): lifespan(), Initialize database on application startup., Initialize database on application startup.

### Community 247 - "Community 247"
Cohesion: 0.40
Nodes (4): SafeStaticFiles, StaticFiles, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on

### Community 178 - "Community 178"
Cohesion: 0.22
Nodes (9): _frontend_placeholder(), serve_frontend(), serve_spa(), Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin (+1 more)

### Community 35 - "Community 35"
Cohesion: 0.09
Nodes (28): Master admin panel backend package., Email provider abstraction for platform transactional mail., ApiError, RequestOptions, readCookie(), setMasterAdminCsrfToken(), clearMasterAdminCsrfToken(), safeJson() (+20 more)

### Community 179 - "Community 179"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 120 - "Community 120"
Cohesion: 0.22
Nodes (11): _dev_outbox_path(), _record_dev_email(), SystemEmailStatus, _normalize_account_email(), _sender_parts(), _build_unavailable_message(), _current_status(), get_system_email_status() (+3 more)

### Community 121 - "Community 121"
Cohesion: 0.22
Nodes (12): RuntimeError, E2ESafetyError, prepare_e2e_environment(), _credentials(), run_migrations(), upsert_seed_data(), main(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet (+4 more)

### Community 29 - "Community 29"
Cohesion: 0.07
Nodes (37): MasterAdminSession, Base, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings, MasterStripeWebhookEvent (+29 more)

### Community 95 - "Community 95"
Cohesion: 0.12
Nodes (4): _serialize_user(), login(), me(), dashboard_summary()

### Community 60 - "Community 60"
Cohesion: 0.18
Nodes (25): _now(), _as_aware(), _hash_value(), _normalize_identifier(), _normalize_pin(), _bootstrap_master_credentials_match(), _pin_matches(), _session_cookie_secure() (+17 more)

### Community 151 - "Community 151"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 250 - "Community 250"
Cohesion: 0.40
Nodes (2): SubscriptionEnforcementMiddleware, Middleware to block mutating requests when subscription enforcement is enabled.

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (37): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, GemmaActionRunError, get_action_run(), approve_action_run() (+29 more)

### Community 100 - "Community 100"
Cohesion: 0.29
Nodes (16): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, AllocationRun, AllocationAssignment, AllocationExplanation, SolverMetric, Allocation, solver and LLM policy models.  The deterministic solver remains the, AllocationRuntimeError (+8 more)

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (25): LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, ManualOverrideReason, LLMPolicySuggestion, LLMFeedbackEvent, AllocationQuestionnaireDraft, AllocationFeedbackDraft (+17 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (51): CashSessionStatusEnum, CashMovementTypeEnum, CashSession, CashMovement, CashCloseReport, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca, Single cash-register shift. Only one OPEN session per hotel at a time     (enfor, Individual money movement within an open cash session.     Linked optionally to (+43 more)

### Community 91 - "Community 91"
Cohesion: 0.18
Nodes (14): CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentStatusUpdate, CompanyDocumentRead (+6 more)

### Community 25 - "Community 25"
Cohesion: 0.10
Nodes (41): APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote, PublicReservationCreate (+33 more)

### Community 138 - "Community 138"
Cohesion: 0.18
Nodes (7): HotelConfiguration — per-hotel business rules. No global/singleton: one row per, Pydantic schemas for HotelConfiguration., 1d1874d Add owner-only visibility panel for hotel config, 1fd0691 Add display permission fields to hotel config with tests, aba40b3 UI: invite link buttons and owner-only role view toggle, b33f5a8 Config UI: advanced owner settings and ops fields, e3aa066 feat(R-extra): configurable per-hotel API rate limit §16 + waitlist promotion on OTA release §10.2

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (11): IntegrationCatalog, IntegrationConnection, IntegrationEvent, _Response, test_validate_gmail_credentials_requires_send_scope(), test_verify_connection_health_for_gmail_updates_connection(), _Response, _seed_gmail_connection() (+3 more)

### Community 111 - "Community 111"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (57): ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum, BillingAdjustmentTypeEnum, ReservationAdjustment, BillingAdjustment, Operational reservation models for adjustments, room moves and audit history., PaymentError, ReservationOperationsError (+49 more)

### Community 27 - "Community 27"
Cohesion: 0.07
Nodes (15): OTASyncJob, OTASyncEvent, Foundational OTA adapter interfaces and orchestration services., OTAAdapterContext, OTAOperationResult, NormalizedOTAReservation, OTAProviderAdapter, Common contracts for OTA provider adapters.  The goal is to keep Booking, Expedi (+7 more)

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (37): PaymentLink, Payment, PaymentWebhookEvent, Payment gateway tracking models: PaymentLink, Payment, PaymentWebhookEvent.  Sou, Guest-facing pre-payment object (checkout URL / QR). May collect partial payment, One gateway payment object (MP preference / PayPal order / Stripe intent)., Raw webhook log per payment — idempotent on (hotel_id, provider, webhook_id)., TransactionTypeEnum (+29 more)

### Community 251 - "Community 251"
Cohesion: 0.60
Nodes (4): PaymentProofStatusEnum, PaymentProofCreate, PaymentProofReject, PaymentProofRead

### Community 112 - "Community 112"
Cohesion: 0.27
Nodes (14): PaymentProof, Private image evidence awaiting explicit staff confirmation., PaymentProofError, _decode_image(), _safe_filename(), _proof_path(), _reservation(), submit_transfer_proof() (+6 more)

### Community 130 - "Community 130"
Cohesion: 0.29
Nodes (13): Permission, RolePermissionDefault, HotelPermissionOverride, Configurable permission matrix models., seed_default_permissions(), resolve(), set_override(), get_matrix() (+5 more)

### Community 307 - "Community 307"
Cohesion: 1.00
Nodes (2): reportable_origin(), Derive the BRM §16.2 reportable origin for a reservation.      Precedence:

### Community 49 - "Community 49"
Cohesion: 0.17
Nodes (28): Subscription, SubscriptionEvent, Lightweight subscription tracking for enforcement and auditing (v2 tables)., _now(), _as_utc(), _plan_defaults(), plan_catalog(), _is_enforcement_enabled() (+20 more)

### Community 236 - "Community 236"
Cohesion: 0.33
Nodes (4): WaitlistStatusEnum, WaitlistEntry, Waitlist / overbooking list model — v72 §9.  When the hotel is at capacity for a, Single guest waiting for a room in a given category for a date range.     Priori

### Community 75 - "Community 75"
Cohesion: 0.12
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 252 - "Community 252"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 180 - "Community 180"
Cohesion: 0.33
Nodes (8): GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead, Pydantic schemas for Guest and companions.

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (14): OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, ProviderSetupPayload, PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, CategoriesPayload (+6 more)

### Community 308 - "Community 308"
Cohesion: 1.00
Nodes (1): Schemas for manual OTA reservation entry.

### Community 205 - "Community 205"
Cohesion: 0.25
Nodes (7): ReservationTransactionSummaryRead, ReservationBillingAdjustmentSummaryRead, ReservationFinancialSummaryRead, ReservationAdjustmentSummaryRead, ReservationOTALinkSummaryRead, ReservationRoomMoveSummaryRead, Schemas for operational reservation actions.

### Community 154 - "Community 154"
Cohesion: 0.27
Nodes (10): RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryUpdate, RoomBase, RoomCreate, RoomRead, CategoryPricingSchema (+2 more)

### Community 237 - "Community 237"
Cohesion: 0.33
Nodes (5): Entitlement, EntitlementsResponse, EntitlementOverrideRequest, TrialRequest, CompedOverrideRequest

### Community 220 - "Community 220"
Cohesion: 0.29
Nodes (6): WaitlistEntryCreate, WaitlistEntryUpdate, WaitlistEntryRead, WaitlistPromoteRequest, WaitlistPromoteResponse, Schemas for hotel-scoped waitlist entries.

### Community 63 - "Community 63"
Cohesion: 0.15
Nodes (21): ValueError, CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy(), update_tax_policy() (+13 more)

### Community 47 - "Community 47"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, AnalyticsAIProviderError, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider, GemmaProvider (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (49): AnalyticsAIProvider, Protocol, LeaseError, RenderRequester, _canonical_json(), _service_id(), _target_sha(), _target_branch() (+41 more)

### Community 66 - "Community 66"
Cohesion: 0.17
Nodes (24): reservation_status_to_outcome(), infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code(), backfill_channel_code(), split_amount_evenly(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact() (+16 more)

### Community 62 - "Community 62"
Cohesion: 0.15
Nodes (22): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _flatten_payload_rows(), _rows_to_csv_bytes(), _png_from_rows(), _sheet_xml_from_table() (+14 more)

### Community 78 - "Community 78"
Cohesion: 0.17
Nodes (20): detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), calculate_pickup_30d(), _reservation_row_kind(), _resolve_no_show_policy(), _reservation_monetary_totals(), _reservation_dates_in_window() (+12 more)

### Community 140 - "Community 140"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (51): _now(), _hotel_local_now(), _ensure_utc(), _money(), _money_str(), _utc_date_range(), _analytics_window(), _comparison_read() (+43 more)

### Community 221 - "Community 221"
Cohesion: 0.43
Nodes (4): payload_json(), create_audit_log(), queue_audit_log(), safe_create_audit_log()

### Community 101 - "Community 101"
Cohesion: 0.20
Nodes (9): _mask_email(), _mask_recipients(), _normalize_display_from(), EmailProviderError, EmailProvider, ABC, ResendEmailProvider, NullEmailProvider (+1 more)

### Community 155 - "Community 155"
Cohesion: 0.25
Nodes (6): Mailer, send_platform_email(), send_verification_email(), send_reset_password_email(), send_verification_success_email(), Platform email service facade backed by the system transactional provider.

### Community 165 - "Community 165"
Cohesion: 0.38
Nodes (9): _is_cache_fresh(), _get_async(), fetch_all_rates(), fetch_rate(), get_usd_official_rate(), get_usd_rate_for_type(), get_all_rates_snapshot(), get_cached_rates() (+1 more)

### Community 238 - "Community 238"
Cohesion: 0.60
Nodes (5): GemmaSuggestedAction, GemmaProposalPreview, build_controlled_proposal(), _detect_channel(), _dedupe_preserve_order()

### Community 239 - "Community 239"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 253 - "Community 253"
Cohesion: 0.60
Nodes (4): GuestProfileError, get_guest_profile(), _enum_value(), validate_primary_guest_record()

### Community 141 - "Community 141"
Cohesion: 0.32
Nodes (11): _now(), _audit(), _get_guest(), _active_tag_filter(), find_or_create_guest(), list_active_tags(), _serialize_stay(), quick_profile() (+3 more)

### Community 240 - "Community 240"
Cohesion: 0.60
Nodes (5): HotelOutboundIdentity, HotelOutboundSendResult, ensure_hotel_gmail_ready(), _build_message(), send_hotel_email()

### Community 61 - "Community 61"
Cohesion: 0.17
Nodes (22): _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload(), get_connection_payload(), derive_expires_at() (+14 more)

### Community 254 - "Community 254"
Cohesion: 0.50
Nodes (4): JurisdictionProfile, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 76 - "Community 76"
Cohesion: 0.28
Nodes (23): OnboardingError, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _merge_extra_policies(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload() (+15 more)

### Community 113 - "Community 113"
Cohesion: 0.23
Nodes (13): _guest_name(), _reservation_summary(), _group(), _active_room_blocks(), _available_with_review(), _cash_session(), _alerts(), daily_report() (+5 more)

### Community 55 - "Community 55"
Cohesion: 0.08
Nodes (3): BookingAdapter, OTAProviderAdapter, ExpediaAdapter

### Community 126 - "Community 126"
Cohesion: 0.16
Nodes (1): DespegarAdapter

### Community 142 - "Community 142"
Cohesion: 0.37
Nodes (12): create_or_update_manual_ota_reservation(), release_no_guarantee(), _attempt_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean(), _apply_manual_amounts() (+4 more)

### Community 79 - "Community 79"
Cohesion: 0.20
Nodes (22): PaymentLinkTestError, _validate_email(), _mercadopago_access_token(), _friendly_mercadopago_error(), _status_from_payment(), _send_payment_link_email(), _notification_url(), _is_public_webhook_base() (+14 more)

### Community 122 - "Community 122"
Cohesion: 0.26
Nodes (14): get_hotel_config(), validate_payment_method_enabled(), _resolve_reservation_hotel(), _resolve_payment_currency(), _payment_method_value(), calculate_payment_surcharge(), calculate_base_amount_before_surcharge(), process_payment() (+6 more)

### Community 156 - "Community 156"
Cohesion: 0.38
Nodes (10): _parse_mercadopago_signature_header(), validate_mercadopago_webhook_signature(), _payload_value(), _normalize_status(), _completed_at(), _find_existing_event(), _insert_event(), _transaction_exists() (+2 more)

### Community 166 - "Community 166"
Cohesion: 0.38
Nodes (9): quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount(), _convert_amount(), _select_fx_policy() (+1 more)

### Community 42 - "Community 42"
Cohesion: 0.11
Nodes (34): get_price_for_date(), get_prices_for_range(), apply_price_period(), generate_confirmation_code(), _invalidate_availability_cache(), _resolve_hotel_id(), _validate_reservation_occupancy(), compute_reservation_pricing() (+26 more)

### Community 182 - "Community 182"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 105 - "Community 105"
Cohesion: 0.27
Nodes (16): _settings(), _cache_enabled(), _get_redis_client(), _load_json(), _store_json(), _get_cached_or_compute(), _date_token(), _availability_key() (+8 more)

### Community 123 - "Community 123"
Cohesion: 0.28
Nodes (14): get_reservation_operations_summary(), list_pending_reservation_actions(), resolve_external_channel_follow_up(), clear_reservation_manual_review(), _build_pending_actions(), _decorate_action(), _dedupe_candidates(), _get_reservation_or_error() (+6 more)

### Community 157 - "Community 157"
Cohesion: 0.25
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (9): update_stock_item(), delete_stock_item(), register_movement(), current_stock(), low_stock_items(), get_stock_item(), get_location(), _get_item() (+1 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (25): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), _upsert_plan_entitlement(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements() (+17 more)

### Community 183 - "Community 183"
Cohesion: 0.33
Nodes (8): _set_context_value(), set_tenant_user_context(), set_tenant_hotel_context(), set_tenant_context(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Set the authenticated user id used by membership RLS policies., Set or clear the current hotel id for tenant-scoped RLS policies., Set both principals for a request or a single-hotel worker job.

### Community 158 - "Community 158"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 207 - "Community 207"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 167 - "Community 167"
Cohesion: 0.44
Nodes (8): WaitlistError, _get_waitlist_entry(), add_to_waitlist(), update_waitlist_entry(), promote_from_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), request_payment_link_for_waitlist()

### Community 184 - "Community 184"
Cohesion: 0.33
Nodes (8): _active_hotel_ids(), _send_report_for_hotel(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports(), Celery tasks for scheduled operational reports (BRM §15.1).  Two beat-driven tas, Build and email the report for a single hotel. Returns True on send.      Best-e, Build and email the report for a single hotel. Returns True on send.      Best-e

### Community 134 - "Community 134"
Cohesion: 0.21
Nodes (4): graphify_state(), main(), 1ebf84a Audit and harden agent operations context, bc938cf Add agent ops vault and cloud QA foundation

### Community 235 - "Community 235"
Cohesion: 0.40
Nodes (3): hotelId, authHeaders(), ensureOnboarding()

### Community 248 - "Community 248"
Cohesion: 0.40
Nodes (2): credentials, PAGES

### Community 249 - "Community 249"
Cohesion: 0.40
Nodes (4): frontendDir, repoRoot, localPython, e2eDbPath

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (28): queryClient, navItems, MasterAdminRoot(), MasterAdminProtectedShell(), MasterAdminAuditPage(), MasterAdminDashboardPage(), MasterAdminLoginPage(), MasterAdminSessionProvider() (+20 more)

### Community 58 - "Community 58"
Cohesion: 0.13
Nodes (22): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, IssueHotelApiKeyPayload, listApiKeys(), issueApiKey(), revokeApiKey(), SessionLike (+14 more)

### Community 48 - "Community 48"
Cohesion: 0.12
Nodes (27): CashSessionStatus, CashMovementType, CashSession, CashMovement, CashCloseReport, CashSessionSummary, CashSessionOpenPayload, CashMovementPayload (+19 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (30): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+22 more)

### Community 119 - "Community 119"
Cohesion: 0.14
Nodes (14): Guest, GuestPayload, GuestUpdatePayload, GuestCompanionPayload, createGuest(), getGuest(), updateGuest(), addGuestCompanions() (+6 more)

### Community 89 - "Community 89"
Cohesion: 0.10
Nodes (15): GuestTagType, GuestTag, GuestTagPayload, getGuestQuickProfile(), listGuestTags(), addGuestTag(), resolveGuestTag(), checkInGuestReservation() (+7 more)

### Community 41 - "Community 41"
Cohesion: 0.05
Nodes (17): PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, setOwner(), setHotelIdentity(), setCategories(), setRooms(), setDepositPolicy() (+9 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (18): RateCalendarChannelPrice, RateCalendarChannelDay, RateCalendarDay, InfoTipProps, PopoverPosition, InfoTip(), RateCalendarGridProps, ChannelSummary (+10 more)

### Community 107 - "Community 107"
Cohesion: 0.13
Nodes (11): RateCalendarResponse, DailyRateRangeRow, RateEditorGridProps, PRICE_ROWS, WEEKDAY, MONTH, INTEGER_LABEL, SOURCE_LABEL (+3 more)

### Community 99 - "Community 99"
Cohesion: 0.13
Nodes (15): Props, IntegrationHelpDrawer(), IntegrationHelp, useIntegrations(), useConnectIntegration(), useRevokeIntegration(), useRefreshIntegration(), FormState (+7 more)

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (14): PriceField, useRateCalendar(), useCategoryDailyRates(), SingleRateInput, useUpsertDailyRate(), useBulkUpsertRates(), useBulkUpdateRateField(), RANGE_LABEL (+6 more)

### Community 36 - "Community 36"
Cohesion: 0.15
Nodes (28): StructuredData, SeoProps, Seo(), navItems, MarketingShellProps, MarketingShell(), PublicButtonLinkProps, isExternal() (+20 more)

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (35): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+27 more)

### Community 110 - "Community 110"
Cohesion: 0.18
Nodes (14): trimTrailingSlash(), ensureLeadingSlash(), normalizeUrl(), PUBLIC_SITE_URL, PUBLIC_APP_URL, APP_URL_HOSTNAME, SITE_URL_HOSTNAME, isAppHostname() (+6 more)

### Community 204 - "Community 204"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 153 - "Community 153"
Cohesion: 0.27
Nodes (7): formatterCache, normalizeCurrencyCode(), getFormatter(), formatMoney(), resolveSingleCurrencyCode(), todayIso(), DashboardPage()

### Community 176 - "Community 176"
Cohesion: 0.28
Nodes (8): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Parse the simple unquoted frontmatter lists used by context packs.

### Community 21 - "Community 21"
Cohesion: 0.08
Nodes (41): Shared, secret-safe binding for the Render QA bootstrap configuration., safe_preview_settings(), test_preview_runtime_accepts_explicitly_disabled_external_effects(), test_preview_runtime_rejects_external_effects_configuration(), Fail-closed safeguards for cloud QA external integrations., wrapper(), env_page(), fixtures() (+33 more)

### Community 128 - "Community 128"
Cohesion: 0.30
Nodes (13): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+5 more)

### Community 162 - "Community 162"
Cohesion: 0.49
Nodes (9): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+1 more)

### Community 106 - "Community 106"
Cohesion: 0.17
Nodes (14): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots. (+6 more)

### Community 147 - "Community 147"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 64 - "Community 64"
Cohesion: 0.23
Nodes (22): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+14 more)

### Community 50 - "Community 50"
Cohesion: 0.09
Nodes (24): BootstrapConfigurationError, JsonGetter, ReadOnlyJsonApi, VerificationConfig, ProviderClients, _decode_lease_entropy(), _verify_qa_external_effects_disabled(), main() (+16 more)

### Community 268 - "Community 268"
Cohesion: 0.50
Nodes (4): bootstrap_configuration_fingerprint(), Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually.

### Community 65 - "Community 65"
Cohesion: 0.22
Nodes (23): AttestationError, _sha256(), _canonical_json(), _b64url_encode(), _b64url_decode(), _read_regular_nofollow(), _read_limited(), _json_object() (+15 more)

### Community 201 - "Community 201"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 269 - "Community 269"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 20 - "Community 20"
Cohesion: 0.09
Nodes (36): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+28 more)

### Community 135 - "Community 135"
Cohesion: 0.35
Nodes (12): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+4 more)

### Community 270 - "Community 270"
Cohesion: 0.83
Nodes (3): run(), validate_json(), main()

### Community 102 - "Community 102"
Cohesion: 0.24
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 51 - "Community 51"
Cohesion: 0.23
Nodes (29): VerificationError, _dict(), _list(), _string(), _validate_config(), _validate_baseline_lease_id(), _verify_github_target(), _canonical_hostname() (+21 more)

### Community 271 - "Community 271"
Cohesion: 0.50
Nodes (4): _verify_dedicated_baseline_lease(), Require an exclusive provider-observed lease for the shared free QA DB.      Thi, Require an exclusive provider-observed lease for the shared free QA DB.      Thi, Require an exclusive provider-observed lease for the shared free QA DB.      Thi

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (44): QABootstrapError, Persona, QABootstrapConfig, ProviderEvidence, _required(), _flag(), _required_port(), _validate_email() (+36 more)

### Community 206 - "Community 206"
Cohesion: 0.25
Nodes (8): QABootstrapResult, _qa_marker(), upsert_qa_data(), Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users.

### Community 181 - "Community 181"
Cohesion: 0.36
Nodes (8): _required(), load_provider_evidence_private_key(), issue_provider_evidence_token(), _safe_output_path(), write_private_token(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer.

### Community 219 - "Community 219"
Cohesion: 0.57
Nodes (6): command(), heading(), fenced(), frontend_routes(), write(), main()

### Community 152 - "Community 152"
Cohesion: 0.35
Nodes (10): derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure(), explain(), print_results() (+2 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (49): _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+41 more)

### Community 222 - "Community 222"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 115 - "Community 115"
Cohesion: 0.17
Nodes (6): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), Regression contracts for the repository's agent-operations setup.

### Community 77 - "Community 77"
Cohesion: 0.18
Nodes (5): make_rooms(), make_res(), TestOverlap, TestGreedyAllocation, TestCPSATAllocation

### Community 168 - "Community 168"
Cohesion: 0.60
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+1 more)

### Community 223 - "Community 223"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 208 - "Community 208"
Cohesion: 0.46
Nodes (7): _slot(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(), test_allocation_run_creates_movement_group_and_events(), _seed_hotel_rooms_guests(), _reservation()

### Community 159 - "Community 159"
Cohesion: 0.24
Nodes (4): _Response, _Client, test_provider_receives_only_curated_hotel_analytics_payload(), test_provider_chat_uses_curated_hotel_context_and_controlled_message()

### Community 160 - "Community 160"
Cohesion: 0.33
Nodes (9): _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads(), test_analytics_dashboard_and_ai_chat_without_provider() (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.18
Nodes (4): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role()

### Community 96 - "Community 96"
Cohesion: 0.35
Nodes (18): _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation(), _audit_for() (+10 more)

### Community 209 - "Community 209"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 161 - "Community 161"
Cohesion: 0.18
Nodes (4): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_hotel_cascade_delete(), test_audit_log_all_actions_persist(), test_transaction_hotel_id_has_fk_constraint()

### Community 104 - "Community 104"
Cohesion: 0.21
Nodes (11): _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend(), test_register_verify_and_reset_use_resend_provider(), test_auth_flows_fail_without_connected_mail_provider(), test_unverified_users_cannot_use_operational_endpoints(), test_login_prefers_a_completed_hotel_when_multiple_memberships_exist() (+3 more)

### Community 304 - "Community 304"
Cohesion: 0.67
Nodes (1): FakeResponse

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+29 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (14): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+6 more)

### Community 68 - "Community 68"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+15 more)

### Community 255 - "Community 255"
Cohesion: 0.80
Nodes (4): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 256 - "Community 256"
Cohesion: 0.70
Nodes (4): _override_auth(), _client_with_db(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 124 - "Community 124"
Cohesion: 0.51
Nodes (14): _make_hotel(), _make_guest(), _make_room(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin(), test_prohibido_tag_from_different_hotel_does_not_block() (+6 more)

### Community 187 - "Community 187"
Cohesion: 0.58
Nodes (8): _get_db_override_target(), _override_auth(), _seed_hotel(), _build_client(), _cleanup_client(), test_owner_can_create_and_update_commercial_configuration(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories()

### Community 257 - "Community 257"
Cohesion: 0.60
Nodes (3): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 224 - "Community 224"
Cohesion: 0.71
Nodes (6): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation()

### Community 225 - "Community 225"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_reservation_is_allocation_locked()

### Community 210 - "Community 210"
Cohesion: 0.32
Nodes (4): get_db_override_target(), get_auth_context_target(), client_with_db(), ctx()

### Community 211 - "Community 211"
Cohesion: 0.25
Nodes (6): client(), test_seed_and_reset_blocked_by_default(), test_seed_and_reset_allowed_when_demo_enabled(), FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Demo utilities work once DEMO_MODE=true is set.

### Community 74 - "Community 74"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 189 - "Community 189"
Cohesion: 0.28
Nodes (3): _read(), test_generates_only_allowed_synthetic_values_with_private_permissions(), test_explicit_rotation_replaces_values_and_preserves_mode()

### Community 190 - "Community 190"
Cohesion: 0.33
Nodes (5): _integration_client(), _Response, test_validate_gmail_credentials_rejects_missing_send_scope(), test_send_hotel_email_uses_connected_gmail(), test_gmail_oauth_callback_uses_signed_state()

### Community 131 - "Community 131"
Cohesion: 0.46
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 191 - "Community 191"
Cohesion: 0.33
Nodes (6): get_db_override_target(), get_auth_context_target(), client_with_db(), owner_ctx(), test_update_role_requires_owner(), test_co_owner_cannot_grant_privileged_roles()

### Community 274 - "Community 274"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 97 - "Community 97"
Cohesion: 0.19
Nodes (12): _seed_platform_admin(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_login_bootstraps_env_account(), test_master_login_sets_cookie_and_hydrates_me(), test_master_login_cookie_works_on_underscore_alias(), test_master_login_locks_out_after_repeated_failures() (+4 more)

### Community 258 - "Community 258"
Cohesion: 0.60
Nodes (3): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 212 - "Community 212"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 213 - "Community 213"
Cohesion: 0.43
Nodes (7): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_reset_endpoint_allows_testing_env()

### Community 144 - "Community 144"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (14): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 192 - "Community 192"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database.

### Community 259 - "Community 259"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 193 - "Community 193"
Cohesion: 0.36
Nodes (7): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records(), API coverage for the expanded onboarding wizard.

### Community 194 - "Community 194"
Cohesion: 0.47
Nodes (6): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped(), test_available_with_review_surfaces_in_report()

### Community 227 - "Community 227"
Cohesion: 0.67
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 169 - "Community 169"
Cohesion: 0.47
Nodes (8): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(), test_release_no_guarantee_promotes_compatible_waitlist_entry(), test_release_no_guarantee_without_waitlist_still_succeeds(), test_manual_ota_cross_hotel_isolation()

### Community 170 - "Community 170"
Cohesion: 0.29
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret(), test_despegar_webhook_scopes_by_hotel_and_secret()

### Community 171 - "Community 171"
Cohesion: 0.44
Nodes (9): _reservation(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_link_best_effort_when_gateway_fails(), test_deliver_link_email_records_channel(), test_deliver_link_email_best_effort_on_failure() (+1 more)

### Community 260 - "Community 260"
Cohesion: 0.60
Nodes (3): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation()

### Community 214 - "Community 214"
Cohesion: 0.57
Nodes (7): _reservation(), _link(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key(), test_balance_due_uses_transactions_not_payments()

### Community 228 - "Community 228"
Cohesion: 0.48
Nodes (5): _seed_hotel(), test_permission_override_allows_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_get_matrix_includes_hotel_overrides()

### Community 229 - "Community 229"
Cohesion: 0.67
Nodes (6): _override_auth(), _client_with_db(), test_permissions_matrix_available_to_authenticated_hotel_member(), test_permission_override_allows_receptionist_guest_edit(), test_permission_denied_is_audited(), test_override_in_hotel_a_does_not_affect_hotel_b()

### Community 69 - "Community 69"
Cohesion: 0.19
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 261 - "Community 261"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_converts_currency_with_fx_policy_spread()

### Community 56 - "Community 56"
Cohesion: 0.17
Nodes (21): manifest(), token_for(), env_page(), FakeRender, HealthResponse, FakeRenderCleanupFailure, FakeRenderPutResponseLost, _mutating_calls() (+13 more)

### Community 148 - "Community 148"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 116 - "Community 116"
Cohesion: 0.23
Nodes (14): tagged(), write_fixture(), test_operator_attestation_binds_exact_bytes_and_real_local_artifacts(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_unsigned_or_fabricated_attestation_is_rejected(), test_altered_signature_is_rejected(), test_signed_attestation_missing_a_summary_hash_is_rejected() (+6 more)

### Community 132 - "Community 132"
Cohesion: 0.48
Nodes (12): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+4 more)

### Community 117 - "Community 117"
Cohesion: 0.17
Nodes (8): FakeRedis, BrokenRedis, test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip(), test_operational_invalidation_clears_availability_and_analytics(), test_analytics_home_cache_key_varies_by_filter()

### Community 195 - "Community 195"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 84 - "Community 84"
Cohesion: 0.24
Nodes (17): iso(), write_bundle(), rewrite_summary(), rewrite_manifest(), errors_for(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_short_code_sha_is_rejected(), test_manifest_byte_hash_is_required() (+9 more)

### Community 196 - "Community 196"
Cohesion: 0.44
Nodes (7): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors()

### Community 215 - "Community 215"
Cohesion: 0.46
Nodes (7): _create_sample_reservation(), _completed_transaction(), test_no_show_can_be_marked_without_auto_charge(), test_date_change_without_payments_cancels_and_recreates(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_extension_requires_payment_or_link_action(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 172 - "Community 172"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 197 - "Community 197"
Cohesion: 0.28
Nodes (3): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 216 - "Community 216"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 145 - "Community 145"
Cohesion: 0.44
Nodes (12): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+4 more)

### Community 217 - "Community 217"
Cohesion: 0.46
Nodes (5): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 241 - "Community 241"
Cohesion: 0.73
Nodes (5): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation(), _seed_group()

### Community 149 - "Community 149"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 230 - "Community 230"
Cohesion: 0.57
Nodes (5): _seed_category(), _delete_audit(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits(), test_price_period_delete_soft_deletes_hides_and_audits()

### Community 262 - "Community 262"
Cohesion: 0.70
Nodes (4): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_low_stock_items_are_hotel_scoped()

### Community 198 - "Community 198"
Cohesion: 0.42
Nodes (6): _ensure_hotel(), _auth_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_records_audit_event(), test_role_gating_for_trial_and_comped_override(), test_manual_transitions_emit_events()

### Community 199 - "Community 199"
Cohesion: 0.39
Nodes (7): _seed_room(), test_create_room_block_public_api(), test_list_room_blocks_public_api(), test_release_room_block_public_api(), test_receptionist_can_create_but_not_release_block_by_default(), test_hotel_override_removing_create_block_is_respected(), test_room_blocks_public_api_is_hotel_scoped()

### Community 43 - "Community 43"
Cohesion: 0.13
Nodes (12): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _make_reservation(), _make_transaction(), TestOpenSession (+4 more)

### Community 173 - "Community 173"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 81 - "Community 81"
Cohesion: 0.17
Nodes (7): _make_reservation(), _pay_deposit(), _pay_full(), TestPaymentGateDepositPaid, TestPaymentGatePending, TestConfigFlag, TestCheckoutGate

### Community 242 - "Community 242"
Cohesion: 0.73
Nodes (5): _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 133 - "Community 133"
Cohesion: 0.47
Nodes (11): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+3 more)

### Community 231 - "Community 231"
Cohesion: 0.62
Nodes (6): _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_no_future_conflict_extends_normally()

### Community 85 - "Community 85"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_reservation_is_motor_protected_set_on_manual_move(), test_reservation_is_wait_listed_field(), test_extend_stay_basic() (+3 more)

### Community 243 - "Community 243"
Cohesion: 0.53
Nodes (4): _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_update_mobility_restriction_triggers_reoptimization(), test_room_move_requires_reason_code_and_accepts_valid_reason()

### Community 174 - "Community 174"
Cohesion: 0.36
Nodes (8): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_movement_group_hotel_isolation(), test_revert_already_reverted_group_returns_400(), _seed_group()

### Community 175 - "Community 175"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 125 - "Community 125"
Cohesion: 0.20
Nodes (3): _make_reservation(), TestWaitlistListing, TestWaitlistResolveLogic

### Community 277 - "Community 277"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation()

### Community 244 - "Community 244"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 200 - "Community 200"
Cohesion: 0.56
Nodes (7): _seed_hotel(), _issue_key(), _headers(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

## Knowledge Gaps
- **383 isolated node(s):** `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`, `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif` (+378 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 278`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 279`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 280`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 281`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 282`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 283`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 284`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 285`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 286`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 287`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 288`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 289`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 290`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 291`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 292`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 293`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 294`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 295`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 296`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 297`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 298`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 299`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 300`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 301`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 302`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 233`** (1 nodes): `SimpleRateLimiter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 129`** (1 nodes): `FastAPI routes for the commercial configuration domain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 218`** (2 nodes): `_mercadopago_webhook_impl()`, `mercadopago_payment_link_webhook()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 305`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 250`** (2 nodes): `SubscriptionEnforcementMiddleware`, `Middleware to block mutating requests when subscription enforcement is enabled.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 307`** (2 nodes): `reportable_origin()`, `Derive the BRM §16.2 reportable origin for a reservation.      Precedence:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 308`** (1 nodes): `Schemas for manual OTA reservation entry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 248`** (2 nodes): `credentials`, `PAGES`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 304`** (1 nodes): `FakeResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 195`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 4` to `Community 234`, `Community 203`, `Community 10`, `Community 26`, `Community 247`, `Community 178`, `Community 303`, `Community 29`, `Community 5`, `Community 100`, `Community 54`, `Community 2`, `Community 16`, `Community 91`, `Community 86`, `Community 137`, `Community 0`, `Community 12`, `Community 25`, `Community 82`, `Community 138`, `Community 37`, `Community 88`, `Community 111`, `Community 11`, `Community 38`, `Community 6`, `Community 27`, `Community 40`, `Community 112`, `Community 251`, `Community 32`, `Community 130`, `Community 1`, `Community 307`, `Community 8`, `Community 34`, `Community 3`, `Community 49`, `Community 236`, `Community 304`, `Community 211`, `Community 74`, `Community 190`, `Community 192`, `Community 193`?**
  _High betweenness centrality (0.125) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 0` to `Community 9`, `Community 37`, `Community 53`, `Community 8`, `Community 150`, `Community 138`, `Community 4`, `Community 29`, `Community 1`, `Community 12`, `Community 240`, `Community 76`, `Community 6`, `Community 79`, `Community 11`, `Community 38`, `Community 2`, `Community 49`, `Community 3`, `Community 67`, `Community 184`, `Community 304`, `Community 16`, `Community 74`, `Community 88`, `Community 190`, `Community 27`, `Community 40`, `Community 43`, `Community 81`, `Community 125`?**
  _High betweenness centrality (0.052) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 8`, `Community 12`, `Community 53`, `Community 2`, `Community 1`, `Community 4`, `Community 29`, `Community 100`, `Community 91`, `Community 253`, `Community 6`, `Community 40`, `Community 112`, `Community 11`, `Community 38`, `Community 34`, `Community 109`, `Community 16`, `Community 43`, `Community 81`, `Community 125`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 450 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 450 INFERRED edges - model-reasoned connections that need verification._
- **Are the 443 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 443 INFERRED edges - model-reasoned connections that need verification._
- **Are the 390 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 390 INFERRED edges - model-reasoned connections that need verification._
- **Are the 334 inferred relationships involving `Room` (e.g. with `RoomBlockCreate` and `RoomBlockRead`) actually correct?**
  _`Room` has 334 INFERRED edges - model-reasoned connections that need verification._