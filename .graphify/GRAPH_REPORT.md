# Graph Report - .  (2026-07-24)

## Corpus Check
- Large corpus: 734 files · ~482,350 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 6642 nodes · 22254 edges · 294 communities detected
- Extraction: 63% EXTRACTED · 37% INFERRED · 0% AMBIGUOUS · INFERRED: 8140 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 8140 · contains: 4247 · calls: 3236 · MODIFIES: 1737 · ON_BRANCH: 1258 · rationale_for: 990 · imports: 722 · imports_from: 568 · method: 557 · inherits: 531 · PARENT_OF: 268


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 734 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 8 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `b8b52fa`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `ReservationStatusEnum` - 538 edges
2. `Reservation` - 537 edges
3. `HotelConfiguration` - 476 edges
4. `Room` - 395 edges
5. `Guest` - 383 edges
6. `RoomCategory` - 366 edges
7. `Base` - 336 edges
8. `RoomStatusEnum` - 302 edges
9. `TransactionTypeEnum` - 242 edges
10. `PaymentMethodEnum` - 239 edges

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

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (177): FastAPI routes for Check-in / Check-out., DocumentTypeEnum, Guest, HotelConfiguration, Reservation, Room, RoomStatusEnum, BenchmarkResult (+169 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (188): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, chore/weekly-orchestrator-2026-07-03, codex/feature/agent-ops-knowledge, codex/feature/pms-e2e-scale-hardening, codex/feature/trusted-qa-bootstrap, codex/fix-render-postgres-enum-values, main, 01498d0 Harden password reset flow (verified-only, dev code return) (+180 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (140): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+132 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (127): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Calculate pricing for a potential booking without persisting it.     Uses Catego, Calculate pricing for a potential booking without persisting it.     Uses Catego, Quickly seed demo bookings (requires DEMO_MODE=true)., Quickly seed demo bookings (requires DEMO_MODE=true)., Ensure computed fields land in the response. (+119 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (106): CheckInRequest, BaseModel, BillingPolicyPayload, BillingPolicyUpdateRequest, EmailTestRequest, MasterAdminLoginRequest, MasterAdminLoginResponse, MasterAdminSessionResponse (+98 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (84): acceptInvitation(), AuthResponse, _build_auth_response(), _generate_code(), getInvitationInfo(), _issue_email_token(), login(), _mask_email() (+76 more)

### Community 6 - "Community 6"
Cohesion: 0.03
Nodes (71): email_status(), getHotelConfig(), HotelConfig, HotelConfigUpdate, FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., updateHotelConfig(), createPaymentSurcharge() (+63 more)

### Community 7 - "Community 7"
Cohesion: 0.03
Nodes (81): Base, Base class for all ORM models., _DecimalAwareEncoder, _frontend_placeholder(), _is_demo_mode_enabled(), lifespan(), StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on (+73 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (37): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, _append_action_event_message(), apply_action_run_draft(), approve_action_run() (+29 more)

### Community 9 - "Community 9"
Cohesion: 0.03
Nodes (26): dc4b68a ojooooo, e34785c prueba, build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so, DashboardPage(), todayIso(), bubbleStyles (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.03
Nodes (66): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), createPaymentLink() (+58 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (33): datastores_healthcheck(), _postgres_healthcheck(), _redis_healthcheck(), Staff management endpoints for hotel public API keys., _backfill_not_null_nulls(), _column_fill_value(), get_db(), get_engine() (+25 more)

### Community 12 - "Community 12"
Cohesion: 0.09
Nodes (72): CashCloseReport, CashCustodyHandoff, CashCustodyStatusEnum, CashMovement, CashMovementTypeEnum, CashSession, CashSessionStatusEnum, Cash register (caja) models — Sprint 1 requirement per v72 §13.  Lifecycle:   Ca (+64 more)

### Community 13 - "Community 13"
Cohesion: 0.07
Nodes (49): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+41 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (55): add_reservation_guests(), buildQueryString(), cancel_reservation(), cancelReservation(), change_dates(), checkInReservation(), checkOutReservation(), clearReservationManualReview() (+47 more)

### Community 15 - "Community 15"
Cohesion: 0.13
Nodes (48): BillingAdjustment, BillingAdjustmentTypeEnum, Financial transaction linked to a reservation.     Every money movement is recor, Transaction, TransactionTypeEnum, PaymentError, _assign_hotel(), ensure_category_pricing_table() (+40 more)

### Community 16 - "Community 16"
Cohesion: 0.04
Nodes (20): 7e2edb6 Merge Analytics R1.0, df173d1 Implement Analytics R1.0 dashboard, chat IA, and support, AnalyticsComparisonStateRead, AnalyticsComparisonWindowRead, AnalyticsMetricCardRead, AnalyticsResponseEnvelopeRead, AnalyticsStarterSummaryDataRead, AnalyticsStarterSummaryRead (+12 more)

### Community 17 - "Community 17"
Cohesion: 0.05
Nodes (31): admin_comped_override(), change_plan(), changeSubscriptionPlan(), getSubscriptionStatus(), listSubscriptionPlans(), Subscription status and entitlements endpoints., _remaining_trial_days(), _serialize_status_payload() (+23 more)

### Community 18 - "Community 18"
Cohesion: 0.13
Nodes (50): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily (+42 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (39): get_settings(), _gmail_is_active(), _has_value(), is_demo_mode(), is_preview_qa_mode(), is_production_mode(), _is_public_https_url(), is_testing_mode() (+31 more)

### Community 20 - "Community 20"
Cohesion: 0.09
Nodes (36): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+28 more)

### Community 21 - "Community 21"
Cohesion: 0.09
Nodes (44): 805b47a Unify reservation pricing with signed quote contract, APIKeyPurposeEnum, PaymentLinkRead, ReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead, PublicAvailabilityResponse (+36 more)

### Community 22 - "Community 22"
Cohesion: 0.11
Nodes (51): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+43 more)

### Community 23 - "Community 23"
Cohesion: 0.07
Nodes (49): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), _load_provider_evidence(), Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, Return ``dsn`` only when provider evidence proves a disposable QA target.      E (+41 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (43): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+35 more)

### Community 25 - "Community 25"
Cohesion: 0.12
Nodes (50): deactivate_payment_surcharge(), _get_surcharge_or_404(), PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, update_payment_surcharge(), FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re (+42 more)

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (36): 107f875 Support legacy master admin underscore routes, 3d34a97 Connect system mail through master admin, 7e196fa Fix master admin cross-origin session cookies, 885bb1a Prefer completed hotel on login, 89b1823 Align master admin env names and bootstrap login, 92ae064 Reduce noisy master session hydration 401, 96ff88b Migrate system mail to Resend, cfaae45 Fix master billing policy for legacy schema (+28 more)

### Community 27 - "Community 27"
Cohesion: 0.07
Nodes (38): IntegrationCatalog, IntegrationConnection, IntegrationEvent, _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error() (+30 more)

### Community 28 - "Community 28"
Cohesion: 0.06
Nodes (25): 1a71e7d feat: add ota allocation data foundation, 24d09f0 feat(db): v72 complete audit — phase 4, multi-tenancy tests, architecture docs, 32c7435 feat(phase2): port daily rates (§13) from fervent, 52604e5 feat(db): PostgreSQL real validation green 8/8 — payment models, migration fixes, 7506225 feat(R2b): soft delete for domain records (§26), 83674a3 feat(phase2): port payment surcharges (§12.3) from fervent, a61a51c chore: checkpoint de prueba antes de gemma 4, c580b56 ojala si (+17 more)

### Community 29 - "Community 29"
Cohesion: 0.07
Nodes (15): OTASyncEvent, OTASyncJob, NormalizedOTAReservation, OTAAdapterContext, OTAOperationResult, OTAProviderAdapter, Common contracts for OTA provider adapters.  The goal is to keep Booking, Expedi, Foundational OTA adapter interfaces and orchestration services. (+7 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (44): GuestCompanion, RateLimitEvent, db(), db_engine(), hotel_config(), pg_engine(), Pytest configuration and fixtures. Uses an in-memory SQLite database for isolate, Create a fresh in-memory SQLite engine for each test. (+36 more)

### Community 31 - "Community 31"
Cohesion: 0.11
Nodes (41): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, LLMFeedbackEvent (+33 more)

### Community 32 - "Community 32"
Cohesion: 0.10
Nodes (47): _b64url_decode(), _b64url_encode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), _canonical_json(), canonical_provider_evidence_json(), cli() (+39 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (36): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsCategoryDetailPage(), AnalyticsChannelsPage(), AnalyticsCompanyDetailPage(), AnalyticsEnvelope, AnalyticsFilterState (+28 more)

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (33): AuthUser, _assert_assignable_role(), _assert_manageable_membership(), invite_user(), inviteUser(), list_users(), listUsers(), _membership_user_info() (+25 more)

### Community 35 - "Community 35"
Cohesion: 0.19
Nodes (33): OTAConnection, OTAProvider, OTARatePlanMapping, OTAReservationLifecycleEnum, OTAReservationLink, OTARoomMapping, OTAReservationMapping, OTASyncStatusEnum (+25 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (37): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+29 more)

### Community 37 - "Community 37"
Cohesion: 0.11
Nodes (14): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session(), TestAutoCashEntry (+6 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (39): Validate reset code without changing password (paso previo en UI)., Prefer a hotel whose onboarding is already complete.      When a user belongs to, validate_reset(), AcceptPayload, InvitePayload, InviteResponse, User management per hotel (owners/co-owners)., UpdateRolePayload (+31 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (14): _make_hotel_guest_reservation(), test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict(), test_pending_action_resolution(), test_refund_request_gateway_path() (+6 more)

### Community 40 - "Community 40"
Cohesion: 0.10
Nodes (29): create_room_block(), _exclusive_end(), _existing_user_id(), _inclusive_end(), list_room_blocks(), _read_block(), release_room_block(), RoomBlockCreate (+21 more)

### Community 41 - "Community 41"
Cohesion: 0.15
Nodes (28): 6e6d179 Prepare release candidate for landing and onboarding, 87b0eb6 Improve marketing SEO content, linking, and metadata, Seo(), SeoProps, StructuredData, resolveAppUrl(), benefitPoints, faqItems (+20 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (28): ApiError, clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminUser, MasterBillingPolicy, MasterDashboardSummary, MasterEmailConnectResponse (+20 more)

### Community 43 - "Community 43"
Cohesion: 0.08
Nodes (32): Base, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterBillingPolicy, MasterStripeSettings, MasterStripeWebhookEvent, MasterSystemEmailConnection (+24 more)

### Community 44 - "Community 44"
Cohesion: 0.05
Nodes (17): OTAChannelsPayload, PaymentMethodsPayload, setCategories(), setDepositPolicy(), setHotelIdentity(), setOtaChannels(), setOwner(), setRooms() (+9 more)

### Community 45 - "Community 45"
Cohesion: 0.11
Nodes (36): Payment, PaymentLink, PaymentWebhookEvent, Payment gateway tracking models: PaymentLink, Payment, PaymentWebhookEvent.  Sou, One gateway payment object (MP preference / PayPal order / Stripe intent)., Raw webhook log per payment — idempotent on (hotel_id, provider, webhook_id)., Guest-facing pre-payment object (checkout URL / QR). May collect partial payment, balance_due_from_transactions() (+28 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (28): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+20 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (25): AnalyticsSegmentsPage(), MasterAdminProtectedShell(), MasterAdminRoot(), navItems, MasterAdminSessionProvider(), OnboardingWizard(), SettingsAssistantPage(), SettingsHotelPage() (+17 more)

### Community 48 - "Community 48"
Cohesion: 0.10
Nodes (32): addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashCustodyHandoff, CashMovement, CashMovementPayload, CashMovementType, CashSession (+24 more)

### Community 49 - "Community 49"
Cohesion: 0.07
Nodes (22): add_companions(), addGuestCompanions(), _build_guest_ledger_csv(), createGuest(), _enum_value(), export_guest_ledger(), getGuest(), Guest (+14 more)

### Community 50 - "Community 50"
Cohesion: 0.45
Nodes (35): FastAPI routes for Reservations. Complete CRUD + cancel, modify, no-show, extend, §5.2 — Run allocation engine in background after reservation changes.     Create, Register the deferred corporate collection (v72 §3.5): settled., Register the deferred corporate collection (v72 §3.5): settled., Register the deferred corporate collection (v72 §3.5): settled., Cancel a reservation. Post check-in cancellations are not allowed., Cancel a reservation. Post check-in cancellations are not allowed., Cancel a reservation. Post check-in cancellations are not allowed. (+27 more)

### Community 51 - "Community 51"
Cohesion: 0.12
Nodes (26): configure_dedicated_baseline(), env_page(), fixtures(), set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation(), test_dedicated_baseline_refuses_provider_lease_mismatch(), test_dedicated_baseline_refuses_weak_or_target_derived_lease() (+18 more)

### Community 52 - "Community 52"
Cohesion: 0.10
Nodes (30): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+22 more)

### Community 53 - "Community 53"
Cohesion: 0.14
Nodes (31): _apply_corporate_pricing(), _apply_custom_deposit_amount(), _apply_pricing_result_to_reservation(), assert_reservation_version(), calculate_reservation_pricing(), _calendar_pricing_source(), check_room_availability(), _compute_deposit_amount() (+23 more)

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (28): FastAPI routes for Guest management., Add new companions to an existing guest., GuestRatingEnum, GuestTag, GuestTagTypeEnum, Behavioral / alert tags on a guest (v72 §2.6).     Multiple tags per guest; each, HotelAPIKey, Per-hotel API credential. `key_hash` stores a hashed version of the secret; (+20 more)

### Community 55 - "Community 55"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider (+12 more)

### Community 56 - "Community 56"
Cohesion: 0.08
Nodes (32): _canonical_identity(), _enabled(), PostgresTargetSafetyError, PostgreSQL validation tests.  Run with:   DATABASE_URL_TEST=<isolated-qa-dsn> \, Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic downgrade to base then upgrade to head — idempotency check., Alembic downgrade to base then upgrade to head — idempotency check., Critical unique constraints reject duplicates in PostgreSQL. (+24 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (26): BootstrapConfigurationError, _decode_lease_entropy(), JsonGetter, main(), ProviderClients, Small GET-only API client with bounded retries and redacted failures., Safe failure whose message never contains provider response bodies., Small GET-only API client with bounded retries and redacted failures. (+18 more)

### Community 58 - "Community 58"
Cohesion: 0.17
Nodes (28): Lightweight subscription tracking for enforcement and auditing (v2 tables)., Subscription, SubscriptionEvent, _actor_payload(), _apply_plan(), _as_utc(), change_subscription_plan(), _compute_can_write() (+20 more)

### Community 59 - "Community 59"
Cohesion: 0.15
Nodes (2): _hotel_default_currency(), OTAIntegrationService

### Community 60 - "Community 60"
Cohesion: 0.23
Nodes (29): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _deployment_git_identity(), _deployment_hosts(), _dict() (+21 more)

### Community 61 - "Community 61"
Cohesion: 0.08
Nodes (8): listTimezones(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., 2ba0905 Cache timezone catalog and remove repeated lookups, 486bfb2 feat(R1): expose Room (§4) and Company (§3) fields in API schemas, 6f60c12 feat(security): SLICE-01 configurable permission matrix + role boundaries, bad20c6 Gate startup email behind SMTP_STARTUP_NOTIFY and send once, ec54376 Add env example and GHCR build/push workflow, useTimezones()

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (22): ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, daily_report(), DailyOperationalReport, getDailyOperationalReport(), getOperationalAlerts(), NightlyOperationalSummary (+14 more)

### Community 63 - "Community 63"
Cohesion: 0.21
Nodes (26): HotelPermissionOverride, Permission, Configurable permission matrix models., RolePermissionDefault, Security / access audit log — free-form operational security events.  Distinct f, SecurityAuditLog, get_matrix(), _insert_if_missing() (+18 more)

### Community 64 - "Community 64"
Cohesion: 0.08
Nodes (3): BookingAdapter, ExpediaAdapter, OTAProviderAdapter

### Community 65 - "Community 65"
Cohesion: 0.15
Nodes (25): PaymentProof, PaymentProofBlob, PaymentProofStatusEnum, Manual bank-transfer evidence and approval lifecycle., Private image evidence awaiting explicit staff confirmation., Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., PaymentProofCreate (+17 more)

### Community 67 - "Community 67"
Cohesion: 0.11
Nodes (15): SimpleRateLimiter, _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), Coarse payment status derived from amounts (no sensitive detail)., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by confirmation code (v72 §16).      Scoped (+7 more)

### Community 68 - "Community 68"
Cohesion: 0.12
Nodes (21): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity() (+13 more)

### Community 69 - "Community 69"
Cohesion: 0.13
Nodes (22): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), SessionLike (+14 more)

### Community 70 - "Community 70"
Cohesion: 0.11
Nodes (20): addLaundryItem(), createLaundryBatch(), LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead (+12 more)

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
Cohesion: 0.15
Nodes (22): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_job_path(), _flatten_payload_rows() (+14 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (21): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product() (+13 more)

### Community 76 - "Community 76"
Cohesion: 0.22
Nodes (23): AttestationError, _b64url_decode(), _b64url_encode(), build_attestation(), _canonical_json(), _iso_utc(), _json_object(), _load_private_key() (+15 more)

### Community 77 - "Community 77"
Cohesion: 0.10
Nodes (16): listGuests(), listRooms(), cancelWaitlistEntry(), createWaitlistEntry(), listWaitlistEntries(), promoteWaitlistEntry(), API routes for reservation waitlist operations., WaitlistEntry (+8 more)

### Community 78 - "Community 78"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 79 - "Community 79"
Cohesion: 0.20
Nodes (23): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+15 more)

### Community 80 - "Community 80"
Cohesion: 0.19
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 81 - "Community 81"
Cohesion: 0.11
Nodes (10): main(), valid_https(), 19b8b7b Harden isolated preview QA and trusted release evidence, command(), fenced(), frontend_routes(), heading(), main() (+2 more)

### Community 82 - "Community 82"
Cohesion: 0.16
Nodes (21): connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration(), get_status() (+13 more)

### Community 83 - "Community 83"
Cohesion: 0.08
Nodes (12): CategoryPayload, DepositPolicyPayload, finishOnboarding(), HotelIdentityPayload, OnboardingProviderSetup, OnboardingStatus, OwnerPayload, FastAPI routes for the onboarding flow used by smoke tests. (+4 more)

### Community 84 - "Community 84"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 85 - "Community 85"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 86 - "Community 86"
Cohesion: 0.28
Nodes (23): _build_finish_gates(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status(), _merge_extra_policies() (+15 more)

### Community 87 - "Community 87"
Cohesion: 0.18
Nodes (5): make_res(), make_rooms(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 88 - "Community 88"
Cohesion: 0.17
Nodes (20): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+12 more)

### Community 89 - "Community 89"
Cohesion: 0.12
Nodes (14): _make_guest(), _make_reservation(), test_api_key_name_unique_per_hotel_not_global(), test_delete_hotel_a_guest_does_not_affect_hotel_b(), test_guest_dedup_same_hotel_raises(), test_guest_dedup_unique_per_hotel_not_global(), test_guest_scoped_to_hotel(), test_guest_tags_scoped_to_hotel() (+6 more)

### Community 90 - "Community 90"
Cohesion: 0.13
Nodes (6): _make_reservation(), TestWaitlistIsolation, TestWaitlistListing, TestWaitlistModelFields, TestWaitlistResolveLogic, tiny_hotel()

### Community 91 - "Community 91"
Cohesion: 0.15
Nodes (19): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), DailyRateOut, DailyRatePrices, getCategoryDailyRates() (+11 more)

### Community 92 - "Community 92"
Cohesion: 0.20
Nodes (21): ReservationError, _available_room_for_conflict(), change_reservation_dates(), _compute_deposit_amount(), extend_reservation_stay(), _extension_amount(), _extension_conflicts(), _has_transactions() (+13 more)

### Community 93 - "Community 93"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 94 - "Community 94"
Cohesion: 0.13
Nodes (11): _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled(), test_get_guest_summary_includes_alerts_and_stays() (+3 more)

### Community 95 - "Community 95"
Cohesion: 0.12
Nodes (12): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+4 more)

### Community 96 - "Community 96"
Cohesion: 0.11
Nodes (2): 4f50de1 Add successor cash register controls, b4c9bd8 Harden cash rotation and payment integrity

### Community 97 - "Community 97"
Cohesion: 0.10
Nodes (15): addGuestTag(), checkInGuestReservation(), getGuestQuickProfile(), GuestTag, GuestTagPayload, GuestTagType, listGuestTags(), resolveGuestTag() (+7 more)

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (14): PriceField, SingleRateInput, useBulkUpdateRateField(), useBulkUpsertRates(), useCategoryDailyRates(), useRateCalendar(), useUpsertDailyRate(), BULK_ACTION_OPTIONS (+6 more)

### Community 99 - "Community 99"
Cohesion: 0.18
Nodes (14): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate (+6 more)

### Community 100 - "Community 100"
Cohesion: 0.14
Nodes (15): fetchPermissionMatrix(), PermissionCell, PermissionMatrix, PermissionMatrixResponse, PermissionOverridePayload, PermissionOverrideRequest, PermissionOverrideResponse, PermissionRole (+7 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (5): CurrentStock, DecimalValue, StockItem, StockLocation, StockMovement

### Community 102 - "Community 102"
Cohesion: 0.12
Nodes (4): dashboard_summary(), login(), me(), _serialize_user()

### Community 103 - "Community 103"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 104 - "Community 104"
Cohesion: 0.32
Nodes (18): _hotel(), _reservation(), test_cash_movement_requires_open_session(), test_cash_payment_posts_income_movement_to_open_session(), test_cash_payment_with_surcharge_posts_gross_amount_to_caja(), test_cash_payment_without_open_session_is_rejected(), test_cash_payment_without_open_session_opens_zero_balance_session(), test_cash_payment_without_open_session_still_succeeds() (+10 more)

### Community 105 - "Community 105"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 106 - "Community 106"
Cohesion: 0.13
Nodes (15): IntegrationHelpDrawer(), Props, IntegrationHelp, useConnectIntegration(), useIntegrations(), useRefreshIntegration(), useRevokeIntegration(), connectedSummary (+7 more)

### Community 107 - "Community 107"
Cohesion: 0.11
Nodes (11): V72 §5.2 — Reoptimización continua del motor de asignación.  After each new rese, If run_persisted_allocation raises, rollback must be called (not commit)., §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation (+3 more)

### Community 108 - "Community 108"
Cohesion: 0.20
Nodes (9): ABC, EmailProvider, EmailProviderError, get_email_provider(), _mask_email(), _mask_recipients(), _normalize_display_from(), NullEmailProvider (+1 more)

### Community 109 - "Community 109"
Cohesion: 0.17
Nodes (7): graphify_state(), main(), main(), run(), validate_json(), 1ebf84a Audit and harden agent operations context, bc938cf Add agent ops vault and cloud QA foundation

### Community 110 - "Community 110"
Cohesion: 0.24
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 111 - "Community 111"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 112 - "Community 112"
Cohesion: 0.17
Nodes (15): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), isAppHostname(), normalizeUrl(), PUBLIC_APP_URL, PUBLIC_SITE_URL, resolveAppLocation() (+7 more)

### Community 113 - "Community 113"
Cohesion: 0.27
Nodes (16): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _date_token(), get_cached_availability_payload(), get_cached_home_payload(), _get_cached_or_compute() (+8 more)

### Community 114 - "Community 114"
Cohesion: 0.29
Nodes (16): _collect_plan_entitlements(), delete_entitlement_override(), ensure_entitlements_seeded(), ensure_room_within_limit(), ensure_subscription(), entitlements_payload(), get_effective_room_limit(), get_entitlements() (+8 more)

### Community 115 - "Community 115"
Cohesion: 0.13
Nodes (6): opened_cash_register(), Tests for Check-in Service. Validates guest data requirements before allowing ch, Operational tests must prepare the caja before collecting cash., TestCheckIn, TestCheckOut, TestGuestValidation

### Community 116 - "Community 116"
Cohesion: 0.13
Nodes (11): DailyRateRangeRow, RateCalendarResponse, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, RateEditorGrid() (+3 more)

### Community 117 - "Community 117"
Cohesion: 0.13
Nodes (14): createStockItem(), createStockLocation(), createStockMovement(), getCurrentStock(), listLowStockItems(), listStockItems(), listStockLocations(), StockMovementCreate (+6 more)

### Community 118 - "Community 118"
Cohesion: 0.23
Nodes (14): Exception, _build_message(), ensure_hotel_gmail_ready(), HotelOutboundEmailError, HotelOutboundIdentity, HotelOutboundSendResult, send_hotel_email(), availability_lookup() (+6 more)

### Community 119 - "Community 119"
Cohesion: 0.23
Nodes (1): OnboardingState

### Community 120 - "Community 120"
Cohesion: 0.23
Nodes (13): _active_room_blocks(), _alerts(), _available_with_review(), _cash_session(), daily_report(), _group(), _guest_name(), is_review_for_today() (+5 more)

### Community 121 - "Community 121"
Cohesion: 0.18
Nodes (9): current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item(), low_stock_items(), Hotel-scoped stock and inventory movement service., register_movement() (+1 more)

### Community 122 - "Community 122"
Cohesion: 0.17
Nodes (6): Regression contracts for the repository's agent-operations setup., run_qa_evidence_check(), test_qa_evidence_rejects_malformed_result_without_traceback(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_schema_accepts_full_catalog(), write_complete_qa_evidence()

### Community 123 - "Community 123"
Cohesion: 0.23
Nodes (14): Security regression tests for local QA operator attestations., tagged(), test_altered_signature_is_rejected(), test_attestation_older_than_24_hours_is_rejected(), test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_manifest_byte_change_after_signing_is_rejected() (+6 more)

### Community 124 - "Community 124"
Cohesion: 0.17
Nodes (8): BrokenRedis, FakeRedis, test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_miss_calls_producer(), test_operational_invalidation_clears_availability_and_analytics(), test_redis_down_falls_back_to_producer_without_raising(), test_ttl_and_serialization_round_trip()

### Community 125 - "Community 125"
Cohesion: 0.15
Nodes (6): 6f4beb1 feat(v72): Wave 3 — public API/keys + allocation V72 rules, _active_reservation_conflicts_for_room(), create_grouped_room_move(), get_group(), list_groups(), revert_group()

### Community 126 - "Community 126"
Cohesion: 0.22
Nodes (11): build_connect_redirect(), _build_unavailable_message(), _current_status(), _dev_outbox_path(), disconnect_system_email(), get_system_email_status(), _normalize_account_email(), _record_dev_email() (+3 more)

### Community 127 - "Community 127"
Cohesion: 0.26
Nodes (14): calculate_base_amount_before_surcharge(), calculate_payment_surcharge(), get_hotel_config(), get_payment_link_with_surcharge(), get_reservation_financial_summary(), _payment_method_value(), process_payment(), _recommended_financial_action() (+6 more)

### Community 128 - "Community 128"
Cohesion: 0.28
Nodes (14): _build_pending_actions(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _get_latest_ota_link(), _get_latest_room_move(), _get_related_adjustments(), get_reservation_operations_summary() (+6 more)

### Community 129 - "Community 129"
Cohesion: 0.51
Nodes (14): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), test_correct_version_passes_optimistic_lock(), test_no_prohibido_tag_allows_checkin(), test_omitting_client_version_skips_check(), test_other_tags_do_not_block_checkin() (+6 more)

### Community 130 - "Community 130"
Cohesion: 0.16
Nodes (1): DespegarAdapter

### Community 131 - "Community 131"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Service adapter for PayPal payment integration.     Creates orders and processes, Process a PayPal webhook notification., Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 132 - "Community 132"
Cohesion: 0.30
Nodes (13): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+5 more)

### Community 133 - "Community 133"
Cohesion: 0.14
Nodes (1): FastAPI routes for the commercial configuration domain.

### Community 134 - "Community 134"
Cohesion: 0.20
Nodes (9): audited_change(), _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity() (+1 more)

### Community 135 - "Community 135"
Cohesion: 0.26
Nodes (13): RuntimeError, _credentials(), E2ESafetyError, main(), normalize_sqlite_url(), prepare_e2e_environment(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet, Raised before any database-capable dependency is imported. (+5 more)

### Community 136 - "Community 136"
Cohesion: 0.16
Nodes (13): push_availability_update(), _push_to_booking(), _push_to_expedia(), Celery tasks for OTA synchronization. Sends inventory/availability updates to Bo, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Expedia EQC API.          In production, this would, Send availability update to Expedia EQC API.          In production, this would (+5 more)

### Community 137 - "Community 137"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 138 - "Community 138"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 139 - "Community 139"
Cohesion: 0.47
Nodes (11): _make_reservation(), _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations(), test_auto_assign_no_double_booking() (+3 more)

### Community 140 - "Community 140"
Cohesion: 0.35
Nodes (12): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _origin(), _timestamp(), _valid_timestamp() (+4 more)

### Community 141 - "Community 141"
Cohesion: 0.27
Nodes (11): _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), get_booking(), list_bookings(), _project_booking_graph() (+3 more)

### Community 142 - "Community 142"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 143 - "Community 143"
Cohesion: 0.24
Nodes (9): create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+1 more)

### Community 144 - "Community 144"
Cohesion: 0.22
Nodes (12): CategoryPricingRead, CategoryPricingSchema, Pydantic schemas for Room and RoomCategory., RoomBase, RoomCategoryBase, RoomCategoryCreate, RoomCategoryRead, RoomCategoryUpdate (+4 more)

### Community 145 - "Community 145"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 146 - "Community 146"
Cohesion: 0.32
Nodes (11): _active_tag_filter(), add_tag(), _audit(), find_or_create_guest(), _get_guest(), list_active_tags(), _now(), quick_profile() (+3 more)

### Community 147 - "Community 147"
Cohesion: 0.37
Nodes (12): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id(), _normalize_required() (+4 more)

### Community 148 - "Community 148"
Cohesion: 0.18
Nodes (4): api_client(), _seed_ota_no_guarantee_reservation(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_release_no_guarantee_endpoint_releases_ota_reservation()

### Community 149 - "Community 149"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 150 - "Community 150"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 151 - "Community 151"
Cohesion: 0.21
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the, Process an IPN (Instant Payment Notification) from MercadoPago.         Queries

### Community 152 - "Community 152"
Cohesion: 0.36
Nodes (11): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., _render(), _strong_password() (+3 more)

### Community 153 - "Community 153"
Cohesion: 0.26
Nodes (11): _generate_secret(), _hash_secret(), HotelAPIKeyError, issue_key(), list_keys(), Hotel-scoped public API key lifecycle., List hotel keys. Callers must not serialize key_hash., Create a key and return the plaintext secret exactly once. (+3 more)

### Community 154 - "Community 154"
Cohesion: 0.35
Nodes (10): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task(), test_company_crud_and_analytics_detail() (+2 more)

### Community 155 - "Community 155"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 156 - "Community 156"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 157 - "Community 157"
Cohesion: 0.42
Nodes (10): clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret(), verify_stripe_signature() (+2 more)

### Community 158 - "Community 158"
Cohesion: 0.35
Nodes (10): cleanup(), derive_test_dsn(), explain(), main(), measure(), percentile(), print_results(), run_alembic_upgrade() (+2 more)

### Community 159 - "Community 159"
Cohesion: 0.25
Nodes (6): Mailer, Platform email service facade backed by the system transactional provider., send_platform_email(), send_reset_password_email(), send_verification_email(), send_verification_success_email()

### Community 160 - "Community 160"
Cohesion: 0.38
Nodes (10): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _normalize_status(), _parse_mercadopago_signature_header(), _payload_value() (+2 more)

### Community 161 - "Community 161"
Cohesion: 0.25
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 162 - "Community 162"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 163 - "Community 163"
Cohesion: 0.24
Nodes (4): _Client, _Response, test_provider_chat_uses_curated_hotel_context_and_controlled_message(), test_provider_receives_only_curated_hotel_analytics_payload()

### Community 164 - "Community 164"
Cohesion: 0.18
Nodes (4): test_audit_log_actor_nullable_for_system_actions(), test_audit_log_all_actions_persist(), test_audit_log_hotel_cascade_delete(), test_transaction_hotel_id_has_fk_constraint()

### Community 165 - "Community 165"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 166 - "Community 166"
Cohesion: 0.38
Nodes (9): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+1 more)

### Community 167 - "Community 167"
Cohesion: 0.27
Nodes (8): booking_webhook(), despegar_webhook(), expedia_webhook(), _handle_ota_webhook(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Expedia., Receive reservation notifications from Despegar.

### Community 168 - "Community 168"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 169 - "Community 169"
Cohesion: 0.38
Nodes (9): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), quote_rate_plan_stay(), _resolve_commission_amount(), _select_fx_policy(), _select_rate_plan_price() (+1 more)

### Community 170 - "Community 170"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 171 - "Community 171"
Cohesion: 0.60
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_is_read_only(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+1 more)

### Community 172 - "Community 172"
Cohesion: 0.47
Nodes (8): _manual_payload(), _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_requires_channel_and_external_id(), test_no_guarantee_ota_internal_release_does_not_call_provider_cancel(), test_release_no_guarantee_promotes_compatible_waitlist_entry(), test_release_no_guarantee_without_waitlist_still_succeeds()

### Community 173 - "Community 173"
Cohesion: 0.29
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret()

### Community 174 - "Community 174"
Cohesion: 0.44
Nodes (9): _fake_mp_gateway(), _reservation(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction(), test_cross_hotel_isolation_for_payment_link_service(), test_deliver_link_email_best_effort_on_failure(), test_deliver_link_email_records_channel() (+1 more)

### Community 175 - "Community 175"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 176 - "Community 176"
Cohesion: 0.38
Nodes (9): _reservation(), test_change_dates_blocked_for_past_check_in(), test_change_dates_blocked_when_room_conflict(), test_change_dates_deposit_paid_auto_fully_paid_when_new_total_lower(), test_change_dates_deposit_paid_keeps_deposit(), test_change_dates_pending_updates_dates_and_price(), test_extend_stay_blocked_for_zero_or_negative_days(), test_extend_stay_blocked_when_room_occupied() (+1 more)

### Community 177 - "Community 177"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 178 - "Community 178"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 179 - "Community 179"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 180 - "Community 180"
Cohesion: 0.28
Nodes (8): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route., Reject context commands that the installed Graphify CLI cannot route.

### Community 181 - "Community 181"
Cohesion: 0.22
Nodes (9): FastAPI routes for stock and inventory operations., StockItemCreate, StockItemRead, StockItemUpdate, StockLocationCreate, StockLocationRead, StockMovementRead, Raised when a stock operation is invalid. (+1 more)

### Community 182 - "Community 182"
Cohesion: 0.22
Nodes (7): e2eDbPath, frontendDir, localPython, pythonCandidates, pythonExecutable, pythonExecutablePath, repoRoot

### Community 183 - "Community 183"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 184 - "Community 184"
Cohesion: 0.33
Nodes (8): GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate, Pydantic schemas for Guest and companions.

### Community 185 - "Community 185"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 186 - "Community 186"
Cohesion: 0.36
Nodes (8): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a short lease and release it only if this worker owns it.      When the, _required(), _settings(), with_distributed_lock()

### Community 187 - "Community 187"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 188 - "Community 188"
Cohesion: 0.33
Nodes (8): Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Set the authenticated user id used by membership RLS policies., Set or clear the current hotel id for tenant-scoped RLS policies., Set both principals for a request or a single-hotel worker job., _set_context_value(), set_tenant_context(), set_tenant_hotel_context(), set_tenant_user_context()

### Community 189 - "Community 189"
Cohesion: 0.33
Nodes (8): _active_hotel_ids(), Celery tasks for scheduled operational reports (BRM §15.1).  Two beat-driven tas, Build and email the report for a single hotel. Returns True on send.      Best-e, Build and email the report for a single hotel. Returns True on send.      Best-e, _run_scheduled_reports(), send_morning_reports(), send_nightly_reports(), _send_report_for_hotel()

### Community 191 - "Community 191"
Cohesion: 0.58
Nodes (8): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_can_read_but_cannot_mutate_commercial_configuration(), test_owner_can_create_and_update_commercial_configuration()

### Community 192 - "Community 192"
Cohesion: 0.28
Nodes (3): _read(), test_explicit_rotation_replaces_values_and_preserves_mode(), test_generates_only_allowed_synthetic_values_with_private_permissions()

### Community 193 - "Community 193"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database., _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category()

### Community 194 - "Community 194"
Cohesion: 0.36
Nodes (7): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement()

### Community 195 - "Community 195"
Cohesion: 0.47
Nodes (6): _make_guest(), _make_reservation(), _make_room_set(), test_available_with_review_surfaces_in_report(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped()

### Community 196 - "Community 196"
Cohesion: 0.50
Nodes (8): _image_base64(), _jpeg_with_exif_base64(), _reservation(), test_approval_creates_completed_transfer_transaction_and_updates_balance(), test_proof_bytes_are_tenant_scoped(), test_rejected_proof_requires_reason_and_cannot_be_approved(), test_submit_transfer_proof_reencodes_and_removes_exif(), test_submit_transfer_proof_validates_image_and_stores_metadata()

### Community 197 - "Community 197"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 198 - "Community 198"
Cohesion: 0.44
Nodes (7): _make_hotel(), _make_reservation(), test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 199 - "Community 199"
Cohesion: 0.28
Nodes (3): _seed_commercial_setup(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 200 - "Community 200"
Cohesion: 0.22
Nodes (1): TestReservationCreation

### Community 201 - "Community 201"
Cohesion: 0.42
Nodes (6): _auth_headers(), _ensure_hotel(), test_comped_override_records_audit_event(), test_manual_transitions_emit_events(), test_role_gating_for_trial_and_comped_override(), test_trial_auto_suspends_after_fourteen_days()

### Community 202 - "Community 202"
Cohesion: 0.39
Nodes (7): _seed_room(), test_create_room_block_public_api(), test_hotel_override_removing_create_block_is_respected(), test_list_room_blocks_public_api(), test_receptionist_can_create_but_not_release_block_by_default(), test_release_room_block_public_api(), test_room_blocks_public_api_is_hotel_scoped()

### Community 203 - "Community 203"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 204 - "Community 204"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 205 - "Community 205"
Cohesion: 0.32
Nodes (7): Demo-only utilities: seed sample data and reset the database. Exposed only when, Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, _require_demo_mode(), reset_demo(), seed_demo()

### Community 206 - "Community 206"
Cohesion: 0.25
Nodes (1): Public WhatsApp bot hooks authenticated only by hotel API key.

### Community 207 - "Community 207"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 208 - "Community 208"
Cohesion: 0.25
Nodes (7): Schemas for operational reservation actions., ReservationAdjustmentSummaryRead, ReservationBillingAdjustmentSummaryRead, ReservationFinancialSummaryRead, ReservationOTALinkSummaryRead, ReservationRoomMoveSummaryRead, ReservationTransactionSummaryRead

### Community 209 - "Community 209"
Cohesion: 0.25
Nodes (8): _qa_marker(), QABootstrapResult, Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., Idempotently create one tagged QA hotel and its four database users., upsert_qa_data()

### Community 210 - "Community 210"
Cohesion: 0.29
Nodes (6): add_item(), create_batch(), get_batch(), _next_batch_code(), Hotel-scoped laundry service., transition_status()

### Community 211 - "Community 211"
Cohesion: 0.32
Nodes (7): get_timezone_catalog(), is_valid_timezone(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Trim whitespace and validate the timezone name.

### Community 212 - "Community 212"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 213 - "Community 213"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 214 - "Community 214"
Cohesion: 0.32
Nodes (4): client_with_db(), ctx(), get_auth_context_target(), get_db_override_target()

### Community 215 - "Community 215"
Cohesion: 0.25
Nodes (6): client(), FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Demo utilities work once DEMO_MODE=true is set., test_seed_and_reset_allowed_when_demo_enabled(), test_seed_and_reset_blocked_by_default()

### Community 216 - "Community 216"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 217 - "Community 217"
Cohesion: 0.43
Nodes (7): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel()

### Community 218 - "Community 218"
Cohesion: 0.57
Nodes (7): _link(), _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction(), test_duplicate_same_webhook_is_idempotent_no_double_transaction(), test_gateway_webhook_is_idempotent_by_provider_webhook_id(), test_process_payment_replays_on_duplicate_idempotency_key()

### Community 219 - "Community 219"
Cohesion: 0.39
Nodes (5): _seed_hotel(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_override_allows_receptionist_guest_edit()

### Community 220 - "Community 220"
Cohesion: 0.46
Nodes (7): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 221 - "Community 221"
Cohesion: 0.46
Nodes (5): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_receptionist_cannot_create_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 222 - "Community 222"
Cohesion: 0.50
Nodes (7): opened_cash_register(), _payment(), _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 223 - "Community 223"
Cohesion: 0.33
Nodes (2): mercadopago_payment_link_webhook(), _mercadopago_webhook_impl()

### Community 224 - "Community 224"
Cohesion: 0.43
Nodes (4): create_audit_log(), payload_json(), queue_audit_log(), safe_create_audit_log()

### Community 225 - "Community 225"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 226 - "Community 226"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 227 - "Community 227"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 228 - "Community 228"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 230 - "Community 230"
Cohesion: 0.67
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 231 - "Community 231"
Cohesion: 0.67
Nodes (6): _client_with_db(), _override_auth(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_permission_denied_is_audited(), test_permission_override_allows_receptionist_guest_edit(), test_permissions_matrix_available_to_authenticated_hotel_member()

### Community 232 - "Community 232"
Cohesion: 0.52
Nodes (6): _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 233 - "Community 233"
Cohesion: 0.57
Nodes (5): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_soft_deletes_hides_and_audits()

### Community 234 - "Community 234"
Cohesion: 0.38
Nodes (3): _load_rls_migration(), test_rls_migration_covers_every_hotel_scoped_model_table(), test_rls_migration_keeps_api_key_bootstrap_exception_explicit()

### Community 235 - "Community 235"
Cohesion: 0.57
Nodes (6): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 236 - "Community 236"
Cohesion: 0.48
Nodes (5): _analytics_enum(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260, _reservation_status_enum_new(), _reservation_status_enum_old(), upgrade()

### Community 237 - "Community 237"
Cohesion: 0.52
Nodes (6): downgrade(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 238 - "Community 238"
Cohesion: 0.53
Nodes (5): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online()

### Community 239 - "Community 239"
Cohesion: 0.40
Nodes (3): authHeaders(), ensureOnboarding(), hotelId

### Community 240 - "Community 240"
Cohesion: 0.40
Nodes (5): annotate_analytics_payload(), _as_utc_datetime(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL, Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 241 - "Community 241"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 242 - "Community 242"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 243 - "Community 243"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 244 - "Community 244"
Cohesion: 0.53
Nodes (4): _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_room_move_requires_reason_code_and_accepts_valid_reason(), test_update_mobility_restriction_triggers_reoptimization()

### Community 245 - "Community 245"
Cohesion: 0.60
Nodes (5): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_payment_confirmation_is_idempotent(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 246 - "Community 246"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 247 - "Community 247"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), downgrade(), _drop_successor_reference(), Add zero-balance cash rotation and custody handoffs., upgrade()

### Community 248 - "Community 248"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), Enable PostgreSQL row-level tenant isolation.  Revision ID: 20260724_tenant_rls_, upgrade()

### Community 249 - "Community 249"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 250 - "Community 250"
Cohesion: 0.60
Nodes (4): _enum_value(), get_guest_profile(), GuestProfileError, validate_primary_guest_record()

### Community 251 - "Community 251"
Cohesion: 0.50
Nodes (4): compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch

### Community 252 - "Community 252"
Cohesion: 0.80
Nodes (4): _link(), _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 253 - "Community 253"
Cohesion: 0.70
Nodes (4): _client_with_db(), _override_auth(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 254 - "Community 254"
Cohesion: 0.60
Nodes (3): _deferred_company(), test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 255 - "Community 255"
Cohesion: 0.70
Nodes (4): _settings(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable()

### Community 256 - "Community 256"
Cohesion: 0.60
Nodes (3): _build_signature(), test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 257 - "Community 257"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 258 - "Community 258"
Cohesion: 0.60
Nodes (3): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation()

### Community 259 - "Community 259"
Cohesion: 0.70
Nodes (4): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 260 - "Community 260"
Cohesion: 0.60
Nodes (3): _quote(), test_confirmed_reservation_stores_pricing_revision(), test_reservation_rejects_quote_after_pricing_revision_changes()

### Community 262 - "Community 262"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 263 - "Community 263"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 264 - "Community 264"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 265 - "Community 265"
Cohesion: 0.50
Nodes (4): bootstrap_configuration_fingerprint(), Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually., Hash the exact provider-observed values without exposing them individually.

### Community 266 - "Community 266"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 267 - "Community 267"
Cohesion: 0.50
Nodes (3): list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog.

### Community 269 - "Community 269"
Cohesion: 0.50
Nodes (1): FakeRedis

### Community 271 - "Community 271"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 274 - "Community 274"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 275 - "Community 275"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 276 - "Community 276"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 277 - "Community 277"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 278 - "Community 278"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 279 - "Community 279"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 280 - "Community 280"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 281 - "Community 281"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 282 - "Community 282"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 283 - "Community 283"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 284 - "Community 284"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 285 - "Community 285"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 286 - "Community 286"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 287 - "Community 287"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 288 - "Community 288"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 289 - "Community 289"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 290 - "Community 290"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 291 - "Community 291"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 292 - "Community 292"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 293 - "Community 293"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 294 - "Community 294"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 295 - "Community 295"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 296 - "Community 296"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 297 - "Community 297"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 298 - "Community 298"
Cohesion: 0.67
Nodes (1): Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati

### Community 299 - "Community 299"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 300 - "Community 300"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 301 - "Community 301"
Cohesion: 1.00
Nodes (1): Schemas for manual OTA reservation entry.

## Knowledge Gaps
- **408 isolated node(s):** `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`, `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`, `launch security hardening  Revision ID: 20260408_launch_security_hardening Revis`, `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`, `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif` (+403 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 59`** (2 nodes): `_hotel_default_currency()`, `OTAIntegrationService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (2 nodes): `4f50de1 Add successor cash register controls`, `b4c9bd8 Harden cash rotation and payment integrity`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `OnboardingState`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 133`** (1 nodes): `FastAPI routes for the commercial configuration domain.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 197`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 200`** (1 nodes): `TestReservationCreation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 206`** (1 nodes): `Public WhatsApp bot hooks authenticated only by hotel API key.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 223`** (2 nodes): `mercadopago_payment_link_webhook()`, `_mercadopago_webhook_impl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 269`** (1 nodes): `FakeRedis`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 275`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 276`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 277`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 278`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 279`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 280`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 281`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 282`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 283`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 284`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 285`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 286`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 287`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 288`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 289`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 290`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 291`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 292`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 293`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 294`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 295`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 296`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 297`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 298`** (1 nodes): `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 299`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 300`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 301`** (1 nodes): `Schemas for manual OTA reservation entry.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 7` to `Community 238`, `Community 205`, `Community 11`, `Community 61`, `Community 134`, `Community 43`, `Community 8`, `Community 31`, `Community 2`, `Community 18`, `Community 3`, `Community 12`, `Community 99`, `Community 95`, `Community 28`, `Community 143`, `Community 0`, `Community 30`, `Community 54`, `Community 5`, `Community 21`, `Community 6`, `Community 38`, `Community 27`, `Community 119`, `Community 15`, `Community 35`, `Community 29`, `Community 45`, `Community 65`, `Community 25`, `Community 63`, `Community 40`, `Community 58`, `Community 136`, `Community 215`, `Community 84`, `Community 193`, `Community 194`?**
  _High betweenness centrality (0.127) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 0` to `Community 6`, `Community 38`, `Community 50`, `Community 67`, `Community 7`, `Community 43`, `Community 298`, `Community 18`, `Community 118`, `Community 86`, `Community 12`, `Community 35`, `Community 59`, `Community 27`, `Community 15`, `Community 25`, `Community 2`, `Community 3`, `Community 92`, `Community 58`, `Community 136`, `Community 189`, `Community 30`, `Community 84`, `Community 54`, `Community 29`, `Community 45`, `Community 56`, `Community 37`, `Community 107`, `Community 90`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 3`, `Community 54`, `Community 67`, `Community 25`, `Community 50`, `Community 28`, `Community 7`, `Community 43`, `Community 2`, `Community 31`, `Community 18`, `Community 99`, `Community 250`, `Community 12`, `Community 35`, `Community 59`, `Community 45`, `Community 65`, `Community 15`, `Community 92`, `Community 40`, `Community 118`, `Community 30`, `Community 115`, `Community 56`, `Community 200`, `Community 37`, `Community 107`, `Community 90`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Are the 536 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`ReservationStatusEnum` has 536 INFERRED edges - model-reasoned connections that need verification._
- **Are the 530 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Calculate pricing for a potential booking without persisting it.     Uses Catego`) actually correct?**
  _`Reservation` has 530 INFERRED edges - model-reasoned connections that need verification._
- **Are the 469 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Hotel Configuration (Admin Panel).` and `Lightweight status so the frontend can check the active system email provider.`) actually correct?**
  _`HotelConfiguration` has 469 INFERRED edges - model-reasoned connections that need verification._
- **Are the 391 inferred relationships involving `Room` (e.g. with `RoomBlockCreate` and `RoomBlockRead`) actually correct?**
  _`Room` has 391 INFERRED edges - model-reasoned connections that need verification._