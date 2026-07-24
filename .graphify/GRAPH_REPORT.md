# Graph Report - .  (2026-07-24)

## Corpus Check
- Large corpus: 710 files · ~468,343 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 6262 nodes · 19856 edges · 256 communities detected
- Extraction: 68% EXTRACTED · 32% INFERRED · 0% AMBIGUOUS · INFERRED: 6369 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 6369 · contains: 4102 · calls: 3142 · MODIFIES: 1626 · ON_BRANCH: 1243 · rationale_for: 794 · imports: 698 · imports_from: 556 · method: 554 · inherits: 519 · PARENT_OF: 253


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 710 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 7 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `14c3453`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `ReservationStatusEnum` - 440 edges
2. `Reservation` - 435 edges
3. `HotelConfiguration` - 379 edges
4. `Room` - 332 edges
5. `Guest` - 317 edges
6. `Base` - 313 edges
7. `RoomCategory` - 305 edges
8. `RoomStatusEnum` - 252 edges
9. `ReservationError` - 196 edges
10. `ReservationSourceEnum` - 195 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati` --uses--> `HotelConfiguration`  [INFERRED]
  tests/perf/explain_probe.py → app/models/hotel_config.py
- `Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py
- `Return ``dsn`` only when provider evidence proves a disposable QA target.      E` --uses--> `QABootstrapError`  [INFERRED]
  tests/postgres_test_safety.py → scripts/bootstrap_cloud_qa.py
- `FastAPI client backed by an isolated SQLite database.` --uses--> `Base`  [INFERRED]
  tests/test_demo_mode.py → app/database.py

## Communities

