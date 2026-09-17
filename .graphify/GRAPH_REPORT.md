# Graph Report - .  (2026-09-17)

## Corpus Check
- Large corpus: 1254 files · ~1,823,552 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 13496 nodes · 77155 edges · 477 communities detected
- Extraction: 65% EXTRACTED · 35% INFERRED · 0% AMBIGUOUS · INFERRED: 26856 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 26856 · ON_BRANCH: 24045 · contains: 7274 · calls: 5295 · MODIFIES: 5126 · rationale_for: 3610 · imports: 1407 · imports_from: 1117 · PARENT_OF: 887 · inherits: 797 · method: 737 · re_exports: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1254 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 12 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `7c5f229`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 1433 edges
2. `ReservationStatusEnum` - 1370 edges
3. `HotelConfiguration` - 1342 edges
4. `Room` - 1232 edges
5. `RoomCategory` - 1089 edges
6. `Guest` - 1006 edges
7. `RoomStatusEnum` - 744 edges
8. `Base` - 676 edges
9. `ReservationError` - 645 edges
10. `ReservationSourceEnum` - 542 edges

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
Nodes (611): daily_report(), occupancy_report(), FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c (+603 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (497): agent-linensplit, agent-login, agent-mobilenav, agent-otafix, agent-settlement, agent-stockedit, agent-stocksplit, agent-ux (+489 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (291): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+283 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (389): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+381 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (358): AuthUser, _assert_assignable_role(), _assert_manageable_membership(), invite_user(), inviteUser(), list_users(), listUsers(), _membership_user_info() (+350 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (152): main(), valid_https(), _archive_historical(), _build_cases(), main(), _write_json(), Shared, secret-safe binding for the Render QA bootstrap configuration., _authorize_override() (+144 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (317): checkin_partial(), B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan, add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest. (+309 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (258): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), Category (+250 more)

### Community 8 - "Community 8"
Cohesion: 0.03
Nodes (289): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses the ca, Calculate pricing for a potential booking without persisting it.     Uses the ca (+281 more)

### Community 9 - "Community 9"
Cohesion: 0.01
Nodes (219): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), getGuestProhibitedDetail() (+211 more)

### Community 10 - "Community 10"
Cohesion: 0.14
Nodes (236): CheckInRequest, FastAPI routes for Check-in / Check-out., cancel_reservation(), change_dates(), create_new_reservation(), create_or_update_manual_ota(), create_reservation_charge(), _ensure_action_permission() (+228 more)

### Community 11 - "Community 11"
Cohesion: 0.01
Nodes (223): Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, _require_demo_mode(), reset_demo(), seed_demo(), Base, Base class for all ORM models. (+215 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (192): booking_webhook(), despegar_webhook(), expedia_webhook(), _guarded_json_payload(), _handle_ota_webhook(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia. (+184 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (182): FxSnapshotRead, create_laundry_remito(), _housekeeping_remito(), LinenItemCreate, LinenItemRead, LinenLocationCreate, LinenLocationRead, LinenMovementCreate (+174 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (104): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online(), Demo-only utilities: seed sample data and reset the database. Exposed only when, 4d12b77 perf(backend): fix N+1 queries and missing indexes (TECH-0063), 5faef28 fix(reservations): trim document_number for bulk guest lookup, bound occupancy report range (+96 more)

### Community 15 - "Community 15"
Cohesion: 0.06
Nodes (187): Tenant-scoped security overview and current-user session revocation., HotelMembership, HotelRoleVisibilityWindow, Reservation visibility limits configured independently per hotel role.      A mi, HotelPermissionOverride, Permission, An employee-specific permission decision within one hotel membership., An employee-specific permission decision within one hotel membership. (+179 more)

### Community 16 - "Community 16"
Cohesion: 0.02
Nodes (154): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsCategoryDetailPage(), AnalyticsChannelsPage(), AnalyticsCompanyDetailPage(), AnalyticsEnvelope, analyticsErrorMessage() (+146 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (159): apple_callback(), _apple_full_name(), apple_login(), _apple_login_config(), apple_start(), _attach_user_session_cookies(), _audit_security_event(), auth_providers() (+151 more)

### Community 18 - "Community 18"
Cohesion: 0.02
Nodes (111): export_cash_ledger_csv(), addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashCustodyHandoff, CashDailyCollector, CashDailyEntry, CashDailyPaymentMethod (+103 more)

### Community 19 - "Community 19"
Cohesion: 0.02
Nodes (90): acceptInvitation(), AuthProvidersResponse, AuthResponse, getInvitationInfo(), loginWithApple(), loginWithGoogle(), RegistrationResponse, requestVerification() (+82 more)

### Community 20 - "Community 20"
Cohesion: 0.02
Nodes (90): _app_secret(), _nested(), Meta Cloud API webhook boundary.  The endpoint verifies Meta's signature before, Walk a chain of dict keys, tolerating non-dict values at any level.      Meta's, receive_webhook(), _verify_token(), verify_webhook(), 7c5f229 Merge WhatsApp CRM W0 and W1 foundation (+82 more)

### Community 21 - "Community 21"
Cohesion: 0.03
Nodes (84): addLaundryItem(), createLaundryBatch(), LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead (+76 more)

### Community 22 - "Community 22"
Cohesion: 0.03
Nodes (75): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), createPricePeriod(), DailyRateOut, DailyRatePrices (+67 more)

### Community 23 - "Community 23"
Cohesion: 0.03
Nodes (41): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+33 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (78): CashCloseReport, CashCustodyHandoff, CashCustodyStatusEnum, CashMovement, CashMovementTypeEnum, CashSession, CashSessionStatusEnum, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca (+70 more)

### Community 25 - "Community 25"
Cohesion: 0.11
Nodes (70): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, FactReservationRowKindEnum, FactRoomOccupancyDaily, FactRoomOccupancyStatusAtNightEnum (+62 more)

### Community 26 - "Community 26"
Cohesion: 0.09
Nodes (63): DailyReportSchedule, Notification, NotificationChannelEnum, NotificationOutbox, NotificationOutboxStatusEnum, NotificationPreference, PushSubscription, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+55 more)

### Community 27 - "Community 27"
Cohesion: 0.05
Nodes (64): SimpleRateLimiter, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterBillingPolicy, MasterStripeWebhookEvent, audit_master_action(), create_master_admin_mfa_challenge() (+56 more)

### Community 28 - "Community 28"
Cohesion: 0.09
Nodes (50): Operational task inbox and shift handoff endpoints., RoomBlockCreate, RoomBlockRead, OperationalTask, OperationalTaskEvent, OperationalTaskPriorityEnum, OperationalTaskStatusEnum, OperationalTaskTypeEnum (+42 more)

### Community 29 - "Community 29"
Cohesion: 0.05
Nodes (37): 2090dc4 feat(security): make TOTP MFA mandatory for Master Admin (TECH-0023), 3690b59 fix(security): close master admin control plane gaps (TECH-0071), 9a70090 feat(security): add optional TOTP MFA for master admin (TECH-0071), b355c74 fix(security): redact sensitive metadata in master admin audit events, da6d6d2 fix(security): shorten master admin session TTL (TECH-0071), complete_mfa_login(), dashboard_summary(), login() (+29 more)

### Community 30 - "Community 30"
Cohesion: 0.08
Nodes (47): APIKeyPurposeEnum, PaymentLinkRead, PublicReservationRead, ReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead, PublicAvailabilityResponse (+39 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (62): Subscription, entitlements_for_hotel(), Alias to expose the snapshot in a name aligned with the spec wording., Alias to expose the snapshot in a name aligned with the spec wording., Alias to expose the snapshot in a name aligned with the spec wording., Alias to expose the snapshot in a name aligned with the spec wording., _collect_plan_entitlements(), delete_entitlement_override() (+54 more)

### Community 32 - "Community 32"
Cohesion: 0.04
Nodes (34): create_movement(), createStockItem(), createStockLocation(), createStockMovement(), CurrentStock, deleteStockItem(), _ensure_adjustment_permission(), get_stock_summary() (+26 more)

### Community 33 - "Community 33"
Cohesion: 0.07
Nodes (43): 114b319 Fix invalid verification email requests, 29236bf feat(security): add Google account unlink endpoint with reauthentication, 300d128 feat(security): audit-log MFA, login, and Google account-linking events, 9f4f9ac feat(security): audit-log MFA, login, and Google account-linking events, _auth_headers(), _complete_onboarding(), _configure_resend(), _enroll_and_confirm_mfa() (+35 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (51): create_restriction(), _get_tenant_guest(), list_restrictions(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, resolve_restriction(), GuestRestriction, GuestRestrictionStatusEnum (+43 more)

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (32): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, _append_action_event_message(), apply_action_run_draft(), approve_action_run() (+24 more)

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (52): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+44 more)

### Community 37 - "Community 37"
Cohesion: 0.11
Nodes (53): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+45 more)

### Community 38 - "Community 38"
Cohesion: 0.07
Nodes (50): AcceptPayload, InvitePayload, InviteResponse, PrimaryOwnerTransferPayload, User management per hotel (owners/co-owners)., Transfer billing/property ownership after explicit account reauth., Transfer billing/property ownership after explicit account reauth., Transfer billing/property ownership after explicit account reauth. (+42 more)

### Community 39 - "Community 39"
Cohesion: 0.14
Nodes (49): _assert_manageable_membership(), create_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Keep permission exceptions aligned with the staff-management boundary., Keep permission exceptions aligned with the staff-management boundary., Keep permission exceptions aligned with the staff-management boundary., Ask for one exceptional permission without changing the requester's role., Ask for one exceptional permission without changing the requester's role. (+41 more)

### Community 40 - "Community 40"
Cohesion: 0.05
Nodes (45): Base, MasterStripeSettings, MasterSystemEmailConnection, FxPolicy, ProductRoomCompatibility, RatePlan, RatePlanPrice, Commercial domain models for the next reservation/OTA foundation.  These tables (+37 more)

### Community 41 - "Community 41"
Cohesion: 0.11
Nodes (42): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, LLMFeedbackEvent (+34 more)

### Community 42 - "Community 42"
Cohesion: 0.10
Nodes (47): _b64url_decode(), _b64url_encode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), _canonical_json(), canonical_provider_evidence_json(), cli() (+39 more)

### Community 43 - "Community 43"
Cohesion: 0.07
Nodes (36): admin_comped_override(), change_plan(), changeSubscriptionPlan(), getSubscriptionStatus(), listSubscriptionPlans(), _remaining_trial_days(), _serialize_status_payload(), start_subscription_trial() (+28 more)

### Community 44 - "Community 44"
Cohesion: 0.07
Nodes (39): connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration(), get_status() (+31 more)

### Community 45 - "Community 45"
Cohesion: 0.13
Nodes (29): 6e6d179 Prepare release candidate for landing and onboarding, 87b0eb6 Improve marketing SEO content, linking, and metadata, b48fd42 Add public marketing inquiry flow and SEO, d7e130f Merge the Hotels-PMS landing page rebuild, Seo(), SeoProps, StructuredData, resolveAppUrl() (+21 more)

### Community 46 - "Community 46"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+29 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (38): _bootstrap_environment(), _evidence_payload(), _local_evidence_payload(), _provider_manifest(), _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_local_test_database_target() (+30 more)

### Community 48 - "Community 48"
Cohesion: 0.11
Nodes (14): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session(), TestAutoCashEntry (+6 more)

### Community 49 - "Community 49"
Cohesion: 0.15
Nodes (39): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _deployment_git_identity(), _deployment_hosts(), _dict() (+31 more)

### Community 50 - "Community 50"
Cohesion: 0.05
Nodes (35): fetchPermissionCatalog(), fetchPermissionMatrix(), fetchRolePermissionProfiles(), fetchUserPermissionOverrides(), fetchVisibilityWindows(), PermissionCatalogItem, PermissionMatrixResponse, PermissionOverridePayload (+27 more)

### Community 51 - "Community 51"
Cohesion: 0.07
Nodes (28): createPromotion(), deactivatePromotion(), listPromotions(), Promotion, PromotionAppliedEntry, PromotionBenefitType, PromotionConditions, PromotionCreatePayload (+20 more)

### Community 52 - "Community 52"
Cohesion: 0.09
Nodes (16): GCSObjectStorage, get_object_storage(), LocalObjectStorage, ObjectStat, ObjectStorage, ObjectStorageError, Minimal object-storage abstraction: put/get/delete bytes by key.  Why this exist, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar (+8 more)

### Community 53 - "Community 53"
Cohesion: 0.06
Nodes (37): consumption_report(), _consumption_totals_by_item(), create_stock_item(), current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item() (+29 more)

### Community 54 - "Community 54"
Cohesion: 0.07
Nodes (16): _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), get_booking(), list_bookings(), _project_booking_graph() (+8 more)

### Community 55 - "Community 55"
Cohesion: 0.07
Nodes (30): 68f7b1c fix(tests): update _invitation_token call sites to new (db, ctx, email) signature, 7a7afb0 fix(security): enforce password minimum on invitation accept, 8223161 fix(security): close staff invitation lifecycle gaps (TECH-0031), a714b07 fix(security): block replay-reactivation of revoked memberships, d333204 fix(security): require account auth for existing invitation accepts, d3dcbfd fix(migrations): chain staff invitation lifecycle migration onto guest search index head, Persisted staff invitations and their one-time acceptance state., client_with_db() (+22 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (34): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), Migration coverage for the deduplication sweep., test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly (+26 more)

### Community 57 - "Community 57"
Cohesion: 0.09
Nodes (21): FastAPI routes for the commercial configuration domain., CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan() (+13 more)

### Community 58 - "Community 58"
Cohesion: 0.09
Nodes (24): 02908b1 feat(storage): add verified tenant object metadata, CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, Durable tenant-scoped metadata for private object-storage blobs., Metadata and lifecycle state; bytes remain outside PostgreSQL. (+16 more)

### Community 59 - "Community 59"
Cohesion: 0.09
Nodes (34): Date-ranged block on a room. NULL ends_at means indefinite.     resolved_at popu, Date-ranged block on a room. NULL ends_at means indefinite.     resolved_at popu, RoomBlock, _active_room_blocks(), _alerts(), _available_with_review(), _cash_session(), daily_report() (+26 more)

### Community 60 - "Community 60"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaService, GemmaServiceError, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 61 - "Community 61"
Cohesion: 0.05
Nodes (38): .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, A guest self-registering must never end up with User.role="platform_admin"     j, JWTs are stateless with no server-side blacklist, so a password reset -     the, JWTs are stateless with no server-side blacklist, so a password reset -     the, A guest self-registering must never end up with User.role="platform_admin"     j (+30 more)

### Community 62 - "Community 62"
Cohesion: 0.11
Nodes (27): configure_dedicated_baseline(), env_page(), fixtures(), set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation(), test_dedicated_baseline_refuses_provider_lease_mismatch(), test_dedicated_baseline_refuses_weak_or_target_derived_lease() (+19 more)

### Community 63 - "Community 63"
Cohesion: 0.10
Nodes (28): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+20 more)

### Community 64 - "Community 64"
Cohesion: 0.10
Nodes (25): differentiators, founder, integrationPoints, integrations, moduleGroups, onboardingSteps, problemPoints, replacedTools (+17 more)

### Community 65 - "Community 65"
Cohesion: 0.08
Nodes (36): D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE (+28 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (32): EffectivePermissionsResponse, fetchEffectivePermissions(), PermissionCatalogResponse, PermissionCell, PermissionDetail, PermissionMatrix, PermissionOverrideRequest, preview_effective_permissions() (+24 more)

### Community 67 - "Community 67"
Cohesion: 0.09
Nodes (28): ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, DailyOperationalReport, getDailyOperationalReport(), getOccupancyReport(), getOperationalAlerts(), getRevenueReport() (+20 more)

### Community 68 - "Community 68"
Cohesion: 0.07
Nodes (32): bootstrap_configuration_fingerprint(), BootstrapConfigurationError, Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., _decode_lease_entropy() (+24 more)

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (26): collaboration_websocket(), CollaborationManager, CollaborationPatchResponse, CollaborationTicket, _consume_ticket(), create_collaboration_ticket(), _live_ticket_is_authorized(), _message_allowed() (+18 more)

### Community 70 - "Community 70"
Cohesion: 0.06
Nodes (30): create_remito(), create_vendor(), _default_currency(), get_vendor(), mark_vendor_settlement_paid(), _quarter_bounds(), Outsourced laundry vendors: vendor/price catalog + remito transfers.  A remito i, Record a remito as a pair of StockMovements per line.      outbound: house_locat (+22 more)

### Community 71 - "Community 71"
Cohesion: 0.17
Nodes (34): AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily, Read a completed export's .xlsx bytes from object storage.      job.file_path ho, _date_window(), _decimal_total(), project_all_derived_facts_incremental(), _project_all_hotels_window() (+26 more)

### Community 72 - "Community 72"
Cohesion: 0.10
Nodes (9): OTASyncEvent, OTASyncJob, OTAOrchestratorError, OTAOrchestratorService, OTA orchestrator service.  This layer coordinates provider adapters, persistent, FailingBookingAdapter, FakeBookingAdapter, test_ota_orchestrator_records_failed_verification() (+1 more)

### Community 73 - "Community 73"
Cohesion: 0.09
Nodes (32): Server-side, revocable sessions for the normal user auth plane., An opaque browser session whose raw token is never persisted., UserSession, _as_aware(), create_session(), csrf_double_submit_matches(), _device_label_from_request(), _hash_value() (+24 more)

### Community 74 - "Community 74"
Cohesion: 0.06
Nodes (31): db(), db_engine(), hotel_config(), _isolate_object_storage(), pg_engine(), No real mail transport in tests — stub auth email senders.      Endpoints raise, A1: permission_service seeds the matrix once per DB engine, not per     request., Route every test's object storage (payment proofs, analytics exports)     to a p (+23 more)

### Community 75 - "Community 75"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 76 - "Community 76"
Cohesion: 0.09
Nodes (22): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Reject context commands that the installed Graphify CLI cannot route. (+14 more)

### Community 77 - "Community 77"
Cohesion: 0.16
Nodes (30): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+22 more)

### Community 78 - "Community 78"
Cohesion: 0.09
Nodes (24): HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia, Per-hotel API credential. `key_hash` stores a hashed version of the secret;, PendingActionPriorityEnum, PendingActionStatusEnum, PendingActionTypeEnum, PendingOperationalAction, PendingOperationalAction — the "pending_actions" table referenced throughout the (+16 more)

### Community 79 - "Community 79"
Cohesion: 0.11
Nodes (29): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+21 more)

### Community 80 - "Community 80"
Cohesion: 0.15
Nodes (30): 955325e feat(security): add critical/step-up/delegable metadata and optimistic versioning to permission catalog, Configurable permission matrix models., _active_membership(), _audit(), audit_permission_denied(), can_role_hold_permission(), canonical_permission_code(), _engine_key() (+22 more)

### Community 81 - "Community 81"
Cohesion: 0.13
Nodes (18): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider, _effective_enabled() (+10 more)

### Community 82 - "Community 82"
Cohesion: 0.15
Nodes (23): _apply_drift(), env_page(), FakeRender, FakeRenderCleanupFailure, FakeRenderPutResponseLost, HealthResponse, manifest(), _mutating_calls() (+15 more)

### Community 83 - "Community 83"
Cohesion: 0.11
Nodes (20): _event_engine(), FakeRedis, A minimal SQLite engine with just the tables the after_commit hook writes to., _settings(), test_nested_commit_publishes_only_after_root_commit(), test_nested_rollback_prunes_only_nested_realtime_signals(), test_optional_backend_degrades_without_fabricating_an_event(), test_permission_invalidation_publishes_without_error_logging() (+12 more)

### Community 84 - "Community 84"
Cohesion: 0.13
Nodes (19): evidence_bytes(), FakeGitHub, iso(), prepare(), Security regression tests for the pull_request_target release gate., test_finalize_rejects_artifact_with_different_bytes(), test_github_client_error_never_discloses_token_or_body(), test_prepare_refuses_head_key_substitution_for_base_checkout_key() (+11 more)

### Community 85 - "Community 85"
Cohesion: 0.10
Nodes (19): fetchPublicPricing(), LeadPayload, PublicPricing, PublicPricingPlan, submitLead(), BrandMarkProps, 9da1f66 Rebuild the public landing page as Hotels-PMS, hero (+11 more)

### Community 86 - "Community 86"
Cohesion: 0.10
Nodes (20): DailyReportSchedule, DailyReportScheduleUpdate, get_daily_report_schedule(), getDailyReportSchedule(), listNotificationPreferences(), listNotifications(), markAllNotificationsRead(), markNotificationRead() (+12 more)

### Community 87 - "Community 87"
Cohesion: 0.17
Nodes (28): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _daily_report_key(), _date_token(), get_cached_availability_payload(), get_cached_daily_report_payload() (+20 more)

### Community 88 - "Community 88"
Cohesion: 0.18
Nodes (28): _actor_payload(), _actor_role(), _actor_user_id(), _apply_plan(), _as_utc(), _assert_same_adjustment(), change_subscription_plan(), _compute_can_write() (+20 more)

### Community 89 - "Community 89"
Cohesion: 0.07
Nodes (1): test_database_foundation_complete()

### Community 90 - "Community 90"
Cohesion: 0.11
Nodes (16): ABC, EmailProvider, EmailProviderError, get_email_provider(), _normalize_display_from(), NullEmailProvider, ResendEmailProvider, ExplodingDB (+8 more)

### Community 91 - "Community 91"
Cohesion: 0.21
Nodes (17): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+9 more)

### Community 93 - "Community 93"
Cohesion: 0.12
Nodes (25): Return which promotions would apply and the resulting price breakdown     for a, Creates a new immutable version; the previous version is deactivated.     Reserv, simulate_promotion_pricing(), update_promotion(), Promotion, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, apply_promotions_to_night(), _conditions_kwargs() (+17 more)

### Community 94 - "Community 94"
Cohesion: 0.15
Nodes (25): MarketingLead, MarketingPricingPlan, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, Someone who asked for access from the public site.      Email is unique so a rep, admin_pricing(), _decode_features(), hash_source() (+17 more)

### Community 95 - "Community 95"
Cohesion: 0.16
Nodes (23): _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet(), get_connection_payload() (+15 more)

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (21): CashHandoffSchemaRepairError, main(), missing_model_tables(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Apply the additive cash-handoff repair in one PostgreSQL transaction., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., Raised when the safe repair cannot run against the configured database. (+13 more)

### Community 97 - "Community 97"
Cohesion: 0.23
Nodes (26): _build_finish_gates(), _build_readiness_checklist(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status() (+18 more)

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (26): _apply_setting(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set or clear the current hotel id for tenant-scoped RLS policies., Stash the last value applied for ``setting_name`` on this session.      ``sessio, Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that (+18 more)

### Community 99 - "Community 99"
Cohesion: 0.09
Nodes (10): _card_value(), _make_reservation(), _operations_analytics(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _request_context(), _starter_analytics() (+2 more)

### Community 100 - "Community 100"
Cohesion: 0.12
Nodes (21): 3abbd31 Complete core reservation business journey, 54eed63 Expose payment method configuration for owners, e85df76 Harden reservation finance loading states, clientNavigate(), credentials, PAGES, revealCollapsedNavLink(), _credentials() (+13 more)

### Community 101 - "Community 101"
Cohesion: 0.13
Nodes (23): 5f2b20a feat(audit): add CSV export for unified audit timeline (TECH-0070), fd2c5b2 feat(security): add unified tenant-scoped audit timeline read endpoint, _details_for_row(), list_audit_timeline(), _parse_redacted_json(), Read-only, tenant-scoped projection of the three hotel audit streams., Return a globally ordered, paginated projection of all audit sources.      The t, Remove credential-like values from otherwise useful text fields. (+15 more)

### Community 102 - "Community 102"
Cohesion: 0.15
Nodes (26): Immutable ledger entry for a subscription discount or override.      This table, SubscriptionAdjustment, SubscriptionEvent, clear_room_limit_override(), _default_adjustment_idempotency_key(), ensure_subscription_seed(), _legacy_status_for_v2(), plan_catalog() (+18 more)

### Community 103 - "Community 103"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+16 more)

### Community 104 - "Community 104"
Cohesion: 0.23
Nodes (22): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+14 more)

### Community 105 - "Community 105"
Cohesion: 0.12
Nodes (14): ef63dcb fix(rooms): close room allocation gap (TECH-0062), f11bb67 fix(rooms): close room allocation gap (TECH-0062), _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later() (+6 more)

### Community 106 - "Community 106"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 107 - "Community 107"
Cohesion: 0.19
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 108 - "Community 108"
Cohesion: 0.09
Nodes (12): 2de6004 Add a leads page to the owner console and fix unreadable console styling, 41ada7f Degrade public pricing instead of failing when the table is unreadable, 628d9a5 Remove screenshot files written to a literal 'undefined' directory, 642c6be Allow our own public hosts through CORS without an env var, { code }, source, DATE, HEADERS (+4 more)

### Community 109 - "Community 109"
Cohesion: 0.11
Nodes (16): 67e4e68 fix(data-integrity): make audit_logs append-only at the database level, TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, When a hotel is deleted all its audit logs cascade., Deleting a hotel cannot destroy its audit-log evidence., Reproduces the DELETE api/stockitems/{id} incident: a stray NOT     NULL colum, Reproduces the DELETE /api/stock/items/{id} incident: a stray NOT     NULL colum, test_audit_log_hotel_cascade_delete(), test_audit_log_hotel_delete_is_restricted() (+8 more)

### Community 110 - "Community 110"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 111 - "Community 111"
Cohesion: 0.17
Nodes (22): TOTP MFA secrets and one-time recovery codes for normal user accounts., UserMfaRecoveryCode, UserMfaSecret, add_recovery_codes(), confirm_enrollment(), consume_mfa_code(), _consume_recovery_code(), _consume_totp_code() (+14 more)

### Community 112 - "Community 112"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 113 - "Community 113"
Cohesion: 0.18
Nodes (5): make_res(), make_rooms(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 114 - "Community 114"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), Unit coverage for the notification outbox/service: dedupe, permission filtering,, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, test_daily_report_does_not_resend_same_local_date(), test_daily_report_dst_transition_shifts_the_utc_trigger_hour(), test_daily_report_uses_hotel_local_hour_not_utc() (+15 more)

### Community 115 - "Community 115"
Cohesion: 0.15
Nodes (10): BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, Acknowledge processed reservation messages in Booking's queue., A provider operation failed before it could return normalized data., NormalizedOTAReservation, OTAAdapterContext, OTAOperationResult, OTAProviderAdapter (+2 more)

### Community 116 - "Community 116"
Cohesion: 0.17
Nodes (20): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+12 more)

### Community 117 - "Community 117"
Cohesion: 0.12
Nodes (14): _make_guest(), _make_reservation(), test_api_key_name_unique_per_hotel_not_global(), test_delete_hotel_a_guest_does_not_affect_hotel_b(), test_guest_dedup_same_hotel_raises(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 118 - "Community 118"
Cohesion: 0.20
Nodes (21): _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error(), _is_public_webhook_base(), list_payment_link_tests(), _mercadopago_access_token() (+13 more)

### Community 119 - "Community 119"
Cohesion: 0.28
Nodes (21): _hotel(), A cash payment on a reservation must land in the open caja as an INCOME     move, _reservation(), test_cash_movement_requires_open_session(), test_cash_payment_posts_income_movement_to_open_session(), test_cash_payment_with_surcharge_posts_gross_amount_to_caja(), test_cash_payment_without_open_session_is_rejected(), test_cash_payment_without_open_session_opens_zero_balance_session() (+13 more)

### Community 121 - "Community 121"
Cohesion: 0.15
Nodes (14): BrokenRedis, _cache_settings(), FakeRedis, _reset_cache_client_state(), test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_disabled_returns_computed_value_without_constructing_redis(), test_cache_miss_calls_producer() (+6 more)

### Community 122 - "Community 122"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 123 - "Community 123"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+4 more)

### Community 124 - "Community 124"
Cohesion: 0.11
Nodes (21): _gmail_is_active(), _has_value(), _is_public_https_url(), _mercadopago_is_active(), _paypal_is_active(), Fail fast if the app is being started in production with placeholder secrets., Fail fast if the app is being started in production with placeholder secrets., Fail fast if the app is being started in production with placeholder secrets. (+13 more)

### Community 125 - "Community 125"
Cohesion: 0.17
Nodes (20): put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi, BillingPolicyPayload, BillingPolicyUpdateRequest, EmailTestRequest, MasterAdminLoginRequest, MasterAdminLoginResponse, MasterAdminMfaCodeRequest (+12 more)

### Community 126 - "Community 126"
Cohesion: 0.10
Nodes (21): get_timezone_catalog(), hotel_today(), is_valid_timezone(), local_today(), normalize_timezone(), Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return a stable, sorted catalog of supported IANA timezone names.      The set i (+13 more)

### Community 127 - "Community 127"
Cohesion: 0.27
Nodes (20): _client_with_db(), _override_auth(), test_effective_permissions_returns_only_current_role_capabilities(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_owner_can_grant_housekeeping_occupancy_planner(), test_permission_catalog_exposes_owner_only_and_normal_metadata(), test_permission_catalog_exposes_owner_only_normal_metadata_and_help_text(), test_permission_denied_is_audited() (+12 more)

### Community 128 - "Community 128"
Cohesion: 0.16
Nodes (17): 393ea8c Refresh generated knowledge inventories, 7433859 Align generated inventories with graph refresh, c50af40 Refresh Graphify knowledge graph, c5914bf Use Render production as cloud QA surface, e2ae869 Use Render production as cloud QA surface, command(), fenced(), frontend_routes() (+9 more)

### Community 129 - "Community 129"
Cohesion: 0.10
Nodes (14): CategoriesPayload, DepositPolicyPayload, HotelIdentityPayload, OnboardingStatus, OTAChannelsPayload, OwnerPayload, PaymentMethodsPayload, ProviderSetupPayload (+6 more)

### Community 130 - "Community 130"
Cohesion: 0.22
Nodes (15): acquire_lease(), env_page(), FakeRender, mutations(), release_lease(), test_acquire_failure_rolls_back_marker_first_then_target_fields(), test_acquire_refuses_every_drift_without_mutation(), test_acquire_validates_before_writing_and_commits_id_last() (+7 more)

### Community 131 - "Community 131"
Cohesion: 0.12
Nodes (7): CacheStore, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, RenderRequester, Protocol, AnalyticsAIProvider

### Community 132 - "Community 132"
Cohesion: 0.12
Nodes (13): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Service adapter for PayPal payment integration.     Creates orders and processes, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification., Process a PayPal webhook notification. (+5 more)

### Community 133 - "Community 133"
Cohesion: 0.16
Nodes (16): 4f50de1 Add successor cash register controls, b4c9bd8 Harden cash rotation and payment integrity, approve_close_difference(), confirm_cash_custody(), _confirmed_cash_movements_total(), get_latest_close_report(), get_session_summary(), list_movements() (+8 more)

### Community 134 - "Community 134"
Cohesion: 0.14
Nodes (19): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., queue_domain_change(), QueuedDomainChange, A safe invalidation signal waiting for the surrounding DB commit., A safe invalidation signal waiting for the surrounding DB commit., A safe invalidation signal waiting for the surrounding DB commit., A safe invalidation signal waiting for the surrounding DB commit. (+11 more)

### Community 135 - "Community 135"
Cohesion: 0.20
Nodes (12): PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, mask_to_weekdays(), PromotionConditions, PromotionCreate, PromotionRead, PromotionSimulateRequest (+4 more)

### Community 136 - "Community 136"
Cohesion: 0.20
Nodes (18): _available_provider_balance(), balance_due_from_transactions(), cancel_link(), create_link(), expire_link(), _find_idempotent_link(), _get_reservation_for_hotel(), _is_safe_provider_url() (+10 more)

### Community 137 - "Community 137"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 138 - "Community 138"
Cohesion: 0.26
Nodes (18): _seed_hotels(), _seed_house_stock(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_create_vendor_creates_its_own_linen_location(), test_create_vendor_creates_its_own_stock_location() (+10 more)

### Community 139 - "Community 139"
Cohesion: 0.12
Nodes (5): _plan(), The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page., TestLeadCapture, TestPublicPricing

### Community 140 - "Community 140"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 141 - "Community 141"
Cohesion: 0.16
Nodes (16): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), normalizeUrl(), PREVIEW_APP_HOST_SUFFIXES, PUBLIC_APP_URL, PUBLIC_SITE_URL, PublicCtaMode (+8 more)

### Community 142 - "Community 142"
Cohesion: 0.14
Nodes (18): get_realtime_client(), _get_redis_client(), publish_domain_event(), Return a configured client after a bounded connectivity check., Return a configured client after a bounded connectivity check., Return a configured client after a bounded connectivity check., Return a configured client after a bounded connectivity check., Return a configured client after a bounded connectivity check. (+10 more)

### Community 143 - "Community 143"
Cohesion: 0.23
Nodes (17): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+9 more)

### Community 144 - "Community 144"
Cohesion: 0.33
Nodes (17): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1) and the linen ite, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, _teardown(), test_housekeeping_can_operate_remitos_but_not_manage_vendors(), test_linen_items_and_locations_are_hotel_scoped() (+9 more)

### Community 145 - "Community 145"
Cohesion: 0.12
Nodes (5): Room.status is a persisted column, not derived from reservations --     a checke, _seed_commercial_setup(), test_move_reservation_room_updates_room_status_for_checked_in_reservation(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 146 - "Community 146"
Cohesion: 0.16
Nodes (10): CeleryJobDispatcher, dispatch_once(), JobDispatcher, JobSpec, Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica, JobDispatchRecord, Durable worker coordination records for portable job dispatch. (+2 more)

### Community 147 - "Community 147"
Cohesion: 0.24
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 148 - "Community 148"
Cohesion: 0.16
Nodes (14): 0d3503a feat(subscription): add idempotent adjustment ledger (TECH-0051), 142d695 feat(subscription): add idempotent adjustment ledger (TECH-0051), 4df2322 fix(migrations): chain subscription adjustment ledger onto guest search index head, 83cc7df fix(migrations): chain subscription adjustment ledger onto staff invitation lifecycle head, a4d0289 fix(migrations): chain subscription adjustment ledger onto staff invitation lifecycle head, a7d08c3 fix(migrations): chain subscription adjustment ledger onto guest search index head, Lightweight subscription tracking for enforcement and auditing (v2 tables)., downgrade() (+6 more)

### Community 149 - "Community 149"
Cohesion: 0.21
Nodes (13): 12f7011 fix(subscription): route all subscription writes through the v2 sync service, 9f8ba34 fix(security): audit and validate comped subscription override, _auth_headers(), _ensure_hotel(), test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_comped_override_records_audit_event(), test_comped_override_rejects_unknown_hotel_without_subscription_state(), test_hotel_bootstrap_and_legacy_plan_entry_point_use_v2_write_path() (+5 more)

### Community 150 - "Community 150"
Cohesion: 0.15
Nodes (12): 16473c9 Refresh Graphify graph after the marketing and metadata pass, 9899fcf Add the master-admin pricing editor, 9eff38b Refresh Graphify graph for the landing page rebuild, f072302 Sell the product on its own terms, and bake per-route metadata, MARKETING_ROUTES, marketingHtmlPlugin(), renderRouteHtml(), replaceTag() (+4 more)

### Community 151 - "Community 151"
Cohesion: 0.24
Nodes (14): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+6 more)

### Community 152 - "Community 152"
Cohesion: 0.15
Nodes (16): _backfill_from_legacy_tags(), downgrade(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), _install_rls(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id): (+8 more)

### Community 153 - "Community 153"
Cohesion: 0.14
Nodes (2): ExpediaAdapter, OTAProviderAdapter

### Community 154 - "Community 154"
Cohesion: 0.15
Nodes (11): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Lazy-initialize the MercadoPago SDK. (+3 more)

### Community 155 - "Community 155"
Cohesion: 0.30
Nodes (15): DrillError, main(), _pg_command(), _pg_count(), _postgres_parts(), Expected, safe failure for a local drill., Expected, safe failure for a local drill., Verify every ready metadata row against the local blob before restore. (+7 more)

### Community 156 - "Community 156"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 157 - "Community 157"
Cohesion: 0.28
Nodes (14): add_internal_note(), add_outbound_message(), assign_conversation(), _channel(), complete_embedded_signup(), _conversation(), _event(), InboundMessageResult (+6 more)

### Community 158 - "Community 158"
Cohesion: 0.19
Nodes (13): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), _load_provider_evidence(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+5 more)

### Community 159 - "Community 159"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 160 - "Community 160"
Cohesion: 0.28
Nodes (14): _manual_payload(), B4: the manual OTA form lets the receptionist type a total + currency     that d, The receptionist can type TWO independent prices (ARS and USD) for a     manual, Root-cause repro for the owner's report: a category with a RatePlan     that is, _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total() (+6 more)

### Community 161 - "Community 161"
Cohesion: 0.19
Nodes (13): A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, _seed_hotel(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b() (+5 more)

### Community 162 - "Community 162"
Cohesion: 0.27
Nodes (15): _client_with_db(), _override_auth(), API-level coverage for stock items: delete-then-recreate (owner-reported bug), u, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Same convention as POST /api/payment-links: a client resending the     same POST, _second_hotel(), _teardown() (+7 more)

### Community 163 - "Community 163"
Cohesion: 0.19
Nodes (14): Fase 3 (QA reservas): PATCH /api/reservations/{id} only understands     room_id/, Receptionists gain only the narrow, same-category move tier by default., B5: cross-category move via the endpoint enforces capacity and price_action., Same wiring as reservation_api_client, but a role without room_move by default (, reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields() (+6 more)

### Community 164 - "Community 164"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 165 - "Community 165"
Cohesion: 0.13
Nodes (15): _cors_contains_wildcard(), Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration., Fail closed when a cloud QA service could reach a live integration. (+7 more)

### Community 166 - "Community 166"
Cohesion: 0.17
Nodes (8): DAILY_REPORT_ROLE_OPTIONS, DAILY_REPORT_SECTIONS, KNOWN_NOTIFICATION_EVENT_TYPES, notificationEventLabel(), preferencesKey(), useDailyReportScheduleMutation(), useNotificationPreferences(), CHANNEL_OPTIONS

### Community 167 - "Community 167"
Cohesion: 0.51
Nodes (14): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), test_correct_version_passes_optimistic_lock(), test_no_prohibido_tag_allows_checkin(), test_omitting_client_version_skips_check(), test_other_tags_do_not_block_checkin() (+6 more)

### Community 168 - "Community 168"
Cohesion: 0.33
Nodes (13): _enable_external_effects(), _fake_mp_gateway(), _reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service() (+5 more)

### Community 169 - "Community 169"
Cohesion: 0.31
Nodes (14): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- per-item stock consumption (out, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+6 more)

### Community 170 - "Community 170"
Cohesion: 0.27
Nodes (10): Read and resolve the guest room-rejection lifecycle., get_active_guest_room_avoidances(), _get_tenant_guest(), _get_tenant_room(), GuestRoomAvoidanceConflictError, GuestRoomAvoidanceNotFoundError, GuestRoomAvoidanceServiceError, _now() (+2 more)

### Community 171 - "Community 171"
Cohesion: 0.18
Nodes (13): 249a761 fix(security): add missing tenant RLS policy to hotel_api_keys, guest_alerts, reservation_movement_groups, ed0d0eb fix(review): chain RLS migration after audit-log-cascade fix, downgrade(), _install_rls(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Install the PostgreSQL tenant policy; no-op on other dialects., Install the PostgreSQL tenant policy; no-op on other dialects. (+5 more)

### Community 172 - "Community 172"
Cohesion: 0.30
Nodes (10): 928e7ad feat(rbac): add restore-to-default for permission overrides (TECH-0040), _auth(), _client(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_owner_can_restore_one_role_override_to_catalog_default_with_audit(), test_owner_can_restore_one_user_override_to_role_default_with_audit(), test_restore_cannot_leave_owner_without_permission_management() (+2 more)

### Community 173 - "Community 173"
Cohesion: 0.18
Nodes (13): _client_signature(), get_async_redis_client(), get_sync_redis_client(), namespaced_key(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Clear process clients for tests and orderly shutdown., Clear process clients for tests and orderly shutdown., Return one sync client per process, or None for empty configuration. (+5 more)

### Community 174 - "Community 174"
Cohesion: 0.14
Nodes (11): channel_for_hotel(), DomainEvent, iter_event_stream(), Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped stream and close when membership is revoked., Yield a tenant-scoped SSE stream; sync iteration runs in Starlette's worker. (+3 more)

### Community 175 - "Community 175"
Cohesion: 0.32
Nodes (13): _active_tag_filter(), add_tag(), _audit(), _escape_like_term(), _get_guest(), _guest_search_rank(), list_active_tags(), _now() (+5 more)

### Community 176 - "Community 176"
Cohesion: 0.30
Nodes (11): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task() (+3 more)

### Community 177 - "Community 177"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 178 - "Community 178"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 179 - "Community 179"
Cohesion: 0.14
Nodes (13): Regression coverage for portable Graphify artifact normalization., A second normalizer run must leave already-portable artifacts unchanged., A second normalizer run must leave already-portable artifacts unchanged., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A generated-instruction symlink must not allow writes outside the repository., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten. (+5 more)

### Community 180 - "Community 180"
Cohesion: 0.29
Nodes (13): _image_base64(), _jpeg_with_exif_base64(), A .png-declared upload whose bytes are NOT actually a decodable image     (magic, Rows written before the object-storage migration have `content` set     and `obj, _reservation(), test_approval_creates_completed_transfer_transaction_and_updates_balance(), test_get_transfer_proof_bytes_falls_back_to_legacy_content_column(), test_proof_bytes_are_tenant_scoped() (+5 more)

### Community 181 - "Community 181"
Cohesion: 0.29
Nodes (12): _ctx(), _seed_hotel(), test_apply_promotions_never_goes_negative(), test_create_promotion_rejects_duplicate_code(), test_create_promotion_rejects_percentage_over_100(), test_deactivate_and_reactivate_promotion(), test_find_applicable_promotions_matches_guest_tag_type(), test_find_applicable_promotions_matches_typed_conditions() (+4 more)

### Community 182 - "Community 182"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 183 - "Community 183"
Cohesion: 0.54
Nodes (13): _build_client(), _cleanup_client(), _override_auth(), _payload(), _seed_bookable_state(), test_co_owner_cannot_set_manual_total_amount_by_default(), test_manager_can_set_manual_total_amount_with_explicit_override(), test_manager_cannot_cross_manual_rate_security_ceiling() (+5 more)

### Community 184 - "Community 184"
Cohesion: 0.47
Nodes (11): _make_reservation(), _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations(), test_auto_assign_no_double_booking() (+3 more)

### Community 185 - "Community 185"
Cohesion: 0.31
Nodes (12): _delivery(), _message(), _post(), HTTP boundary tests for the Meta Cloud API WhatsApp webhook.  The endpoint had n, Regression: a bad phone used to raise 400 and roll the whole batch back.      Me, ``text`` and ``profile`` arriving as strings must not raise a 500., _signature(), test_ingests_a_signed_inbound_message() (+4 more)

### Community 186 - "Community 186"
Cohesion: 0.22
Nodes (13): _backfill_defaults(), _contract_legacy_rows(), _copy_role_overrides(), downgrade(), _insert_permission_rows(), _install_user_override_rls(), expand RBAC catalog and add tenant-scoped user overrides  Revision ID: 20260813_, Install the PostgreSQL tenant policy; no-op on other dialects. (+5 more)

### Community 187 - "Community 187"
Cohesion: 0.32
Nodes (12): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., Raised when the local persona file cannot be created safely., _render() (+4 more)

### Community 188 - "Community 188"
Cohesion: 0.35
Nodes (12): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _origin(), _timestamp(), _valid_timestamp() (+4 more)

### Community 189 - "Community 189"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 190 - "Community 190"
Cohesion: 0.26
Nodes (8): emailOutboxPath, readLatestCode(), waitForCode(), cleanupEmailOutbox(), emailOutboxPath, readLatestCode(), resetEmailOutbox(), waitForCode()

### Community 191 - "Community 191"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 192 - "Community 192"
Cohesion: 0.15
Nodes (13): get_domain_event_outbox_metrics(), get_domain_event_recovery(), Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, Return changed domains after a tenant-scoped outbox cursor.      V2 rows use ``s, Return changed domains after a tenant-scoped outbox cursor.      V2 rows use ``s (+5 more)

### Community 193 - "Community 193"
Cohesion: 0.37
Nodes (12): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id(), _normalize_required() (+4 more)

### Community 194 - "Community 194"
Cohesion: 0.21
Nodes (9): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi (+1 more)

### Community 196 - "Community 196"
Cohesion: 0.15
Nodes (13): _make_hotel_guest_reservation(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict(), test_pending_action_resolution(), test_refund_request_gateway_path(), test_refund_request_manual_review_path() (+5 more)

### Community 197 - "Community 197"
Cohesion: 0.31
Nodes (9): _outbox_row(), _seed_hotels(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_old_pending_row_emits_stale_metric_alert(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision() (+1 more)

### Community 198 - "Community 198"
Cohesion: 0.37
Nodes (11): _link(), _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_mercadopago_notification_rejects_different_collector_account(), test_minimal_mercadopago_notification_is_verified_by_provider_fetcher() (+3 more)

### Community 199 - "Community 199"
Cohesion: 0.18
Nodes (8): _count_queries(), _mk_reservation(), The real N+1 this fix targets: query count must track the number of     reservat, The real N+1 this fix targets: query count must track the number of     reservat, Every distinct way `_build_pending_actions` can produce an action must     still, Every distinct way `_build_pending_actions` can produce an action must     still, test_pending_actions_prefilter_matches_unfiltered_scan_for_every_trigger_type(), test_pending_actions_query_count_scales_with_candidates_not_total_reservations()

### Community 200 - "Community 200"
Cohesion: 0.23
Nodes (10): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), test_listing_uses_one_scalar_reservation_query(), test_order_recent_is_created_at_desc_id_desc() (+2 more)

### Community 201 - "Community 201"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 202 - "Community 202"
Cohesion: 0.33
Nodes (11): _approve(), _request(), test_consume_rejects_a_different_requester(), test_deny_does_not_populate_approver_field(), test_expired_grant_is_rejected_and_marked_expired(), test_invalid_totp_rejects_approval(), test_non_approver_role_cannot_approve(), test_owner_without_mfa_cannot_approve() (+3 more)

### Community 203 - "Community 203"
Cohesion: 0.15
Nodes (4): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 204 - "Community 204"
Cohesion: 0.18
Nodes (9): NotificationItem, NotificationSeverity, NotificationsPanel(), Props, severityDot, severityLabel, severityStyles, useNotificationMutations() (+1 more)

### Community 205 - "Community 205"
Cohesion: 0.23
Nodes (9): registerPushSubscription(), unregisterPushSubscription(), BeforeInstallPromptEvent, Event, isIOSDevice(), isStandaloneDisplay(), useInstallPrompt(), PushSubscriptionState (+1 more)

### Community 206 - "Community 206"
Cohesion: 0.26
Nodes (7): acknowledge_shift_handoff(), _can(), _conflict(), create_operational_task(), patch_operational_task(), _report_type_allowed(), resolve_operational_task()

### Community 207 - "Community 207"
Cohesion: 0.17
Nodes (12): AuthContext, get_auth_context(), _parse_header_hotel_id(), _parse_token_hotel_id(), Return an authenticated context scoped to an active hotel membership., Return an authenticated context scoped to an active hotel membership., Return an authenticated context scoped to an active hotel membership., Return an authenticated context scoped to an active hotel membership. (+4 more)

### Community 208 - "Community 208"
Cohesion: 0.17
Nodes (12): Dependency to enforce that the current user has one of the allowed roles in the, Dependency to enforce that the current user has one of the allowed roles in the, Like require_permission, but grants access if the caller holds ANY one of     th, Like require_permission, but grants access if the caller holds ANY one of     th, Dependency to enforce that the current user has one of the allowed roles in the, Like require_permission, but grants access if the caller holds ANY one of     th, Like require_permission, but grants access if the caller holds ANY one of     th, Dependency to enforce that the current user has one of the allowed roles in the (+4 more)

### Community 209 - "Community 209"
Cohesion: 0.17
Nodes (9): LeadCreateRequest, LeadCreateResponse, MasterLeadListPayload, MasterLeadPayload, MasterPricingPlanListPayload, MasterPricingPlanPayload, PublicPricingPlan, PublicPricingResponse (+1 more)

### Community 210 - "Community 210"
Cohesion: 0.17
Nodes (10): DailyReportScheduleRead, DailyReportScheduleUpdate, NotificationListResponse, NotificationMarkReadRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, NotificationRead, PushSubscriptionRegisterRequest (+2 more)

### Community 211 - "Community 211"
Cohesion: 0.44
Nodes (11): _seed_daily_rates(), _seed_hotel(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_manual_override_skips_promotions_entirely() (+3 more)

### Community 212 - "Community 212"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 213 - "Community 213"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 214 - "Community 214"
Cohesion: 0.31
Nodes (10): channel_status(), complete_channel(), create_note(), inbox(), Authenticated human WhatsApp CRM inbox.  This router never calls Meta directly., Store metadata after the backend completes Embedded Signup.      No bearer token, _require_plan(), send_message() (+2 more)

### Community 215 - "Community 215"
Cohesion: 0.18
Nodes (11): is_test_mode(), True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV, True for pytest (TESTING=1) and the isolated Playwright E2E backend     (APP_ENV (+3 more)

### Community 216 - "Community 216"
Cohesion: 0.29
Nodes (8): 9a39e0e fix(data-model): allow HotelAuditEvent to represent system/automated actors, _alter_user_column(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2, _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade(), _user_fk()

### Community 217 - "Community 217"
Cohesion: 0.24
Nodes (10): f3141e0 fix(migrations): chain temporary action grants migration onto permission metadata head, fc31288 feat(security): add core temporary one-time action authorization (TECH-0041), downgrade(), _install_rls(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table., Remove the PostgreSQL tenant policy before dropping the table. (+2 more)

### Community 218 - "Community 218"
Cohesion: 0.35
Nodes (10): cleanup(), derive_test_dsn(), explain(), main(), measure(), percentile(), print_results(), run_alembic_upgrade() (+2 more)

### Community 219 - "Community 219"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 220 - "Community 220"
Cohesion: 0.18
Nodes (11): format_sse(), iter_postgres_event_stream(), _outbox_sse_payload(), Build a safe invalidation frame from a committed outbox row.      The PostgreSQL, Build a safe invalidation frame from a committed outbox row.      The PostgreSQL, Build a safe invalidation frame from a committed outbox row.      The PostgreSQL, Build a safe invalidation frame from a committed outbox row.      The PostgreSQL, Stream committed outbox invalidations when Redis is unavailable.      Each poll (+3 more)

### Community 221 - "Community 221"
Cohesion: 0.18
Nodes (11): publish_queued_domain_changes(), Publish committed signals without allowing Redis to break the request., Publish committed signals without allowing Redis to break the request.      This, Publish committed signals without allowing Redis to break the request.      This, Publish committed signals without allowing Redis to break the request.      This, Publish committed signals without allowing Redis to break the request.      This, Record one publish attempt on a durable outbox row, if it still exists., Record one publish attempt on a durable outbox row, if it still exists. (+3 more)

### Community 222 - "Community 222"
Cohesion: 0.36
Nodes (10): _actor_name(), _area_for(), _bounds(), _date_filter(), list_operational_audit(), _matches(), _money(), _row() (+2 more)

### Community 223 - "Community 223"
Cohesion: 0.31
Nodes (9): approve_transfer_proof(), _decode_image(), get_transfer_proof(), proof_file_path(), _proof_path(), reject_transfer_proof(), _reservation(), _safe_filename() (+1 more)

### Community 224 - "Community 224"
Cohesion: 0.56
Nodes (10): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only() (+2 more)

### Community 225 - "Community 225"
Cohesion: 0.35
Nodes (7): FakeJwkClient, test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_valid_apple_token_is_verified(), _token(), _verify()

### Community 226 - "Community 226"
Cohesion: 0.38
Nodes (10): _create_payload(), _reservation(), _seed_guest_inventory(), _seed_hotel(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_receptionist_cannot_override_until_canonical_permission_is_granted(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(), test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass() (+2 more)

### Community 227 - "Community 227"
Cohesion: 0.18
Nodes (3): The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today, utc_server_clock()

### Community 228 - "Community 228"
Cohesion: 0.42
Nodes (8): _create_link(), _post_webhook(), _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_rejected_webhook_records_payment_without_completing_a_transaction(), test_webhook_with_invalid_signature_is_rejected_and_changes_nothing()

### Community 229 - "Community 229"
Cohesion: 0.27
Nodes (6): _reserve(), test_cancelled_reservation_is_excluded(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(), test_reservation_entirely_before_or_after_window_is_excluded(), test_reservation_spanning_the_window_is_returned_unclipped()

### Community 230 - "Community 230"
Cohesion: 0.27
Nodes (6): Focused coverage for the operational audit and hotel-local cash projection., _reservation(), test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(), test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(), _transaction(), _user()

### Community 231 - "Community 231"
Cohesion: 0.36
Nodes (7): _move(), _seed_move_shapes(), test_capacity_tier_alone_includes_each_narrower_tier(), test_existing_wide_roles_still_move_anywhere(), test_manager_can_move_each_shape(), test_manager_capacity_permission_does_not_bypass_occupancy_validation(), test_receptionist_is_limited_to_same_category_moves()

### Community 233 - "Community 233"
Cohesion: 0.29
Nodes (6): _context(), _hotel_today(), Regression tests for tenant-scoped, per-role reservation visibility., _reserve(), test_in_house_guest_remains_visible_when_check_in_predates_window(), test_visibility_window_filters_far_future_and_null_is_unlimited()

### Community 234 - "Community 234"
Cohesion: 0.29
Nodes (10): _create_linen_tables(), downgrade(), _drop_kind_column(), _finalize_laundry_vendor_columns(), _migrate_linen_data(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li, Reverse of _migrate_linen_data: every linen_items row moves back into     stock_ (+2 more)

### Community 235 - "Community 235"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 236 - "Community 236"
Cohesion: 0.31
Nodes (8): main(), _non_empty(), validate_manifest(), 0735930 feat(ci): close TECH-0112 versionable gaps — SHA-pinned artifacts, release validation, manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 237 - "Community 237"
Cohesion: 0.22
Nodes (5): 024bad4 fix(migrations): chain guest search index migration onto primary owner head, 14dfc42 perf(guests): harden tenant-scoped guest search (TECH-0060), db4e5ad perf(guests): harden tenant-scoped guest search (TECH-0060), Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati, Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 238 - "Community 238"
Cohesion: 0.31
Nodes (9): _cassandra_probe(), _close_clients(), _enable(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each, Avoid reusing a client created by another test or stale .env flags., reset_projection_clients(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), test_mongo_audit_projection_lands_document() (+1 more)

### Community 239 - "Community 239"
Cohesion: 0.20
Nodes (10): _outbox_backoff_seconds(), publish_pending_domain_events(), Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th (+2 more)

### Community 240 - "Community 240"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 241 - "Community 241"
Cohesion: 0.27
Nodes (8): create_linen_item(), create_location(), delete_linen_item(), get_linen_item(), get_location(), linen_summary(), list_linen_items(), register_movement()

### Community 242 - "Community 242"
Cohesion: 0.38
Nodes (9): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), quote_rate_plan_stay(), _resolve_commission_amount(), _select_fx_policy(), _select_rate_plan_price() (+1 more)

### Community 243 - "Community 243"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 244 - "Community 244"
Cohesion: 0.56
Nodes (8): _guest(), _reservation(), _seed_hotel(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_previous_completed_room_signal_requires_the_new_reservation_category()

### Community 245 - "Community 245"
Cohesion: 0.20
Nodes (10): RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage (+2 more)

### Community 246 - "Community 246"
Cohesion: 0.49
Nodes (9): _client_with_db(), _override_auth(), _seed_fully_paid_reservation(), test_add_companion_during_checkin_flow_appears_in_additional_guests(), test_add_companion_exceeding_capacity_returns_clear_400(), test_checkin_captures_missing_fields_in_same_request(), test_checkin_without_new_fields_fails_with_clear_message(), test_partial_checkin_reaches_pre_check_in_then_final_checkin() (+1 more)

### Community 247 - "Community 247"
Cohesion: 0.58
Nodes (9): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_manager_has_no_access_to_commercial_configuration() (+1 more)

### Community 249 - "Community 249"
Cohesion: 0.31
Nodes (7): _login(), Public pricing is owner-editable from the master-admin console.  Reuses the mast, test_a_plan_dropped_from_the_payload_disappears(), test_negative_price_is_rejected(), test_owner_can_read_captured_leads(), test_owner_sets_a_price_and_the_public_endpoint_serves_it(), test_saving_pricing_writes_an_audit_event()

### Community 250 - "Community 250"
Cohesion: 0.47
Nodes (7): _build_client(), _cleanup(), _override_auth(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_reactivate_deactivated_surcharge_via_patch()

### Community 251 - "Community 251"
Cohesion: 0.38
Nodes (7): _make_hotel(), _make_reservation(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 252 - "Community 252"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 253 - "Community 253"
Cohesion: 0.42
Nodes (7): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_cannot_create_room_block_by_default(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 254 - "Community 254"
Cohesion: 0.20
Nodes (10): MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup. (+2 more)

### Community 255 - "Community 255"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_blocked_for_past_check_in(), test_change_dates_blocked_when_room_conflict(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_pending_updates_dates_and_price(), test_extend_stay_blocked_for_zero_or_negative_days(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 256 - "Community 256"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 257 - "Community 257"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 258 - "Community 258"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 259 - "Community 259"
Cohesion: 0.29
Nodes (9): downgrade(), _insert_default_rows(), _insert_permission_rows(), _install_rls(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls() (+1 more)

### Community 260 - "Community 260"
Cohesion: 0.42
Nodes (8): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity()

### Community 261 - "Community 261"
Cohesion: 0.44
Nodes (8): _catalog(), initialize(), _json_bytes(), main(), OperationalQAError, _utc_now(), validate(), _write()

### Community 262 - "Community 262"
Cohesion: 0.22
Nodes (8): Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, recover_domain_events(), stream_domain_events(), DomainEventRecoveryResponse, Safe cursor response used to repair missed realtime invalidations.

### Community 263 - "Community 263"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 264 - "Community 264"
Cohesion: 0.33
Nodes (8): GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate, Pydantic schemas for Guest and companions.

### Community 265 - "Community 265"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 266 - "Community 266"
Cohesion: 0.25
Nodes (9): _model_event_payload(), _model_hotel_id(), queue_model_changes(), Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends. (+1 more)

### Community 267 - "Community 267"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 268 - "Community 268"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_surfaces_retryable_provider_outage()

### Community 269 - "Community 269"
Cohesion: 0.42
Nodes (7): _seed_hotel(), _seed_reservation(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner(), test_guest_export_permission_ceiling_cannot_be_overridden_for_reception(), test_guest_export_permission_defaults_and_override_are_hotel_scoped()

### Community 270 - "Community 270"
Cohesion: 0.50
Nodes (8): _auth(), _client(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and, test_daily_report_schedule_is_owner_co_owner_only(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_preferences_crud(), test_push_subscription_register_and_unregister()

### Community 271 - "Community 271"
Cohesion: 0.50
Nodes (8): _outbox_event_types(), _owner(), Integration coverage: the real domain-event call sites (reservation lifecycle, c, test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), test_no_show_enqueues_notification(), test_reservation_lifecycle_enqueues_notifications()

### Community 272 - "Community 272"
Cohesion: 0.56
Nodes (8): _client(), _close(), test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(), test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation(), test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation(), test_stock_read_movement_and_admin_are_independently_enforced_without_mutation()

### Community 273 - "Community 273"
Cohesion: 0.36
Nodes (6): _add_event(), test_missing_or_zero_cursor_requires_full_refetch(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch(), test_stale_cursor_requires_full_refetch()

### Community 274 - "Community 274"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 275 - "Community 275"
Cohesion: 0.56
Nodes (7): _role_connection(), _seed_engine(), _seed_session(), test_after_commit_listener_reapplies_hotel_context(), test_master_admin_bypass_sees_all_hotels_subscriptions(), test_no_tenant_context_hides_all_rows(), test_tenant_isolation_blocks_cross_hotel_reads()

### Community 276 - "Community 276"
Cohesion: 0.28
Nodes (8): downgrade(), _install_rls(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 277 - "Community 277"
Cohesion: 0.28
Nodes (8): downgrade(), _install_rls(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 278 - "Community 278"
Cohesion: 0.42
Nodes (8): _columns(), _create_index_if_missing(), downgrade(), _drop_index_if_present(), _indexes(), Operational audit fields, daily cash indexes, and audit read permission., _seed_audit_permission(), upgrade()

### Community 279 - "Community 279"
Cohesion: 0.28
Nodes (8): downgrade(), _install_rls(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 280 - "Community 280"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 281 - "Community 281"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 282 - "Community 282"
Cohesion: 0.25
Nodes (8): get_db(), FastAPI dependency: yields a database session., FastAPI dependency: yields a database session., Get or create a session factory., FastAPI dependency: yields a database session., FastAPI dependency: yields a database session., FastAPI dependency: yields a database session., FastAPI dependency: yields a database session.

### Community 283 - "Community 283"
Cohesion: 0.25
Nodes (8): get_engine(), _install_slow_query_listener(), Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod)., Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod)., Log slow SQL without echoing bound values or changing normal runs., Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod)., Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod)., Create a SQLAlchemy engine for SQLite (dev) or PostgreSQL (prod).

### Community 284 - "Community 284"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 285 - "Community 285"
Cohesion: 0.50
Nodes (7): _actor_name(), _db_utc_bounds(), _decimal(), get_daily_summary(), _utc(), _utc_bounds(), _value()

### Community 286 - "Community 286"
Cohesion: 0.39
Nodes (7): apply_configuration_update(), Shared writes for hotel configuration concepts., Apply a validated Settings payload to one hotel configuration row., set_deposit_policy(), set_identity(), set_ota_channels(), set_payment_methods()

### Community 287 - "Community 287"
Cohesion: 0.50
Nodes (7): availability_lookup(), create_reservation(), generate_payment_link(), handle_payment_confirmation(), options_with_prices(), price_quote(), WhatsAppBookingError

### Community 288 - "Community 288"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 289 - "Community 289"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 290 - "Community 290"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 291 - "Community 291"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 292 - "Community 292"
Cohesion: 0.46
Nodes (7): test_handoff_is_tenant_scoped_and_acknowledged(), test_list_tasks_orders_priority_and_due_date(), test_maintenance_task_keeps_block_until_authorized_release(), test_operator_scope_matches_role_and_assignment(), test_task_lifecycle_history_and_stale_version(), test_task_links_cannot_cross_tenant(), _user()

### Community 293 - "Community 293"
Cohesion: 0.54
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 294 - "Community 294"
Cohesion: 0.50
Nodes (6): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_lists_only_active_blocking_reservations_and_allows_delete_after_move(), test_room_delete_soft_deletes_hides_and_audits()

### Community 295 - "Community 295"
Cohesion: 0.50
Nodes (7): opened_cash_register(), _payment(), _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 296 - "Community 296"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 297 - "Community 297"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 298 - "Community 298"
Cohesion: 0.29
Nodes (3): LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default., Telemetry

### Community 299 - "Community 299"
Cohesion: 0.48
Nodes (7): _allow_mfa_attempt(), complete_mfa_login(), confirm_mfa_enrollment(), disable_mfa(), _mfa_attempt_key(), regenerate_mfa_recovery_codes(), _reset_mfa_attempts()

### Community 300 - "Community 300"
Cohesion: 0.43
Nodes (7): approve_temporary_action_grant(), consume_temporary_action_grant(), deny_temporary_action_grant(), _raise_temporary_grant_http_error(), read_pending_temporary_action_grants(), _temporary_grant_actor(), _temporary_grant_response()

### Community 301 - "Community 301"
Cohesion: 0.29
Nodes (7): Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details., recent_security_events(), _safe_resource_id()

### Community 302 - "Community 302"
Cohesion: 0.33
Nodes (7): get_settings(), is_demo_mode(), is_preview_qa_mode(), is_production_mode(), is_testing_mode(), _normalized_env_value(), _resend_is_active()

### Community 303 - "Community 303"
Cohesion: 0.29
Nodes (7): _column_fill_value(), Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref, Best concrete default value for a NOT-NULL column, or None if unknown.      Pref

### Community 304 - "Community 304"
Cohesion: 0.29
Nodes (7): get_session_factory(), Initialize the database engine.      Local development and tests may bootstrap S, Additively add model columns that are missing from existing tables.      create_, Get or create a session factory., Get or create a session factory., Get or create a session factory., Get or create a session factory.

### Community 305 - "Community 305"
Cohesion: 0.29
Nodes (7): Return the SQL text of a column's server_default, if it has one.      Boolean co, Return the SQL text of a column's server_default, if it has one.      Boolean co, Return the SQL text of a column's server_default, if it has one.      Boolean co, Return the SQL text of a column's server_default, if it has one.      Boolean co, Return the SQL text of a column's server_default, if it has one.      Boolean co, Return the SQL text of a column's server_default, if it has one.      Boolean co, _render_server_default()

### Community 306 - "Community 306"
Cohesion: 0.43
Nodes (6): capture(), login(), main(), SHOTS, toWebp(), VIEWPORTS

### Community 307 - "Community 307"
Cohesion: 0.33
Nodes (3): JobDispatcher, _FakeDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 308 - "Community 308"
Cohesion: 0.52
Nodes (5): main(), RealtimeMetrics, _run(), run_load(), validate_target()

### Community 309 - "Community 309"
Cohesion: 0.29
Nodes (6): Schemas for hotel-scoped waitlist entries., WaitlistEntryCreate, WaitlistEntryRead, WaitlistEntryUpdate, WaitlistPromoteRequest, WaitlistPromoteResponse

### Community 310 - "Community 310"
Cohesion: 0.33
Nodes (4): chat_completions(), ChatCompletionRequest, ChatMessage, _extract_latest_user_message()

### Community 311 - "Community 311"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 312 - "Community 312"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 313 - "Community 313"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 315 - "Community 315"
Cohesion: 0.67
Nodes (6): _auth(), _client(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_restriction_api_permissions_tenant_isolation_and_event(), test_restriction_override_reason_rejects_whitespace()

### Community 316 - "Community 316"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 317 - "Community 317"
Cohesion: 0.71
Nodes (6): _build_client(), _cleanup(), _override_auth(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 318 - "Community 318"
Cohesion: 0.52
Nodes (6): _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 319 - "Community 319"
Cohesion: 0.29
Nodes (3): Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro, test_duplicate_room_number_returns_409()

### Community 320 - "Community 320"
Cohesion: 0.29
Nodes (3): _no_real_db(), Every response must carry baseline security headers so the SPA and API are not m, The unmatched-path SPA fallback still depends on get_db; stub it so this     tes

### Community 321 - "Community 321"
Cohesion: 0.57
Nodes (6): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 322 - "Community 322"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 323 - "Community 323"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 324 - "Community 324"
Cohesion: 0.52
Nodes (6): _backfill_authoritative_values(), _columns(), _decode(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea, upgrade()

### Community 325 - "Community 325"
Cohesion: 0.57
Nodes (6): downgrade(), _drop_index_if_present(), _ensure_index(), _index_map(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar, upgrade()

### Community 326 - "Community 326"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op, _remove_rls(), upgrade()

### Community 327 - "Community 327"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat, _remove_rls(), upgrade()

### Community 328 - "Community 328"
Cohesion: 0.43
Nodes (6): downgrade(), _event_id_type(), _install_rls(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i, _remove_rls(), upgrade()

### Community 329 - "Community 329"
Cohesion: 0.80
Nodes (5): build_sql(), _literal(), load_env(), main(), SharedSandboxBootstrapError

### Community 330 - "Community 330"
Cohesion: 0.33
Nodes (6): Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., revoke_current_user_sessions()

### Community 331 - "Community 331"
Cohesion: 0.33
Nodes (6): init_db(), Initialize the database engine.      Local development and tests may bootstrap S, Initialize the database engine.      Local development and tests may bootstrap S, Initialize the database engine.      Local development and tests may bootstrap S, Initialize the database engine.      Local development and tests may bootstrap S, Initialize the database engine.      Local development and tests may bootstrap S

### Community 332 - "Community 332"
Cohesion: 0.33
Nodes (6): Additively add model columns that are missing from existing tables.      create_, Additively add model columns that are missing from existing tables.      create_, Fill NULLs in NOT-NULL model columns that carry a default.      A column added i, Additively add model columns that are missing from existing tables.      create_, Additively add model columns that are missing from existing tables.      create_, _sync_missing_columns()

### Community 333 - "Community 333"
Cohesion: 0.40
Nodes (4): 239b432 fix(migrations): chain primary owner migration onto temporary action grants head, _backfill_primary_owners(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima, upgrade()

### Community 334 - "Community 334"
Cohesion: 0.40
Nodes (3): 3dee498 fix(review): chain permission-metadata migration after latest head, 77fa337 feat(security): add critical/step-up/delegable metadata and optimistic versioning to permission catalog, add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 335 - "Community 335"
Cohesion: 0.33
Nodes (1): credentials

### Community 336 - "Community 336"
Cohesion: 0.33
Nodes (1): credentials

### Community 337 - "Community 337"
Cohesion: 0.40
Nodes (3): authHeaders(), ensureOnboarding(), hotelId

### Community 338 - "Community 338"
Cohesion: 0.60
Nodes (5): _migration_dsn(), Disposable live PostgreSQL proof for the forward Alembic release path.  The rele, _run_alembic(), test_fresh_postgres_migrations_are_repeatable_and_reversible(), test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips()

### Community 339 - "Community 339"
Cohesion: 0.33
Nodes (5): ReservationEmailDeliveryRead, ReservationEmailKind, ReservationEmailSendRequest, ReservationEmailSendResponse, ReservationEmailStatus

### Community 340 - "Community 340"
Cohesion: 0.40
Nodes (5): annotate_analytics_payload(), _as_utc_datetime(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL, Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 341 - "Community 341"
Cohesion: 0.33
Nodes (6): discard_queued_domain_changes(), Drop signals from a rolled-back root or nested transaction., Drop signals from a rolled-back root or nested transaction., Drop signals from a rolled-back root or nested transaction., Drop signals from a rolled-back root or nested transaction., Drop signals from a rolled-back root or nested transaction.

### Community 342 - "Community 342"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 343 - "Community 343"
Cohesion: 0.53
Nodes (5): _create_receptionist_user(), _open_cash_session(), POST /api/payments and GET /api/payments/summary/{id} only allowed     owner/co_, _receptionist_context(), test_receptionist_can_view_and_make_reservation_payments()

### Community 344 - "Community 344"
Cohesion: 0.47
Nodes (4): _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 345 - "Community 345"
Cohesion: 0.40
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 346 - "Community 346"
Cohesion: 0.53
Nodes (5): _alembic(), _assert_migrated(), Data-contract regression for the payment-link execution-mode migration., _seed_legacy_links(), test_payment_link_migration_backfills_provider_history_and_reupgrades()

### Community 347 - "Community 347"
Cohesion: 0.67
Nodes (5): _auth_for(), _seed_guests(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 348 - "Community 348"
Cohesion: 0.60
Nodes (5): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 349 - "Community 349"
Cohesion: 0.60
Nodes (5): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_invalid_recipient_is_rejected_before_provider(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly()

### Community 350 - "Community 350"
Cohesion: 0.47
Nodes (3): _quote(), test_confirmed_reservation_stores_pricing_revision(), test_reservation_rejects_quote_after_pricing_revision_changes()

### Community 351 - "Community 351"
Cohesion: 0.60
Nodes (5): _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 352 - "Community 352"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 353 - "Community 353"
Cohesion: 0.40
Nodes (5): _create_rooms_with_soft_deleted_tail(), Regression coverage for room soft-delete visibility across count surfaces., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, test_soft_deleted_rooms_are_excluded_from_every_room_count_surface()

### Community 354 - "Community 354"
Cohesion: 0.53
Nodes (4): _override_auth(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms()

### Community 355 - "Community 355"
Cohesion: 0.33
Nodes (6): OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, test_validate_runtime_security_rejects_localhost_redirect_when_service_configured()

### Community 356 - "Community 356"
Cohesion: 0.33
Nodes (6): Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, test_validate_runtime_security_rejects_weak_master_admin_password_in_production()

### Community 357 - "Community 357"
Cohesion: 0.53
Nodes (4): test_env_file_requires_owner_only_permissions(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), _values()

### Community 358 - "Community 358"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 359 - "Community 359"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 360 - "Community 360"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 361 - "Community 361"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 362 - "Community 362"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), seed section visibility permissions and their role defaults  Revision ID: 202608, upgrade()

### Community 363 - "Community 363"
Cohesion: 0.60
Nodes (5): downgrade(), _has_column(), _has_table(), Fold legacy category pricing into seasonal price periods., upgrade()

### Community 364 - "Community 364"
Cohesion: 0.60
Nodes (5): downgrade(), Align section defaults and remove the self-session catalog permission.  Revision, _restore_session_permission(), _set_role_default(), upgrade()

### Community 365 - "Community 365"
Cohesion: 0.47
Nodes (5): downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns., _set_role_default(), upgrade()

### Community 366 - "Community 366"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083, upgrade()

### Community 367 - "Community 367"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 368 - "Community 368"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 369 - "Community 369"
Cohesion: 0.40
Nodes (5): _authorize_oauth_state_actor(), Revalidate the actor embedded in a short-lived OAuth state token.      Provider, Revalidate the actor embedded in a short-lived OAuth state token.      Provider, Revalidate the actor embedded in a short-lived OAuth state token.      Provider, Revalidate the actor embedded in a short-lived OAuth state token.      Provider

### Community 370 - "Community 370"
Cohesion: 0.50
Nodes (3): create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, _request_source()

### Community 371 - "Community 371"
Cohesion: 0.40
Nodes (5): _backfill_not_null_nulls(), Fill NULLs in NOT-NULL model columns that carry a default.      A column added i, Fill NULLs in NOT-NULL model columns that carry a default.      A column added i, Fill NULLs in NOT-NULL model columns that carry a default.      A column added i, Fill NULLs in NOT-NULL model columns that carry a default.      A column added i

### Community 372 - "Community 372"
Cohesion: 0.40
Nodes (3): 1e7bc27 feat(pwa): close TECH-0090 gaps — manifest, offline banner, maskable icons, frontendRoot, publicRoot

### Community 373 - "Community 373"
Cohesion: 0.40
Nodes (1): credentials

### Community 374 - "Community 374"
Cohesion: 0.40
Nodes (2): credentials, receptionistCredentials

### Community 375 - "Community 375"
Cohesion: 0.40
Nodes (4): Stock and inventory movement models., StockItem, StockLocation, StockMovement

### Community 376 - "Community 376"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 377 - "Community 377"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceRead, GuestRoomAvoidanceResolveRequest, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 378 - "Community 378"
Cohesion: 0.40
Nodes (2): HotelConfigUpdate, _normalize_currency()

### Community 379 - "Community 379"
Cohesion: 0.50
Nodes (3): _prepare_environment(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2, seed()

### Community 380 - "Community 380"
Cohesion: 0.40
Nodes (5): Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., with_distributed_lock()

### Community 381 - "Community 381"
Cohesion: 0.50
Nodes (4): compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 382 - "Community 382"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 383 - "Community 383"
Cohesion: 0.80
Nodes (4): _link(), _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 384 - "Community 384"
Cohesion: 0.70
Nodes (4): _client_with_db(), _override_auth(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 385 - "Community 385"
Cohesion: 0.80
Nodes (4): _client(), _move(), test_receptionist_can_record_complaint_but_cannot_resolve_it(), test_second_complaint_reactivates_the_same_guest_room_row()

### Community 386 - "Community 386"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 387 - "Community 387"
Cohesion: 0.60
Nodes (4): Same per-location bug as stock_service: an 'out' at location B must be     valid, _seed_hotels(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped()

### Community 388 - "Community 388"
Cohesion: 0.40
Nodes (1): Response

### Community 389 - "Community 389"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 390 - "Community 390"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 392 - "Community 392"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 393 - "Community 393"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 394 - "Community 394"
Cohesion: 0.60
Nodes (4): _check_clause(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in, upgrade()

### Community 395 - "Community 395"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 396 - "Community 396"
Cohesion: 0.50
Nodes (3): Add durable job dedupe and worker heartbeat metadata., _rls(), upgrade()

### Community 397 - "Community 397"
Cohesion: 0.50
Nodes (4): main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only., Replace this repository's absolute root in generated instructions only.

### Community 398 - "Community 398"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 399 - "Community 399"
Cohesion: 0.50
Nodes (4): _build_audit_timeline_csv(), export_audit_timeline(), Export the redacted unified timeline, capped at 5,000 rows per request., Export the redacted unified timeline, capped at 5,000 rows per request.

### Community 400 - "Community 400"
Cohesion: 0.50
Nodes (4): Global application settings loaded from environment variables., Global application settings loaded from environment variables., Settings, BaseSettings

### Community 401 - "Community 401"
Cohesion: 0.50
Nodes (4): Non-delegable invariant: only this hotel's owner administers RBAC., Non-delegable invariant: only this hotel's owner administers RBAC., Non-delegable invariant: only this hotel's owner administers RBAC., require_permission_administrator()

### Community 402 - "Community 402"
Cohesion: 0.50
Nodes (1): credentials

### Community 403 - "Community 403"
Cohesion: 0.50
Nodes (1): credentials

### Community 404 - "Community 404"
Cohesion: 0.50
Nodes (2): ownerCredentials, receptionistCredentials

### Community 405 - "Community 405"
Cohesion: 0.67
Nodes (3): build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 406 - "Community 406"
Cohesion: 0.50
Nodes (3): OperationalAuditItemRead, OperationalAuditRead, Contracts for the owner/co-owner operational audit projection.

### Community 407 - "Community 407"
Cohesion: 0.83
Nodes (3): compute_canonical_stay_pricing(), _hotel_default_currency(), _quantize()

### Community 408 - "Community 408"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 409 - "Community 409"
Cohesion: 0.67
Nodes (3): GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti, _receptionist_context(), test_receptionist_can_view_operations_summary_and_pending_actions()

### Community 410 - "Community 410"
Cohesion: 0.67
Nodes (2): _override_auth(), test_receptionist_can_get_price_quote()

### Community 411 - "Community 411"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 412 - "Community 412"
Cohesion: 0.67
Nodes (3): B3.2: migration adding guests.birth_place/birth_country/marital_status/occupatio, _run(), test_guest_checkin_profile_migration_up_down_up_on_sqlite()

### Community 413 - "Community 413"
Cohesion: 0.67
Nodes (3): _override_auth(), Regression guard for a real bug B3.2 uncovered: POST /api/guests/ dumps every Gu, test_create_guest_via_api_accepts_new_checkin_profile_fields()

### Community 414 - "Community 414"
Cohesion: 0.67
Nodes (3): _client(), _DB, test_owner_can_enter_secret_connection_mutations_but_co_owner_is_denied()

### Community 415 - "Community 415"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 416 - "Community 416"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 417 - "Community 417"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t, test_process_outbox_delivers_across_every_active_hotel()

### Community 418 - "Community 418"
Cohesion: 0.50
Nodes (4): Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, test_verify_email_code_guessing_is_rate_limited()

### Community 419 - "Community 419"
Cohesion: 0.50
Nodes (4): validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th, test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate()

### Community 420 - "Community 420"
Cohesion: 0.50
Nodes (4): Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun, test_register_is_rate_limited_by_source()

### Community 421 - "Community 421"
Cohesion: 0.83
Nodes (3): _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations()

### Community 422 - "Community 422"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 423 - "Community 423"
Cohesion: 0.67
Nodes (3): _index_names(), Focused regression tests for the TECH-0063 OLTP audit fixes., test_hot_path_composite_indexes_exist_in_models()

### Community 425 - "Community 425"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 426 - "Community 426"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 427 - "Community 427"
Cohesion: 0.50
Nodes (1): guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho

### Community 428 - "Community 428"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 429 - "Community 429"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 430 - "Community 430"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 431 - "Community 431"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 432 - "Community 432"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 433 - "Community 433"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 434 - "Community 434"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 435 - "Community 435"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 436 - "Community 436"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 437 - "Community 437"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 438 - "Community 438"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 439 - "Community 439"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 440 - "Community 440"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 441 - "Community 441"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 442 - "Community 442"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 443 - "Community 443"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 444 - "Community 444"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 445 - "Community 445"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 446 - "Community 446"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 447 - "Community 447"
Cohesion: 0.50
Nodes (1): Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re

### Community 448 - "Community 448"
Cohesion: 0.50
Nodes (1): Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for

### Community 449 - "Community 449"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 450 - "Community 450"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 451 - "Community 451"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 452 - "Community 452"
Cohesion: 0.50
Nodes (1): stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision

### Community 453 - "Community 453"
Cohesion: 0.50
Nodes (1): repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/

### Community 454 - "Community 454"
Cohesion: 0.50
Nodes (1): add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide

### Community 455 - "Community 455"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 456 - "Community 456"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 457 - "Community 457"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 458 - "Community 458"
Cohesion: 0.50
Nodes (1): Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  `

### Community 459 - "Community 459"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 460 - "Community 460"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 461 - "Community 461"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 462 - "Community 462"
Cohesion: 0.50
Nodes (1): laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre

### Community 463 - "Community 463"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 464 - "Community 464"
Cohesion: 0.50
Nodes (1): laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7

### Community 465 - "Community 465"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 466 - "Community 466"
Cohesion: 1.00
Nodes (2): main(), validate()

### Community 467 - "Community 467"
Cohesion: 1.00
Nodes (2): BridgeActivity, MainActivity

### Community 468 - "Community 468"
Cohesion: 0.67
Nodes (1): credentials

### Community 469 - "Community 469"
Cohesion: 0.67
Nodes (1): owner

### Community 471 - "Community 471"
Cohesion: 0.67
Nodes (1): credentials

### Community 472 - "Community 472"
Cohesion: 0.67
Nodes (3): inboxKey(), useNotificationsInbox(), useUnreadNotificationCount()

### Community 473 - "Community 473"
Cohesion: 0.67
Nodes (3): Non-financial category metadata safe for housekeeping workflows., Non-financial category metadata safe for housekeeping workflows., RoomCategoryOperationalRead

### Community 474 - "Community 474"
Cohesion: 0.67
Nodes (3): Room state without rates or free-text notes that may contain PII., Room state without rates or free-text notes that may contain PII., RoomHousekeepingRead

### Community 475 - "Community 475"
Cohesion: 0.67
Nodes (1): One-shot notification cycle: generate due daily reports, then deliver pending ou

### Community 478 - "Community 478"
Cohesion: 0.67
Nodes (1): TestCurrentSession

### Community 479 - "Community 479"
Cohesion: 0.67
Nodes (1): TestExportSession

### Community 480 - "Community 480"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 483 - "Community 483"
Cohesion: 1.00
Nodes (1): Minimal API for recording room preferences on a guest profile.

### Community 486 - "Community 486"
Cohesion: 1.00
Nodes (1): Pydantic schemas for the small guest-room preference signal.

### Community 490 - "Community 490"
Cohesion: 1.00
Nodes (1): Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260

### Community 491 - "Community 491"
Cohesion: 1.00
Nodes (1): Set one global default without creating duplicate rows on reruns.

### Community 492 - "Community 492"
Cohesion: 1.00
Nodes (1): add tenant-scoped guest room preferences  Revision ID: 3c2dea57666d Revises: 202

### Community 493 - "Community 493"
Cohesion: 1.00
Nodes (1): Install the PostgreSQL tenant policy; no-op on other dialects.

### Community 494 - "Community 494"
Cohesion: 1.00
Nodes (1): Remove the PostgreSQL tenant policy before dropping its table.

## Knowledge Gaps
- **1400 isolated node(s):** `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.`, `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho` (+1395 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 75`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `test_database_foundation_complete()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 153`** (2 nodes): `ExpediaAdapter`, `OTAProviderAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 156`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 164`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 274`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 335`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 336`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 345`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 373`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 374`** (2 nodes): `credentials`, `receptionistCredentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 378`** (2 nodes): `HotelConfigUpdate`, `_normalize_currency()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 388`** (1 nodes): `Response`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 402`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 403`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 404`** (2 nodes): `ownerCredentials`, `receptionistCredentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 410`** (2 nodes): `_override_auth()`, `test_receptionist_can_get_price_quote()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 415`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 426`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 427`** (1 nodes): `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 428`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 429`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 430`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 431`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 432`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 433`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 434`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 435`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 436`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 437`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 438`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 439`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 440`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 441`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 442`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 443`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 444`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 445`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 446`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 447`** (1 nodes): `Add (hotel_id, created_at) index on reservations for A2 recent-order paging.  Re`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 448`** (1 nodes): `Add (hotel_id, room_id, check_in_date, check_out_date) index on reservations for`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 449`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 450`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 451`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 452`** (1 nodes): `stock_items.kind (supply vs linen) + soft-delete-aware name uniqueness  Revision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 453`** (1 nodes): `repair: ensure (hotel_id, id) unique constraints exist on rooms/room_categories/`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 454`** (1 nodes): `add idempotency_key to stock_movements  Revision ID: 20260818_stock_movement_ide`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 455`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 456`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 457`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 458`** (1 nodes): `Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  ``
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 459`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 460`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 461`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 462`** (1 nodes): `laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 463`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 464`** (1 nodes): `laundry vendor settlements (quarterly paid/not-paid mark)  Revision ID: e2c4a9f7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 465`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 466`** (2 nodes): `main()`, `validate()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 467`** (2 nodes): `BridgeActivity`, `MainActivity`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 468`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 469`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 471`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 475`** (1 nodes): `One-shot notification cycle: generate due daily reports, then deliver pending ou`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 478`** (1 nodes): `TestCurrentSession`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 479`** (1 nodes): `TestExportSession`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 480`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 483`** (1 nodes): `Minimal API for recording room preferences on a guest profile.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 486`** (1 nodes): `Pydantic schemas for the small guest-room preference signal.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 490`** (1 nodes): `Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 491`** (1 nodes): `Set one global default without creating duplicate rows on reruns.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 492`** (1 nodes): `add tenant-scoped guest room preferences  Revision ID: 3c2dea57666d Revises: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 493`** (1 nodes): `Install the PostgreSQL tenant policy; no-op on other dialects.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 494`** (1 nodes): `Remove the PostgreSQL tenant policy before dropping its table.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 11` to `Community 14`, `Community 2`, `Community 27`, `Community 40`, `Community 35`, `Community 41`, `Community 8`, `Community 25`, `Community 71`, `Community 10`, `Community 0`, `Community 18`, `Community 24`, `Community 3`, `Community 58`, `Community 123`, `Community 134`, `Community 6`, `Community 34`, `Community 30`, `Community 78`, `Community 15`, `Community 5`, `Community 20`, `Community 55`, `Community 38`, `Community 146`, `Community 94`, `Community 26`, `Community 156`, `Community 28`, `Community 12`, `Community 72`, `Community 80`, `Community 93`, `Community 135`, `Community 59`, `Community 375`, `Community 148`, `Community 102`, `Community 31`, `Community 39`, `Community 111`, `Community 73`, `Community 17`, `Community 96`, `Community 109`, `Community 33`, `Community 245`, `Community 61`, `Community 110`, `Community 413`, `Community 144`, `Community 19`, `Community 418`, `Community 419`, `Community 420`, `Community 162`, `Community 169`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 0` to `Community 38`, `Community 10`, `Community 8`, `Community 6`, `Community 5`, `Community 125`, `Community 2`, `Community 11`, `Community 40`, `Community 25`, `Community 286`, `Community 12`, `Community 13`, `Community 70`, `Community 26`, `Community 97`, `Community 3`, `Community 59`, `Community 102`, `Community 88`, `Community 31`, `Community 126`, `Community 71`, `Community 7`, `Community 237`, `Community 109`, `Community 33`, `Community 245`, `Community 61`, `Community 78`, `Community 119`, `Community 24`, `Community 110`, `Community 20`, `Community 413`, `Community 144`, `Community 56`, `Community 27`, `Community 72`, `Community 15`, `Community 418`, `Community 419`, `Community 420`, `Community 162`, `Community 169`, `Community 65`, `Community 48`, `Community 478`, `Community 479`?**
  _High betweenness centrality (0.071) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 8`, `Community 6`, `Community 10`, `Community 28`, `Community 14`, `Community 11`, `Community 40`, `Community 41`, `Community 25`, `Community 58`, `Community 34`, `Community 97`, `Community 3`, `Community 59`, `Community 12`, `Community 287`, `Community 78`, `Community 119`, `Community 24`, `Community 151`, `Community 48`, `Community 478`, `Community 479`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Are the 1426 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses the ca`) actually correct?**
  _`Reservation` has 1426 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1368 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses the ca`) actually correct?**
  _`ReservationStatusEnum` has 1368 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1335 inferred relationships involving `HotelConfiguration` (e.g. with `AcceptPayload` and `FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend`) actually correct?**
  _`HotelConfiguration` has 1335 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1226 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses the ca`) actually correct?**
  _`Room` has 1226 INFERRED edges - model-reasoned connections that need verification._