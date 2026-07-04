# Graph Report - .  (2026-07-04)

## Corpus Check
- Large corpus: 656 files · ~931,991 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 5448 nodes · 16641 edges · 247 communities detected
- Extraction: 65% EXTRACTED · 35% INFERRED · 0% AMBIGUOUS · INFERRED: 5757 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 5757 · contains: 3560 · calls: 2352 · MODIFIES: 1462 · imports: 696 · rationale_for: 651 · imports_from: 547 · method: 506 · inherits: 500 · ON_BRANCH: 400 · PARENT_OF: 210


## Input Scope
- Requested: auto
- Resolved: committed (source: default-auto)
- Included files: 656 · Candidates: 1611
- Excluded: 0 untracked · 21557 ignored · 6 sensitive · 0 missing committed
- Recommendation: Use --scope all or graphify.yaml inputs.corpus for a knowledge-base folder.

## Graph Freshness
- Built from Git commit: `55b4b0c`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `ReservationStatusEnum` - 391 edges
2. `Reservation` - 386 edges
3. `HotelConfiguration` - 330 edges
4. `Base` - 303 edges
5. `Room` - 294 edges
6. `Guest` - 268 edges
7. `RoomCategory` - 256 edges
8. `RoomStatusEnum` - 214 edges
9. `ReservationError` - 189 edges
10. `TransactionTypeEnum` - 155 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati` --uses--> `HotelConfiguration`  [INFERRED]
  tests/perf/explain_probe.py → app/models/hotel_config.py
- `End-to-end onboarding flow exposed through the FastAPI routers.` --uses--> `Base`  [INFERRED]
  tests/test_onboarding_flow.py → app/database.py
- `API coverage for the expanded onboarding wizard.` --uses--> `Base`  [INFERRED]
  tests/test_onboarding_wizard.py → app/database.py
- `BenchmarkResult` --uses--> `DocumentTypeEnum`  [INFERRED]
  tests/perf/benchmark_pg.py → app/models/guest.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (84): Demo-only utilities: seed sample data and reset the database. Exposed only when, _backfill_not_null_nulls(), _column_fill_value(), get_db(), get_engine(), get_session_factory(), init_db(), Database engine and session management. Supports both PostgreSQL (production) an (+76 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (161): chore/weekly-orchestrator-2026-07-03, main, 01498d0 Harden password reset flow (verified-only, dev code return), 093f7d3 ui(manager): ocultar config y redirigir al dashboard al cambiar vista, 0a4396e Add multi-hotel isolation tests and bcrypt shim, 0b14a55 Subscription status: seed starter and add safe fallback, 0c9034f Fix clsx reference in app shell, 0de2c27 Align deploy config and docs for Vercel, Render, and Cloudflare (+153 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (114): PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Occupancy report for a date range (default: last 30 days)., Revenue report for a date range., Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c (+106 more)

### Community 3 - "Community 3"
Cohesion: 0.02
Nodes (105): Base, Base class for all ORM models., _DecimalAwareEncoder, lifespan(), StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, Initialize database on application startup., SafeStaticFiles, Base (+97 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (91): Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by id (v72 §16).      Scoped to the API key, FastAPI routes for Room management + Housekeeping., Resolve today's effective rate from the single source of truth and attach it, Simple availability helper. Returns a placeholder message if required     parame, Generic room update (number, floor, notes, status, etc.). (+83 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (78): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, acceptInvitation(), AuthResponse, _build_auth_response(), _generate_code(), getInvitationInfo(), _issue_email_token(), login() (+70 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (82): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), createPaymentLink() (+74 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (53): email_status(), getHotelConfig(), HotelConfig, HotelConfigUpdate, FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., updateHotelConfig(), createPaymentSurcharge() (+45 more)

### Community 8 - "Community 8"
Cohesion: 0.04
Nodes (64): GuestCompanion, HotelConfiguration, HotelOutboundEmailError, A review is 'for today' when the stay is active on `today`.      §13.3: reviews, §13.3 review routing.      If the reservation under manual review is active *tod, Subscription helpers: plan lookup, room limits, status checks and entitlements., Seed entitlement rows for known plans.     Always keeps room entitlement aligned, Ensure a subscription record exists; create starter active if missing and seed e (+56 more)

### Community 9 - "Community 9"
Cohesion: 0.05
Nodes (76): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Ensure computed fields land in the response., Lightweight availability placeholder. When all parameters are provided,     it r, ReservationSourceEnum, ReservationStatusEnum, ReservationError (+68 more)

### Community 10 - "Community 10"
Cohesion: 0.06
Nodes (65): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+57 more)

### Community 11 - "Community 11"
Cohesion: 0.04
Nodes (69): BaseModel, BillingPolicyPayload, BillingPolicyUpdateRequest, EmailTestRequest, MasterAdminLoginRequest, MasterAdminLoginResponse, MasterAdminSessionResponse, MasterAdminUserPayload (+61 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (61): AuthUser, Validate reset code without changing password (paso previo en UI)., validate_reset(), AcceptPayload, _assert_assignable_role(), _assert_manageable_membership(), invite_user(), InvitePayload (+53 more)

### Community 13 - "Community 13"
Cohesion: 0.08
Nodes (68): cancel_reservation(), create_new_reservation(), create_or_update_manual_ota(), extend_stay(), mark_no_show(), modify_reservation(), _project_reservation_graph(), FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend (+60 more)

### Community 14 - "Community 14"
Cohesion: 0.06
Nodes (50): CheckInRequest, FastAPI routes for Check-in / Check-out., DocumentTypeEnum, CheckInError, perform_checkin(), perform_checkout(), validate_guest_for_checkin(), _enum_value() (+42 more)

### Community 15 - "Community 15"
Cohesion: 0.09
Nodes (31): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., OTAConnection, OTAProvider, OTARatePlanMapping, OTAReservationLifecycleEnum (+23 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (21): 24d09f0 feat(db): v72 complete audit — phase 4, multi-tenancy tests, architecture docs, 52604e5 feat(db): PostgreSQL real validation green 8/8 — payment models, migration fixes, 7e2edb6 Merge Analytics R1.0, df173d1 Implement Analytics R1.0 dashboard, chat IA, and support, e1bc3d1 feat(db): v72 gaps phase 3 — room_movement_groups, BillingAdjustment Numeric, Room.description, e202fdd feat(db): v72 gaps phase 1+2 — Numeric precision, new tables, search indexes, OTA dedup, f0ca779 feat(security): prohibido_alojar enforcement, optimistic locking, payment tables, Reservation model with strict state machine. States: pending â†’ deposit_paid â† (+13 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (36): admin_comped_override(), change_plan(), changeSubscriptionPlan(), getSubscriptionStatus(), listSubscriptionPlans(), Subscription status and entitlements endpoints., _remaining_trial_days(), _serialize_status_payload() (+28 more)

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (21): OTACommissionRule, OTAConnectionStatusEnum, OTACurrencyRate, OTASyncEvent, OTASyncJob, OTASyncJobStatusEnum, OTA domain models for channel mappings, sync orchestration and external links., NormalizedOTAReservation (+13 more)

### Community 19 - "Community 19"
Cohesion: 0.15
Nodes (45): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily (+37 more)

### Community 20 - "Community 20"
Cohesion: 0.11
Nodes (51): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+43 more)

### Community 21 - "Community 21"
Cohesion: 0.11
Nodes (39): FastAPI routes for Guest management., Add new companions to an existing guest., Guest, GuestRatingEnum, GuestTag, GuestTagTypeEnum, SecurityAuditLog, HotelVoucher (+31 more)

### Community 22 - "Community 22"
Cohesion: 0.10
Nodes (41): APIKeyPurposeEnum, PaymentLinkRead, ReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead, PublicAvailabilityResponse, PublicCategoryRead (+33 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (34): ApiError, 3d34a97 Connect system mail through master admin, ad4249c Implement master admin panel, Email provider abstraction for platform transactional mail., clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminUser (+26 more)

### Community 24 - "Community 24"
Cohesion: 0.07
Nodes (38): IntegrationCatalog, IntegrationConnection, IntegrationEvent, _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error() (+30 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (41): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, LLMFeedbackEvent (+33 more)

### Community 26 - "Community 26"
Cohesion: 0.07
Nodes (28): ABC, EmailProvider, EmailProviderError, get_email_provider(), _mask_email(), _mask_recipients(), _normalize_display_from(), NullEmailProvider (+20 more)

### Community 27 - "Community 27"
Cohesion: 0.06
Nodes (34): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsCategoryDetailPage(), AnalyticsChannelsPage(), AnalyticsCompanyDetailPage(), AnalyticsEnvelope, AnalyticsFilterState (+26 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (24): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider (+16 more)

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (14): _make_hotel_guest_reservation(), test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict(), test_pending_action_resolution(), test_refund_request_gateway_path() (+6 more)

### Community 30 - "Community 30"
Cohesion: 0.17
Nodes (35): ReservationAllocationLock, Company, Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).     Suppo, RoomMoveEvent, RoomMovementGroup, RoomMoveTypeEnum, _adjacency_bonus_for_room(), AllocationError (+27 more)

### Community 31 - "Community 31"
Cohesion: 0.10
Nodes (29): create_room_block(), _exclusive_end(), _existing_user_id(), _inclusive_end(), list_room_blocks(), _read_block(), release_room_block(), RoomBlockCreate (+21 more)

### Community 32 - "Community 32"
Cohesion: 0.15
Nodes (28): 6e6d179 Prepare release candidate for landing and onboarding, 87b0eb6 Improve marketing SEO content, linking, and metadata, Seo(), SeoProps, StructuredData, resolveAppUrl(), resolveSalesContactUrl(), benefitPoints (+20 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (18): OwnerPayload, RoomPayload, setCategories(), setDepositPolicy(), setHotelIdentity(), setOtaChannels(), setOwner(), setRooms() (+10 more)

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (24): eee73bf test(perf+e2e): PG guest-search trgm indexes, benchmark harness, Playwright e2e harness, credentials, PAGES, e2eDbPath, frontendDir, repoRoot, cleanup(), derive_test_dsn() (+16 more)

### Community 35 - "Community 35"
Cohesion: 0.10
Nodes (28): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+20 more)

### Community 36 - "Community 36"
Cohesion: 0.10
Nodes (27): Public WhatsApp bot hooks authenticated only by hotel API key., balance_due_from_transactions(), cancel_active_links_for_reservation(), cancel_link(), create_link(), _create_mercadopago_preference(), _default_email_delivery(), deliver_link() (+19 more)

### Community 37 - "Community 37"
Cohesion: 0.10
Nodes (30): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+22 more)

### Community 38 - "Community 38"
Cohesion: 0.14
Nodes (30): _apply_corporate_pricing(), _apply_custom_deposit_amount(), _apply_pricing_result_to_reservation(), assert_reservation_version(), calculate_reservation_pricing(), _calendar_pricing_source(), check_room_availability(), _compute_deposit_amount() (+22 more)

### Community 39 - "Community 39"
Cohesion: 0.15
Nodes (3): GemmaPolicyDraft, GemmaService, Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 40 - "Community 40"
Cohesion: 0.12
Nodes (27): addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashMovement, CashMovementPayload, CashMovementType, CashSession, CashSessionClosePayload (+19 more)

### Community 41 - "Community 41"
Cohesion: 0.11
Nodes (24): get_settings(), _gmail_is_active(), _has_value(), is_demo_mode(), is_production_mode(), _is_public_https_url(), is_testing_mode(), _mercadopago_is_active() (+16 more)

### Community 42 - "Community 42"
Cohesion: 0.17
Nodes (28): Lightweight subscription tracking for enforcement and auditing (v2 tables)., Subscription, SubscriptionEvent, _actor_payload(), _apply_plan(), _as_utc(), change_subscription_plan(), _compute_can_write() (+20 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (22): AnalyticsSegmentsPage(), MasterAdminAuditPage(), MasterAdminDashboardPage(), MasterAdminLoginPage(), SettingsAssistantPage(), SettingsHotelPage(), SettingsSecurityPage(), SettingsUsersPage() (+14 more)

### Community 44 - "Community 44"
Cohesion: 0.10
Nodes (22): ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, daily_report(), DailyOperationalReport, getDailyOperationalReport(), getOperationalAlerts(), NightlyOperationalSummary (+14 more)

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (3): BookingAdapter, ExpediaAdapter, OTAProviderAdapter

### Community 46 - "Community 46"
Cohesion: 0.11
Nodes (20): createRoomBlock(), listActiveRoomBlocks(), resolveRoomBlock(), RoomBlock, RoomBlockCreatePayload, RoomBlockReasonCode, 9db1623 feat(frontend): V72 Wave D — room blocks, allocation revert, guest tags/override UI, roomBlockReasonLabel (+12 more)

### Community 47 - "Community 47"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 49 - "Community 49"
Cohesion: 0.10
Nodes (21): addLaundryItem(), createLaundryBatch(), LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead (+13 more)

### Community 50 - "Community 50"
Cohesion: 0.14
Nodes (7): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session()

### Community 51 - "Community 51"
Cohesion: 0.13
Nodes (22): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), SessionLike (+14 more)

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (18): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS, buildChannelSummaries() (+10 more)

### Community 53 - "Community 53"
Cohesion: 0.18
Nodes (25): _as_aware(), audit_master_action(), authenticate_master_login(), _authorize_user_for_master_panel(), _bootstrap_master_credentials_match(), create_master_session(), _hash_value(), _idle_expiry() (+17 more)

### Community 54 - "Community 54"
Cohesion: 0.11
Nodes (23): RateLimitEvent, db(), db_engine(), hotel_config(), Pytest configuration and fixtures. Uses an in-memory SQLite database for isolate, Create a fresh in-memory SQLite engine for each test., # IMPORTANT: parse .env manually — do NOT load_dotenv() it. Exporting the full ., Provide a transactional database session for each test. (+15 more)

### Community 55 - "Community 55"
Cohesion: 0.17
Nodes (22): _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet(), get_connection_payload() (+14 more)

### Community 56 - "Community 56"
Cohesion: 0.11
Nodes (16): 885bb1a Prefer completed hotel on login, 96ff88b Migrate system mail to Resend, _auth_headers(), _complete_onboarding(), _configure_resend(), _register_owner(), test_auth_flows_fail_without_connected_mail_provider(), test_login_prefers_a_completed_hotel_when_multiple_memberships_exist() (+8 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (22): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_job_path(), _flatten_payload_rows() (+14 more)

### Community 58 - "Community 58"
Cohesion: 0.15
Nodes (22): connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration(), get_status() (+14 more)

### Community 59 - "Community 59"
Cohesion: 0.20
Nodes (24): ReservationNoShowPolicyAppliedEnum, _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), PricingPolicyError, quote_rate_plan_stay(), _resolve_commission_amount() (+16 more)

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 61 - "Community 61"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+15 more)

### Community 62 - "Community 62"
Cohesion: 0.12
Nodes (5): _make_period(), TestApplyPricePeriod, TestGetPriceForDate, TestPricePeriodModel, TestResolveRateCalendar

### Community 63 - "Community 63"
Cohesion: 0.11
Nodes (15): listGuests(), cancelWaitlistEntry(), createWaitlistEntry(), listWaitlistEntries(), promoteWaitlistEntry(), API routes for reservation waitlist operations., WaitlistEntry, WaitlistEntryCreate (+7 more)

### Community 64 - "Community 64"
Cohesion: 0.08
Nodes (12): CategoryPayload, DepositPolicyPayload, finishOnboarding(), HotelIdentityPayload, OnboardingProviderSetup, OnboardingStatus, OTAChannelsPayload, PaymentMethodsPayload (+4 more)

### Community 65 - "Community 65"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 67 - "Community 67"
Cohesion: 0.28
Nodes (23): _build_finish_gates(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status(), _merge_extra_policies() (+15 more)

### Community 68 - "Community 68"
Cohesion: 0.18
Nodes (5): make_res(), make_rooms(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 69 - "Community 69"
Cohesion: 0.17
Nodes (20): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+12 more)

### Community 70 - "Community 70"
Cohesion: 0.12
Nodes (14): _make_guest(), _make_reservation(), test_api_key_name_unique_per_hotel_not_global(), test_delete_hotel_a_guest_does_not_affect_hotel_b(), test_guest_dedup_same_hotel_raises(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 71 - "Community 71"
Cohesion: 0.13
Nodes (15): Staff management endpoints for hotel public API keys., HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia, Per-hotel API credential. `key_hash` stores a hashed version of the secret;, _generate_secret(), _hash_secret(), HotelAPIKeyError, issue_key() (+7 more)

### Community 72 - "Community 72"
Cohesion: 0.15
Nodes (19): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), DailyRateOut, DailyRatePrices, getCategoryDailyRates() (+11 more)

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (17): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product(), Commercial configuration service.  This service owns the hotel-scoped CRUD rules (+9 more)

### Community 74 - "Community 74"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled(), test_get_guest_summary_includes_alerts_and_stays() (+3 more)

### Community 75 - "Community 75"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+4 more)

### Community 76 - "Community 76"
Cohesion: 0.10
Nodes (8): add_companions(), _build_guest_ledger_csv(), _enum_value(), export_guest_ledger(), GuestCheckInReservation, GuestCompanion, GuestQuickProfile, GuestStaySummary

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (15): addGuestTag(), checkInGuestReservation(), getGuestQuickProfile(), GuestTag, GuestTagPayload, GuestTagType, listGuestTags(), resolveGuestTag() (+7 more)

### Community 78 - "Community 78"
Cohesion: 0.11
Nodes (14): PriceField, SingleRateInput, useBulkUpdateRateField(), useBulkUpsertRates(), useCategoryDailyRates(), useRateCalendar(), useUpsertDailyRate(), BULK_ACTION_OPTIONS (+6 more)

### Community 79 - "Community 79"
Cohesion: 0.18
Nodes (14): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate (+6 more)

### Community 80 - "Community 80"
Cohesion: 0.10
Nodes (14): CategoriesPayload, DepositPolicyPayload, HotelIdentityPayload, OnboardingStatus, OTAChannelsPayload, OwnerPayload, PaymentMethodsPayload, ProviderSetupPayload (+6 more)

### Community 81 - "Community 81"
Cohesion: 0.14
Nodes (15): fetchPermissionMatrix(), PermissionCell, PermissionMatrix, PermissionMatrixResponse, PermissionOverridePayload, PermissionOverrideRequest, PermissionOverrideResponse, PermissionRole (+7 more)

### Community 82 - "Community 82"
Cohesion: 0.11
Nodes (5): CurrentStock, DecimalValue, StockItem, StockLocation, StockMovement

### Community 83 - "Community 83"
Cohesion: 0.12
Nodes (4): dashboard_summary(), login(), me(), _serialize_user()

### Community 84 - "Community 84"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 85 - "Community 85"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 86 - "Community 86"
Cohesion: 0.13
Nodes (15): IntegrationHelpDrawer(), Props, IntegrationHelp, useConnectIntegration(), useIntegrations(), useRefreshIntegration(), useRevokeIntegration(), connectedSummary (+7 more)

### Community 87 - "Community 87"
Cohesion: 0.21
Nodes (12): _configure_resend(), _seed_hotel(), _seed_platform_admin(), _seed_subscription(), test_master_email_status_and_test_mail(), test_master_login_bootstraps_env_account(), test_master_login_cookie_works_on_underscore_alias(), test_master_login_locks_out_after_repeated_failures() (+4 more)

### Community 88 - "Community 88"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 89 - "Community 89"
Cohesion: 0.21
Nodes (15): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+7 more)

### Community 90 - "Community 90"
Cohesion: 0.27
Nodes (16): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _date_token(), get_cached_availability_payload(), get_cached_home_payload(), _get_cached_or_compute() (+8 more)

### Community 91 - "Community 91"
Cohesion: 0.29
Nodes (16): _collect_plan_entitlements(), delete_entitlement_override(), ensure_entitlements_seeded(), ensure_room_within_limit(), ensure_subscription(), entitlements_payload(), get_effective_room_limit(), get_entitlements() (+8 more)

### Community 92 - "Community 92"
Cohesion: 0.13
Nodes (11): DailyRateRangeRow, RateCalendarResponse, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, RateEditorGrid() (+3 more)

### Community 93 - "Community 93"
Cohesion: 0.13
Nodes (14): createStockItem(), createStockLocation(), createStockMovement(), getCurrentStock(), listLowStockItems(), listStockItems(), listStockLocations(), StockMovementCreate (+6 more)

### Community 94 - "Community 94"
Cohesion: 0.18
Nodes (14): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), isAppHostname(), normalizeUrl(), PUBLIC_APP_URL, PUBLIC_SITE_URL, resolveAppLocation() (+6 more)

### Community 95 - "Community 95"
Cohesion: 0.24
Nodes (13): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+5 more)

### Community 96 - "Community 96"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 97 - "Community 97"
Cohesion: 0.27
Nodes (13): HotelPermissionOverride, Permission, Configurable permission matrix models., RolePermissionDefault, get_matrix(), Permission matrix resolution and mutation., Create or repair the built-in role permission matrix., Resolve override > default > deny for a hotel role permission. (+5 more)

### Community 98 - "Community 98"
Cohesion: 0.13
Nodes (15): GemmaActionApplyDraftRequest, GemmaActionApplyDraftResponse, GemmaActionApproveRequest, GemmaActionApproveResponse, GemmaActionRejectRequest, GemmaActionRejectResponse, GemmaActionReviewDraftRequest, GemmaActionReviewDraftResponse (+7 more)

### Community 99 - "Community 99"
Cohesion: 0.23
Nodes (13): _active_room_blocks(), _alerts(), _available_with_review(), _cash_session(), daily_report(), _group(), _guest_name(), is_review_for_today() (+5 more)

### Community 100 - "Community 100"
Cohesion: 0.17
Nodes (9): current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item(), low_stock_items(), Hotel-scoped stock and inventory movement service., register_movement() (+1 more)

### Community 101 - "Community 101"
Cohesion: 0.17
Nodes (8): BrokenRedis, FakeRedis, test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_operational_invalidation_clears_availability_and_analytics(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip()

### Community 102 - "Community 102"
Cohesion: 0.22
Nodes (13): availability(), _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), get_booking(), list_bookings() (+5 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (14): addGuestCompanions(), createGuest(), getGuest(), Guest, GuestCompanionPayload, GuestPayload, GuestUpdatePayload, updateGuest() (+6 more)

### Community 104 - "Community 104"
Cohesion: 0.31
Nodes (13): add_movement(), approve_close_difference(), CashRegisterError, close_session(), _confirmed_cash_movements_total(), get_open_session(), get_session_summary(), list_movements() (+5 more)

### Community 105 - "Community 105"
Cohesion: 0.26
Nodes (14): calculate_base_amount_before_surcharge(), calculate_payment_surcharge(), get_hotel_config(), get_payment_link_with_surcharge(), get_reservation_financial_summary(), _payment_method_value(), process_payment(), _recommended_financial_action() (+6 more)

### Community 106 - "Community 106"
Cohesion: 0.51
Nodes (14): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), test_correct_version_passes_optimistic_lock(), test_no_prohibido_tag_allows_checkin(), test_omitting_client_version_skips_check(), test_other_tags_do_not_block_checkin() (+6 more)

### Community 107 - "Community 107"
Cohesion: 0.14
Nodes (4): Tests for Check-in Service. Validates guest data requirements before allowing ch, TestCheckIn, TestCheckOut, TestGuestValidation

### Community 108 - "Community 108"
Cohesion: 0.16
Nodes (1): DespegarAdapter

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Service adapter for PayPal payment integration.     Creates orders and processes, Process a PayPal webhook notification., Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 110 - "Community 110"
Cohesion: 0.14
Nodes (1): FastAPI routes for the commercial configuration domain.

### Community 111 - "Community 111"
Cohesion: 0.42
Nodes (13): _hotel(), _reservation(), test_cash_movement_requires_open_session(), test_cash_payment_posts_income_movement_to_open_session(), test_cash_payment_with_surcharge_posts_gross_amount_to_caja(), test_cash_payment_without_open_session_still_succeeds(), test_close_report_expected_balance_from_confirmed_cash(), test_close_with_difference_requires_approval() (+5 more)

### Community 112 - "Community 112"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 113 - "Community 113"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 114 - "Community 114"
Cohesion: 0.47
Nodes (11): _make_reservation(), _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations(), test_auto_assign_no_double_booking() (+3 more)

### Community 115 - "Community 115"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 116 - "Community 116"
Cohesion: 0.24
Nodes (9): create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+1 more)

### Community 117 - "Community 117"
Cohesion: 0.22
Nodes (12): CategoryPricingRead, CategoryPricingSchema, Pydantic schemas for Room and RoomCategory., RoomBase, RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryUpdate (+4 more)

### Community 118 - "Community 118"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 119 - "Community 119"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 120 - "Community 120"
Cohesion: 0.32
Nodes (11): _active_tag_filter(), add_tag(), _audit(), find_or_create_guest(), _get_guest(), list_active_tags(), _now(), quick_profile() (+3 more)

### Community 121 - "Community 121"
Cohesion: 0.18
Nodes (4): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_release_no_guarantee_endpoint_releases_ota_reservation()

### Community 122 - "Community 122"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 123 - "Community 123"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 124 - "Community 124"
Cohesion: 0.21
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process an IPN (Instant Payment Notification) from MercadoPago.         Queries

### Community 125 - "Community 125"
Cohesion: 0.24
Nodes (7): _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity()

### Community 126 - "Community 126"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 127 - "Community 127"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 128 - "Community 128"
Cohesion: 0.42
Nodes (10): clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret(), verify_stripe_signature() (+2 more)

### Community 129 - "Community 129"
Cohesion: 0.38
Nodes (10): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _normalize_status(), _parse_mercadopago_signature_header(), _payload_value() (+2 more)

### Community 130 - "Community 130"
Cohesion: 0.25
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 131 - "Community 131"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 132 - "Community 132"
Cohesion: 0.33
Nodes (9): _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task(), test_company_crud_and_analytics_detail(), test_room_state_events_and_variable_cost_audit() (+1 more)

### Community 133 - "Community 133"
Cohesion: 0.18
Nodes (4): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_all_actions_persist(), test_audit_log_hotel_cascade_delete(), test_transaction_hotel_id_has_fk_constraint()

### Community 134 - "Community 134"
Cohesion: 0.29
Nodes (4): SimpleRateLimiter, get_public_api_context(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth.

### Community 135 - "Community 135"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), _serialize_reservation_status()

### Community 136 - "Community 136"
Cohesion: 0.31
Nodes (9): v72 §16.2 reportable origin — the 7 business-level booking origins.      Derived, ReportableOriginEnum, v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic() (+1 more)

### Community 137 - "Community 137"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 138 - "Community 138"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 139 - "Community 139"
Cohesion: 0.24
Nodes (9): push_availability_update(), _push_to_booking(), _push_to_expedia(), Celery tasks for OTA synchronization. Sends inventory/availability updates to Bo, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Expedia EQC API.          In production, this would, Full sync: push availability for ALL categories for the next N days.     Typical, Push availability updates to all enabled OTAs for a given category and date rang (+1 more)

### Community 140 - "Community 140"
Cohesion: 0.60
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+1 more)

### Community 141 - "Community 141"
Cohesion: 0.47
Nodes (8): _manual_payload(), _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_requires_channel_and_external_id(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(), test_release_no_guarantee_promotes_compatible_waitlist_entry(), test_release_no_guarantee_without_waitlist_still_succeeds()

### Community 142 - "Community 142"
Cohesion: 0.44
Nodes (9): _fake_mp_gateway(), _reservation(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service(), test_deliver_link_email_best_effort_on_failure(), test_deliver_link_email_records_channel() (+1 more)

### Community 143 - "Community 143"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 144 - "Community 144"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_blocked_for_past_check_in(), test_change_dates_blocked_when_room_conflict(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_pending_updates_dates_and_price(), test_extend_stay_blocked_for_zero_or_negative_days(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 145 - "Community 145"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 146 - "Community 146"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 147 - "Community 147"
Cohesion: 0.22
Nodes (9): FastAPI routes for stock and inventory operations., StockItemCreate, StockItemRead, StockItemUpdate, StockLocationCreate, StockLocationRead, StockMovementRead, Raised when a stock operation is invalid. (+1 more)

### Community 148 - "Community 148"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 149 - "Community 149"
Cohesion: 0.33
Nodes (8): GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate, Pydantic schemas for Guest and companions.

### Community 150 - "Community 150"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 152 - "Community 152"
Cohesion: 0.58
Nodes (8): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_owner_can_create_and_update_commercial_configuration()

### Community 153 - "Community 153"
Cohesion: 0.36
Nodes (7): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement()

### Community 154 - "Community 154"
Cohesion: 0.47
Nodes (6): _make_guest(), _make_reservation(), _make_room_set(), test_available_with_review_surfaces_in_report(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped()

### Community 155 - "Community 155"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 156 - "Community 156"
Cohesion: 0.44
Nodes (7): _make_hotel(), _make_reservation(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 157 - "Community 157"
Cohesion: 0.28
Nodes (3): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 158 - "Community 158"
Cohesion: 0.42
Nodes (6): _auth_headers(), _ensure_hotel(), test_comped_override_records_audit_event(), test_manual_transitions_emit_events(), test_role_gating_for_trial_and_comped_override(), test_trial_auto_suspends_after_fourteen_days()

### Community 159 - "Community 159"
Cohesion: 0.39
Nodes (7): _seed_room(), test_create_room_block_public_api(), test_hotel_override_removing_create_block_is_respected(), test_list_room_blocks_public_api(), test_receptionist_can_create_but_not_release_block_by_default(), test_release_room_block_public_api(), test_room_blocks_public_api_is_hotel_scoped()

### Community 160 - "Community 160"
Cohesion: 0.56
Nodes (7): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp()

### Community 161 - "Community 161"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 162 - "Community 162"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 163 - "Community 163"
Cohesion: 0.25
Nodes (5): AnalyticsAIChatRead, AnalyticsAIChatRequest, AnalyticsInsightRead, AnalyticsInsightRequest, AnalyticsInsightStatusRead

### Community 164 - "Community 164"
Cohesion: 0.29
Nodes (6): add_item(), create_batch(), get_batch(), _next_batch_code(), Hotel-scoped laundry service., transition_status()

### Community 165 - "Community 165"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 166 - "Community 166"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 167 - "Community 167"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 168 - "Community 168"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 169 - "Community 169"
Cohesion: 0.43
Nodes (7): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel()

### Community 170 - "Community 170"
Cohesion: 0.57
Nodes (7): _link(), _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_process_payment_replays_on_duplicate_idempotency_key()

### Community 171 - "Community 171"
Cohesion: 0.32
Nodes (4): authed_client(), client_with_db(), get_auth_context_target(), get_db_override_target()

### Community 172 - "Community 172"
Cohesion: 0.46
Nodes (7): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 173 - "Community 173"
Cohesion: 0.46
Nodes (5): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 174 - "Community 174"
Cohesion: 0.33
Nodes (2): mercadopago_payment_link_webhook(), _mercadopago_webhook_impl()

### Community 175 - "Community 175"
Cohesion: 0.38
Nodes (3): RuntimeError, GemmaServiceError, Raised when a Gemma request cannot be completed safely.

### Community 176 - "Community 176"
Cohesion: 0.29
Nodes (6): Schemas for hotel-scoped waitlist entries., WaitlistEntryCreate, WaitlistEntryRead, WaitlistEntryUpdate, WaitlistPromoteRequest, WaitlistPromoteResponse

### Community 177 - "Community 177"
Cohesion: 0.43
Nodes (4): create_audit_log(), payload_json(), queue_audit_log(), safe_create_audit_log()

### Community 178 - "Community 178"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 179 - "Community 179"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 180 - "Community 180"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 181 - "Community 181"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 183 - "Community 183"
Cohesion: 0.67
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 184 - "Community 184"
Cohesion: 0.48
Nodes (5): _seed_hotel(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_override_allows_receptionist_guest_edit()

### Community 185 - "Community 185"
Cohesion: 0.67
Nodes (6): _client_with_db(), _override_auth(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_denied_is_audited(), test_permission_override_allows_receptionist_guest_edit(), test_permissions_matrix_available_to_authenticated_hotel_member()

### Community 186 - "Community 186"
Cohesion: 0.57
Nodes (5): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits()

### Community 187 - "Community 187"
Cohesion: 0.62
Nodes (6): _payment(), _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 188 - "Community 188"
Cohesion: 0.48
Nodes (5): _analytics_enum(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260, _reservation_status_enum_new(), _reservation_status_enum_old(), upgrade()

### Community 189 - "Community 189"
Cohesion: 0.53
Nodes (5): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online()

### Community 190 - "Community 190"
Cohesion: 0.33
Nodes (6): Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, _require_demo_mode(), reset_demo(), seed_demo()

### Community 191 - "Community 191"
Cohesion: 0.53
Nodes (4): booking_webhook(), despegar_webhook(), expedia_webhook(), _handle_ota_webhook()

### Community 193 - "Community 193"
Cohesion: 0.47
Nodes (3): deactivate_payment_surcharge(), _get_surcharge_or_404(), update_payment_surcharge()

### Community 194 - "Community 194"
Cohesion: 0.33
Nodes (6): _frontend_placeholder(), Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., serve_frontend(), serve_spa()

### Community 195 - "Community 195"
Cohesion: 0.40
Nodes (4): 1af6bfc Add demo seed script and README instructions for stage 1, main(), Seed minimal demo data for local testing.  Usage:     python -m app.scripts.seed, seed()

### Community 196 - "Community 196"
Cohesion: 0.40
Nodes (3): authHeaders(), ensureOnboarding(), hotelId

### Community 197 - "Community 197"
Cohesion: 0.33
Nodes (2): Protocol, AnalyticsAIProvider

### Community 198 - "Community 198"
Cohesion: 0.33
Nodes (5): CompedOverrideRequest, Entitlement, EntitlementOverrideRequest, EntitlementsResponse, TrialRequest

### Community 199 - "Community 199"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 200 - "Community 200"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 201 - "Community 201"
Cohesion: 0.60
Nodes (5): _build_message(), ensure_hotel_gmail_ready(), HotelOutboundIdentity, HotelOutboundSendResult, send_hotel_email()

### Community 202 - "Community 202"
Cohesion: 0.60
Nodes (5): _active_hotel_ids(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports(), _send_report_for_hotel()

### Community 204 - "Community 204"
Cohesion: 0.47
Nodes (4): _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 205 - "Community 205"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 206 - "Community 206"
Cohesion: 0.73
Nodes (5): _add_billing_charge(), _create_checked_in_reservation(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 207 - "Community 207"
Cohesion: 0.53
Nodes (4): _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_update_mobility_restriction_triggers_reoptimization()

### Community 208 - "Community 208"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 209 - "Community 209"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 210 - "Community 210"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 211 - "Community 211"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 212 - "Community 212"
Cohesion: 0.50
Nodes (4): compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 213 - "Community 213"
Cohesion: 0.80
Nodes (4): _link(), _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 214 - "Community 214"
Cohesion: 0.70
Nodes (4): _client_with_db(), _override_auth(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 216 - "Community 216"
Cohesion: 0.60
Nodes (3): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 217 - "Community 217"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 218 - "Community 218"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 219 - "Community 219"
Cohesion: 0.70
Nodes (4): _seed_hotels(), test_low_stock_items_are_hotel_scoped(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_requires_positive_quantity()

### Community 221 - "Community 221"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 222 - "Community 222"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 223 - "Community 223"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 224 - "Community 224"
Cohesion: 0.83
Nodes (3): datastores_healthcheck(), _postgres_healthcheck(), _redis_healthcheck()

### Community 225 - "Community 225"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 226 - "Community 226"
Cohesion: 0.67
Nodes (4): create_tax_policy(), _get_tax_policy(), _replace_tax_rules(), update_tax_policy()

### Community 228 - "Community 228"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 230 - "Community 230"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 231 - "Community 231"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 232 - "Community 232"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 233 - "Community 233"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 234 - "Community 234"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 235 - "Community 235"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 236 - "Community 236"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 237 - "Community 237"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 238 - "Community 238"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 239 - "Community 239"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 240 - "Community 240"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 241 - "Community 241"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 242 - "Community 242"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 243 - "Community 243"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 244 - "Community 244"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 245 - "Community 245"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 246 - "Community 246"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 247 - "Community 247"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 248 - "Community 248"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 249 - "Community 249"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 250 - "Community 250"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 251 - "Community 251"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 252 - "Community 252"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 253 - "Community 253"
Cohesion: 0.67
Nodes (1): SubscriptionEnforcementMiddleware

### Community 254 - "Community 254"
Cohesion: 0.67
Nodes (2): RoomMoveEventRead, RoomMovementGroupRead

### Community 256 - "Community 256"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

## Knowledge Gaps
- **314 isolated node(s):** `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`, `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif` (+309 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 96`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `FastAPI routes for the commercial configuration domain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 155`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 174`** (2 nodes): `mercadopago_payment_link_webhook()`, `_mercadopago_webhook_impl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 197`** (2 nodes): `Protocol`, `AnalyticsAIProvider`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 231`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 232`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 233`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 234`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 235`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 236`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 237`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 238`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 239`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 240`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 241`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 242`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 243`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 244`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 245`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 246`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 247`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 248`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 249`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 250`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 251`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 252`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 253`** (1 nodes): `SubscriptionEnforcementMiddleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 254`** (2 nodes): `RoomMoveEventRead`, `RoomMovementGroupRead`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 256`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 3` to `Community 189`, `Community 0`, `Community 190`, `Community 194`, `Community 95`, `Community 25`, `Community 30`, `Community 19`, `Community 4`, `Community 2`, `Community 79`, `Community 75`, `Community 10`, `Community 116`, `Community 14`, `Community 21`, `Community 8`, `Community 22`, `Community 71`, `Community 1`, `Community 12`, `Community 24`, `Community 96`, `Community 17`, `Community 18`, `Community 15`, `Community 97`, `Community 54`, `Community 16`, `Community 136`, `Community 59`, `Community 9`, `Community 31`, `Community 42`, `Community 139`, `Community 65`, `Community 153`?**
  _High betweenness centrality (0.143) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 8` to `Community 7`, `Community 12`, `Community 13`, `Community 4`, `Community 134`, `Community 1`, `Community 3`, `Community 2`, `Community 34`, `Community 19`, `Community 14`, `Community 21`, `Community 201`, `Community 67`, `Community 15`, `Community 24`, `Community 9`, `Community 59`, `Community 38`, `Community 42`, `Community 139`, `Community 54`, `Community 65`, `Community 18`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 4` to `Community 9`, `Community 21`, `Community 2`, `Community 13`, `Community 16`, `Community 3`, `Community 30`, `Community 25`, `Community 19`, `Community 14`, `Community 79`, `Community 8`, `Community 15`, `Community 36`, `Community 59`, `Community 38`, `Community 31`, `Community 89`, `Community 54`, `Community 107`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 389 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 389 INFERRED edges - model-reasoned connections that need verification._
- **Are the 379 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 379 INFERRED edges - model-reasoned connections that need verification._
- **Are the 323 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 323 INFERRED edges - model-reasoned connections that need verification._
- **Are the 300 inferred relationships involving `Base` (e.g. with `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` and `Demo-only utilities: seed sample data and reset the database. Exposed only when`) actually correct?**
  _`Base` has 300 INFERRED edges - model-reasoned connections that need verification._