### Community 213 - "Community 213"
Cohesion: 0.53
Nodes (5): get_url(), run_migrations_offline(), _ensure_wide_version_table(), run_migrations_online(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (62): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c, master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a, master admin system owner mail and stripe settings  Revision ID: 20260421_master, _analytics_enum(), _reservation_status_enum_old(), _reservation_status_enum_new(), upgrade(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260 (+54 more)

### Community 42 - "Community 42"
Cohesion: 0.06
Nodes (24): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2, add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio, add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D, _has_column(), upgrade(), downgrade(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, PaymentLinkTestCreate (+16 more)

### Community 234 - "Community 234"
Cohesion: 0.60
Nodes (4): _fk_names(), upgrade(), downgrade(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (40): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em, reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif, ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026, ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026, ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d, baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7, chat_completions(), _extract_latest_user_message() (+32 more)

### Community 49 - "Community 49"
Cohesion: 0.07
Nodes (12): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard, add trial and comped fields to subscriptions  Revision ID: 20260419_subscription, _resolve_jurisdiction_code(), _register_owner(), _auth_headers(), _complete_onboarding(), _configure_resend(), test_register_verify_and_reset_use_resend_provider() (+4 more)

### Community 241 - "Community 241"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 242 - "Community 242"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 243 - "Community 243"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 244 - "Community 244"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 223 - "Community 223"
Cohesion: 0.40
Nodes (3): _pg_enum(), upgrade(), vouchers, refund_requests, and pending_operational_actions  Implements the three

### Community 245 - "Community 245"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 246 - "Community 246"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 247 - "Community 247"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 248 - "Community 248"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 249 - "Community 249"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 250 - "Community 250"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 251 - "Community 251"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 252 - "Community 252"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 253 - "Community 253"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 254 - "Community 254"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 255 - "Community 255"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 256 - "Community 256"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 257 - "Community 257"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 258 - "Community 258"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (37): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi, apply_price_period(), generate_confirmation_code(), _invalidate_availability_cache(), _resolve_hotel_id(), _validate_reservation_occupancy(), compute_reservation_pricing(), calculate_reservation_pricing() (+29 more)

### Community 141 - "Community 141"
Cohesion: 0.21
Nodes (7): MercadoPagoAdapter, get_mercadopago_adapter(), MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process an IPN (Instant Payment Notification) from MercadoPago.         Queries

### Community 123 - "Community 123"
Cohesion: 0.18
Nodes (8): PayPalAdapter, get_paypal_adapter(), PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification.

### Community 1 - "Community 1"
Cohesion: 0.07
Nodes (177): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, Pydantic schemas for HotelConfiguration., 01498d0 Harden password reset flow (verified-only, dev code return), 0737a5a feat(frontend): V72 Wave A/B/C — companies, cash, reports, waitlist, laundry, stock, api-keys, permissions, whatsapp, 093f7d3 ui(manager): ocultar config y redirigir al dashboard al cambiar vista, 0a4396e Add multi-hotel isolation tests and bcrypt shim, 0b14a55 Subscription status: seed starter and add safe fallback, 0c9034f Fix clsx reference in app shell (+169 more)

### Community 154 - "Community 154"
Cohesion: 0.29
Nodes (4): SimpleRateLimiter, get_public_api_context(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth.

### Community 100 - "Community 100"
Cohesion: 0.24
Nodes (16): _serialize_policy_version(), _serialize_suggestion(), _serialize_run_details(), get_active_policy(), get_policy_versions(), create_version(), publish_version(), get_policy_suggestions() (+8 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (46): _generate_code(), _mask_email(), _pick_default_hotel_id(), _build_auth_response(), _issue_email_token(), register(), request_verify(), login() (+38 more)

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (52): validate_reset(), Validate reset code without changing password (paso previo en UI)., AcceptPayload, LoginRequest, _assert_assignable_role(), _assert_manageable_membership(), _membership_user_info(), list_users() (+44 more)

### Community 44 - "Community 44"
Cohesion: 0.10
Nodes (29): RoomBlockCreate, RoomBlockRead, _validate_block_dates(), _exclusive_end(), _inclusive_end(), _existing_user_id(), _read_block(), create_room_block() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (93): BaseModel, CheckInRequest, MasterAdminLoginRequest, MasterAdminUserPayload, MasterAdminLoginResponse, MasterAdminSessionResponse, BillingPolicyUpdateRequest, BillingPolicyPayload (+85 more)

### Community 116 - "Community 116"
Cohesion: 0.22
Nodes (13): _require_demo_mode(), _booking_to_read(), _project_booking_graph(), availability(), price_quote(), list_bookings(), create_booking(), get_booking() (+5 more)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (217): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail). (+209 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (10): _is_demo_mode_enabled(), _require_demo_mode(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., Check whether demo-only utilities should be exposed., 1f352e4 feat(reports): SLICE-11 operational reports + alerts, 283135b feat(ops): SLICE-13 laundry + stock foundations, 6f4beb1 feat(v72): Wave 3 — public API/keys + allocation V72 rules, 6f60c12 feat(security): SLICE-01 configurable permission matrix + role boundaries (+2 more)

### Community 11 - "Community 11"
Cohesion: 0.05
Nodes (58): FastAPI routes for Check-in / Check-out., HotelConfiguration, Configuration table scoped by hotel (id == hotel_id)., CheckInError, validate_guest_for_checkin(), perform_checkin(), perform_checkout(), HotelOutboundEmailError (+50 more)

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (22): FastAPI routes for the commercial configuration domain., ValueError, CommercialConfigError, create_sellable_product(), update_sellable_product(), create_rate_plan(), update_rate_plan(), create_tax_policy() (+14 more)

### Community 51 - "Community 51"
Cohesion: 0.10
Nodes (28): Company, CompanyPayload, CompanyDocumentType, CompanyDocumentStatus, CompanyDocument, CompanyDocumentPayload, listCompanies(), createCompany() (+20 more)

### Community 187 - "Community 187"
Cohesion: 0.32
Nodes (3): _get_document_or_404(), get_company_document(), delete_company_document()

### Community 130 - "Community 130"
Cohesion: 0.19
Nodes (9): email_status(), FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., HotelConfig, HotelConfigUpdate, getHotelConfig(), updateHotelConfig(), hotelConfigKey() (+1 more)

### Community 88 - "Community 88"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, _validate_payload(), upsert_connection(), Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection. (+4 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (83): DailyRateOut, Config, DailyRateFallbackOut, DailyRateIn, BulkRateIn, BulkFieldRateIn, BulkRateOut, PricePeriodIn (+75 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (85): _require_demo_mode(), seed_demo(), reset_demo(), Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Base (+77 more)

### Community 131 - "Community 131"
Cohesion: 0.19
Nodes (8): _retired(), send_verification(), send_reset(), verify_code(), Legacy public email endpoints.  The system transactional mail now lives exclusiv, EmailSendResponse, EmailVerifyResponse, SmtpStatus

### Community 132 - "Community 132"
Cohesion: 0.24
Nodes (9): FxRateItem, FxRateUsdOficial, FxSnapshotRead, FxSnapshotCreateResponse, get_all_rates(), get_usd_oficial_rate(), get_single_rate(), create_fx_snapshot() (+1 more)

### Community 96 - "Community 96"
Cohesion: 0.20
Nodes (11): get_chat_history(), get_chat_insights(), archive_chat_session(), get_chat_session(), send_chat_message(), _serialize_session_summary(), _serialize_message(), _serialize_session_envelope() (+3 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (37): _enum_value(), _build_guest_ledger_csv(), export_guest_ledger(), add_companions(), Guest, GuestTagType, GuestTag, GuestTagPayload (+29 more)

### Community 105 - "Community 105"
Cohesion: 0.32
Nodes (14): FastAPI routes for Guest management., Add new companions to an existing guest., GuestRatingEnum, GuestTagTypeEnum, Guest and GuestCompanion models. Exhaustive fields for check-in panel: identity, GuestTagCreate, GuestTagRead, GuestRatingUpdate (+6 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (38): _postgres_healthcheck(), _redis_healthcheck(), datastores_healthcheck(), Settings, BaseSettings, get_settings(), _normalized_env_value(), _has_value() (+30 more)

### Community 84 - "Community 84"
Cohesion: 0.13
Nodes (15): Staff management endpoints for hotel public API keys., HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia, Per-hotel API credential. `key_hash` stores a hashed version of the secret;, HotelAPIKeyError, _hash_secret(), _generate_secret(), issue_key() (+7 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (76): _ensure_enabled(), _connection_error_message(), _origin_for_popup(), _oauth_state_token(), _oauth_callback_page(), _find_integration(), _store_oauth_code(), get_status() (+68 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (39): get_engine(), _render_server_default(), _column_fill_value(), _backfill_not_null_nulls(), _sync_missing_columns(), init_db(), get_session_factory(), get_db() (+31 more)

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (26): LaundryItemCreate, LaundryItemRead, LaundryBatchCreate, LaundryBatchRead, LaundryStatusUpdate, FastAPI routes for laundry operations., LaundryError, create_batch() (+18 more)

### Community 101 - "Community 101"
Cohesion: 0.21
Nodes (15): MovementEventRead, MovementGroupRead, _enum_value(), _event_to_read(), _group_to_read(), _not_found_or_bad_request(), list_movement_groups(), read_movement_group() (+7 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (29): FastAPI routes for the onboarding flow used by smoke tests., OnboardingProviderSetup, OnboardingStatus, OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, CategoryPayload, RoomPayload (+21 more)

### Community 155 - "Community 155"
Cohesion: 0.27
Nodes (8): _handle_ota_webhook(), booking_webhook(), expedia_webhook(), despegar_webhook(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar.

### Community 200 - "Community 200"
Cohesion: 0.33
Nodes (2): _mercadopago_webhook_impl(), mercadopago_payment_link_webhook()

### Community 167 - "Community 167"
Cohesion: 0.28
Nodes (6): PaymentSurchargeRead, PaymentSurchargeCreate, PaymentSurchargeUpdate, _get_surcharge_or_404(), update_payment_surcharge(), deactivate_payment_surcharge()

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (76): FastAPI routes for Payments., _is_manager_context(), _trigger_reoptimization_bg(), _project_reservation_graph(), create_new_reservation(), create_or_update_manual_ota(), list_reservations(), get_reservation() (+68 more)

### Community 92 - "Community 92"
Cohesion: 0.14
Nodes (15): PermissionOverrideRequest, FastAPI routes for hotel permission matrix management., PermissionRole, PermissionCell, PermissionMatrix, PermissionMatrixResponse, PermissionOverridePayload, PermissionOverrideResponse (+7 more)

### Community 156 - "Community 156"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), _serialize_reservation_status(), public_reservation_status_by_code(), public_reservation_status()

### Community 85 - "Community 85"
Cohesion: 0.15
Nodes (19): RateCalendarChannelRestrictions, RateCalendarMeta, GetRateCalendarDailyParams, getRateCalendarDaily(), DailyRatePrices, DailyRateOut, getCategoryDailyRates(), BulkRateResult (+11 more)

### Community 236 - "Community 236"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 64 - "Community 64"
Cohesion: 0.10
Nodes (22): daily_report(), occupancy_report(), revenue_report(), OperationalReservationSummary, OperationalReservationGroup, AvailableWithReviewItem, ActiveRoomBlockItem, CashSessionStatusRead (+14 more)

### Community 58 - "Community 58"
Cohesion: 0.25
Nodes (31): _to_read(), register_settlement(), cancel_reservation(), release_no_guarantee_reservation(), mark_no_show(), modify_reservation(), extend_stay(), FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend (+23 more)

### Community 10 - "Community 10"
Cohesion: 0.04
Nodes (59): _serialize_reallocation_result(), _attach_current_rate(), list_categories(), get_category(), room_availability(), update_room(), update_room_status(), update_room_category() (+51 more)

### Community 93 - "Community 93"
Cohesion: 0.11
Nodes (5): DecimalValue, StockItem, StockLocation, StockMovement, CurrentStock

### Community 168 - "Community 168"
Cohesion: 0.22
Nodes (9): StockItemCreate, StockItemUpdate, StockItemRead, StockLocationCreate, StockLocationRead, StockMovementRead, FastAPI routes for stock and inventory operations., StockError (+1 more)

### Community 107 - "Community 107"
Cohesion: 0.13
Nodes (14): StockMovementCreate, StockMovementType, listStockItems(), listLowStockItems(), createStockItem(), listStockLocations(), createStockLocation(), createStockMovement() (+6 more)

### Community 57 - "Community 57"
Cohesion: 0.10
Nodes (26): _remaining_trial_days(), _serialize_status_payload(), subscription_status(), change_plan(), start_subscription_trial(), admin_comped_override(), Subscription status and entitlements endpoints., SubscriptionPlan (+18 more)

### Community 72 - "Community 72"
Cohesion: 0.10
Nodes (17): API routes for reservation waitlist operations., listGuests(), Reservation, listRooms(), WaitlistStatus, WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload (+9 more)

### Community 108 - "Community 108"
Cohesion: 0.18
Nodes (8): Public WhatsApp bot hooks authenticated only by hotel API key., WhatsAppBookingError, availability_lookup(), price_quote(), options_with_prices(), create_reservation(), generate_payment_link(), handle_payment_confirmation()

### Community 261 - "Community 261"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 133 - "Community 133"
Cohesion: 0.22
Nodes (8): _get_model_for_table(), _first_bound_value(), _extract_entity_arg(), _extract_db(), _extract_actor_user_id(), _extract_record_id(), _load_entity(), audited_change()

### Community 262 - "Community 262"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 41 - "Community 41"
Cohesion: 0.08
Nodes (28): Master admin panel backend package., Email provider abstraction for platform transactional mail., ApiError, RequestOptions, readCookie(), setMasterAdminCsrfToken(), clearMasterAdminCsrfToken(), safeJson() (+20 more)

### Community 169 - "Community 169"
Cohesion: 0.44
Nodes (8): BillingDecision, _utcnow(), _policy_table(), _parse_hotel_ids(), _parse_user_ids(), get_policy_payload(), update_policy(), evaluate_hotel_write_access()

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (28): MasterEmailConnectionError, _dev_outbox_path(), _record_dev_email(), SystemEmailStatus, _normalize_account_email(), _sender_parts(), _build_unavailable_message(), _current_status() (+20 more)

### Community 143 - "Community 143"
Cohesion: 0.30
Nodes (11): RuntimeError, E2ESafetyError, prepare_e2e_environment(), _credentials(), run_migrations(), upsert_seed_data(), main(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet (+3 more)

### Community 37 - "Community 37"
Cohesion: 0.07
Nodes (37): MasterAdminSession, Base, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterBillingPolicy, MasterSystemEmailConnection, MasterStripeSettings, MasterStripeWebhookEvent (+29 more)

### Community 94 - "Community 94"
Cohesion: 0.12
Nodes (4): _serialize_user(), login(), me(), dashboard_summary()

### Community 70 - "Community 70"
Cohesion: 0.18
Nodes (25): _now(), _as_aware(), _hash_value(), _normalize_identifier(), _normalize_pin(), _bootstrap_master_credentials_match(), _pin_matches(), _session_cookie_secure() (+17 more)

### Community 147 - "Community 147"
Cohesion: 0.42
Nodes (10): _get_settings_row(), _stripe_secret(), _webhook_secret(), _validate_stripe_secret(), get_stripe_status(), save_stripe_settings(), clear_stripe_settings(), stripe_secret_configured() (+2 more)

### Community 224 - "Community 224"
Cohesion: 0.40
Nodes (2): SubscriptionEnforcementMiddleware, Middleware to block mutating requests when subscription enforcement is enabled.

### Community 109 - "Community 109"
Cohesion: 0.24
Nodes (13): AIAssistantSession, AIAssistantMessage, AIAssistantActionRun, AIAssistantInsight, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., GemmaIntent, classify_gemma_intent() (+5 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (41): AllocationRunStatusEnum, AllocationAssignmentStatusEnum, LLMPolicySuggestionStatusEnum, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationAssignment, AllocationExplanation (+33 more)

### Community 23 - "Community 23"
Cohesion: 0.15
Nodes (45): str, AnalyticsExportFormatEnum, AnalyticsCurrencyDisplayEnum, AnalyticsExportStatusEnum, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsExportJob, AnalyticsAIUsageMonthly (+37 more)

### Community 39 - "Community 39"
Cohesion: 0.16
Nodes (37): ReservationAllocationLock, Company, RoomMoveTypeEnum, RoomMovementGroup, RoomMoveEvent, Operational reservation models for adjustments, room moves and audit history., Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).     Suppo, AllocationError (+29 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (118): CashSessionStatusEnum, CashMovementTypeEnum, CashSession, CashMovement, CashCloseReport, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca, Single cash-register shift. Only one OPEN session per hotel at a time     (enfor, Individual money movement within an open cash session.     Linked optionally to (+110 more)

### Community 90 - "Community 90"
Cohesion: 0.18
Nodes (14): CompanyDocumentTypeEnum, CompanyDocumentStatusEnum, CompanyDocument, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentStatusUpdate, CompanyDocumentRead (+6 more)

### Community 263 - "Community 263"
Cohesion: 1.00
Nodes (1): V72 §8.5 — Per-day pricing models.  DailyRate: explicit price for a (hotel, cate

### Community 29 - "Community 29"
Cohesion: 0.10
Nodes (46): DocumentTypeEnum, GuestCompanion, RateLimitEvent, GuestProfile, GuestProfileError, get_guest_profile(), _enum_value(), validate_primary_guest_record() (+38 more)

### Community 26 - "Community 26"
Cohesion: 0.10
Nodes (41): APIKeyPurposeEnum, HotelAPIKeyIssue, HotelAPIKeyRead, HotelAPIKeyIssued, PublicAvailabilityResponse, PublicCategoryRead, PublicRateQuote, PublicReservationCreate (+33 more)

### Community 27 - "Community 27"
Cohesion: 0.07
Nodes (38): IntegrationCatalog, IntegrationConnection, IntegrationEvent, PaymentLinkTestError, _validate_email(), _mercadopago_access_token(), _friendly_mercadopago_error(), _status_from_payment() (+30 more)

### Community 110 - "Community 110"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 12 - "Community 12"
Cohesion: 0.07
Nodes (60): ReservationAdjustmentKindEnum, ReservationAdjustmentStatusEnum, BillingAdjustmentTypeEnum, ReservationAdjustment, BillingAdjustment, Exception, PaymentLinkError, PaymentError (+52 more)

### Community 59 - "Community 59"
Cohesion: 0.32
Nodes (29): OTASyncStatusEnum, OTAReservationMapping, OTAWebhookCredential, OTA (Online Travel Agency) reservation mapping. Tracks the link between external, Maps an external OTA reservation to an internal reservation.     Stores the raw, Per-hotel OTA webhook credential. The secret is stored as a hash so the     raw, OTAReservationLifecycleEnum, OTAProvider (+21 more)

### Community 30 - "Community 30"
Cohesion: 0.07
Nodes (15): OTASyncJob, OTASyncEvent, Foundational OTA adapter interfaces and orchestration services., OTAAdapterContext, OTAOperationResult, NormalizedOTAReservation, OTAProviderAdapter, Common contracts for OTA provider adapters.  The goal is to keep Booking, Expedi (+7 more)

### Community 259 - "Community 259"
Cohesion: 0.67
Nodes (1): Payment surcharge model - v72 section 12.3.  Defines per-payment-method surcharg

### Community 124 - "Community 124"
Cohesion: 0.29
Nodes (13): Permission, RolePermissionDefault, HotelPermissionOverride, Configurable permission matrix models., seed_default_permissions(), resolve(), set_override(), get_matrix() (+5 more)

### Community 62 - "Community 62"
Cohesion: 0.17
Nodes (28): Subscription, SubscriptionEvent, Lightweight subscription tracking for enforcement and auditing (v2 tables)., _now(), _as_utc(), _plan_defaults(), plan_catalog(), _is_enforcement_enabled() (+20 more)

### Community 78 - "Community 78"
Cohesion: 0.12
Nodes (23): ProductRoomCompatibilityWrite, ProductRoomCompatibilityRead, SellableProductBase, SellableProductCreate, SellableProductUpdate, SellableProductRead, RatePlanPriceWrite, RatePlanPriceRead (+15 more)

### Community 225 - "Community 225"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 170 - "Community 170"
Cohesion: 0.33
Nodes (8): GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestBase, GuestCreate, GuestUpdate, GuestRead, Pydantic schemas for Guest and companions.

### Community 91 - "Community 91"
Cohesion: 0.10
Nodes (14): OwnerPayload, HotelIdentityPayload, DepositPolicyPayload, ProviderSetupPayload, PaymentMethodsPayload, OTAChannelsPayload, SubscriptionChoicePayload, CategoriesPayload (+6 more)

### Community 201 - "Community 201"
Cohesion: 0.29
Nodes (6): WaitlistEntryCreate, WaitlistEntryUpdate, WaitlistEntryRead, WaitlistPromoteRequest, WaitlistPromoteResponse, Schemas for hotel-scoped waitlist entries.

### Community 48 - "Community 48"
Cohesion: 0.09
Nodes (21): AnalyticsAIProviderConfig, AnalyticsAIProviderStatus, AnalyticsAIResult, AnalyticsAIProviderError, AnalyticsAIProvider, Protocol, DisabledAnalyticsAIProvider, _OpenAICompatibleProvider (+13 more)

### Community 74 - "Community 74"
Cohesion: 0.17
Nodes (24): reservation_status_to_outcome(), infer_guest_segment_from_company(), resolve_guest_segment(), normalize_channel_code(), backfill_channel_code(), split_amount_evenly(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact() (+16 more)

### Community 73 - "Community 73"
Cohesion: 0.15
Nodes (22): _now(), _ensure_utc(), _normalize_export_payload(), _format_scalar(), _flatten_payload_rows(), _rows_to_csv_bytes(), _png_from_rows(), _sheet_xml_from_table() (+14 more)

### Community 81 - "Community 81"
Cohesion: 0.17
Nodes (20): detect_no_shows(), refresh_fact_reservation_daily(), refresh_fact_room_occupancy_daily(), calculate_pickup_30d(), _reservation_row_kind(), _resolve_no_show_policy(), _reservation_monetary_totals(), _reservation_dates_in_window() (+12 more)

### Community 134 - "Community 134"
Cohesion: 0.32
Nodes (12): _now(), _runtime_status(), get_analytics_ai_status(), _request_payload(), _assert_analytics_chat_domain(), _chat_context(), _fallback_insight_summary(), _build_insight() (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.11
Nodes (51): _now(), _hotel_local_now(), _ensure_utc(), _money(), _money_str(), _utc_date_range(), _analytics_window(), _comparison_read() (+43 more)

### Community 202 - "Community 202"
Cohesion: 0.43
Nodes (4): payload_json(), create_audit_log(), queue_audit_log(), safe_create_audit_log()

### Community 157 - "Community 157"
Cohesion: 0.38
Nodes (9): _is_cache_fresh(), _get_async(), fetch_all_rates(), fetch_rate(), get_usd_official_rate(), get_usd_rate_for_type(), get_all_rates_snapshot(), get_cached_rates() (+1 more)

### Community 135 - "Community 135"
Cohesion: 0.45
Nodes (11): GemmaActionRunError, get_action_run(), approve_action_run(), reject_action_run(), review_action_run_draft(), apply_action_run_draft(), _load_json_dict(), _coerce_numeric_dict() (+3 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (8): GemmaOrchestrator, _build_session_title(), _safe_text(), _coerce_string_list(), _coerce_float(), _coerce_action_list(), _resolve_existing_user_id(), _derive_models_endpoint()

### Community 50 - "Community 50"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaServiceError, GemmaService, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 215 - "Community 215"
Cohesion: 0.60
Nodes (5): _run_write(), _enum_value(), project_reservation_assignment(), project_room_movement(), project_company_link()

### Community 136 - "Community 136"
Cohesion: 0.32
Nodes (11): _now(), _audit(), _get_guest(), _active_tag_filter(), find_or_create_guest(), list_active_tags(), _serialize_stay(), quick_profile() (+3 more)

### Community 216 - "Community 216"
Cohesion: 0.60
Nodes (5): HotelOutboundIdentity, HotelOutboundSendResult, ensure_hotel_gmail_ready(), _build_message(), send_hotel_email()

### Community 71 - "Community 71"
Cohesion: 0.17
Nodes (22): _fernet(), encrypt_payload(), decrypt_payload(), seed_catalog(), list_catalog_with_status(), get_provider_connection_payload(), get_connection_payload(), derive_expires_at() (+14 more)

### Community 226 - "Community 226"
Cohesion: 0.50
Nodes (4): JurisdictionProfile, get_profile(), compute_missing_guest_fields(), Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 79 - "Community 79"
Cohesion: 0.28
Nodes (23): OnboardingError, resolve_hotel_id(), get_or_create_state(), _get_or_create_config(), _merge_extra_policies(), _serialize_categories(), _serialize_rooms(), _summarize_provider_payload() (+15 more)

### Community 111 - "Community 111"
Cohesion: 0.23
Nodes (13): _guest_name(), _reservation_summary(), _group(), _active_room_blocks(), _available_with_review(), _cash_session(), _alerts(), daily_report() (+5 more)

### Community 121 - "Community 121"
Cohesion: 0.16
Nodes (1): BookingAdapter

### Community 115 - "Community 115"
Cohesion: 0.15
Nodes (2): OTAProviderAdapter, ExpediaAdapter

### Community 122 - "Community 122"
Cohesion: 0.16
Nodes (1): DespegarAdapter

### Community 137 - "Community 137"
Cohesion: 0.37
Nodes (12): create_or_update_manual_ota_reservation(), release_no_guarantee(), _attempt_waitlist_promotion_after_release(), _update_existing_manual_ota_reservation(), _source_for_channel(), _normalize_required(), _clean(), _apply_manual_amounts() (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (54): ManifestContinuityError, _timestamp(), _provider_subject(), verify_manifest_continuity(), _load_manifest(), main(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots. (+46 more)

### Community 63 - "Community 63"
Cohesion: 0.15
Nodes (2): _hotel_default_currency(), OTAIntegrationService

### Community 98 - "Community 98"
Cohesion: 0.18
Nodes (17): _default_email_delivery(), _money(), _signing_secret(), _signature(), sign_external_reference(), resolve_signed_external_reference(), _get_reservation_for_hotel(), _unique_link_code() (+9 more)

### Community 117 - "Community 117"
Cohesion: 0.26
Nodes (14): get_hotel_config(), validate_payment_method_enabled(), _resolve_reservation_hotel(), _resolve_payment_currency(), _payment_method_value(), calculate_payment_surcharge(), calculate_base_amount_before_surcharge(), process_payment() (+6 more)

### Community 149 - "Community 149"
Cohesion: 0.38
Nodes (10): _parse_mercadopago_signature_header(), validate_mercadopago_webhook_signature(), _payload_value(), _normalize_status(), _completed_at(), _find_existing_event(), _insert_event(), _transaction_exists() (+2 more)

### Community 150 - "Community 150"
Cohesion: 0.42
Nodes (10): PricingPolicyError, quote_rate_plan_stay(), _select_rate_plan_price(), _select_tax_policy(), _apply_tax_policy(), _calculate_rule_amount(), _resolve_commission_amount(), _convert_amount() (+2 more)

### Community 171 - "Community 171"
Cohesion: 0.50
Nodes (8): get_daily_calendar(), _build_direct_prices(), _build_ota_prices(), _select_rate_plan_price(), _select_ota_price_rule(), _aggregate_inventory_rules(), _default_restrictions(), _build_missing_channel()

### Community 103 - "Community 103"
Cohesion: 0.27
Nodes (16): _settings(), _cache_enabled(), _get_redis_client(), _load_json(), _store_json(), _get_cached_or_compute(), _date_token(), _availability_key() (+8 more)

### Community 118 - "Community 118"
Cohesion: 0.28
Nodes (14): get_reservation_operations_summary(), list_pending_reservation_actions(), resolve_external_channel_follow_up(), clear_reservation_manual_review(), _build_pending_actions(), _decorate_action(), _dedupe_candidates(), _get_reservation_or_error() (+6 more)

### Community 151 - "Community 151"
Cohesion: 0.25
Nodes (8): _About, _jwt_secret(), create_access_token(), decode_access_token(), create_signed_token(), decode_signed_token(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 112 - "Community 112"
Cohesion: 0.17
Nodes (9): update_stock_item(), delete_stock_item(), register_movement(), current_stock(), low_stock_items(), get_stock_item(), get_location(), _get_item() (+1 more)

### Community 104 - "Community 104"
Cohesion: 0.29
Nodes (16): is_enforcement_enabled(), _infer_type(), _serialize_value(), _parse_value(), _upsert_plan_entitlement(), ensure_entitlements_seeded(), ensure_subscription(), _collect_plan_entitlements() (+8 more)

### Community 152 - "Community 152"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _to_datetime(), _enum_value(), _json_payload(), _room_state_event_row(), _daily_rate_change_row(), _schema_statements(), ensure_cassandra_schema() (+2 more)

### Community 190 - "Community 190"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 158 - "Community 158"
Cohesion: 0.44
Nodes (8): WaitlistError, _get_waitlist_entry(), add_to_waitlist(), update_waitlist_entry(), promote_from_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), request_payment_link_for_waitlist()

### Community 159 - "Community 159"
Cohesion: 0.24
Nodes (9): push_availability_update(), _push_to_booking(), _push_to_expedia(), sync_all_availability(), Celery tasks for OTA synchronization. Sends inventory/availability updates to Bo, Push availability updates to all enabled OTAs for a given category and date rang, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Expedia EQC API.          In production, this would (+1 more)

### Community 217 - "Community 217"
Cohesion: 0.60
Nodes (5): _active_hotel_ids(), _send_report_for_hotel(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports()

### Community 214 - "Community 214"
Cohesion: 0.40
Nodes (3): hotelId, authHeaders(), ensureOnboarding()

### Community 97 - "Community 97"
Cohesion: 0.11
Nodes (9): credentials, PAGES, frontendDir, repoRoot, localPython, e2eDbPath, Seed and serve the E2E backend on 127.0.0.1:8040.  This wrapper avoids shell-spe, Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati (+1 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (25): navItems, MasterAdminRoot(), MasterAdminProtectedShell(), MasterAdminAuditPage(), MasterAdminDashboardPage(), MasterAdminLoginPage(), MasterAdminSessionProvider(), APP_HOST (+17 more)

### Community 61 - "Community 61"
Cohesion: 0.12
Nodes (27): CashSessionStatus, CashMovementType, CashSession, CashMovement, CashCloseReport, CashSessionSummary, CashSessionOpenPayload, CashMovementPayload (+19 more)

### Community 55 - "Community 55"
Cohesion: 0.10
Nodes (30): GemmaChatRole, GemmaChatSession, GemmaChatMessage, GemmaChatEnvelope, GemmaChatMessagePayload, GemmaApproveActionPayload, GemmaApproveActionResponse, GemmaRejectActionPayload (+22 more)

### Community 69 - "Community 69"
Cohesion: 0.09
Nodes (18): RateCalendarChannelPrice, RateCalendarChannelDay, RateCalendarDay, InfoTipProps, PopoverPosition, InfoTip(), RateCalendarGridProps, ChannelSummary (+10 more)

### Community 106 - "Community 106"
Cohesion: 0.13
Nodes (11): RateCalendarResponse, DailyRateRangeRow, RateEditorGridProps, PRICE_ROWS, WEEKDAY, MONTH, INTEGER_LABEL, SOURCE_LABEL (+3 more)

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (14): PriceField, useRateCalendar(), useCategoryDailyRates(), SingleRateInput, useUpsertDailyRate(), useBulkUpsertRates(), useBulkUpdateRateField(), RANGE_LABEL (+6 more)

### Community 46 - "Community 46"
Cohesion: 0.15
Nodes (28): StructuredData, SeoProps, Seo(), navItems, MarketingShellProps, MarketingShell(), PublicButtonLinkProps, isExternal() (+20 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (34): StatCardProps, toneClasses, StatCard(), AnalyticsEnvelope, AnalyticsStarterSummary, Company, RoomStateEvent, RoomStateEventCreate (+26 more)

### Community 102 - "Community 102"
Cohesion: 0.17
Nodes (15): trimTrailingSlash(), ensureLeadingSlash(), normalizeUrl(), PUBLIC_SITE_URL, PUBLIC_APP_URL, APP_URL_HOSTNAME, SITE_URL_HOSTNAME, resolveSalesContactUrl() (+7 more)

### Community 188 - "Community 188"
Cohesion: 0.25
Nodes (7): DashboardStats, Reservation, Room, Activity, mockReservations, mockRooms, mockActivities

### Community 35 - "Community 35"
Cohesion: 0.06
Nodes (32): inline_list(), graphify_command_error(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., graphify_state(), main(), run() (+24 more)

### Community 22 - "Community 22"
Cohesion: 0.08
Nodes (50): fail(), mapping(), positive_integer(), utc_timestamp(), preview_origin(), nested_value(), load_json_object(), validate_evidence_bundle() (+42 more)

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (26): ReleaseEvidenceError, git(), resolve_commit(), changed_paths(), is_release_relevant_path(), validate_explicit_summary_path(), select_summary(), main() (+18 more)

### Community 142 - "Community 142"
Cohesion: 0.36
Nodes (11): QALocalEnvError, _validate_domain(), _validate_https_url(), _new_run_id(), _strong_password(), build_values(), _render(), _assert_replaceable() (+3 more)

### Community 19 - "Community 19"
Cohesion: 0.08
Nodes (46): LeaseError, _canonical_json(), _service_id(), _target_sha(), _target_branch(), _repository(), _service_repository(), _lease_id() (+38 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (42): ProvisionError, _canonical_json(), _decode_token_payload(), _object(), _string(), _canonical_hostname(), _https_origin(), _github_repository() (+34 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (26): BootstrapConfigurationError, bootstrap_configuration_fingerprint(), Hash the exact provider-observed values without exposing them individually., JsonGetter, ReadOnlyJsonApi, _decode_lease_entropy(), _verify_dedicated_baseline_lease(), _verify_qa_external_effects_disabled() (+18 more)

### Community 185 - "Community 185"
Cohesion: 0.50
Nodes (7): _roles(), _instructions(), _claude(), _toml_string(), _codex(), _expected(), main()

### Community 235 - "Community 235"
Cohesion: 0.83
Nodes (3): _skill_dirs(), _compare_dirs(), main()

### Community 20 - "Community 20"
Cohesion: 0.09
Nodes (36): TrustedGateError, full_sha(), positive_integer(), GitHubClient, changed_blob_paths(), require_base_public_key(), require_pull_identity(), require_evidence_ancestry() (+28 more)

### Community 129 - "Community 129"
Cohesion: 0.35
Nodes (12): _mapping(), _non_empty(), _canonical_host(), _https_preview_url(), _timestamp(), _validate_baseline_lease_id(), _validate_observation_time(), validate_manifest() (+4 more)

### Community 99 - "Community 99"
Cohesion: 0.24
Nodes (13): BundleVerificationError, _NoRedirect, _ScriptParser, HTMLParser, _origin(), discover_script_urls(), verify_asset_payloads(), _asset_entries() (+5 more)

### Community 53 - "Community 53"
Cohesion: 0.19
Nodes (33): VerificationError, VerificationConfig, ProviderClients, _dict(), _list(), _string(), _validate_config(), _validate_baseline_lease_id() (+25 more)

### Community 33 - "Community 33"
Cohesion: 0.11
Nodes (45): QABootstrapError, Persona, QABootstrapConfig, ProviderEvidence, _required(), _flag(), _required_port(), _validate_email() (+37 more)

### Community 189 - "Community 189"
Cohesion: 0.25
Nodes (8): QABootstrapResult, _qa_marker(), upsert_qa_data(), Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users.

### Community 148 - "Community 148"
Cohesion: 0.35
Nodes (10): derive_test_dsn(), run_alembic_upgrade(), cleanup(), seed(), percentile(), measure(), explain(), print_results() (+2 more)

### Community 25 - "Community 25"
Cohesion: 0.07
Nodes (49): _enabled(), _canonical_identity(), _identity_contains(), _load_local_evidence(), _verify_remote_provider_evidence(), validate_postgres_test_target(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+41 more)

### Community 203 - "Community 203"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_onboarding_flow_complete(), test_multihotel_isolation_owner_state(), test_permissions_headers_applied_to_config()

### Community 113 - "Community 113"
Cohesion: 0.17
Nodes (6): write_complete_qa_evidence(), run_qa_evidence_check(), test_qa_evidence_schema_accepts_full_catalog(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_rejects_malformed_result_without_traceback(), Regression contracts for the repository's agent-operations setup.

### Community 80 - "Community 80"
Cohesion: 0.18
Nodes (5): make_rooms(), make_res(), TestOverlap, TestGreedyAllocation, TestCPSATAllocation

### Community 160 - "Community 160"
Cohesion: 0.60
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only(), test_allocation_policy_questionnaire_endpoint_creates_draft_suggestion(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion(), test_allocation_policy_api_can_review_and_apply_suggestion() (+1 more)

### Community 204 - "Community 204"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback()

### Community 191 - "Community 191"
Cohesion: 0.46
Nodes (7): _slot(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations(), test_allocation_run_creates_movement_group_and_events(), _seed_hotel_rooms_guests(), _reservation()

### Community 153 - "Community 153"
Cohesion: 0.33
Nodes (9): _seed_analytics_data(), test_starter_summary_and_plan_gate(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads(), test_analytics_dashboard_and_ai_chat_without_provider() (+1 more)

### Community 138 - "Community 138"
Cohesion: 0.18
Nodes (4): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_releases_ota_reservation(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role()

### Community 95 - "Community 95"
Cohesion: 0.35
Nodes (18): _hotel(), _user(), _context(), _category(), _room(), _guest(), _reservation(), _audit_for() (+10 more)

### Community 192 - "Community 192"
Cohesion: 0.57
Nodes (7): _hotel(), _user(), _guest(), test_modifying_guest_creates_audit_log_with_before_after(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_uses_correct_hotel_id_isolation(), test_audit_log_has_correct_action_enum_value()

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _env(), _provider_manifest(), _cloud_env(), test_raw_base64_ed25519_keys_issue_and_verify(), test_load_config_rejects_production_even_when_isolated_flag_is_set(), test_load_config_rejects_unmarked_database(), test_load_config_rejects_known_live_production_ref_even_with_fake_qa_attestations() (+29 more)

### Community 43 - "Community 43"
Cohesion: 0.06
Nodes (14): test_database_foundation_complete(), _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_voucher_redemption_persists(), test_voucher_remaining_amount_cannot_be_negative(), test_refund_request_gateway_path(), test_refund_request_voucher_path() (+6 more)

### Community 75 - "Community 75"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_pending_payment_marks_cell(), test_ota_with_balance_marks_ota_unpaid(), test_requires_manual_review_marks_available_with_review(), test_fully_paid_direct_marks_nothing(), test_cell_states_isolated_per_hotel(), _ensure_hotel() (+15 more)

### Community 227 - "Community 227"
Cohesion: 0.80
Nodes (4): _reservation(), _link(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 125 - "Community 125"
Cohesion: 0.42
Nodes (13): _hotel(), _user(), _reservation(), _transaction(), test_only_one_open_cash_session_per_hotel_is_allowed(), test_cash_movement_requires_open_session(), test_close_report_expected_balance_from_confirmed_cash(), test_close_with_difference_requires_approval() (+5 more)

### Community 120 - "Community 120"
Cohesion: 0.14
Nodes (4): TestGuestValidation, TestCheckIn, TestCheckOut, Tests for Check-in Service. Validates guest data requirements before allowing ch

### Community 228 - "Community 228"
Cohesion: 0.70
Nodes (4): _override_auth(), _client_with_db(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 119 - "Community 119"
Cohesion: 0.51
Nodes (14): _make_hotel(), _make_guest(), _make_room(), _make_paid_reservation(), test_prohibido_alojar_blocks_checkin(), test_other_tags_do_not_block_checkin(), test_no_prohibido_tag_allows_checkin(), test_prohibido_tag_from_different_hotel_does_not_block() (+6 more)

### Community 172 - "Community 172"
Cohesion: 0.58
Nodes (8): _get_db_override_target(), _override_auth(), _seed_hotel(), _build_client(), _cleanup_client(), test_owner_can_create_and_update_commercial_configuration(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories()

### Community 218 - "Community 218"
Cohesion: 0.47
Nodes (4): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi

### Community 205 - "Community 205"
Cohesion: 0.71
Nodes (6): _override_auth(), _client_with_db(), _seed_reservation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_company_documents_api_cross_hotel_isolation()

### Community 206 - "Community 206"
Cohesion: 0.57
Nodes (6): _company(), _user(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_corporate_reservation_is_allocation_locked()

### Community 193 - "Community 193"
Cohesion: 0.32
Nodes (4): get_db_override_target(), get_auth_context_target(), client_with_db(), ctx()

### Community 77 - "Community 77"
Cohesion: 0.23
Nodes (18): _override_auth(), _build_client(), _cleanup_client(), test_gemma_chat_creates_session_and_persists_messages_with_fallback(), test_gemma_chat_scopes_history_by_user_and_hotel(), test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_persists_and_lists_insights(), test_gemma_chat_returns_controlled_preview_for_policy_change_requests() (+10 more)

### Community 174 - "Community 174"
Cohesion: 0.28
Nodes (3): _read(), test_generates_only_allowed_synthetic_values_with_private_permissions(), test_explicit_rotation_replaces_values_and_preserves_mode()

### Community 126 - "Community 126"
Cohesion: 0.46
Nodes (13): _hotel(), _user(), _guest(), _room(), _reservation(), test_guest_search_matches_document_phone_email_name(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_quick_profile_includes_observations() (+5 more)

### Community 175 - "Community 175"
Cohesion: 0.33
Nodes (6): get_db_override_target(), get_auth_context_target(), client_with_db(), owner_ctx(), test_update_role_requires_owner(), test_co_owner_cannot_grant_privileged_roles()

### Community 238 - "Community 238"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (25): _seed_platform_admin(), _seed_hotel(), _seed_subscription(), _configure_resend(), test_master_login_bootstraps_env_account(), test_master_login_sets_cookie_and_hydrates_me(), test_master_login_cookie_works_on_underscore_alias(), test_master_login_locks_out_after_repeated_failures() (+17 more)

### Community 229 - "Community 229"
Cohesion: 0.60
Nodes (3): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 194 - "Community 194"
Cohesion: 0.46
Nodes (5): _hotel(), _user(), _guest(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), test_audit_projection_document_shape_from_decorator()

### Community 195 - "Community 195"
Cohesion: 0.43
Nodes (7): client_with_db(), get_db_override_target(), create_hotel_with_membership(), test_rooms_list_isolated_by_hotel(), test_reservations_list_isolated_by_hotel(), test_room_cap_enforced(), test_reset_endpoint_allows_testing_env()

### Community 139 - "Community 139"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_membership(), _seed_hotel_payload(), _set_auth_context_override(), test_rooms_and_reservations_are_scoped_to_active_hotel(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 82 - "Community 82"
Cohesion: 0.12
Nodes (14): two_hotels(), _make_guest(), _make_reservation(), test_guest_scoped_to_hotel(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_dedup_same_hotel_raises(), test_reservations_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 176 - "Community 176"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database.

### Community 230 - "Community 230"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 177 - "Community 177"
Cohesion: 0.36
Nodes (7): _register_owner(), _complete_onboarding_setup(), test_each_step_persists(), test_invalid_data_blocks_advancement(), test_complete_nine_step_flow_works(), test_idempotent_step_updates_do_not_duplicate_records(), API coverage for the expanded onboarding wizard.

### Community 178 - "Community 178"
Cohesion: 0.47
Nodes (6): _make_room_set(), _make_guest(), _make_reservation(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped(), test_available_with_review_surfaces_in_report()

### Community 208 - "Community 208"
Cohesion: 0.67
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_modify_updates_existing_reservation_and_guest(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 161 - "Community 161"
Cohesion: 0.47
Nodes (8): _seed_hotel(), _manual_payload(), test_manual_ota_requires_channel_and_external_id(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(), test_release_no_guarantee_promotes_compatible_waitlist_entry(), test_release_no_guarantee_without_waitlist_still_succeeds(), test_manual_ota_cross_hotel_isolation()

### Community 144 - "Community 144"
Cohesion: 0.17
Nodes (4): TestBookingWebhook, TestExpediaWebhook, TestOTARaceCondition, TestAvailabilityUpdate

### Community 162 - "Community 162"
Cohesion: 0.44
Nodes (9): _reservation(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service(), _fake_mp_gateway(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_link_best_effort_when_gateway_fails(), test_deliver_link_email_records_channel(), test_deliver_link_email_best_effort_on_failure() (+1 more)

### Community 231 - "Community 231"
Cohesion: 0.60
Nodes (3): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation()

### Community 196 - "Community 196"
Cohesion: 0.57
Nodes (7): _reservation(), _link(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_process_payment_replays_on_duplicate_idempotency_key(), test_balance_due_uses_transactions_not_payments()

### Community 209 - "Community 209"
Cohesion: 0.48
Nodes (5): _seed_hotel(), test_permission_override_allows_receptionist_guest_edit(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_get_matrix_includes_hotel_overrides()

### Community 210 - "Community 210"
Cohesion: 0.67
Nodes (6): _override_auth(), _client_with_db(), test_permissions_matrix_available_to_authenticated_hotel_member(), test_permission_override_allows_receptionist_guest_edit(), test_permission_denied_is_audited(), test_override_in_hotel_a_does_not_affect_hotel_b()

### Community 76 - "Community 76"
Cohesion: 0.19
Nodes (22): example_manifest(), validate(), test_example_is_sha_task_and_artifact_run_bound(), test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_legacy_boolean_self_attestation_is_rejected(), test_legacy_entrypoint_delegates_to_the_strong_contract(), test_production_urls_are_rejected_everywhere() (+14 more)

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (28): FakeApi, wrapper(), env_page(), fixtures(), set_render_preview_env(), configure_dedicated_baseline(), test_happy_path_compares_production_secrets_without_serializing_values(), test_preview_rejects_external_effects_enabled() (+20 more)

### Community 145 - "Community 145"
Cohesion: 0.47
Nodes (10): _seed_hotel(), _issue_public_key(), _headers(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_revoked_key_is_rejected(), _seed_reservation(), test_public_reservation_status_returns_own_reservation() (+2 more)

### Community 127 - "Community 127"
Cohesion: 0.48
Nodes (12): _override_auth(), _build_client(), _cleanup_client(), _seed_hotel(), test_endpoint_requires_authentication(), test_endpoint_rejects_forbidden_role(), test_unknown_category_returns_404(), test_date_to_before_date_from_returns_422() (+4 more)

### Community 197 - "Community 197"
Cohesion: 0.32
Nodes (4): get_db_override_target(), get_auth_context_target(), client_with_db(), authed_client()

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (8): FakeRedis, BrokenRedis, test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip(), test_operational_invalidation_clears_availability_and_analytics(), test_analytics_home_cache_key_varies_by_filter()

### Community 179 - "Community 179"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 180 - "Community 180"
Cohesion: 0.44
Nodes (7): _make_hotel(), _make_reservation(), test_send_morning_reports_iterates_active_hotels(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_today_triggers_immediate_alert(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_routing_swallows_email_errors()

### Community 163 - "Community 163"
Cohesion: 0.64
Nodes (9): _override_auth(), _build_client(), _cleanup_client(), _seed_operational_state(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservations_list_surfaces_serialization_failures_as_http_500() (+1 more)

### Community 198 - "Community 198"
Cohesion: 0.43
Nodes (7): _res(), test_origin_from_channel(), test_company_id_overrides_channel(), test_company_channel_is_empresa(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception(), v72 §16.2: reportable_origin derivation from channel_code + company_id + source.

### Community 86 - "Community 86"
Cohesion: 0.09
Nodes (3): TestAvailability, TestReservationCreation, TestStateTransitions

### Community 140 - "Community 140"
Cohesion: 0.44
Nodes (12): _hotel(), _category(), _room(), _guest(), _user(), _reservation(), test_active_room_block_excludes_room_from_availability(), test_indefinite_block_excludes_future_dates_until_resolved() (+4 more)

### Community 199 - "Community 199"
Cohesion: 0.46
Nodes (5): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 219 - "Community 219"
Cohesion: 0.73
Nodes (5): _override_auth(), _client_with_db(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation(), _seed_group()

### Community 146 - "Community 146"
Cohesion: 0.32
Nodes (11): PublicRoute, _dependency_call_name(), _dependency_call_qualname(), _walk_dependants(), _route_has_auth_dependency(), _path_is_allowlisted(), _endpoint_source_mentions(), _route_has_webhook_signature_gate() (+3 more)

### Community 211 - "Community 211"
Cohesion: 0.57
Nodes (5): _seed_category(), _delete_audit(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits(), test_price_period_delete_soft_deletes_hides_and_audits()

### Community 232 - "Community 232"
Cohesion: 0.70
Nodes (4): _seed_hotels(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity(), test_low_stock_items_are_hotel_scoped()

### Community 181 - "Community 181"
Cohesion: 0.42
Nodes (6): _ensure_hotel(), _auth_headers(), test_trial_auto_suspends_after_fourteen_days(), test_comped_override_records_audit_event(), test_role_gating_for_trial_and_comped_override(), test_manual_transitions_emit_events()

### Community 182 - "Community 182"
Cohesion: 0.39
Nodes (7): _seed_room(), test_create_room_block_public_api(), test_list_room_blocks_public_api(), test_release_room_block_public_api(), test_receptionist_can_create_but_not_release_block_by_default(), test_hotel_override_removing_create_block_is_respected(), test_room_blocks_public_api_is_hotel_scoped()

### Community 68 - "Community 68"
Cohesion: 0.14
Nodes (7): _make_user(), _make_hotel(), _auth_context(), _open_cash_session(), _add_cash_movement(), _make_reservation(), _make_transaction()

### Community 164 - "Community 164"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_pending_updates_dates_and_price(), test_change_dates_blocked_when_room_conflict(), test_change_dates_blocked_for_past_check_in(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_extend_stay_increases_nights_and_recalculates_price(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 220 - "Community 220"
Cohesion: 0.73
Nodes (5): _create_checked_in_reservation(), _add_billing_charge(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 128 - "Community 128"
Cohesion: 0.47
Nodes (11): _seed_hotel(), _seed_category(), _seed_room(), _seed_guest(), _make_reservation(), test_no_double_booking_same_room_same_dates(), test_auto_assign_no_double_booking(), test_allocation_respects_existing_reservations() (+3 more)

### Community 212 - "Community 212"
Cohesion: 0.62
Nodes (6): _reservation(), _payment(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_no_future_conflict_extends_normally()

### Community 87 - "Community 87"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_blocked_by_prohibido_alojar(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_reservation_mobility_restriction_field(), test_reservation_is_motor_protected_set_on_manual_move(), test_reservation_is_wait_listed_field(), test_extend_stay_basic() (+3 more)

### Community 221 - "Community 221"
Cohesion: 0.53
Nodes (4): _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_update_mobility_restriction_triggers_reoptimization(), test_room_move_requires_reason_code_and_accepts_valid_reason()

### Community 165 - "Community 165"
Cohesion: 0.36
Nodes (8): test_list_movement_groups_with_filters(), test_read_movement_group_detail_includes_movements(), test_revert_movement_group_restores_original_room_and_audits(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_movement_group_hotel_isolation(), test_revert_already_reverted_group_returns_400(), _seed_group()

### Community 166 - "Community 166"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_percentage_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_surcharge_is_scoped_per_hotel(), test_payment_link_requested_amount_includes_surcharge() (+1 more)

### Community 183 - "Community 183"
Cohesion: 0.22
Nodes (2): TestReoptimizationTrigger, TestReoptimizationIntegration

### Community 83 - "Community 83"
Cohesion: 0.13
Nodes (6): _make_reservation(), tiny_hotel(), TestWaitlistModelFields, TestWaitlistListing, TestWaitlistResolveLogic, TestWaitlistIsolation

### Community 240 - "Community 240"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_cross_hotel_isolation()

### Community 222 - "Community 222"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 184 - "Community 184"
Cohesion: 0.56
Nodes (7): _seed_hotel(), _issue_key(), _headers(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link()

## Knowledge Gaps
- **375 isolated node(s):** `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`, `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif` (+370 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 241`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 242`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 243`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 244`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 245`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 246`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 247`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 248`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 249`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 250`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 251`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 252`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 253`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 254`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 255`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 256`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 257`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 258`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 200`** (2 nodes): `_mercadopago_webhook_impl()`, `mercadopago_payment_link_webhook()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 261`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 262`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 224`** (2 nodes): `SubscriptionEnforcementMiddleware`, `Middleware to block mutating requests when subscription enforcement is enabled.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 263`** (1 nodes): `V72 §8.5 — Per-day pricing models.  DailyRate: explicit price for a (hotel, cate`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 259`** (1 nodes): `Payment surcharge model - v72 section 12.3.  Defines per-payment-method surcharg`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (2 nodes): `OTAProviderAdapter`, `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (2 nodes): `_hotel_default_currency()`, `OTAIntegrationService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 179`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 183`** (2 nodes): `TestReoptimizationTrigger`, `TestReoptimizationIntegration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 6` to `Community 213`, `Community 13`, `Community 18`, `Community 37`, `Community 109`, `Community 32`, `Community 39`, `Community 23`, `Community 5`, `Community 2`, `Community 90`, `Community 88`, `Community 263`, `Community 132`, `Community 29`, `Community 0`, `Community 105`, `Community 26`, `Community 84`, `Community 11`, `Community 3`, `Community 17`, `Community 27`, `Community 110`, `Community 12`, `Community 59`, `Community 30`, `Community 259`, `Community 124`, `Community 44`, `Community 62`, `Community 159`, `Community 77`, `Community 176`, `Community 177`?**
  _High betweenness centrality (0.123) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 11` to `Community 130`, `Community 17`, `Community 58`, `Community 0`, `Community 154`, `Community 3`, `Community 6`, `Community 37`, `Community 97`, `Community 23`, `Community 216`, `Community 79`, `Community 59`, `Community 63`, `Community 27`, `Community 12`, `Community 5`, `Community 62`, `Community 159`, `Community 29`, `Community 2`, `Community 77`, `Community 30`, `Community 144`, `Community 183`, `Community 83`?**
  _High betweenness centrality (0.051) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 105`, `Community 58`, `Community 3`, `Community 6`, `Community 37`, `Community 39`, `Community 32`, `Community 23`, `Community 11`, `Community 90`, `Community 29`, `Community 59`, `Community 63`, `Community 12`, `Community 2`, `Community 5`, `Community 44`, `Community 101`, `Community 108`, `Community 120`, `Community 144`, `Community 86`, `Community 183`, `Community 83`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 438 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 438 INFERRED edges - model-reasoned connections that need verification._
- **Are the 428 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 428 INFERRED edges - model-reasoned connections that need verification._
- **Are the 372 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 372 INFERRED edges - model-reasoned connections that need verification._
- **Are the 328 inferred relationships involving `Room` (e.g. with `RoomBlockCreate` and `RoomBlockRead`) actually correct?**
  _`Room` has 328 INFERRED edges - model-reasoned connections that need verification._