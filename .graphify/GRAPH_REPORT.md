# Graph Report - .  (2026-07-27)

## Corpus Check
- Large corpus: 835 files · ~581,176 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 8423 nodes · 33715 edges · 316 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 13352 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 13352 · contains: 5004 · ON_BRANCH: 4405 · calls: 3687 · MODIFIES: 2393 · rationale_for: 1581 · imports: 878 · imports_from: 674 · method: 595 · PARENT_OF: 585 · inherits: 558 · re_exports: 3


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 835 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 9 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `531bfbf`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `ReservationStatusEnum` - 816 edges
2. `Reservation` - 815 edges
3. `HotelConfiguration` - 767 edges
4. `Room` - 656 edges
5. `Guest` - 638 edges
6. `RoomCategory` - 593 edges
7. `Base` - 453 edges
8. `RoomStatusEnum` - 396 edges
9. `ReservationError` - 364 edges
10. `ReservationSourceEnum` - 338 edges

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

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (245): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Quickly seed demo bookings (requires DEMO_MODE=true)., Ensure computed fields land in the response. (+237 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (257): Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Occupancy report for a date range (default: last 30 days)., Revenue report for a date range., Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, User management per hotel (owners/co-owners)., AuditLog, Append-only record of every significant mutation within a hotel tenant.     Do N (+249 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (232): delete_room(), housekeeping_summary(), FastAPI routes for Room management + Housekeeping., Resolve today's effective rate from the single source of truth and attach it, Resolve today's effective rate from the single source of truth and attach it, Simple availability helper. Returns a placeholder message if required     parame, Simple availability helper. Returns a placeholder message if required     parame, Generic room update (number, floor, notes, status, etc.). (+224 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (116): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online(), _clickhouse_healthcheck(), datastores_healthcheck(), _postgres_healthcheck() (+108 more)

### Community 4 - "Community 4"
Cohesion: 0.04
Nodes (215): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+207 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (174): chore/weekly-orchestrator-2026-07-03, codex/feature/agent-ops-knowledge, codex/feature/trusted-qa-bootstrap, codex/fix-render-postgres-enum-values, main, 01498d0 Harden password reset flow (verified-only, dev code return), 093f7d3 ui(manager): ocultar config y redirigir al dashboard al cambiar vista, 0a4396e Add multi-hotel isolation tests and bcrypt shim (+166 more)

### Community 6 - "Community 6"
Cohesion: 0.14
Nodes (187): agent-settlement, agent-ux, agent-warehouse, worktree-agent-a256bbe12be1abe44, worktree-agent-a3a198c21200e26be, worktree-agent-a3c8668a591bf7739, worktree-agent-a60ea08d416533eef, worktree-agent-a86cd1e171e139840 (+179 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (142): claude/feature/pms-roles-housekeeping-qa, codex/feature/pms-e2e-scale-hardening, 00bf891 Explain analytics errors and add retry action, 02f4bb4 Record Apple WebKit business matrix, 03832c5 Run onboarding journey on WebKit, 0391f8f Fix flaky detached-node false positive in mobile touch-target check, 03f4d70 Document cloud date and quote regressions, 0449677 Document cloud role and preview blocker (+134 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (152): cancel_reservation(), create_reservation_charge(), extend_stay(), mark_no_show(), modify_reservation(), occupancy_grid(), FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend, §5.2 — Run allocation engine in background after reservation changes.     Create (+144 more)

### Community 9 - "Community 9"
Cohesion: 0.02
Nodes (124): FastAPI routes for outsourced laundry vendors, pricing and remitos.  Separate ro, RemitoCreate, RemitoCreateResponse, RemitoLineIn, RemitoLineRead, RemitoRead, VendorBalanceLine, VendorCreate (+116 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (113): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), Category (+105 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (117): Base, Base class for all ORM models., _DecimalAwareEncoder, _frontend_placeholder(), _is_demo_mode_enabled(), lifespan(), Initialize database on application startup., Initialize database on application startup. (+109 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (95): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, acceptInvitation(), AuthResponse, AuthUser, _build_auth_response(), _generate_code(), getInvitationInfo(), _issue_email_token() (+87 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (42): cancelPaymentLinkTest(), createMercadoPagoPaymentLinkTest(), listPaymentLinkTests(), PaymentLinkTest, PaymentLinkTestCreatePayload, refreshPaymentLinkTest(), 1af6bfc Add demo seed script and README instructions for stage 1, 26970dd Add token store cleanup helper (+34 more)

### Community 14 - "Community 14"
Cohesion: 0.03
Nodes (47): _authorize_override(), checkin(), checkin_partial(), CategoryPayload, DepositPolicyPayload, finishOnboarding(), getOnboardingStatus(), HotelIdentityPayload (+39 more)

### Community 15 - "Community 15"
Cohesion: 0.07
Nodes (84): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, HotelPermissionOverride, Permission, Configurable permission matrix models. (+76 more)

### Community 16 - "Community 16"
Cohesion: 0.03
Nodes (61): email_status(), getHotelConfig(), HotelConfig, HotelConfigUpdate, FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., updateHotelConfig() (+53 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (21): DespegarAdapter, ExpediaAdapter, OTASyncEvent, OTASyncJob, NormalizedOTAReservation, OTAAdapterContext, OTAOperationResult, OTAProviderAdapter (+13 more)

### Community 18 - "Community 18"
Cohesion: 0.09
Nodes (43): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., OTAConnection, OTAProvider, OTARatePlanMapping, OTAReservationLifecycleEnum (+35 more)

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (33): 0254334 Merge branch 'agent-ux' into codex/feature/pms-e2e-scale-hardening, 099e4c8 fix(e2e): stop the WebKit business Apple matrix from colliding with itself, 10e9d42 fix(security): gate manual reservation total_amount behind reservation:manual_rate, 194af4d fix(reservations): search guests by name/DNI instead of raw ID field, 1ae9c1e fix(security): wire room-blocks endpoint to granular create/release permissions, 23f30ca feat(ux): Apple-HIG-style polish pass -- motion, focus rings, tap targets, consistent status colors, 29feed9 chore(graphify): refresh code graph after reservation quote error fix, 531bfbf docs(design): audit action-permission granularity + design step-up token (not wired) (+25 more)

### Community 20 - "Community 20"
Cohesion: 0.03
Nodes (66): MasterAdminProtectedShell(), MasterAdminRoot(), navItems, MasterAdminSessionProvider(), OnboardingWizard(), SettingsAssistantPage(), SettingsHotelPage(), SettingsSecurityPage() (+58 more)

### Community 21 - "Community 21"
Cohesion: 0.04
Nodes (57): addLaundryItem(), createLaundryBatch(), LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead (+49 more)

### Community 22 - "Community 22"
Cohesion: 0.07
Nodes (62): _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by confirmation code (v72 §16).      Scoped (+54 more)

### Community 23 - "Community 23"
Cohesion: 0.10
Nodes (60): CashCloseReport, CashCustodyHandoff, CashCustodyStatusEnum, CashMovement, CashMovementTypeEnum, CashSession, CashSessionStatusEnum, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca (+52 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (58): validateGuestForCheckin(), add_reservation_guests(), addReservationCharge(), addReservationGuests(), buildQueryString(), cancelReservation(), change_dates(), CheckInPayload (+50 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (44): addGuestCompanions(), addGuestTag(), _build_guest_ledger_csv(), buildGuestQueryString(), checkInGuestReservation(), createGuest(), _enum_value(), export_guest_ledger() (+36 more)

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (49): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity() (+41 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (54): BootstrapConfigurationError, build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _decode_lease_entropy(), _deployment_git_identity() (+46 more)

### Community 28 - "Community 28"
Cohesion: 0.05
Nodes (45): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), DailyRateOut, DailyRatePrices, DailyRateRangeRow (+37 more)

### Community 29 - "Community 29"
Cohesion: 0.09
Nodes (36): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+28 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (44): 805b47a Unify reservation pricing with signed quote contract, APIKeyPurposeEnum, PaymentLinkRead, ReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead, PublicAvailabilityResponse (+36 more)

### Community 31 - "Community 31"
Cohesion: 0.11
Nodes (53): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+45 more)

### Community 32 - "Community 32"
Cohesion: 0.05
Nodes (43): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), approvePaymentProof() (+35 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (28): create_movement(), createStockItem(), createStockLocation(), createStockMovement(), CurrentStock, DecimalValue, deleteStockItem(), _ensure_adjustment_permission() (+20 more)

### Community 34 - "Community 34"
Cohesion: 0.10
Nodes (43): Exception, AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum (+35 more)

### Community 35 - "Community 35"
Cohesion: 0.06
Nodes (38): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsCategoryDetailPage(), AnalyticsChannelsPage(), AnalyticsCompanyDetailPage(), AnalyticsEnvelope, analyticsErrorMessage() (+30 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (46): AcceptPayload, AuthContext, get_auth_context(), _parse_header_hotel_id(), _parse_token_hotel_id(), Return an authenticated context scoped to an active hotel membership., Return an authenticated context scoped to an active hotel membership., Return an authenticated context scoped to an active hotel membership. (+38 more)

### Community 37 - "Community 37"
Cohesion: 0.07
Nodes (35): ad4249c Implement master admin panel, Email provider abstraction for platform transactional mail., clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminUser, MasterBillingPolicy, MasterDashboardSummary (+27 more)

### Community 38 - "Community 38"
Cohesion: 0.10
Nodes (47): _b64url_decode(), _b64url_encode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), _canonical_json(), canonical_provider_evidence_json(), cli() (+39 more)

### Community 39 - "Community 39"
Cohesion: 0.07
Nodes (39): AnalyticsWarehouseUnavailable, build_cash_movement_fact_row(), build_hotel_dimension_row(), build_payment_fact_row(), build_reservation_fact_row(), build_room_category_dimension_row(), build_room_dimension_row(), build_stock_movement_fact_row() (+31 more)

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (35): addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashCustodyHandoff, CashMovement, CashMovementPayload, CashMovementType, CashSession (+27 more)

### Community 41 - "Community 41"
Cohesion: 0.07
Nodes (30): ABC, _pick_default_hotel_id(), Auth endpoints: register, login, email verification and password reset. Verifica, Validate reset code without changing password (paso previo en UI)., Validate reset code without changing password (paso previo en UI)., Prefer a hotel whose onboarding is already complete.      When a user belongs to, Prefer a hotel whose onboarding is already complete.      When a user belongs to, validate_reset() (+22 more)

### Community 42 - "Community 42"
Cohesion: 0.05
Nodes (31): graphify_state(), main(), main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only., Replace this repository's absolute root in generated instructions only., main(), run() (+23 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+29 more)

### Community 44 - "Community 44"
Cohesion: 0.07
Nodes (36): Base, FxPolicy, ProductRoomCompatibility, RatePlan, RatePlanPrice, Commercial domain models for the next reservation/OTA foundation.  These tables, SellableProduct, TaxPolicy (+28 more)

### Community 45 - "Community 45"
Cohesion: 0.09
Nodes (38): _bootstrap_environment(), _evidence_payload(), _local_evidence_payload(), _provider_manifest(), _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_local_test_database_target() (+30 more)

### Community 46 - "Community 46"
Cohesion: 0.05
Nodes (11): e34785c prueba, bubbleStyles, modeLabel, roleLabel, runtimeLabel, suggestedPrompts, build_gemma_hotel_context(), _enum_value() (+3 more)

### Community 47 - "Community 47"
Cohesion: 0.10
Nodes (38): Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, stream_domain_events(), channel_for_hotel(), DomainEvent, format_sse(), get_realtime_client(), _get_redis_client(), iter_event_stream() (+30 more)

### Community 48 - "Community 48"
Cohesion: 0.14
Nodes (30): 6e6d179 Prepare release candidate for landing and onboarding, 87b0eb6 Improve marketing SEO content, linking, and metadata, Seo(), SeoProps, StructuredData, resolveAppUrl(), resolveSalesContactUrl(), benefitPoints (+22 more)

### Community 49 - "Community 49"
Cohesion: 0.06
Nodes (14): _make_hotel_guest_reservation(), test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict(), test_pending_action_resolution(), test_refund_request_gateway_path() (+6 more)

### Community 50 - "Community 50"
Cohesion: 0.10
Nodes (12): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session(), TestAutoCashEntry (+4 more)

### Community 51 - "Community 51"
Cohesion: 0.09
Nodes (26): RoomBlockCreate, RoomBlockRead, RoomBlockReasonEnum, blocked_room_ids_for_range(), create_block(), get_block(), _invalidate_availability_cache(), list_active_blocks() (+18 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (10): 0a457cb feat(checkin): B3 partial check-in + mandatory guest profile capture + companions, a5ee7be fix(migrations): make schema-drift-era tables idempotent against self-healed production, receptionist, guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho, v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event, Store private transfer-proof bytes separately from searchable metadata., Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re, Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for (+2 more)

### Community 53 - "Community 53"
Cohesion: 0.08
Nodes (28): PaymentMethod, ReservationStatus, CheckinCaptureForm, emptyCaptureForm, guestFullName(), paymentMethodOptions, Props, ReservationDetailDrawer() (+20 more)

### Community 54 - "Community 54"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaService, GemmaServiceError, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 55 - "Community 55"
Cohesion: 0.10
Nodes (28): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+20 more)

### Community 56 - "Community 56"
Cohesion: 0.20
Nodes (27): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, FactRoomOccupancyDaily, HotelAuditEvent, RoomStateEvent, RoomStateEventReasonCodeEnum, RoomStateEventTypeEnum (+19 more)

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (26): SimpleRateLimiter, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterBillingPolicy, MasterStripeSettings, MasterStripeWebhookEvent, MasterSystemEmailConnection (+18 more)

### Community 58 - "Community 58"
Cohesion: 0.10
Nodes (30): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+22 more)

### Community 59 - "Community 59"
Cohesion: 0.10
Nodes (26): admin_comped_override(), change_plan(), changeSubscriptionPlan(), getSubscriptionStatus(), listSubscriptionPlans(), Subscription status and entitlements endpoints., _remaining_trial_days(), _serialize_status_payload() (+18 more)

### Community 60 - "Community 60"
Cohesion: 0.16
Nodes (30): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+22 more)

### Community 61 - "Community 61"
Cohesion: 0.11
Nodes (27): Date-ranged block on a room. NULL ends_at means indefinite.     resolved_at popu, RoomBlock, _build_message(), ensure_hotel_gmail_ready(), HotelOutboundEmailError, HotelOutboundIdentity, HotelOutboundSendResult, send_hotel_email() (+19 more)

### Community 62 - "Community 62"
Cohesion: 0.08
Nodes (32): get_settings(), _gmail_is_active(), _has_value(), is_demo_mode(), is_preview_qa_mode(), is_production_mode(), _is_public_https_url(), is_test_mode() (+24 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (32): _backfill_not_null_nulls(), _column_fill_value(), get_db(), get_engine(), get_session_factory(), init_db(), Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref (+24 more)

### Community 64 - "Community 64"
Cohesion: 0.10
Nodes (23): ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, daily_report(), DailyOperationalReport, getDailyOperationalReport(), getOperationalAlerts(), NightlyOperationalSummary (+15 more)

### Community 65 - "Community 65"
Cohesion: 0.13
Nodes (18): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider, _effective_enabled() (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 67 - "Community 67"
Cohesion: 0.17
Nodes (21): _apply_drift(), env_page(), FakeRender, FakeRenderCleanupFailure, FakeRenderPutResponseLost, HealthResponse, manifest(), _mutating_calls() (+13 more)

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (15): IntegrationCatalog, IntegrationConnection, _Response, test_validate_gmail_credentials_requires_send_scope(), test_verify_connection_health_for_gmail_updates_connection(), _integration_client(), _Response, test_gmail_oauth_callback_uses_signed_state() (+7 more)

### Community 70 - "Community 70"
Cohesion: 0.12
Nodes (15): main(), valid_https(), _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _origin() (+7 more)

### Community 71 - "Community 71"
Cohesion: 0.09
Nodes (18): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS, buildChannelSummaries() (+10 more)

### Community 72 - "Community 72"
Cohesion: 0.18
Nodes (25): _as_aware(), audit_master_action(), authenticate_master_login(), _authorize_user_for_master_panel(), _bootstrap_master_credentials_match(), create_master_session(), _hash_value(), _idle_expiry() (+17 more)

### Community 73 - "Community 73"
Cohesion: 0.17
Nodes (22): _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet(), get_connection_payload() (+14 more)

### Community 74 - "Community 74"
Cohesion: 0.11
Nodes (26): _apply_setting(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set or clear the current hotel id for tenant-scoped RLS policies., Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that (+18 more)

### Community 75 - "Community 75"
Cohesion: 0.10
Nodes (22): deactivate_payment_surcharge(), _get_surcharge_or_404(), PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, update_payment_surcharge(), calculate_base_amount_before_surcharge(), calculate_payment_surcharge() (+14 more)

### Community 76 - "Community 76"
Cohesion: 0.15
Nodes (22): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_job_path(), _flatten_payload_rows() (+14 more)

### Community 77 - "Community 77"
Cohesion: 0.23
Nodes (22): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+14 more)

### Community 78 - "Community 78"
Cohesion: 0.22
Nodes (23): AttestationError, _b64url_decode(), _b64url_encode(), build_attestation(), _canonical_json(), _iso_utc(), _json_object(), _load_private_key() (+15 more)

### Community 79 - "Community 79"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 80 - "Community 80"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product() (+12 more)

### Community 81 - "Community 81"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+15 more)

### Community 82 - "Community 82"
Cohesion: 0.19
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 83 - "Community 83"
Cohesion: 0.11
Nodes (15): Reservation, cancelWaitlistEntry(), createWaitlistEntry(), listWaitlistEntries(), promoteWaitlistEntry(), API routes for reservation waitlist operations., WaitlistEntry, WaitlistEntryCreate (+7 more)

### Community 84 - "Community 84"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 85 - "Community 85"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (21): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+13 more)

### Community 87 - "Community 87"
Cohesion: 0.28
Nodes (23): _build_finish_gates(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status(), _merge_extra_policies() (+15 more)

### Community 88 - "Community 88"
Cohesion: 0.18
Nodes (5): make_res(), make_rooms(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 89 - "Community 89"
Cohesion: 0.20
Nodes (22): _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error(), _is_public_webhook_base(), list_payment_link_tests(), _mercadopago_access_token() (+14 more)

### Community 90 - "Community 90"
Cohesion: 0.12
Nodes (14): _make_guest(), _make_reservation(), test_api_key_name_unique_per_hotel_not_global(), test_delete_hotel_a_guest_does_not_affect_hotel_b(), test_guest_dedup_same_hotel_raises(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 91 - "Community 91"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled(), test_get_guest_summary_includes_alerts_and_stays() (+3 more)

### Community 93 - "Community 93"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+4 more)

### Community 94 - "Community 94"
Cohesion: 0.21
Nodes (18): add_companions(), Add new companions to an existing guest., Add new companions to an existing guest., Add new companions to an existing guest., GuestRatingUpdate, GuestTagCreate, GuestTagRead, _active_tag_filter() (+10 more)

### Community 95 - "Community 95"
Cohesion: 0.10
Nodes (11): OccupancyGridBlock, OccupancyGridReservation, OccupancyGridResponse, OccupancyGridRoom, CategoryGroup, DATE_LABEL, OccupancyGrid(), OccupancyGridProps (+3 more)

### Community 96 - "Community 96"
Cohesion: 0.14
Nodes (18): hasQuickGuestFormData(), QuickGuestFormValues, CHANNEL_OPTIONS, emptyFormState(), FormState, ManualOtaReservationModalProps, todayIso(), tomorrowIso() (+10 more)

### Community 97 - "Community 97"
Cohesion: 0.13
Nodes (14): consumption_report(), _consumption_totals_by_item(), current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item(), low_stock_items() (+6 more)

### Community 98 - "Community 98"
Cohesion: 0.30
Nodes (20): _hotel(), _reservation(), test_cash_movement_requires_open_session(), test_cash_payment_posts_income_movement_to_open_session(), test_cash_payment_with_surcharge_posts_gross_amount_to_caja(), test_cash_payment_without_open_session_is_rejected(), test_cash_payment_without_open_session_opens_zero_balance_session(), test_cash_payment_without_open_session_still_succeeds() (+12 more)

### Community 99 - "Community 99"
Cohesion: 0.15
Nodes (14): _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_master_admin_bypass_migration(), _load_rls_migration(), C2: app/master_admin/router.py queries Subscription directly, and     transitive, Return model relationships not covered by the core composite contract., _remaining_scoped_scalar_fks(), test_core_composite_fk_migration_covers_the_metadata_contract() (+6 more)

### Community 100 - "Community 100"
Cohesion: 0.15
Nodes (14): Staff management endpoints for hotel public API keys., HotelAPIKey, Per-hotel API credential. `key_hash` stores a hashed version of the secret;, _generate_secret(), _hash_secret(), HotelAPIKeyError, issue_key(), list_keys() (+6 more)

### Community 101 - "Community 101"
Cohesion: 0.25
Nodes (20): AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily, project_all_derived_facts_incremental(), _project_all_hotels_window(), project_operational_facts_to_clickhouse(), _project_operational_window(), project_reservation_facts_to_clickhouse() (+12 more)

### Community 102 - "Community 102"
Cohesion: 0.10
Nodes (14): CategoriesPayload, DepositPolicyPayload, HotelIdentityPayload, OnboardingStatus, OTAChannelsPayload, OwnerPayload, PaymentMethodsPayload, ProviderSetupPayload (+6 more)

### Community 103 - "Community 103"
Cohesion: 0.32
Nodes (19): _actor_payload(), _apply_plan(), _as_utc(), change_subscription_plan(), _compute_can_write(), end_trial(), ensure_subscription_seed(), entitlements_for_hotel() (+11 more)

### Community 104 - "Community 104"
Cohesion: 0.22
Nodes (15): acquire_lease(), env_page(), FakeRender, mutations(), release_lease(), test_acquire_failure_rolls_back_marker_first_then_target_fields(), test_acquire_refuses_every_drift_without_mutation(), test_acquire_validates_before_writing_and_commits_id_last() (+7 more)

### Community 105 - "Community 105"
Cohesion: 0.12
Nodes (4): dashboard_summary(), login(), me(), _serialize_user()

### Community 106 - "Community 106"
Cohesion: 0.22
Nodes (18): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+10 more)

### Community 107 - "Community 107"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 108 - "Community 108"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 109 - "Community 109"
Cohesion: 0.31
Nodes (18): AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, FactReservationRowKindEnum, FactRoomOccupancyStatusAtNightEnum, OTAConnectionStatusEnum, OTASyncJobStatusEnum, ReservationCancellationReasonCodeEnum, ReservationGuestSegmentEnum (+10 more)

### Community 110 - "Community 110"
Cohesion: 0.12
Nodes (13): create_remito(), create_vendor(), _default_currency(), get_vendor(), Outsourced laundry vendors: vendor/price catalog + remito transfers.  A remito i, Record a remito as a pair of StockMovements per line.      outbound: house_locat, What is physically at the vendor's laundry right now, per item., Total charged by the vendor in a period.      Assumption (see plan D1/D3, flagge (+5 more)

### Community 111 - "Community 111"
Cohesion: 0.18
Nodes (17): balance_due_from_transactions(), cancel_active_links_for_reservation(), cancel_link(), create_link(), _default_email_delivery(), deliver_link(), expire_link(), get_preference_id() (+9 more)

### Community 112 - "Community 112"
Cohesion: 0.24
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 113 - "Community 113"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (15): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), isAppHostname(), normalizeUrl(), PREVIEW_APP_HOST_SUFFIXES, PUBLIC_APP_URL, PUBLIC_SITE_URL (+7 more)

### Community 115 - "Community 115"
Cohesion: 0.29
Nodes (16): _collect_plan_entitlements(), delete_entitlement_override(), ensure_entitlements_seeded(), ensure_room_within_limit(), ensure_subscription(), entitlements_payload(), get_effective_room_limit(), get_entitlements() (+8 more)

### Community 117 - "Community 117"
Cohesion: 0.18
Nodes (8): Public WhatsApp bot hooks authenticated only by hotel API key., availability_lookup(), create_reservation(), generate_payment_link(), handle_payment_confirmation(), options_with_prices(), price_quote(), WhatsAppBookingError

### Community 118 - "Community 118"
Cohesion: 0.24
Nodes (13): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+5 more)

### Community 119 - "Community 119"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 120 - "Community 120"
Cohesion: 0.31
Nodes (14): add_movement(), approve_close_difference(), CashRegisterError, close_session(), confirm_cash_custody(), _confirmed_cash_movements_total(), get_latest_close_report(), get_session_summary() (+6 more)

### Community 121 - "Community 121"
Cohesion: 0.17
Nodes (6): Regression contracts for the repository's agent-operations setup., run_qa_evidence_check(), test_qa_evidence_rejects_malformed_result_without_traceback(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_schema_accepts_full_catalog(), write_complete_qa_evidence()

### Community 122 - "Community 122"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 123 - "Community 123"
Cohesion: 0.26
Nodes (13): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+5 more)

### Community 124 - "Community 124"
Cohesion: 0.23
Nodes (14): Security regression tests for local QA operator attestations., tagged(), test_altered_signature_is_rejected(), test_attestation_older_than_24_hours_is_rejected(), test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_manifest_byte_change_after_signing_is_rejected() (+6 more)

### Community 125 - "Community 125"
Cohesion: 0.17
Nodes (8): BrokenRedis, FakeRedis, test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_operational_invalidation_clears_availability_and_analytics(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip()

### Community 126 - "Community 126"
Cohesion: 0.15
Nodes (1): BookingAdapter

### Community 127 - "Community 127"
Cohesion: 0.20
Nodes (9): 15fdb88 Create missing cash custody handoff schema, b1e1bd0 Repair legacy cash handoff schema at startup, Repair known legacy PostgreSQL schema drift before starting the API.  The manage, FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_adds_only_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets() (+1 more)

### Community 128 - "Community 128"
Cohesion: 0.25
Nodes (14): RuntimeError, _credentials(), E2ESafetyError, main(), normalize_sqlite_url(), prepare_e2e_environment(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet, Raised before any database-capable dependency is imported. (+6 more)

### Community 129 - "Community 129"
Cohesion: 0.51
Nodes (14): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), test_correct_version_passes_optimistic_lock(), test_no_prohibido_tag_allows_checkin(), test_omitting_client_version_skips_check(), test_other_tags_do_not_block_checkin() (+6 more)

### Community 130 - "Community 130"
Cohesion: 0.20
Nodes (14): _configure_resend(), _seed_hotel(), _seed_platform_admin(), _seed_subscription(), test_master_dashboard_summary_counts_subscriptions_across_hotels(), test_master_email_status_and_test_mail(), test_master_login_bootstraps_env_account(), test_master_login_cookie_works_on_underscore_alias() (+6 more)

### Community 131 - "Community 131"
Cohesion: 0.31
Nodes (14): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- per-item stock consumption (out, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+6 more)

### Community 132 - "Community 132"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Service adapter for PayPal payment integration.     Creates orders and processes, Process a PayPal webhook notification., Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 133 - "Community 133"
Cohesion: 0.30
Nodes (13): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+5 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (1): FastAPI routes for the commercial configuration domain.

### Community 135 - "Community 135"
Cohesion: 0.15
Nodes (14): CashHandoffSchemaRepairError, main(), missing_model_tables(), Apply the additive cash-handoff repair in one PostgreSQL transaction., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., Raised when the safe repair cannot run against the configured database., Raised when the safe repair cannot run against the configured database. (+6 more)

### Community 136 - "Community 136"
Cohesion: 0.16
Nodes (13): push_availability_update(), _push_to_booking(), _push_to_expedia(), Celery tasks for OTA synchronization. Sends inventory/availability updates to Bo, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Expedia EQC API.          In production, this would, Send availability update to Expedia EQC API.          In production, this would (+5 more)

### Community 137 - "Community 137"
Cohesion: 0.30
Nodes (11): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task() (+3 more)

### Community 138 - "Community 138"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 139 - "Community 139"
Cohesion: 0.16
Nodes (4): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_release_no_guarantee_endpoint_releases_ota_reservation()

### Community 140 - "Community 140"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 141 - "Community 141"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 142 - "Community 142"
Cohesion: 0.47
Nodes (11): _make_reservation(), _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations(), test_auto_assign_no_double_booking() (+3 more)

### Community 143 - "Community 143"
Cohesion: 0.27
Nodes (11): _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), get_booking(), list_bookings(), _project_booking_graph() (+3 more)

### Community 144 - "Community 144"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 145 - "Community 145"
Cohesion: 0.26
Nodes (8): emailOutboxPath, readLatestCode(), waitForCode(), cleanupEmailOutbox(), emailOutboxPath, readLatestCode(), resetEmailOutbox(), waitForCode()

### Community 146 - "Community 146"
Cohesion: 0.22
Nodes (12): CategoryPricingRead, CategoryPricingSchema, Pydantic schemas for Room and RoomCategory., RoomBase, RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryUpdate (+4 more)

### Community 147 - "Community 147"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 148 - "Community 148"
Cohesion: 0.23
Nodes (12): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a short lease and release it only if this worker owns it.      When the, Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a short lease and release it only if this worker owns it.      Redis/Val (+4 more)

### Community 149 - "Community 149"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 150 - "Community 150"
Cohesion: 0.38
Nodes (12): _seed_hotels(), _seed_house_stock(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_create_vendor_creates_its_own_stock_location(), test_remito_line_snapshots_price_and_flags_missing_price() (+4 more)

### Community 151 - "Community 151"
Cohesion: 0.35
Nodes (12): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_approval_creates_completed_transfer_transaction_and_updates_balance(), test_proof_bytes_are_tenant_scoped(), test_rejected_proof_requires_reason_and_cannot_be_approved(), test_submit_transfer_proof_allows_amount_covering_billing_adjustments(), test_submit_transfer_proof_reencodes_and_removes_exif() (+4 more)

### Community 152 - "Community 152"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 153 - "Community 153"
Cohesion: 0.15
Nodes (4): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 154 - "Community 154"
Cohesion: 0.21
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process an IPN (Instant Payment Notification) from MercadoPago.         Queries

### Community 155 - "Community 155"
Cohesion: 0.36
Nodes (11): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., _render(), _strong_password() (+3 more)

### Community 156 - "Community 156"
Cohesion: 0.27
Nodes (9): create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+1 more)

### Community 157 - "Community 157"
Cohesion: 0.24
Nodes (7): _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity()

### Community 158 - "Community 158"
Cohesion: 0.35
Nodes (11): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _is_allowed_status_transition(), _normalize_status(), _parse_mercadopago_signature_header() (+3 more)

### Community 159 - "Community 159"
Cohesion: 0.27
Nodes (11): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), _load_provider_evidence(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+3 more)

### Community 160 - "Community 160"
Cohesion: 0.26
Nodes (7): client_with_db(), ctx(), get_auth_context_target(), get_db_override_target(), _override_role(), test_manager_with_config_manage_override_can_access_without_base_role(), test_manager_without_config_manage_permission_is_denied()

### Community 161 - "Community 161"
Cohesion: 0.26
Nodes (6): FakeRedis, _settings(), test_optional_backend_degrades_without_fabricating_an_event(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_required_backend_raises_when_unavailable(), test_stream_endpoint_sets_no_cache_headers_and_tenant_stream()

### Community 162 - "Community 162"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 163 - "Community 163"
Cohesion: 0.20
Nodes (3): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 164 - "Community 164"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 165 - "Community 165"
Cohesion: 0.42
Nodes (10): clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret(), verify_stripe_signature() (+2 more)

### Community 166 - "Community 166"
Cohesion: 0.35
Nodes (10): cleanup(), derive_test_dsn(), explain(), main(), measure(), percentile(), print_results(), run_alembic_upgrade() (+2 more)

### Community 167 - "Community 167"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 168 - "Community 168"
Cohesion: 0.33
Nodes (9): _adjacency_bonus_for_room(), apply_allocation_result(), _check_overlap(), _is_protected_reservation(), _lowest_available_compatible_floor(), _lowest_compatible_floor(), _one_night_gap_penalty_for_room(), run_allocation() (+1 more)

### Community 169 - "Community 169"
Cohesion: 0.31
Nodes (9): approve_transfer_proof(), _decode_image(), get_transfer_proof(), proof_file_path(), _proof_path(), reject_transfer_proof(), _reservation(), _safe_filename() (+1 more)

### Community 170 - "Community 170"
Cohesion: 0.25
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 171 - "Community 171"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 172 - "Community 172"
Cohesion: 0.18
Nodes (4): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_all_actions_persist(), test_audit_log_hotel_cascade_delete(), test_transaction_hotel_id_has_fk_constraint()

### Community 173 - "Community 173"
Cohesion: 0.42
Nodes (8): _create_link(), _post_webhook(), _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing()

### Community 174 - "Community 174"
Cohesion: 0.44
Nodes (9): _manual_payload(), _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_requires_channel_and_external_id(), test_manual_ota_total_amount_and_currency_label_applied(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(), test_release_no_guarantee_promotes_compatible_waitlist_entry() (+1 more)

### Community 175 - "Community 175"
Cohesion: 0.38
Nodes (10): _fake_mp_gateway(), _reservation(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service(), test_deliver_link_email_best_effort_on_failure(), test_deliver_link_email_records_channel() (+2 more)

### Community 176 - "Community 176"
Cohesion: 0.64
Nodes (10): _build_client(), _cleanup_client(), _override_auth(), _payload(), _seed_bookable_state(), test_manager_can_set_manual_total_amount_with_explicit_override(), test_manager_cannot_set_manual_total_amount_by_default(), test_owner_can_still_set_manual_total_amount() (+2 more)

### Community 177 - "Community 177"
Cohesion: 0.33
Nodes (10): D1: current_stock(location_id=...) narrows the balance to one location;     omit, _seed_hotels(), test_current_stock_location_filter_is_additive_and_hotel_wide_total_unchanged(), test_low_stock_items_are_hotel_scoped(), test_stock_adjustment_can_correct_quantity_downward(), test_stock_adjustment_downward_cannot_make_quantity_negative(), test_stock_item_and_movement_are_hotel_scoped(), test_stock_movement_history_is_hotel_scoped_newest_first_and_limited() (+2 more)

### Community 178 - "Community 178"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 180 - "Community 180"
Cohesion: 0.24
Nodes (6): AnalyticsAIRequest, GemmaProvider, _Client, _Response, test_provider_chat_uses_curated_hotel_context_and_controlled_message(), test_provider_receives_only_curated_hotel_analytics_payload()

### Community 181 - "Community 181"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 182 - "Community 182"
Cohesion: 0.38
Nodes (9): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), quote_rate_plan_stay(), _resolve_commission_amount(), _select_fx_policy(), _select_rate_plan_price() (+1 more)

### Community 183 - "Community 183"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 184 - "Community 184"
Cohesion: 0.60
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+1 more)

### Community 185 - "Community 185"
Cohesion: 0.49
Nodes (9): _client_with_db(), _override_auth(), _seed_fully_paid_reservation(), test_add_companion_during_checkin_flow_appears_in_additional_guests(), test_add_companion_exceeding_capacity_returns_clear_400(), test_checkin_captures_missing_fields_in_same_request(), test_checkin_without_new_fields_fails_with_clear_message(), test_partial_checkin_reaches_pre_check_in_then_final_checkin() (+1 more)

### Community 186 - "Community 186"
Cohesion: 0.47
Nodes (7): _make_guest(), _make_reservation(), _make_room_set(), test_available_with_review_surfaces_in_report(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped(), test_daily_report_pending_payments_reflect_consumption_charges()

### Community 187 - "Community 187"
Cohesion: 0.29
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret()

### Community 188 - "Community 188"
Cohesion: 0.49
Nodes (9): _link(), _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(), test_process_payment_replays_on_duplicate_idempotency_key() (+1 more)

### Community 189 - "Community 189"
Cohesion: 0.51
Nodes (9): _client_with_db(), _override_auth(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_denied_is_audited(), test_permission_override_allows_receptionist_guest_edit(), test_permissions_matrix_available_to_authenticated_hotel_member(), test_stock_history_api_is_hotel_scoped_and_limited(), test_stock_operator_cannot_adjust_downward_without_explicit_adjust_permission() (+1 more)

### Community 190 - "Community 190"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 191 - "Community 191"
Cohesion: 0.42
Nodes (7): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_cannot_create_room_block_by_default(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 192 - "Community 192"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_blocked_for_past_check_in(), test_change_dates_blocked_when_room_conflict(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_pending_updates_dates_and_price(), test_extend_stay_blocked_for_zero_or_negative_days(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 193 - "Community 193"
Cohesion: 0.33
Nodes (8): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_endpoint_rejects_capacity_overflow_and_returns_delta_on_reprice(), test_room_move_rejects_receptionist_without_room_move_permission(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_update_mobility_restriction_triggers_reoptimization()

### Community 194 - "Community 194"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 195 - "Community 195"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 196 - "Community 196"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 197 - "Community 197"
Cohesion: 0.28
Nodes (8): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Reject context commands that the installed Graphify CLI cannot route.

### Community 198 - "Community 198"
Cohesion: 0.28
Nodes (5): createReservation(), localIsoDate(), owner, parseMoney(), readStat()

### Community 199 - "Community 199"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 200 - "Community 200"
Cohesion: 0.33
Nodes (8): GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate, Pydantic schemas for Guest and companions.

### Community 201 - "Community 201"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 202 - "Community 202"
Cohesion: 0.36
Nodes (7): create_audit_log(), model_snapshot(), payload_json(), queue_audit_log(), Allow-list guest audit context before persistence or external projection., safe_create_audit_log(), sanitize_audit_payload()

### Community 203 - "Community 203"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 204 - "Community 204"
Cohesion: 0.33
Nodes (8): _active_hotel_ids(), Celery tasks for scheduled operational reports (BRM §15.1).  Two beat-driven tas, Build and email the report for a single hotel. Returns True on send.      Best-e, Build and email the report for a single hotel. Returns True on send.      Best-e, _run_scheduled_reports(), send_morning_reports(), send_nightly_reports(), _send_report_for_hotel()

### Community 206 - "Community 206"
Cohesion: 0.58
Nodes (8): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_owner_can_create_and_update_commercial_configuration()

### Community 207 - "Community 207"
Cohesion: 0.28
Nodes (3): _read(), test_explicit_rotation_replaces_values_and_preserves_mode(), test_generates_only_allowed_synthetic_values_with_private_permissions()

### Community 208 - "Community 208"
Cohesion: 0.56
Nodes (8): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1): permission gatin, _teardown(), test_housekeeping_can_operate_remitos_but_not_manage_vendors(), test_owner_can_manage_vendors_and_receptionist_cannot(), test_remito_rejects_insufficient_house_stock_via_api(), test_vendors_and_balance_are_hotel_scoped_across_the_api()

### Community 209 - "Community 209"
Cohesion: 0.36
Nodes (7): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement()

### Community 210 - "Community 210"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 211 - "Community 211"
Cohesion: 0.44
Nodes (7): _make_hotel(), _make_reservation(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 212 - "Community 212"
Cohesion: 0.28
Nodes (4): _count_queries(), _mk_reservation(), test_pending_actions_prefilter_matches_unfiltered_scan_for_every_trigger_type(), test_pending_actions_query_count_scales_with_candidates_not_total_reservations()

### Community 213 - "Community 213"
Cohesion: 0.33
Nodes (7): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_skip_and_limit_page_through_results()

### Community 214 - "Community 214"
Cohesion: 0.56
Nodes (7): _role_connection(), _seed_engine(), _seed_session(), test_after_commit_listener_reapplies_hotel_context(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_no_tenant_context_hides_all_rows(), test_tenant_isolation_blocks_cross_hotel_reads()

### Community 215 - "Community 215"
Cohesion: 0.42
Nodes (6): _auth_headers(), _ensure_hotel(), test_comped_override_records_audit_event(), test_manual_transitions_emit_events(), test_role_gating_for_trial_and_comped_override(), test_trial_auto_suspends_after_fourteen_days()

### Community 216 - "Community 216"
Cohesion: 0.25
Nodes (3): RenderRequester, Protocol, AnalyticsAIProvider

### Community 217 - "Community 217"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 218 - "Community 218"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 219 - "Community 219"
Cohesion: 0.32
Nodes (7): Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, _require_demo_mode(), reset_demo(), seed_demo()

### Community 220 - "Community 220"
Cohesion: 0.46
Nodes (7): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), _not_found_or_bad_request(), read_movement_group(), revert_movement_group()

### Community 221 - "Community 221"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 222 - "Community 222"
Cohesion: 0.25
Nodes (8): _qa_marker(), QABootstrapResult, Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., upsert_qa_data()

### Community 223 - "Community 223"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 224 - "Community 224"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 225 - "Community 225"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 226 - "Community 226"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 227 - "Community 227"
Cohesion: 0.39
Nodes (6): example(), Regression tests for final provider-evidence continuity., test_any_provider_subject_drift_is_rejected(), test_cli_rejects_symlinked_manifest(), test_final_observation_cannot_predate_probes(), test_only_a_newer_observation_timestamp_may_change()

### Community 228 - "Community 228"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 229 - "Community 229"
Cohesion: 0.43
Nodes (7): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel()

### Community 230 - "Community 230"
Cohesion: 0.32
Nodes (3): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation()

### Community 231 - "Community 231"
Cohesion: 0.46
Nodes (7): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 232 - "Community 232"
Cohesion: 0.43
Nodes (7): v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 233 - "Community 233"
Cohesion: 0.50
Nodes (7): opened_cash_register(), _payment(), _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 234 - "Community 234"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 235 - "Community 235"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 236 - "Community 236"
Cohesion: 0.33
Nodes (4): 906d009 Hide room status and block controls from roles that cannot use them, fdce0a4 Hide laundry batch creation from housekeeping, Persona, personas

### Community 237 - "Community 237"
Cohesion: 0.57
Nodes (6): command(), fenced(), frontend_routes(), heading(), main(), write()

### Community 238 - "Community 238"
Cohesion: 0.29
Nodes (6): Schemas for hotel-scoped waitlist entries., WaitlistEntryCreate, WaitlistEntryRead, WaitlistEntryUpdate, WaitlistPromoteRequest, WaitlistPromoteResponse

### Community 239 - "Community 239"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 240 - "Community 240"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 241 - "Community 241"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 242 - "Community 242"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 243 - "Community 243"
Cohesion: 0.52
Nodes (5): _seed_hotel(), _seed_reservation(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_permission_defaults_and_override_are_hotel_scoped()

### Community 244 - "Community 244"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 245 - "Community 245"
Cohesion: 0.67
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 246 - "Community 246"
Cohesion: 0.29
Nodes (3): _no_real_db(), Every response must carry baseline security headers so the SPA and API are not m, The unmatched-path SPA fallback still depends on get_db; stub it so this     tes

### Community 247 - "Community 247"
Cohesion: 0.57
Nodes (5): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits()

### Community 248 - "Community 248"
Cohesion: 0.57
Nodes (6): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 249 - "Community 249"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 250 - "Community 250"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 251 - "Community 251"
Cohesion: 0.53
Nodes (4): booking_webhook(), despegar_webhook(), expedia_webhook(), _handle_ota_webhook()

### Community 253 - "Community 253"
Cohesion: 0.33
Nodes (3): backendURL, credentials, StoredSession

### Community 254 - "Community 254"
Cohesion: 0.40
Nodes (4): clientNavigate(), credentials, PAGES, revealCollapsedNavLink()

### Community 255 - "Community 255"
Cohesion: 0.33
Nodes (5): CompedOverrideRequest, Entitlement, EntitlementOverrideRequest, EntitlementsResponse, TrialRequest

### Community 256 - "Community 256"
Cohesion: 0.40
Nodes (5): annotate_analytics_payload(), _as_utc_datetime(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL, Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 257 - "Community 257"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 258 - "Community 258"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 259 - "Community 259"
Cohesion: 0.47
Nodes (4): _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 260 - "Community 260"
Cohesion: 0.40
Nodes (4): C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it()

### Community 261 - "Community 261"
Cohesion: 0.60
Nodes (5): _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 262 - "Community 262"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 263 - "Community 263"
Cohesion: 0.53
Nodes (4): _override_auth(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms()

### Community 264 - "Community 264"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 265 - "Community 265"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 266 - "Community 266"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), downgrade(), _drop_successor_reference(), Add zero-balance cash rotation and custody handoffs., upgrade()

### Community 267 - "Community 267"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 268 - "Community 268"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 269 - "Community 269"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 270 - "Community 270"
Cohesion: 0.40
Nodes (1): credentials

### Community 271 - "Community 271"
Cohesion: 0.40
Nodes (2): housekeeping, owner

### Community 272 - "Community 272"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 273 - "Community 273"
Cohesion: 0.50
Nodes (2): chat_completions(), _extract_latest_user_message()

### Community 274 - "Community 274"
Cohesion: 0.50
Nodes (4): compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 275 - "Community 275"
Cohesion: 0.70
Nodes (4): _create_receptionist_user(), _open_cash_session(), _receptionist_context(), test_receptionist_can_view_and_make_reservation_payments()

### Community 276 - "Community 276"
Cohesion: 0.80
Nodes (4): _link(), _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 277 - "Community 277"
Cohesion: 0.70
Nodes (4): _client_with_db(), _override_auth(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 278 - "Community 278"
Cohesion: 0.80
Nodes (4): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 279 - "Community 279"
Cohesion: 0.40
Nodes (1): Response

### Community 280 - "Community 280"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 281 - "Community 281"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 282 - "Community 282"
Cohesion: 0.60
Nodes (3): _quote(), test_confirmed_reservation_stores_pricing_revision(), test_reservation_rejects_quote_after_pricing_revision_changes()

### Community 284 - "Community 284"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 285 - "Community 285"
Cohesion: 0.60
Nodes (4): _check_clause(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in, upgrade()

### Community 286 - "Community 286"
Cohesion: 0.50
Nodes (4): bootstrap_configuration_fingerprint(), Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually.

### Community 287 - "Community 287"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 288 - "Community 288"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 289 - "Community 289"
Cohesion: 0.50
Nodes (2): owner, receptionist

### Community 290 - "Community 290"
Cohesion: 0.67
Nodes (3): GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti, _receptionist_context(), test_receptionist_can_view_operations_summary_and_pending_actions()

### Community 292 - "Community 292"
Cohesion: 0.67
Nodes (2): _override_auth(), test_receptionist_can_get_price_quote()

### Community 293 - "Community 293"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 294 - "Community 294"
Cohesion: 0.67
Nodes (3): B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio, _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite()

### Community 295 - "Community 295"
Cohesion: 0.67
Nodes (3): _override_auth(), Regression guard for a real bug B3.2 uncovered: POST /api/guests/ dumps every Gu, test_create_guest_via_api_accepts_new_checkin_profile_fields()

### Community 297 - "Community 297"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 298 - "Community 298"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 299 - "Community 299"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 300 - "Community 300"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 301 - "Community 301"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 302 - "Community 302"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 303 - "Community 303"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 304 - "Community 304"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 305 - "Community 305"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 306 - "Community 306"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 307 - "Community 307"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 308 - "Community 308"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 309 - "Community 309"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 310 - "Community 310"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 311 - "Community 311"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 312 - "Community 312"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 313 - "Community 313"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 314 - "Community 314"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 315 - "Community 315"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 316 - "Community 316"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 317 - "Community 317"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 318 - "Community 318"
Cohesion: 0.67
Nodes (1): credentials

### Community 319 - "Community 319"
Cohesion: 0.67
Nodes (1): owner

### Community 320 - "Community 320"
Cohesion: 0.67
Nodes (1): credentials

### Community 321 - "Community 321"
Cohesion: 0.67
Nodes (2): RoomMoveEventRead, RoomMovementGroupRead

### Community 322 - "Community 322"
Cohesion: 0.67
Nodes (1): Seed and serve the E2E backend on 127.0.0.1:8040.  This wrapper avoids shell-spe

### Community 323 - "Community 323"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

## Knowledge Gaps
- **622 isolated node(s):** `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`, `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em` (+617 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 119`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 134`** (1 nodes): `FastAPI routes for the commercial configuration domain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 210`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 270`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 271`** (2 nodes): `housekeeping`, `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 273`** (2 nodes): `chat_completions()`, `_extract_latest_user_message()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 279`** (1 nodes): `Response`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 289`** (2 nodes): `owner`, `receptionist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 292`** (2 nodes): `_override_auth()`, `test_receptionist_can_get_price_quote()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 299`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 300`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 301`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 302`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 303`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 304`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 305`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 306`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 307`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 308`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 309`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 310`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 311`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 312`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 313`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 314`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 315`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 316`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 317`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 318`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 319`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 320`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 321`** (2 nodes): `RoomMoveEventRead`, `RoomMovementGroupRead`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 322`** (1 nodes): `Seed and serve the E2E backend on 127.0.0.1:8040.  This wrapper avoids shell-spe`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 323`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 11` to `Community 3`, `Community 219`, `Community 57`, `Community 118`, `Community 34`, `Community 4`, `Community 56`, `Community 109`, `Community 101`, `Community 8`, `Community 1`, `Community 23`, `Community 44`, `Community 15`, `Community 93`, `Community 156`, `Community 2`, `Community 0`, `Community 30`, `Community 100`, `Community 36`, `Community 69`, `Community 119`, `Community 14`, `Community 22`, `Community 18`, `Community 17`, `Community 13`, `Community 61`, `Community 51`, `Community 135`, `Community 127`, `Community 136`, `Community 84`, `Community 295`, `Community 208`, `Community 209`, `Community 131`, `Community 99`?**
  _High betweenness centrality (0.130) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 1` to `Community 16`, `Community 36`, `Community 8`, `Community 12`, `Community 9`, `Community 22`, `Community 5`, `Community 3`, `Community 11`, `Community 44`, `Community 2`, `Community 109`, `Community 56`, `Community 0`, `Community 61`, `Community 18`, `Community 110`, `Community 87`, `Community 89`, `Community 4`, `Community 57`, `Community 101`, `Community 136`, `Community 204`, `Community 84`, `Community 69`, `Community 295`, `Community 208`, `Community 260`, `Community 51`, `Community 17`, `Community 15`, `Community 131`, `Community 177`, `Community 50`, `Community 23`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 22` to `Community 0`, `Community 94`, `Community 1`, `Community 8`, `Community 2`, `Community 3`, `Community 11`, `Community 44`, `Community 34`, `Community 4`, `Community 109`, `Community 56`, `Community 15`, `Community 61`, `Community 18`, `Community 51`, `Community 117`, `Community 50`, `Community 23`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 814 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 814 INFERRED edges - model-reasoned connections that need verification._
- **Are the 808 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 808 INFERRED edges - model-reasoned connections that need verification._
- **Are the 760 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 760 INFERRED edges - model-reasoned connections that need verification._
- **Are the 651 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Room` has 651 INFERRED edges - model-reasoned connections that need verification._