# Graph Report - .  (2026-08-20)

## Corpus Check
- Large corpus: 1039 files · ~1,649,934 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 10174 nodes · 50027 edges · 378 communities detected
- Extraction: 67% EXTRACTED · 33% INFERRED · 0% AMBIGUOUS · INFERRED: 16471 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 16471 · ON_BRANCH: 13894 · contains: 5948 · calls: 4368 · MODIFIES: 3372 · rationale_for: 2098 · imports: 1078 · imports_from: 835 · PARENT_OF: 694 · inherits: 650 · method: 616 · re_exports: 3


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1039 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 12 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `897b057`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 950 edges
2. `ReservationStatusEnum` - 946 edges
3. `HotelConfiguration` - 921 edges
4. `Room` - 776 edges
5. `Guest` - 732 edges
6. `RoomCategory` - 710 edges
7. `Base` - 545 edges
8. `RoomStatusEnum` - 473 edges
9. `ReservationError` - 443 edges
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

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (364): PaymentSurchargeCreate, daily_report(), occupancy_report(), FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Occupancy report for a date range (default: last 30 days)., Occupancy report for a date range (default: last 30 days). (+356 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (331): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+323 more)

### Community 2 - "Community 2"
Cohesion: 0.16
Nodes (352): agent-linensplit, agent-login, agent-mobilenav, agent-otafix, agent-settlement, agent-stockedit, agent-stocksplit, agent-ux (+344 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (138): _authorize_override(), checkin(), _clickhouse_healthcheck(), datastores_healthcheck(), _postgres_healthcheck(), _redis_healthcheck(), Application Configuration. Uses pydantic-settings for environment variable manag, Database engine and session management. Supports both PostgreSQL (production) an (+130 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (320): add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest., Add new companions to an existing guest., Add new companions to an existing guest., Add new companions to an existing guest., Base, Base class for all ORM models. (+312 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (153): Shared, secret-safe binding for the Render QA bootstrap configuration., requestVerification(), ApiError, ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, DailyOperationalReport, getDailyOperationalReport() (+145 more)

### Community 6 - "Community 6"
Cohesion: 0.01
Nodes (209): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), Category (+201 more)

### Community 7 - "Community 7"
Cohesion: 0.04
Nodes (228): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, AuthUser, _assert_assignable_role(), _assert_manageable_membership(), invite_user(), InvitePayload, InviteResponse, inviteUser() (+220 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (168): create_laundry_remito(), _housekeeping_remito(), LinenItemCreate, LinenItemRead, LinenLocationCreate, LinenLocationRead, LinenMovementCreate, LinenMovementRead (+160 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (172): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Reject context commands that the installed Graphify CLI cannot route. (+164 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (176): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Quickly seed demo bookings (requires DEMO_MODE=true). (+168 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (145): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), apiFetch() (+137 more)

### Community 12 - "Community 12"
Cohesion: 0.17
Nodes (161): CheckInRequest, FastAPI routes for Check-in / Check-out., cancel_reservation(), change_dates(), create_reservation_charge(), _ensure_action_permission(), extend_stay(), _is_manager_context() (+153 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (118): ad4249c Implement master admin panel, PermissionGate(), StatCard(), StatCardProps, toneClasses, Email provider abstraction for platform transactional mail., clearMasterAdminCsrfToken(), masterAdminFetch() (+110 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (77): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online(), _booking_to_read(), cancel_booking(), checkin_booking() (+69 more)

### Community 15 - "Community 15"
Cohesion: 0.03
Nodes (71): email_status(), getHotelConfig(), HotelConfig, HotelConfigUpdate, FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., updateHotelConfig() (+63 more)

### Community 16 - "Community 16"
Cohesion: 0.09
Nodes (82): HotelPermissionOverride, Permission, Configurable permission matrix models., An employee-specific permission decision within one hotel membership., An employee-specific permission decision within one hotel membership., RolePermissionDefault, UserPermissionOverride, SecurityAuditLog (+74 more)

### Community 17 - "Community 17"
Cohesion: 0.09
Nodes (69): CashCloseReport, CashCustodyHandoff, CashCustodyStatusEnum, CashMovement, CashMovementTypeEnum, CashSession, CashSessionStatusEnum, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca (+61 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (64): createLaundryRemito(), createLaundryVendor(), getLaundryVendorBalance(), getLaundryVendorSettlements(), getLaundryVendorSpend(), LaundryRemito, LaundryRemitoCreate, LaundryRemitoCreateResponse (+56 more)

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (74): AcceptPayload, Thin FastAPI transport for the tenant-scoped permission service., _current_user(), Tenant-scoped security overview and current-user session revocation., Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details. (+66 more)

### Community 20 - "Community 20"
Cohesion: 0.04
Nodes (48): create_movement(), createStockItem(), createStockLocation(), createStockMovement(), CurrentStock, deleteStockItem(), _ensure_adjustment_permission(), get_stock_summary() (+40 more)

### Community 21 - "Community 21"
Cohesion: 0.05
Nodes (49): DailyReportSchedule, DailyReportScheduleUpdate, get_daily_report_schedule(), getDailyReportSchedule(), listNotificationPreferences(), listNotifications(), markAllNotificationsRead(), markNotificationRead() (+41 more)

### Community 22 - "Community 22"
Cohesion: 0.04
Nodes (32): CategoryPayload, DepositPolicyPayload, finishOnboarding(), getOnboardingStatus(), HotelIdentityPayload, OnboardingProviderSetup, OnboardingStatus, OTAChannelsPayload (+24 more)

### Community 23 - "Community 23"
Cohesion: 0.06
Nodes (53): _build_login_response(), google_login(), list_sessions(), logout(), _pick_default_hotel_id(), Auth endpoints: register, login, email verification and password reset. Verifica, Prefer a hotel whose onboarding is already complete.      When a user belongs to, Project a global identity event into every hotel the user actively belongs to. (+45 more)

### Community 24 - "Community 24"
Cohesion: 0.06
Nodes (50): RoomBlockCreate, RoomBlockRead, Exception, PendingActionPriorityEnum, PendingActionStatusEnum, PendingActionTypeEnum, PendingOperationalAction, PendingOperationalAction — the "pending_actions" table referenced throughout the (+42 more)

### Community 25 - "Community 25"
Cohesion: 0.09
Nodes (36): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+28 more)

### Community 26 - "Community 26"
Cohesion: 0.04
Nodes (26): BridgeActivity, 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations, credentials, createdPromotion, mockCategories, simulateResult, ownerCredentials, receptionistCredentials (+18 more)

### Community 27 - "Community 27"
Cohesion: 0.08
Nodes (52): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+44 more)

### Community 28 - "Community 28"
Cohesion: 0.07
Nodes (41): 300d128 feat(security): audit-log MFA, login, and Google account-linking events, 9f4f9ac feat(security): audit-log MFA, login, and Google account-linking events, _auth_headers(), _complete_onboarding(), _configure_resend(), _enroll_and_confirm_mfa(), _fake_google_claims(), FakeResponse (+33 more)

### Community 29 - "Community 29"
Cohesion: 0.11
Nodes (53): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+45 more)

### Community 30 - "Community 30"
Cohesion: 0.10
Nodes (44): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+36 more)

### Community 31 - "Community 31"
Cohesion: 0.09
Nodes (44): 805b47a Unify reservation pricing with signed quote contract, APIKeyPurposeEnum, PaymentLinkRead, ReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead, PublicAvailabilityResponse (+36 more)

### Community 32 - "Community 32"
Cohesion: 0.07
Nodes (18): OTASyncEvent, OTASyncJob, NormalizedOTAReservation, OTAAdapterContext, OTAOperationResult, OTAProviderAdapter, Common contracts for OTA provider adapters.  The goal is to keep Booking, Expedi, Foundational OTA adapter interfaces and orchestration services. (+10 more)

### Community 33 - "Community 33"
Cohesion: 0.09
Nodes (43): Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, stream_domain_events(), create_restriction(), _get_tenant_guest(), list_restrictions(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, resolve_restriction() (+35 more)

### Community 34 - "Community 34"
Cohesion: 0.06
Nodes (33): 0ff9102 fix(security): return CSRF token in the response body, 429e62c fix(review): require the CSRF cookie explicitly, no silent fallback, b47b916 feat(security): add revocable server-side sessions alongside existing JWT (backend only), Server-side, revocable sessions for the normal user auth plane., An opaque browser session whose raw token is never persisted., UserSession, _as_aware(), create_session() (+25 more)

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (31): b0fb0c8 fix(security): close master admin control plane gaps (TECH-0071), b355c74 fix(security): redact sensitive metadata in master admin audit events, dashboard_summary(), login(), me(), _serialize_user(), _as_aware(), audit_master_action() (+23 more)

### Community 36 - "Community 36"
Cohesion: 0.11
Nodes (41): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, LLMFeedbackEvent (+33 more)

### Community 37 - "Community 37"
Cohesion: 0.07
Nodes (39): AnalyticsWarehouseUnavailable, build_cash_movement_fact_row(), build_hotel_dimension_row(), build_payment_fact_row(), build_reservation_fact_row(), build_room_category_dimension_row(), build_room_dimension_row(), build_stock_movement_fact_row() (+31 more)

### Community 38 - "Community 38"
Cohesion: 0.06
Nodes (35): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsCategoryDetailPage(), AnalyticsChannelsPage(), AnalyticsCompanyDetailPage(), AnalyticsEnvelope, analyticsErrorMessage() (+27 more)

### Community 39 - "Community 39"
Cohesion: 0.24
Nodes (39): FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar., OTAConnection, OTAProvider, OTARatePlanMapping, OTAReservationLifecycleEnum (+31 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+29 more)

### Community 41 - "Community 41"
Cohesion: 0.12
Nodes (42): _b64url_decode(), _b64url_encode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), _canonical_json(), canonical_provider_evidence_json(), cli() (+34 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (38): _bootstrap_environment(), _evidence_payload(), _local_evidence_payload(), _provider_manifest(), _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_local_test_database_target() (+30 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (28): createPromotion(), deactivatePromotion(), listPromotions(), Promotion, PromotionAppliedEntry, PromotionBenefitType, PromotionConditions, PromotionCreatePayload (+20 more)

### Community 44 - "Community 44"
Cohesion: 0.06
Nodes (14): _make_hotel_guest_reservation(), test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict(), test_pending_action_resolution(), test_refund_request_gateway_path() (+6 more)

### Community 45 - "Community 45"
Cohesion: 0.11
Nodes (13): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session(), TestAutoCashEntry (+5 more)

### Community 46 - "Community 46"
Cohesion: 0.16
Nodes (38): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _deployment_git_identity(), _deployment_hosts(), _dict() (+30 more)

### Community 47 - "Community 47"
Cohesion: 0.11
Nodes (28): configure_dedicated_baseline(), env_page(), FakeApi, fixtures(), set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation(), test_dedicated_baseline_refuses_provider_lease_mismatch() (+20 more)

### Community 48 - "Community 48"
Cohesion: 0.06
Nodes (36): bootstrap_configuration_fingerprint(), BootstrapConfigurationError, Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., _decode_lease_entropy(), JsonGetter (+28 more)

### Community 49 - "Community 49"
Cohesion: 0.10
Nodes (35): addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashCustodyHandoff, CashMovement, CashMovementPayload, CashMovementType, CashSession (+27 more)

### Community 50 - "Community 50"
Cohesion: 0.09
Nodes (21): FastAPI routes for the commercial configuration domain., CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan() (+13 more)

### Community 51 - "Community 51"
Cohesion: 0.07
Nodes (35): Base, MasterBillingPolicy, MasterStripeSettings, MasterSystemEmailConnection, FxPolicy, ProductRoomCompatibility, RatePlan, RatePlanPrice (+27 more)

### Community 52 - "Community 52"
Cohesion: 0.16
Nodes (27): 6e6d179 Prepare release candidate for landing and onboarding, 87b0eb6 Improve marketing SEO content, linking, and metadata, Seo(), SeoProps, StructuredData, resolveAppUrl(), benefitPoints, faqItems (+19 more)

### Community 53 - "Community 53"
Cohesion: 0.07
Nodes (38): get_settings(), _gmail_is_active(), _has_value(), is_demo_mode(), is_preview_qa_mode(), is_production_mode(), _is_public_https_url(), is_test_mode() (+30 more)

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (32): DailyReportSchedule, Notification, NotificationChannelEnum, NotificationOutbox, NotificationOutboxStatusEnum, NotificationPreference, PushSubscription, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+24 more)

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaService, GemmaServiceError, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (33): consumption_report(), _consumption_totals_by_item(), create_stock_item(), current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item() (+25 more)

### Community 57 - "Community 57"
Cohesion: 0.10
Nodes (28): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+20 more)

### Community 58 - "Community 58"
Cohesion: 0.11
Nodes (11): ensure_all_ota_webhook_secrets(), _ensure_membership_and_subscription(), ensure_plans_seeded(), get_or_create_hotel_for_owner(), Hotel helper utilities (ownership + bootstrap)., Seed default plans if missing., Find a hotel configuration owned by the given email, or create a new one.     Al, Create owner membership and starter subscription if missing. (+3 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (36): D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE (+28 more)

### Community 60 - "Community 60"
Cohesion: 0.12
Nodes (32): MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterStripeWebhookEvent, MasterAdminContext, Subscription, _configure_resend(), FakeResponse (+24 more)

### Community 61 - "Community 61"
Cohesion: 0.11
Nodes (22): ABC, EmailProvider, EmailProviderError, get_email_provider(), _mask_email(), _mask_recipients(), _normalize_display_from(), NullEmailProvider (+14 more)

### Community 62 - "Community 62"
Cohesion: 0.11
Nodes (28): acceptInvitation(), _allow_mfa_attempt(), _attach_user_session_cookies(), _audit_security_event(), AuthResponse, _build_auth_response(), complete_mfa_login(), confirm_mfa_enrollment() (+20 more)

### Community 63 - "Community 63"
Cohesion: 0.10
Nodes (30): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+22 more)

### Community 64 - "Community 64"
Cohesion: 0.06
Nodes (30): create_remito(), create_vendor(), _default_currency(), get_vendor(), mark_vendor_settlement_paid(), _quarter_bounds(), Outsourced laundry vendors: vendor/price catalog + remito transfers.  A remito i, Record a remito as a pair of StockMovements per line.      outbound: house_locat (+22 more)

### Community 65 - "Community 65"
Cohesion: 0.16
Nodes (30): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+22 more)

### Community 66 - "Community 66"
Cohesion: 0.07
Nodes (32): _frontend_placeholder(), StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on (+24 more)

### Community 67 - "Community 67"
Cohesion: 0.07
Nodes (32): _backfill_not_null_nulls(), _column_fill_value(), get_db(), get_engine(), get_session_factory(), init_db(), Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref (+24 more)

### Community 68 - "Community 68"
Cohesion: 0.13
Nodes (26): 362fdd4 feat(security): add core TOTP/MFA enrollment, verification, and recovery codes, get_encryption_fernet(), Shared Fernet encryption for secrets stored in the database.  The integration en, Return the repository's existing Fernet instance for stored secrets., _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at() (+18 more)

### Community 69 - "Community 69"
Cohesion: 0.23
Nodes (24): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, RoomStateEventReasonCodeEnum, RoomStateEventTypeEnum, AnalyticsAIConfigRead, AnalyticsAIConfigUpdate, AnalyticsAlertSettingsRead (+16 more)

### Community 70 - "Community 70"
Cohesion: 0.07
Nodes (3): BookingAdapter, ExpediaAdapter, OTAProviderAdapter

### Community 71 - "Community 71"
Cohesion: 0.10
Nodes (21): 6d2a815 feat(security): migrate password hashing to Argon2id with transparent bcrypt upgrade, 9f8ba34 fix(security): audit and validate comped subscription override, _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config(), _complete_onboarding_setup() (+13 more)

### Community 72 - "Community 72"
Cohesion: 0.13
Nodes (18): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider, _effective_enabled() (+10 more)

### Community 73 - "Community 73"
Cohesion: 0.14
Nodes (29): _available_provider_balance(), balance_due_from_transactions(), cancel_active_links_for_reservation(), cancel_link(), create_link(), _create_mercadopago_preference(), deliver_link(), expire_link() (+21 more)

### Community 74 - "Community 74"
Cohesion: 0.13
Nodes (24): _active_push_subscriptions(), _actor_role(), _build_daily_report_body(), _deliver_email(), _deliver_in_app(), _deliver_push(), enqueue_notifications_for_event(), generate_due_daily_reports() (+16 more)

### Community 75 - "Community 75"
Cohesion: 0.09
Nodes (21): addLaundryItem(), createLaundryBatch(), LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead (+13 more)

### Community 76 - "Community 76"
Cohesion: 0.18
Nodes (27): AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, FactReservationRowKindEnum, FactRoomOccupancyDaily, FactRoomOccupancyStatusAtNightEnum, HotelAuditEvent, RoomStateEvent, OTAConnectionStatusEnum (+19 more)

### Community 77 - "Community 77"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 79 - "Community 79"
Cohesion: 0.12
Nodes (25): Return which promotions would apply and the resulting price breakdown     for a, Creates a new immutable version; the previous version is deactivated.     Reserv, simulate_promotion_pricing(), update_promotion(), Promotion, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, apply_promotions_to_night(), _conditions_kwargs() (+17 more)

### Community 80 - "Community 80"
Cohesion: 0.09
Nodes (18): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS, buildChannelSummaries() (+10 more)

### Community 81 - "Community 81"
Cohesion: 0.20
Nodes (26): SubscriptionEvent, _actor_payload(), _apply_plan(), _as_utc(), change_subscription_plan(), _compute_can_write(), end_trial(), ensure_subscription_seed() (+18 more)

### Community 82 - "Community 82"
Cohesion: 0.10
Nodes (21): CashHandoffSchemaRepairError, main(), missing_model_tables(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Apply the additive cash-handoff repair in one PostgreSQL transaction., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., Raised when the safe repair cannot run against the configured database. (+13 more)

### Community 83 - "Community 83"
Cohesion: 0.18
Nodes (26): _active_membership(), _audit(), audit_permission_denied(), can_role_hold_permission(), canonical_permission_code(), _engine_key(), ensure_permission_matrix_seeded(), get_effective_permission_details() (+18 more)

### Community 84 - "Community 84"
Cohesion: 0.11
Nodes (26): _apply_setting(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set or clear the current hotel id for tenant-scoped RLS policies., Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that (+18 more)

### Community 85 - "Community 85"
Cohesion: 0.22
Nodes (26): AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily, project_all_derived_facts_incremental(), _project_all_hotels_window(), project_operational_facts_to_clickhouse(), _project_operational_window(), project_reservation_facts_to_clickhouse() (+18 more)

### Community 86 - "Community 86"
Cohesion: 0.15
Nodes (22): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_job_path(), _flatten_payload_rows() (+14 more)

### Community 87 - "Community 87"
Cohesion: 0.11
Nodes (14): SimpleRateLimiter, Staff management endpoints for hotel public API keys., Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val, require_public_api_purpose(), _generate_secret(), _hash_secret(), HotelAPIKeyError (+6 more)

### Community 88 - "Community 88"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 89 - "Community 89"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+15 more)

### Community 90 - "Community 90"
Cohesion: 0.19
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 91 - "Community 91"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 92 - "Community 92"
Cohesion: 0.17
Nodes (22): TOTP MFA secrets and one-time recovery codes for normal user accounts., UserMfaRecoveryCode, UserMfaSecret, add_recovery_codes(), confirm_enrollment(), consume_mfa_code(), _consume_recovery_code(), _consume_totp_code() (+14 more)

### Community 93 - "Community 93"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 94 - "Community 94"
Cohesion: 0.17
Nodes (21): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+13 more)

### Community 95 - "Community 95"
Cohesion: 0.28
Nodes (23): _build_finish_gates(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status(), _merge_extra_policies() (+15 more)

### Community 96 - "Community 96"
Cohesion: 0.18
Nodes (5): make_res(), make_rooms(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 97 - "Community 97"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), Unit coverage for the notification outbox/service: dedupe, permission filtering,, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, test_daily_report_does_not_resend_same_local_date(), test_daily_report_dst_transition_shifts_the_utc_trigger_hour(), test_daily_report_uses_hotel_local_hour_not_utc() (+15 more)

### Community 98 - "Community 98"
Cohesion: 0.21
Nodes (22): _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error(), _is_public_webhook_base(), list_payment_link_tests(), _mercadopago_access_token() (+14 more)

### Community 99 - "Community 99"
Cohesion: 0.26
Nodes (22): _hotel(), A cash payment must be visible in caja even when the shift was not     opened ma, MercadoPago and bank-transfer payments settle the reservation balance     but mu, _reservation(), test_cash_movement_requires_open_session(), test_cash_payment_posts_income_movement_to_open_session(), test_cash_payment_with_surcharge_posts_gross_amount_to_caja(), test_cash_payment_without_open_session_is_rejected() (+14 more)

### Community 100 - "Community 100"
Cohesion: 0.12
Nodes (14): _make_guest(), _make_reservation(), test_api_key_name_unique_per_hotel_not_global(), test_delete_hotel_a_guest_does_not_affect_hotel_b(), test_guest_dedup_same_hotel_raises(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 101 - "Community 101"
Cohesion: 0.12
Nodes (16): _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_rls_migration(), _load_user_override_migration(), Return model relationships not covered by the core composite contract., Compile the additive RLS helpers through Alembic's PostgreSQL recorder.      Thi, Compile the additive RLS helpers through Alembic's PostgreSQL recorder.      Thi, Return model relationships not covered by the core composite contract. (+8 more)

### Community 102 - "Community 102"
Cohesion: 0.13
Nodes (18): EffectivePermissionsResponse, fetchEffectivePermissions(), PermissionCell, PermissionMatrix, PermissionOverrideRequest, PermissionOverrideResponse, preview_effective_permissions(), Expose the server-resolved capabilities used to drive the current UI. (+10 more)

### Community 103 - "Community 103"
Cohesion: 0.15
Nodes (19): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), DailyRateOut, DailyRatePrices, getCategoryDailyRates() (+11 more)

### Community 104 - "Community 104"
Cohesion: 0.11
Nodes (21): audited_change(), Record an AuditLog row for a successful entity mutation., Record an AuditLog row for a successful entity mutation., AuditLog, Append-only record of every significant mutation within a hotel tenant.     Do N, TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., System-triggered events (e.g. OTA sync) have no human actor. (+13 more)

### Community 105 - "Community 105"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 106 - "Community 106"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled(), test_get_guest_summary_includes_alerts_and_stays() (+3 more)

### Community 107 - "Community 107"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+4 more)

### Community 108 - "Community 108"
Cohesion: 0.12
Nodes (12): 67e4e68 fix(data-integrity): make audit_logs append-only at the database level, Tenant-scoped audit log for tracking mutations across core tables. Every write t, Reproduces the DELETE /api/stock/items/{id} incident: a stray NOT     NULL colum, test_audit_log_hotel_delete_is_restricted(), test_failed_audit_log_insert_does_not_roll_back_callers_change(), downgrade(), _hotel_fk(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs. (+4 more)

### Community 109 - "Community 109"
Cohesion: 0.18
Nodes (18): LinenItem, LinenLocation, LinenMovement, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, create_linen_item(), create_location(), current_stock(), delete_linen_item() (+10 more)

### Community 110 - "Community 110"
Cohesion: 0.19
Nodes (18): channel_for_hotel(), DomainEvent, format_sse(), get_realtime_client(), _get_redis_client(), iter_event_stream(), publish_domain_event(), Tenant-scoped realtime domain events backed by Redis/Valkey pub/sub.  Postgres r (+10 more)

### Community 111 - "Community 111"
Cohesion: 0.18
Nodes (14): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate (+6 more)

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (15): acquire_lease(), env_page(), FakeRender, mutations(), release_lease(), test_acquire_failure_rolls_back_marker_first_then_target_fields(), test_acquire_refuses_every_drift_without_mutation(), test_acquire_validates_before_writing_and_commits_id_last() (+7 more)

### Community 113 - "Community 113"
Cohesion: 0.12
Nodes (13): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Service adapter for PayPal payment integration.     Creates orders and processes, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification., Process a PayPal webhook notification. (+5 more)

### Community 114 - "Community 114"
Cohesion: 0.17
Nodes (16): 7a7afb0 fix(security): enforce password minimum on invitation accept, a714b07 fix(security): block replay-reactivation of revoked memberships, d333204 fix(security): require account auth for existing invitation accepts, client_with_db(), get_auth_context_target(), get_db_override_target(), _invitation_token(), owner_ctx() (+8 more)

### Community 115 - "Community 115"
Cohesion: 0.11
Nodes (13): SingleRateInput, useBulkUpdateRateField(), useBulkUpsertRates(), useCategoryDailyRates(), useRateCalendar(), useUpsertDailyRate(), BULK_ACTION_OPTIONS, BULK_FIELD_OPTIONS (+5 more)

### Community 116 - "Community 116"
Cohesion: 0.20
Nodes (12): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, mask_to_weekdays(), PromotionConditions, PromotionCreate, PromotionRead, PromotionSimulateRequest (+4 more)

### Community 117 - "Community 117"
Cohesion: 0.24
Nodes (18): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _date_token(), get_cached_availability_payload(), get_cached_home_payload(), _get_cached_or_compute() (+10 more)

### Community 118 - "Community 118"
Cohesion: 0.22
Nodes (18): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+10 more)

### Community 119 - "Community 119"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 120 - "Community 120"
Cohesion: 0.26
Nodes (18): _seed_hotels(), _seed_house_stock(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_create_vendor_creates_its_own_linen_location(), test_create_vendor_creates_its_own_stock_location() (+10 more)

### Community 121 - "Community 121"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 122 - "Community 122"
Cohesion: 0.16
Nodes (16): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), isAppHostname(), normalizeUrl(), PREVIEW_APP_HOST_SUFFIXES, PUBLIC_APP_URL, PUBLIC_SITE_URL (+8 more)

### Community 123 - "Community 123"
Cohesion: 0.21
Nodes (17): _available_room_for_conflict(), _compute_deposit_amount(), extend_reservation_stay(), _extension_amount(), _extension_conflicts(), _has_transactions(), _hotel_default_currency(), _invalidate_availability_cache() (+9 more)

### Community 124 - "Community 124"
Cohesion: 0.24
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 125 - "Community 125"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 126 - "Community 126"
Cohesion: 0.21
Nodes (14): _credentials(), E2ESafetyError, main(), normalize_sqlite_url(), prepare_e2e_environment(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet, Raised before any database-capable dependency is imported., Validate and normalize the only database target allowed for local E2E.      Both (+6 more)

### Community 127 - "Community 127"
Cohesion: 0.29
Nodes (15): add_movement(), approve_close_difference(), CashRegisterError, close_session(), confirm_cash_custody(), _confirmed_cash_movements_total(), get_latest_close_report(), get_open_session() (+7 more)

### Community 128 - "Community 128"
Cohesion: 0.29
Nodes (16): _collect_plan_entitlements(), delete_entitlement_override(), ensure_entitlements_seeded(), ensure_room_within_limit(), ensure_subscription(), entitlements_payload(), get_effective_room_limit(), get_entitlements() (+8 more)

### Community 130 - "Community 130"
Cohesion: 0.15
Nodes (11): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Lazy-initialize the MercadoPago SDK. (+3 more)

### Community 131 - "Community 131"
Cohesion: 0.24
Nodes (13): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+5 more)

### Community 132 - "Community 132"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 133 - "Community 133"
Cohesion: 0.20
Nodes (13): _active_room_blocks(), _alerts(), _available_with_review(), _cash_session(), daily_report(), _group(), _guest_name(), manual_review_alert_body() (+5 more)

### Community 134 - "Community 134"
Cohesion: 0.19
Nodes (13): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), _load_provider_evidence(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+5 more)

### Community 135 - "Community 135"
Cohesion: 0.17
Nodes (6): Regression contracts for the repository's agent-operations setup., run_qa_evidence_check(), test_qa_evidence_rejects_malformed_result_without_traceback(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_schema_accepts_full_catalog(), write_complete_qa_evidence()

### Community 136 - "Community 136"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 137 - "Community 137"
Cohesion: 0.38
Nodes (15): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1) and the linen ite, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, _teardown(), test_housekeeping_can_operate_remitos_but_not_manage_vendors(), test_linen_items_and_locations_are_hotel_scoped(), test_linen_summary_is_hotel_scoped_and_denies_roles_without_laundry_permission() (+7 more)

### Community 138 - "Community 138"
Cohesion: 0.34
Nodes (15): _client_with_db(), _override_auth(), test_effective_permissions_returns_only_current_role_capabilities(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_catalog_exposes_owner_only_and_normal_metadata(), test_permission_denied_is_audited(), test_permission_override_allows_receptionist_guest_edit(), test_permission_override_can_deny_receptionist_guest_edit() (+7 more)

### Community 139 - "Community 139"
Cohesion: 0.17
Nodes (8): BrokenRedis, FakeRedis, test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_operational_invalidation_clears_availability_and_analytics(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip()

### Community 140 - "Community 140"
Cohesion: 0.27
Nodes (15): _client_with_db(), _override_auth(), API-level coverage for stock items: delete-then-recreate (owner-reported bug), u, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Same convention as POST /api/payment-links: a client resending the     same POST, _second_hotel(), _teardown() (+7 more)

### Community 141 - "Community 141"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 142 - "Community 142"
Cohesion: 0.14
Nodes (10): RateCalendarResponse, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, RateEditorGrid(), RateEditorGridProps (+2 more)

### Community 143 - "Community 143"
Cohesion: 0.51
Nodes (14): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), test_correct_version_passes_optimistic_lock(), test_no_prohibido_tag_allows_checkin(), test_omitting_client_version_skips_check(), test_other_tags_do_not_block_checkin() (+6 more)

### Community 144 - "Community 144"
Cohesion: 0.33
Nodes (13): _enable_external_effects(), _fake_mp_gateway(), _reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service() (+5 more)

### Community 145 - "Community 145"
Cohesion: 0.31
Nodes (14): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- per-item stock consumption (out, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+6 more)

### Community 146 - "Community 146"
Cohesion: 0.18
Nodes (11): 2a14eb9 feat(security): add unified tenant-scoped audit timeline read endpoint, Public, redacted contracts for hotel security settings., RevokeAllSessionsResponse, SecurityCurrentUserRead, SecurityEventRead, SecurityEventsRead, SecurityOverviewRead, _headers() (+3 more)

### Community 147 - "Community 147"
Cohesion: 0.30
Nodes (11): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task() (+3 more)

### Community 148 - "Community 148"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 149 - "Community 149"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 150 - "Community 150"
Cohesion: 0.14
Nodes (13): Regression coverage for portable Graphify artifact normalization., A second normalizer run must leave already-portable artifacts unchanged., A second normalizer run must leave already-portable artifacts unchanged., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A generated-instruction symlink must not allow writes outside the repository., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+5 more)

### Community 151 - "Community 151"
Cohesion: 0.29
Nodes (12): _ctx(), _seed_hotel(), test_apply_promotions_never_goes_negative(), test_create_promotion_rejects_duplicate_code(), test_create_promotion_rejects_percentage_over_100(), test_deactivate_and_reactivate_promotion(), test_find_applicable_promotions_matches_guest_tag_type(), test_find_applicable_promotions_matches_typed_conditions() (+4 more)

### Community 152 - "Community 152"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 153 - "Community 153"
Cohesion: 0.47
Nodes (11): _make_reservation(), _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations(), test_auto_assign_no_double_booking() (+3 more)

### Community 154 - "Community 154"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), downgrade(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), _install_rls(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):, Create an active GuestRestriction for every currently-active (non-expired)     l (+5 more)

### Community 155 - "Community 155"
Cohesion: 0.32
Nodes (12): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., Raised when the local persona file cannot be created safely., _render() (+4 more)

### Community 156 - "Community 156"
Cohesion: 0.35
Nodes (12): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _origin(), _timestamp(), _valid_timestamp() (+4 more)

### Community 157 - "Community 157"
Cohesion: 0.15
Nodes (13): lifespan(), Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Initialize database on application startup., Initialize database on application startup., Initialize database on application startup., Initialize database on application startup., Initialize database on application startup. (+5 more)

### Community 158 - "Community 158"
Cohesion: 0.26
Nodes (8): emailOutboxPath, readLatestCode(), waitForCode(), cleanupEmailOutbox(), emailOutboxPath, readLatestCode(), resetEmailOutbox(), waitForCode()

### Community 159 - "Community 159"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 160 - "Community 160"
Cohesion: 0.23
Nodes (12): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a short lease and release it only if this worker owns it.      When the, Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a short lease and release it only if this worker owns it.      Redis/Val (+4 more)

### Community 161 - "Community 161"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 162 - "Community 162"
Cohesion: 0.37
Nodes (12): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id(), _normalize_required() (+4 more)

### Community 163 - "Community 163"
Cohesion: 0.21
Nodes (9): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi (+1 more)

### Community 164 - "Community 164"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 165 - "Community 165"
Cohesion: 0.38
Nodes (11): _manual_payload(), _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total(), test_manual_ota_requires_channel_and_external_id(), test_manual_ota_total_amount_and_currency_label_applied(), test_manual_ota_total_amount_bypasses_rate_plan_policy_restriction() (+3 more)

### Community 166 - "Community 166"
Cohesion: 0.35
Nodes (12): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_approval_creates_completed_transfer_transaction_and_updates_balance(), test_proof_bytes_are_tenant_scoped(), test_rejected_proof_requires_reason_and_cannot_be_approved(), test_submit_transfer_proof_allows_amount_covering_billing_adjustments(), test_submit_transfer_proof_reencodes_and_removes_exif() (+4 more)

### Community 167 - "Community 167"
Cohesion: 0.58
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _payload(), _seed_bookable_state(), test_co_owner_cannot_set_manual_total_amount_by_default(), test_manager_can_set_manual_total_amount_with_explicit_override(), test_manager_cannot_cross_manual_rate_security_ceiling() (+4 more)

### Community 168 - "Community 168"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 169 - "Community 169"
Cohesion: 0.15
Nodes (4): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 170 - "Community 170"
Cohesion: 0.24
Nodes (12): _backfill_defaults(), _contract_legacy_rows(), _copy_role_overrides(), downgrade(), _insert_permission_rows(), _install_user_override_rls(), expand RBAC catalog and add tenant-scoped user overrides  Revision ID: 20260813_, Install the PostgreSQL tenant policy; no-op on other dialects. (+4 more)

### Community 171 - "Community 171"
Cohesion: 0.27
Nodes (9): create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+1 more)

### Community 172 - "Community 172"
Cohesion: 0.24
Nodes (7): _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity()

### Community 173 - "Community 173"
Cohesion: 0.17
Nodes (10): DailyReportScheduleRead, DailyReportScheduleUpdate, NotificationListResponse, NotificationMarkReadRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, NotificationRead, PushSubscriptionRegisterRequest (+2 more)

### Community 174 - "Community 174"
Cohesion: 0.36
Nodes (10): _active_tag_filter(), add_tag(), _audit(), _get_guest(), list_active_tags(), _now(), quick_profile(), resolve_tag() (+2 more)

### Community 175 - "Community 175"
Cohesion: 0.35
Nodes (11): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _is_allowed_status_transition(), _normalize_status(), _parse_mercadopago_signature_header() (+3 more)

### Community 176 - "Community 176"
Cohesion: 0.26
Nodes (6): FakeRedis, _settings(), test_optional_backend_degrades_without_fabricating_an_event(), test_publish_domain_event_scopes_channel_and_increments_revision(), test_required_backend_raises_when_unavailable(), test_stream_endpoint_sets_no_cache_headers_and_tenant_stream()

### Community 177 - "Community 177"
Cohesion: 0.44
Nodes (11): _seed_daily_rates(), _seed_hotel(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_manual_override_skips_promotions_entirely() (+3 more)

### Community 178 - "Community 178"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 179 - "Community 179"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 180 - "Community 180"
Cohesion: 0.20
Nodes (10): fetchPermissionMatrix(), PermissionMatrixResponse, PermissionOverridePayload, PermissionRole, updatePermissionOverride(), getPermissionCodes(), permissionLabels, roleLabels (+2 more)

### Community 181 - "Community 181"
Cohesion: 0.29
Nodes (8): 9a39e0e fix(data-model): allow HotelAuditEvent to represent system/automated actors, _alter_user_column(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2, _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade(), _user_fk()

### Community 182 - "Community 182"
Cohesion: 0.35
Nodes (10): cleanup(), derive_test_dsn(), explain(), main(), measure(), percentile(), print_results(), run_alembic_upgrade() (+2 more)

### Community 183 - "Community 183"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 184 - "Community 184"
Cohesion: 0.31
Nodes (9): approve_transfer_proof(), _decode_image(), get_transfer_proof(), proof_file_path(), _proof_path(), reject_transfer_proof(), _reservation(), _safe_filename() (+1 more)

### Community 185 - "Community 185"
Cohesion: 0.29
Nodes (9): blocked_room_ids_for_range(), create_block(), get_block(), _invalidate_availability_cache(), list_active_blocks(), resolve_block(), room_block_overlap_filter(), room_has_active_block() (+1 more)

### Community 186 - "Community 186"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 187 - "Community 187"
Cohesion: 0.56
Nodes (10): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only() (+2 more)

### Community 188 - "Community 188"
Cohesion: 0.38
Nodes (10): _create_payload(), _reservation(), _seed_guest_inventory(), _seed_hotel(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_receptionist_cannot_override_until_canonical_permission_is_granted(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(), test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass() (+2 more)

### Community 189 - "Community 189"
Cohesion: 0.42
Nodes (8): _create_link(), _post_webhook(), _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing()

### Community 190 - "Community 190"
Cohesion: 0.27
Nodes (6): _reserve(), test_cancelled_reservation_is_excluded(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(), test_reservation_entirely_before_or_after_window_is_excluded(), test_reservation_spanning_the_window_is_returned_unclipped()

### Community 191 - "Community 191"
Cohesion: 0.42
Nodes (9): _link(), _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_out_of_order_webhook_cannot_regress_completed_payment_to_pending(), test_process_payment_replays_on_duplicate_idempotency_key() (+1 more)

### Community 192 - "Community 192"
Cohesion: 0.31
Nodes (8): _seed_hotel(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_override_allows_receptionist_guest_edit(), test_permission_override_can_deny_receptionist_guest_edit(), test_resolve_seeds_the_matrix_once_per_engine_not_per_call(), test_role_ceiling_ignores_a_stale_privilege_escalating_override()

### Community 193 - "Community 193"
Cohesion: 0.29
Nodes (10): _create_linen_tables(), downgrade(), _drop_kind_column(), _finalize_laundry_vendor_columns(), _migrate_linen_data(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li, Reverse of _migrate_linen_data: every linen_items row moves back into     stock_ (+2 more)

### Community 194 - "Community 194"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 196 - "Community 196"
Cohesion: 0.38
Nodes (9): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+1 more)

### Community 197 - "Community 197"
Cohesion: 0.33
Nodes (8): booking_webhook(), despegar_webhook(), expedia_webhook(), _guarded_json_payload(), _handle_ota_webhook(), Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar.

### Community 198 - "Community 198"
Cohesion: 0.20
Nodes (7): DailyRateRangeRow, PriceField, DAY_LABEL, PRICE_FIELDS, RateEditorMobileCards(), RateEditorMobileCardsProps, WEEKDAY_LABEL

### Community 199 - "Community 199"
Cohesion: 0.27
Nodes (9): 249a761 fix(security): add missing tenant RLS policy to hotel_api_keys, guest_alerts, reservation_movement_groups, ed0d0eb fix(review): chain RLS migration after audit-log-cascade fix, downgrade(), _install_rls(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state., _remove_rls() (+1 more)

### Community 200 - "Community 200"
Cohesion: 0.31
Nodes (9): v72 §16.2 reportable origin — the 7 business-level booking origins.      Derived, ReportableOriginEnum, v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic() (+1 more)

### Community 201 - "Community 201"
Cohesion: 0.33
Nodes (8): create_audit_log(), model_snapshot(), payload_json(), queue_audit_log(), Best-effort audit log: a failure here must never discard the caller's     real,, Allow-list guest audit context before persistence or external projection., safe_create_audit_log(), sanitize_audit_payload()

### Community 202 - "Community 202"
Cohesion: 0.31
Nodes (8): external_effects_enabled(), google_login_enabled(), inbound_provider_events_enabled(), Fail-closed policy gates for provider traffic and provider-originated events.  T, require_external_connections(), require_external_effects(), require_google_login(), require_inbound_provider_events()

### Community 203 - "Community 203"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 204 - "Community 204"
Cohesion: 0.38
Nodes (9): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), quote_rate_plan_stay(), _resolve_commission_amount(), _select_fx_policy(), _select_rate_plan_price() (+1 more)

### Community 206 - "Community 206"
Cohesion: 0.49
Nodes (9): _client_with_db(), _override_auth(), _seed_fully_paid_reservation(), test_add_companion_during_checkin_flow_appears_in_additional_guests(), test_add_companion_exceeding_capacity_returns_clear_400(), test_checkin_captures_missing_fields_in_same_request(), test_checkin_without_new_fields_fails_with_clear_message(), test_partial_checkin_reaches_pre_check_in_then_final_checkin() (+1 more)

### Community 207 - "Community 207"
Cohesion: 0.58
Nodes (9): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_manager_has_no_access_to_commercial_configuration() (+1 more)

### Community 209 - "Community 209"
Cohesion: 0.47
Nodes (7): _build_client(), _cleanup(), _override_auth(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_reactivate_deactivated_surcharge_via_patch()

### Community 210 - "Community 210"
Cohesion: 0.38
Nodes (7): _make_hotel(), _make_reservation(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 211 - "Community 211"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 212 - "Community 212"
Cohesion: 0.42
Nodes (7): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_cannot_create_room_block_by_default(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 213 - "Community 213"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_blocked_for_past_check_in(), test_change_dates_blocked_when_room_conflict(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_pending_updates_dates_and_price(), test_extend_stay_blocked_for_zero_or_negative_days(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 214 - "Community 214"
Cohesion: 0.33
Nodes (8): reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields(), test_room_move_endpoint_rejects_capacity_overflow_and_returns_delta_on_reprice(), test_room_move_rejects_receptionist_without_room_move_permission(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_update_mobility_restriction_triggers_reoptimization()

### Community 215 - "Community 215"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 216 - "Community 216"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 217 - "Community 217"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 218 - "Community 218"
Cohesion: 0.42
Nodes (8): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity()

### Community 219 - "Community 219"
Cohesion: 0.44
Nodes (8): _catalog(), initialize(), _json_bytes(), main(), OperationalQAError, _utc_now(), validate(), _write()

### Community 220 - "Community 220"
Cohesion: 0.22
Nodes (9): _is_demo_mode_enabled(), Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed., Check whether demo-only utilities should be exposed. (+1 more)

### Community 221 - "Community 221"
Cohesion: 0.28
Nodes (5): createReservation(), localIsoDate(), owner, parseMoney(), readStat()

### Community 222 - "Community 222"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 223 - "Community 223"
Cohesion: 0.33
Nodes (8): GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate, Pydantic schemas for Guest and companions.

### Community 224 - "Community 224"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 225 - "Community 225"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 226 - "Community 226"
Cohesion: 0.50
Nodes (8): _auth(), _client(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and, test_daily_report_schedule_is_owner_co_owner_only(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_preferences_crud(), test_push_subscription_register_and_unregister()

### Community 227 - "Community 227"
Cohesion: 0.50
Nodes (8): _outbox_event_types(), _owner(), Integration coverage: the real domain-event call sites (reservation lifecycle, c, test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), test_no_show_enqueues_notification(), test_reservation_lifecycle_enqueues_notifications()

### Community 228 - "Community 228"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database., _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category()

### Community 229 - "Community 229"
Cohesion: 0.31
Nodes (4): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation(), test_payment_links_api_rejects_manager_without_cash_operate()

### Community 230 - "Community 230"
Cohesion: 0.39
Nodes (5): _auth(), _client(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_user_override_rejects_self_elevation_and_cross_hotel_id_without_disclosure()

### Community 231 - "Community 231"
Cohesion: 0.56
Nodes (8): _client(), _close(), test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(), test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation(), test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation(), test_stock_read_movement_and_admin_are_independently_enforced_without_mutation()

### Community 232 - "Community 232"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 233 - "Community 233"
Cohesion: 0.33
Nodes (7): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history(), test_skip_and_limit_page_through_results()

### Community 234 - "Community 234"
Cohesion: 0.56
Nodes (7): _role_connection(), _seed_engine(), _seed_session(), test_after_commit_listener_reapplies_hotel_context(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_no_tenant_context_hides_all_rows(), test_tenant_isolation_blocks_cross_hotel_reads()

### Community 235 - "Community 235"
Cohesion: 0.25
Nodes (3): RenderRequester, Protocol, AnalyticsAIProvider

### Community 236 - "Community 236"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 237 - "Community 237"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 238 - "Community 238"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 239 - "Community 239"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 240 - "Community 240"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 241 - "Community 241"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 242 - "Community 242"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 243 - "Community 243"
Cohesion: 0.39
Nodes (6): example(), Regression tests for final provider-evidence continuity., test_any_provider_subject_drift_is_rejected(), test_cli_rejects_symlinked_manifest(), test_final_observation_cannot_predate_probes(), test_only_a_newer_observation_timestamp_may_change()

### Community 244 - "Community 244"
Cohesion: 0.46
Nodes (6): _seed_hotel(), _seed_reservation(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_permission_ceiling_cannot_be_overridden_for_reception(), test_guest_export_permission_defaults_and_override_are_hotel_scoped()

### Community 245 - "Community 245"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 246 - "Community 246"
Cohesion: 0.54
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 247 - "Community 247"
Cohesion: 0.46
Nodes (7): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 248 - "Community 248"
Cohesion: 0.50
Nodes (7): opened_cash_register(), _payment(), _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 249 - "Community 249"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 250 - "Community 250"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 251 - "Community 251"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 252 - "Community 252"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 253 - "Community 253"
Cohesion: 0.33
Nodes (2): mercadopago_payment_link_webhook(), _mercadopago_webhook_impl()

### Community 254 - "Community 254"
Cohesion: 0.48
Nodes (5): create_payment_surcharge(), deactivate_payment_surcharge(), _get_surcharge_or_404(), _has_per_method_nightly_price(), update_payment_surcharge()

### Community 255 - "Community 255"
Cohesion: 0.29
Nodes (6): Schemas for hotel-scoped waitlist entries., WaitlistEntryCreate, WaitlistEntryRead, WaitlistEntryUpdate, WaitlistPromoteRequest, WaitlistPromoteResponse

### Community 256 - "Community 256"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 257 - "Community 257"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 258 - "Community 258"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 259 - "Community 259"
Cohesion: 0.38
Nodes (4): _make_completed_transaction(), Regression coverage for app/api/reports.py's financial endpoints (/api/reports/d, test_daily_report_totals_a_completed_transaction_without_crashing(), test_revenue_report_totals_multiple_completed_transactions_without_crashing()

### Community 260 - "Community 260"
Cohesion: 0.67
Nodes (6): _auth(), _client(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_restriction_api_permissions_tenant_isolation_and_event(), test_restriction_override_reason_rejects_whitespace()

### Community 261 - "Community 261"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_legacy_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags()

### Community 262 - "Community 262"
Cohesion: 0.43
Nodes (6): _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly, Hand-insert a real 'linen' StockItem plus movements and a laundry     vendor/pri, _run_alembic(), _seed_pre_split_data(), test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade()

### Community 263 - "Community 263"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 264 - "Community 264"
Cohesion: 0.71
Nodes (6): _build_client(), _cleanup(), _override_auth(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 265 - "Community 265"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_pre_migration_surcharge(), test_promotions_migration_owns_reversible_postgresql_rls(), test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data()

### Community 266 - "Community 266"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_pre_revision(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions()

### Community 267 - "Community 267"
Cohesion: 0.29
Nodes (3): _no_real_db(), Every response must carry baseline security headers so the SPA and API are not m, The unmatched-path SPA fallback still depends on get_db; stub it so this     tes

### Community 268 - "Community 268"
Cohesion: 0.57
Nodes (5): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits()

### Community 269 - "Community 269"
Cohesion: 0.57
Nodes (6): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 270 - "Community 270"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 271 - "Community 271"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 272 - "Community 272"
Cohesion: 0.80
Nodes (5): build_sql(), _literal(), load_env(), main(), SharedSandboxBootstrapError

### Community 273 - "Community 273"
Cohesion: 0.40
Nodes (3): 3dee498 fix(review): chain permission-metadata migration after latest head, 77fa337 feat(security): add critical/step-up/delegable metadata and optimistic versioning to permission catalog, add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 274 - "Community 274"
Cohesion: 0.33
Nodes (3): backendURL, credentials, StoredSession

### Community 275 - "Community 275"
Cohesion: 0.33
Nodes (1): credentials

### Community 276 - "Community 276"
Cohesion: 0.40
Nodes (3): authHeaders(), ensureOnboarding(), hotelId

### Community 277 - "Community 277"
Cohesion: 0.33
Nodes (5): LaundryRemito, LaundryRemitoLine, LaundryVendor, LaundryVendorPrice, Laundry vendor, pricing and remito (delivery note) models.  An outsourced laundr

### Community 278 - "Community 278"
Cohesion: 0.33
Nodes (4): Waitlist / overbooking list model — v72 §9.  When the hotel is at capacity for a, Single guest waiting for a room in a given category for a date range.     Priori, WaitlistEntry, WaitlistStatusEnum

### Community 279 - "Community 279"
Cohesion: 0.40
Nodes (5): annotate_analytics_payload(), _as_utc_datetime(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL, Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 280 - "Community 280"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 281 - "Community 281"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 282 - "Community 282"
Cohesion: 0.60
Nodes (5): _build_message(), ensure_hotel_gmail_ready(), HotelOutboundIdentity, HotelOutboundSendResult, send_hotel_email()

### Community 283 - "Community 283"
Cohesion: 0.53
Nodes (4): CanonicalPricingResult, compute_canonical_stay_pricing(), _hotel_default_currency(), _quantize()

### Community 284 - "Community 284"
Cohesion: 0.47
Nodes (5): _active_reservation_conflicts_for_room(), create_grouped_room_move(), get_group(), list_groups(), revert_group()

### Community 285 - "Community 285"
Cohesion: 0.53
Nodes (5): _create_receptionist_user(), _open_cash_session(), POST /api/payments and GET /api/payments/summary/{id} only allowed     owner/co_, _receptionist_context(), test_receptionist_can_view_and_make_reservation_payments()

### Community 286 - "Community 286"
Cohesion: 0.47
Nodes (4): _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 287 - "Community 287"
Cohesion: 0.53
Nodes (5): _alembic(), _assert_migrated(), Data-contract regression for the payment-link execution-mode migration., _seed_legacy_links(), test_payment_link_migration_backfills_provider_history_and_reupgrades()

### Community 288 - "Community 288"
Cohesion: 0.60
Nodes (5): _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 289 - "Community 289"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 290 - "Community 290"
Cohesion: 0.53
Nodes (4): _override_auth(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms()

### Community 291 - "Community 291"
Cohesion: 0.53
Nodes (4): test_env_file_requires_owner_only_permissions(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), _values()

### Community 292 - "Community 292"
Cohesion: 0.33
Nodes (6): _load_master_admin_bypass_migration(), C2: app/master_admin/router.py queries Subscription directly, and     transitive, C2: app/master_admin/router.py queries Subscription directly, and     transitive, C2: app/master_admin/router.py queries Subscription directly, and     transitive, test_master_admin_bypass_migration_only_touches_tables_the_panel_actually_queries(), test_master_admin_bypass_migration_uses_the_documented_session_flag()

### Community 293 - "Community 293"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 294 - "Community 294"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 295 - "Community 295"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), downgrade(), _drop_successor_reference(), Add zero-balance cash rotation and custody handoffs., upgrade()

### Community 296 - "Community 296"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 297 - "Community 297"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 298 - "Community 298"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, upgrade()

### Community 299 - "Community 299"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 300 - "Community 300"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 301 - "Community 301"
Cohesion: 0.80
Nodes (4): _archive_historical(), _build_cases(), main(), _write_json()

### Community 302 - "Community 302"
Cohesion: 0.40
Nodes (5): checkin_partial(), B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan

### Community 303 - "Community 303"
Cohesion: 0.40
Nodes (1): credentials

### Community 304 - "Community 304"
Cohesion: 0.40
Nodes (4): Stock and inventory movement models., StockItem, StockLocation, StockMovement

### Community 305 - "Community 305"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 306 - "Community 306"
Cohesion: 0.40
Nodes (1): HotelIdentityPayload

### Community 307 - "Community 307"
Cohesion: 0.50
Nodes (4): compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 308 - "Community 308"
Cohesion: 0.60
Nodes (4): generate_daily_reports(), process_outbox(), Celery tasks for the notification backend: process the outbox (bounded retry/exp, _session()

### Community 309 - "Community 309"
Cohesion: 0.70
Nodes (4): _active_hotel_ids(), _run_scheduled_reports(), send_morning_reports(), send_nightly_reports()

### Community 310 - "Community 310"
Cohesion: 0.80
Nodes (4): _link(), _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 311 - "Community 311"
Cohesion: 0.80
Nodes (4): _auth_for(), _seed_guests(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 312 - "Community 312"
Cohesion: 0.60
Nodes (4): Same per-location bug as stock_service: an 'out' at location B must be     valid, _seed_hotels(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped()

### Community 313 - "Community 313"
Cohesion: 0.40
Nodes (1): Response

### Community 314 - "Community 314"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 315 - "Community 315"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 316 - "Community 316"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 317 - "Community 317"
Cohesion: 0.60
Nodes (3): _quote(), test_confirmed_reservation_stores_pricing_revision(), test_reservation_rejects_quote_after_pricing_revision_changes()

### Community 320 - "Community 320"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 321 - "Community 321"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 322 - "Community 322"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 323 - "Community 323"
Cohesion: 0.60
Nodes (4): _check_clause(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in, upgrade()

### Community 324 - "Community 324"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 325 - "Community 325"
Cohesion: 0.50
Nodes (4): main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only., Replace this repository's absolute root in generated instructions only.

### Community 326 - "Community 326"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 327 - "Community 327"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 329 - "Community 329"
Cohesion: 0.83
Nodes (3): cassandra_healthcheck(), _contact_points(), get_cassandra_session()

### Community 330 - "Community 330"
Cohesion: 0.50
Nodes (1): credentials

### Community 331 - "Community 331"
Cohesion: 0.50
Nodes (3): _LenientDateTime, DateTime that also accepts ISO-formatted strings on bind.      Callers occasiona, TypeDecorator

### Community 332 - "Community 332"
Cohesion: 0.67
Nodes (3): GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti, _receptionist_context(), test_receptionist_can_view_operations_summary_and_pending_actions()

### Community 334 - "Community 334"
Cohesion: 0.67
Nodes (2): _override_auth(), test_receptionist_can_get_price_quote()

### Community 335 - "Community 335"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 336 - "Community 336"
Cohesion: 0.67
Nodes (3): B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio, _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite()

### Community 338 - "Community 338"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 339 - "Community 339"
Cohesion: 0.50
Nodes (1): TestBookingWebhook

### Community 340 - "Community 340"
Cohesion: 0.83
Nodes (3): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations()

### Community 341 - "Community 341"
Cohesion: 0.50
Nodes (4): Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., test_validate_runtime_security_ignores_incomplete_optional_integrations()

### Community 342 - "Community 342"
Cohesion: 0.50
Nodes (4): OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, test_validate_runtime_security_rejects_localhost_redirect_when_service_configured()

### Community 343 - "Community 343"
Cohesion: 0.67
Nodes (3): _index_names(), Focused regression tests for the TECH-0063 OLTP audit fixes., test_hot_path_composite_indexes_exist_in_models()

### Community 345 - "Community 345"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 346 - "Community 346"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 347 - "Community 347"
Cohesion: 0.50
Nodes (1): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho

### Community 348 - "Community 348"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 349 - "Community 349"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 350 - "Community 350"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 351 - "Community 351"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 352 - "Community 352"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 353 - "Community 353"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 354 - "Community 354"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 355 - "Community 355"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 356 - "Community 356"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 357 - "Community 357"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 358 - "Community 358"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 359 - "Community 359"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 360 - "Community 360"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 361 - "Community 361"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 362 - "Community 362"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 363 - "Community 363"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 364 - "Community 364"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 365 - "Community 365"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 366 - "Community 366"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 367 - "Community 367"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 368 - "Community 368"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 369 - "Community 369"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 370 - "Community 370"
Cohesion: 0.50
Nodes (1): Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re

### Community 371 - "Community 371"
Cohesion: 0.50
Nodes (1): Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for

### Community 372 - "Community 372"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 373 - "Community 373"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 374 - "Community 374"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 375 - "Community 375"
Cohesion: 0.50
Nodes (1): stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision

### Community 376 - "Community 376"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 377 - "Community 377"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 378 - "Community 378"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 379 - "Community 379"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 380 - "Community 380"
Cohesion: 0.50
Nodes (1): laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre

### Community 381 - "Community 381"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 382 - "Community 382"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 383 - "Community 383"
Cohesion: 0.50
Nodes (1): laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7

### Community 384 - "Community 384"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 385 - "Community 385"
Cohesion: 0.67
Nodes (1): owner

### Community 386 - "Community 386"
Cohesion: 0.67
Nodes (1): credentials

### Community 388 - "Community 388"
Cohesion: 1.00
Nodes (2): 0286caf feat(security): add core temporary one-time action authorization (TECH-0041), 68c5ae6 fix(migrations): chain temporary action grants migration onto permission metadata head

### Community 389 - "Community 389"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

## Knowledge Gaps
- **828 isolated node(s):** `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`, `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis` (+823 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 132`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 141`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 232`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 253`** (2 nodes): `mercadopago_payment_link_webhook()`, `_mercadopago_webhook_impl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 275`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 303`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 306`** (1 nodes): `HotelIdentityPayload`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 313`** (1 nodes): `Response`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 330`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 334`** (2 nodes): `_override_auth()`, `test_receptionist_can_get_price_quote()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 339`** (1 nodes): `TestBookingWebhook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 346`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 347`** (1 nodes): `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 348`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 349`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 350`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 351`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 352`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 353`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 354`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 355`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 356`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 357`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 358`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 359`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 360`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 361`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 362`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 363`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 364`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 365`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 366`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 367`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 368`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 369`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 370`** (1 nodes): `Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 371`** (1 nodes): `Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 372`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 373`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 374`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 375`** (1 nodes): `stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 376`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 377`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 378`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 379`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 380`** (1 nodes): `laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 381`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 382`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 383`** (1 nodes): `laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 384`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 385`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 386`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 388`** (2 nodes): `0286caf feat(security): add core temporary one-time action authorization (TECH-0041)`, `68c5ae6 fix(migrations): chain temporary action grants migration onto permission metadata head`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 389`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 4` to `Community 14`, `Community 10`, `Community 3`, `Community 157`, `Community 66`, `Community 220`, `Community 104`, `Community 60`, `Community 51`, `Community 131`, `Community 36`, `Community 1`, `Community 69`, `Community 76`, `Community 85`, `Community 12`, `Community 108`, `Community 17`, `Community 111`, `Community 107`, `Community 171`, `Community 331`, `Community 33`, `Community 31`, `Community 0`, `Community 19`, `Community 5`, `Community 277`, `Community 109`, `Community 54`, `Community 132`, `Community 39`, `Community 32`, `Community 24`, `Community 16`, `Community 79`, `Community 116`, `Community 200`, `Community 304`, `Community 81`, `Community 92`, `Community 34`, `Community 278`, `Community 82`, `Community 28`, `Community 91`, `Community 137`, `Community 228`, `Community 71`, `Community 140`, `Community 145`, `Community 292`, `Community 101`?**
  _High betweenness centrality (0.129) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 4` to `Community 15`, `Community 19`, `Community 12`, `Community 10`, `Community 7`, `Community 8`, `Community 1`, `Community 87`, `Community 14`, `Community 51`, `Community 76`, `Community 69`, `Community 0`, `Community 24`, `Community 282`, `Community 58`, `Community 64`, `Community 54`, `Community 95`, `Community 39`, `Community 98`, `Community 283`, `Community 81`, `Community 85`, `Community 6`, `Community 104`, `Community 28`, `Community 99`, `Community 91`, `Community 3`, `Community 137`, `Community 20`, `Community 262`, `Community 60`, `Community 32`, `Community 339`, `Community 16`, `Community 140`, `Community 145`, `Community 59`, `Community 17`, `Community 45`?**
  _High betweenness centrality (0.065) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 10`, `Community 4`, `Community 1`, `Community 12`, `Community 14`, `Community 51`, `Community 36`, `Community 76`, `Community 69`, `Community 111`, `Community 33`, `Community 24`, `Community 39`, `Community 58`, `Community 73`, `Community 99`, `Community 339`, `Community 17`, `Community 45`?**
  _High betweenness centrality (0.033) - this node is a cross-community bridge._
- **Are the 943 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 943 INFERRED edges - model-reasoned connections that need verification._
- **Are the 944 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 944 INFERRED edges - model-reasoned connections that need verification._
- **Are the 914 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 914 INFERRED edges - model-reasoned connections that need verification._
- **Are the 771 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Room` has 771 INFERRED edges - model-reasoned connections that need verification._