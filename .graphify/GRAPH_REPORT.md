# Graph Report - .  (2026-09-27)

## Corpus Check
- Large corpus: 1460 files · ~1,935,834 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 11362 nodes · 30119 edges · 566 communities detected
- Extraction: 78% EXTRACTED · 22% INFERRED · 0% AMBIGUOUS · INFERRED: 6552 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: contains: 7644 · uses: 6552 · calls: 5583 · MODIFIES: 3087 · rationale_for: 1587 · imports: 1392 · ON_BRANCH: 1211 · imports_from: 1137 · inherits: 824 · method: 756 · PARENT_OF: 342 · re_exports: 4


## Input Scope
- Requested: committed
- Resolved: committed (source: cli)
- Included files: 1460 · Candidates: 1616
- Excluded: 4 untracked · 31275 ignored · 14 sensitive · 0 missing committed
- Recommendation: Use --scope all or graphify.yaml inputs.corpus for a knowledge-base folder.

## Graph Freshness
- Built from Git commit: `9d05e2c`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Base` - 381 edges
2. `Reservation` - 287 edges
3. `HotelConfiguration` - 274 edges
4. `ReservationStatusEnum` - 225 edges
5. `Room` - 217 edges
6. `HotelMembership` - 191 edges
7. `RoomCategory` - 180 edges
8. `AuditActionEnum` - 166 edges
9. `SecurityAuditLog` - 163 edges
10. `ReservationError` - 136 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `FastAPI routes for the commercial configuration domain.` --uses--> `CommercialConfigError`  [INFERRED]
  app/api/commercial.py → app/services/commercial_service.py
- `FastAPI routes for the onboarding flow used by smoke tests.` --uses--> `OnboardingError`  [INFERRED]
  app/api/onboarding.py → app/services/onboarding_service.py
- `API routes for reservation waitlist operations.` --uses--> `WaitlistError`  [INFERRED]
  app/api/waitlist.py → app/services/waitlist_service.py
- `Authenticated human WhatsApp CRM inbox.  This router never calls Meta directly.` --uses--> `WhatsAppCRMError`  [INFERRED]
  app/api/whatsapp_crm.py → app/services/whatsapp_crm_service.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (98): export_cash_ledger_csv(), _require_cash_difference_approval_when_requested(), Read-only integral operations audit endpoint., Bound inbound webhook bodies before parsing or signature verification., _DecimalAwareEncoder, _InvitationAccessLogFilter, _is_demo_mode_enabled(), lifespan() (+90 more)

### Community 1 - "Community 1"
Cohesion: 0.06
Nodes (193): codex/production-render-qa, codex/public-site-inquiries, docs/auditoria-pms-20260908, feature/operational-audit-cash-daily, feature/secure-auth-marketing-release-20260926, main, 009a9ed docs(tech-0140): pin final local verification, 02908b1 feat(storage): add verified tenant object metadata (+185 more)

### Community 2 - "Community 2"
Cohesion: 0.02
Nodes (140): Guard endpoints so they only run in explicit demo mode or tests., Guard endpoints so they only run in explicit demo mode or tests., Populate the database with minimal demo data.     Idempotent: running twice simp, Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Drop and recreate all tables.     Keeps the app in a known-good empty state for, _require_demo_mode(), reset_demo() (+132 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (141): Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., Read and resolve the guest room-rejection lifecycle., FastAPI routes for Guest management., Add new companions to an existing guest., FastAPI routes for Room management + Housekeeping., Resolve today's effective rate from the single source of truth and attach it, Materialize the safe projection before FastAPI can inspect the ORM. (+133 more)

### Community 4 - "Community 4"
Cohesion: 0.02
Nodes (52): _archive_historical(), _build_cases(), main(), _write_json(), bootstrap_configuration_fingerprint(), BootstrapConfigurationError, Shared, secret-safe binding for the Render QA bootstrap configuration., Hash the exact provider-observed values without exposing them individually. (+44 more)

### Community 5 - "Community 5"
Cohesion: 0.02
Nodes (92): create_movement(), createStockItem(), createStockLocation(), createStockMovement(), CurrentStock, deleteStockItem(), _ensure_adjustment_permission(), get_stock_summary() (+84 more)

### Community 6 - "Community 6"
Cohesion: 0.02
Nodes (78): 15142fe feat(dashboard): hotel-vocabulary pending action titles + open-drawer button (B6.2), 1763603 Clarify password login and finish MFA recovery, 222ef84 Fix auth bootstrap and harden rate limits, 230041e Fix E2E MFA journeys and clarify retention schedule, 25d09dc fix(mobile): replace two competing mobile nav mechanisms with one menu button, 2bbe038 Merge remote-tracking branch 'origin/main' into codex/clarify-mfa-code, 3e274ad Keep the landing's occupancy board in step with the real planilla, 3ff6f17 Preserve password access when linking Google (+70 more)

### Community 7 - "Community 7"
Cohesion: 0.02
Nodes (115): BaseModel, ActiveAllocationPolicyRead, AllocationExplanationRead, AllocationFeedbackDraftRequest, AllocationPolicySuggestionApplyRequest, AllocationPolicySuggestionApplyResponse, AllocationPolicySuggestionCreate, AllocationPolicySuggestionRead (+107 more)

### Community 8 - "Community 8"
Cohesion: 0.05
Nodes (123): PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, FastAPI routes for Payments., FastAPI routes for Reports & Night Audit. Daily summaries, occupancy reports, re, Night Audit / Daily Report.     Shows arrivals, departures, occupancy, revenue c, Occupancy report for a date range (default: last 30 days). (+115 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (116): AuthUser, _accept_invitation(), accept_invitation_legacy_path(), _accept_invitation_with_google(), accept_invitation_with_google_legacy_path(), AcceptPayload, _activate_invitation_for_user(), _activate_invitation_for_user_audited() (+108 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (58): FastAPI routes for the commercial configuration domain., create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, _request_source(), _backfill_not_null_nulls(), _collect_realtime_events_after_flush(), _column_fill_value(), _discard_realtime_events_after_rollback() (+50 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (101): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+93 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (68): Demo-only utilities: seed sample data and reset the database. Exposed only when, _cors_contains_wildcard(), get_settings(), _gmail_is_active(), _has_value(), is_demo_mode(), is_preview_qa_mode(), is_production_mode() (+60 more)

### Community 13 - "Community 13"
Cohesion: 0.03
Nodes (88): validateGuestForCheckin(), add_reservation_guests(), addReservationCharge(), addReservationGuests(), buildQueryString(), cancelReservation(), CheckInPayload, checkInReservation() (+80 more)

### Community 14 - "Community 14"
Cohesion: 0.05
Nodes (72): 654d69e Add reservation arrival metadata and internal comments, 8c239da Merge pull request #100 from Maximo-Paulos/feature/reservation-arrival-comment, APIKeyPurposeEnum, LinenItem, ReservationSourceEnum, PaymentLinkRead, PublicReservationRead, Pydantic schemas for Booking (lightweight wrapper around Reservation). (+64 more)

### Community 15 - "Community 15"
Cohesion: 0.04
Nodes (70): DailyReportSchedule, DailyReportScheduleUpdate, get_daily_report_schedule(), getDailyReportSchedule(), listNotificationPreferences(), listNotifications(), markAllNotificationsRead(), markNotificationRead() (+62 more)

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (59): booking_webhook(), despegar_webhook(), expedia_webhook(), _guarded_json_payload(), _handle_ota_webhook(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Booking.com. (+51 more)

### Community 17 - "Community 17"
Cohesion: 0.07
Nodes (81): AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsCurrencyDisplayEnum, AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum, FactReservationDaily (+73 more)

### Community 18 - "Community 18"
Cohesion: 0.04
Nodes (61): createGuestRestriction(), getGuestProhibitedDetail(), GuestProhibitedErrorBody, GuestRestriction, GuestRestrictionCreatePayload, GuestRestrictionResolvePayload, GuestRestrictionStatus, listGuestRestrictions() (+53 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (60): fetchPublicPricing(), LeadPayload, PublicPricing, PublicPricingPlan, submitLead(), 16473c9 Refresh Graphify graph after the marketing and metadata pass, 9da1f66 Rebuild the public landing page as Hotels-PMS, d7e130f Merge the Hotels-PMS landing page rebuild (+52 more)

### Community 20 - "Community 20"
Cohesion: 0.05
Nodes (69): list_sessions(), logout(), Auth endpoints: register, login, email verification and password reset. Verifica, Remove the Google login only after proving control of the password.      Google-, Complete Sign in with Apple from Apple JS SDK or another OIDC client., Start Apple's form_post redirect flow with a signed state and nonce., Complete Apple's server-side form_post redirect flow., Remove the Apple login only after proving control of the password. (+61 more)

### Community 21 - "Community 21"
Cohesion: 0.06
Nodes (81): Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, Subscription, SubscriptionAdjustment, SubscriptionEvent, _actor_payload(), _actor_role(), _actor_user_id() (+73 more)

### Community 22 - "Community 22"
Cohesion: 0.04
Nodes (39): requestVerification(), verifyEmail(), CategoryPayload, DepositPolicyPayload, finishOnboarding(), getOnboardingStatus(), HotelIdentityPayload, OnboardingProviderSetup (+31 more)

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (60): createLaundryRemito(), createLaundryVendor(), getLaundryVendorBalance(), getLaundryVendorSettlements(), getLaundryVendorSpend(), LaundryRemito, LaundryRemitoCreate, LaundryRemitoCreateResponse (+52 more)

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (44): 5616166 Merge pull request #90 from Maximo-Paulos/feature/realtime-collaboration, 9aee997 Implement real-time synchronization and collaboration, createReservation(), localIsoDate(), owner, parseMoney(), readStat(), CollaborationPatchRequest (+36 more)

### Community 25 - "Community 25"
Cohesion: 0.03
Nodes (69): PermissionGate(), MasterAdminProtectedShell(), MasterAdminRoot(), navItems, MasterAdminSessionProvider(), ContactPage(), FaqPage(), FunctionsPage() (+61 more)

### Community 26 - "Community 26"
Cohesion: 0.13
Nodes (62): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Lightweight availability placeholder. When all parameters are provided,     it r, Calculate pricing for a potential booking without persisting it.     Uses the ca, Quickly seed demo bookings (requires DEMO_MODE=true)., Ensure computed fields land in the response., CheckInRequest, FastAPI routes for Check-in / Check-out., B3.1: writes PRE_CHECK_IN — the 'huésped ingresó al cuarto, faltan     acompañan (+54 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (59): Operational task inbox and shift handoff endpoints., Match direct task access to the user's effective shared-read/manage grants., RoomBlockCreate, RoomBlockRead, OperationalTask, OperationalTaskEvent, OperationalTaskPriorityEnum, OperationalTaskStatusEnum (+51 more)

### Community 28 - "Community 28"
Cohesion: 0.04
Nodes (47): getPaymentSummary(), makePayment(), newPaymentIdempotencyKey(), PaymentMethod, PaymentRequest, PaymentSummary, TransactionType, ReservationStatus (+39 more)

### Community 29 - "Community 29"
Cohesion: 0.06
Nodes (55): _auth_headers(), _complete_onboarding(), _configure_resend(), _enroll_and_confirm_mfa(), _fake_apple_claims(), _fake_google_claims(), FakeResponse, _next_totp_code() (+47 more)

### Community 30 - "Community 30"
Cohesion: 0.11
Nodes (65): _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by id (v72 §16).      Scoped to the API key, _serialize_reservation_status() (+57 more)

### Community 31 - "Community 31"
Cohesion: 0.05
Nodes (56): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), Category (+48 more)

### Community 32 - "Community 32"
Cohesion: 0.04
Nodes (57): createPaymentSurcharge(), deactivatePaymentSurcharge(), grossWithSurcharge(), listPaymentSurcharges(), PaymentSurcharge, PaymentSurchargeCreatePayload, PaymentSurchargeType, _attach_current_rate() (+49 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (56): assignWhatsAppConversation(), completeWhatsAppChannel(), createWhatsAppNote(), fetchWhatsAppChannel(), fetchWhatsAppConversations(), _app_secret(), _nested(), Meta Cloud API webhook boundary.  The endpoint verifies Meta's signature before (+48 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (56): DailyReportSchedule, Notification, NotificationChannelEnum, NotificationOutbox, NotificationOutboxStatusEnum, NotificationPreference, PushSubscription, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+48 more)

### Community 35 - "Community 35"
Cohesion: 0.04
Nodes (31): _authorize_override(), checkin(), checkin_partial(), BridgeActivity, 958fce2 Merge pull request #31 from Maximo-Paulos/feature/mobile-first-operations, dad55df feat(mobile): wrap PWA with Capacitor for App Store/Play Store (Task 11), credentials, ownerCredentials (+23 more)

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (56): ActionStepUpChallenge, ActionStepUpHandler, actionStepUpQueue, ActionStepUpTicket, buildAuthHeaders(), buildUrl(), clearPermissionAdminReadStepUpCache(), formatErrorDetail() (+48 more)

### Community 37 - "Community 37"
Cohesion: 0.06
Nodes (46): create_laundry_remito(), _housekeeping_remito(), LinenItemCreate, LinenItemRead, LinenLocationCreate, LinenLocationRead, LinenMovementCreate, LinenMovementRead (+38 more)

### Community 38 - "Community 38"
Cohesion: 0.05
Nodes (37): ApiError, clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminLoginResult, MasterAdminMfaChallengeResponse, MasterAdminMfaEnrollment, MasterAdminMfaRecoveryCodes (+29 more)

### Community 39 - "Community 39"
Cohesion: 0.06
Nodes (52): PrivacyRetentionHold, Current legal-retention exception for one public lead or inquiry.      Changes a, _as_utc(), create_retention_hold(), _effective(), _lock_hold_table_for_write(), _mask_email(), Use a consistent table-lock order with the scheduled purge function. (+44 more)

### Community 40 - "Community 40"
Cohesion: 0.09
Nodes (56): Authenticated field-level collaboration endpoints.  Drafts are ephemeral and saf, Issue a short-lived, one-use ticket for one tenant resource., Persist an optimistic, field-level merge under the current tenant., Authenticate with a one-use ticket, then exchange safe draft signals., Keep collaboration permissions aligned with the normal resource API., Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, recover_domain_events() (+48 more)

### Community 41 - "Community 41"
Cohesion: 0.07
Nodes (49): _allow_mfa_attempt(), apple_callback(), _apple_full_name(), apple_login(), _apple_login_config(), apple_start(), _attach_user_session_cookies(), _audit_security_event() (+41 more)

### Community 42 - "Community 42"
Cohesion: 0.23
Nodes (56): HotelRole, A stable custom role code whose policy is scoped to one hotel., HotelRoleVisibilityWindow, Reservation visibility limits configured independently per hotel role.      A mi, StaffInvitation, HotelPermissionOverride, Permission, Configurable permission matrix models. (+48 more)

### Community 43 - "Community 43"
Cohesion: 0.11
Nodes (53): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+45 more)

### Community 44 - "Community 44"
Cohesion: 0.07
Nodes (31): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, Public contact form endpoint for the marketing site., PublicInquiryPayload, PublicInquiryResponse, submitPublicInquiry(), 09d0b08 feat(marketing): secure inquiries and enforce 90-day retention, 9306eb5 Add public marketing inquiry flow and SEO, b48fd42 Add public marketing inquiry flow and SEO (+23 more)

### Community 45 - "Community 45"
Cohesion: 0.10
Nodes (53): active_reservations(), active_reservations_select(), _active_reservations_without_hotel(), _apply_corporate_pricing(), _apply_custom_deposit_amount(), _apply_manual_total_override(), _apply_pricing_result_to_reservation(), assert_reservation_version() (+45 more)

### Community 46 - "Community 46"
Cohesion: 0.06
Nodes (36): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), currentUser() (+28 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (48): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., channel_for_hotel(), discard_queued_domain_changes(), DomainEvent, format_sse(), get_domain_event_outbox_metrics(), get_domain_event_recovery() (+40 more)

### Community 48 - "Community 48"
Cohesion: 0.07
Nodes (41): _clickhouse_healthcheck(), _critical_lock_readiness(), datastores_healthcheck(), live_healthcheck(), _postgres_healthcheck(), Report whether the API can safely accept critical writes., Process liveness only; never depends on PostgreSQL or Redis., ready_healthcheck() (+33 more)

### Community 49 - "Community 49"
Cohesion: 0.08
Nodes (45): 9d05e2c security: bind master admin requests to app origin, a142c70 security: restrict RLS event trigger execution, allow_master_admin_mfa_attempt(), _as_aware(), audit_master_action(), authenticate_master_login(), authenticate_master_mfa_login(), _authorize_user_for_master_panel() (+37 more)

### Community 50 - "Community 50"
Cohesion: 0.09
Nodes (17): _add_cash_movement(), _auth_context(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session(), Adapted tests for V72 §17 - Caja Basica (Cash Register).  This branch implements (+9 more)

### Community 51 - "Community 51"
Cohesion: 0.07
Nodes (41): addCashMovement(), approveCashCloseDifference(), CashCloseReport, CashCustodyHandoff, CashDailyCollector, CashDailyEntry, CashDailyPaymentMethod, CashDailySession (+33 more)

### Community 52 - "Community 52"
Cohesion: 0.06
Nodes (37): acknowledgeShiftHandoff(), createOperationalTask(), createShiftHandoff(), listOperationalTaskHistory(), listOperationalTasks(), listShiftHandoffs(), OperationalTask, OperationalTaskCreate (+29 more)

### Community 53 - "Community 53"
Cohesion: 0.12
Nodes (47): LookupError, _active_membership(), _active_role_codes(), archive_custom_role(), _assert_owner_management_restore(), _audit(), audit_permission_denied(), can_role_hold_permission() (+39 more)

### Community 54 - "Community 54"
Cohesion: 0.09
Nodes (47): _b64url_decode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), canonical_provider_evidence_json(), cli(), database_connection_fingerprint(), _decode_baseline_lease_entropy() (+39 more)

### Community 55 - "Community 55"
Cohesion: 0.07
Nodes (30): client_with_db(), _enable_test_google(), get_auth_context_target(), get_db_override_target(), _google_claims(), _invitation_token(), owner_ctx(), test_atomic_invitation_consumption_rejects_a_rotated_token_hash() (+22 more)

### Community 56 - "Community 56"
Cohesion: 0.07
Nodes (33): list_countries(), list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog., Return the curated country -> primary IANA timezone catalog., ReferenceCountry, listCountries(), ReferenceCountry (+25 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (29): _assign_hotel(), ensure_category_pricing_table(), opened_cash_register(), Tests for Payment Service — Financial Engine. Tests the complete payment lifecyc, Paying LESS than the deposit threshold should keep status as PENDING., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Critical test: Simulates web booking with deposit, then balance payment at check (+21 more)

### Community 58 - "Community 58"
Cohesion: 0.07
Nodes (32): createPromotion(), deactivatePromotion(), listPromotions(), Promotion, PromotionAppliedEntry, PromotionBenefitType, PromotionConditions, PromotionCreatePayload (+24 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (39): refreshAfterMutation(), refreshCashState(), refreshDomains(), refreshGuestState(), refreshPaymentState(), refreshReservationGuestState(), refreshReservationState(), refreshRoomState() (+31 more)

### Community 60 - "Community 60"
Cohesion: 0.04
Nodes (21): Tests for Reservation Service — booking creation, availability checks, state tra, Availability lookup must not issue one reservation query per room., Tests for reservation creation logic., Create a standard reservation and verify computed fields., B4: manual tarifa on a direct reservation with no company_id -- the         auto, Reserve a specific room., Should fail for non-existent guest., Should fail when check-out is before check-in. (+13 more)

### Community 61 - "Community 61"
Cohesion: 0.12
Nodes (35): SimpleRateLimiter, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterBillingPolicy, MasterStripeSettings, MasterStripeWebhookEvent, MasterSystemEmailConnection (+27 more)

### Community 62 - "Community 62"
Cohesion: 0.06
Nodes (16): _make_hotel_guest_reservation(), Database business-requirement tests.  Verifies that ALL tables required to fulfi, Gate assertion: all tables required by the business requirements exist.     This, test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict() (+8 more)

### Community 63 - "Community 63"
Cohesion: 0.08
Nodes (34): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+26 more)

### Community 64 - "Community 64"
Cohesion: 0.10
Nodes (33): Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, mask_to_weekdays(), PromotionConditions, PromotionCreate (+25 more)

### Community 65 - "Community 65"
Cohesion: 0.06
Nodes (29): acceptInvitation(), acceptInvitationWithGoogle(), AuthResponse, AuthResult, completeMfaInvitationAcceptance(), completeMfaLogin(), getInvitationInfo(), isMfaChallenge() (+21 more)

### Community 66 - "Community 66"
Cohesion: 0.08
Nodes (36): _authorize_oauth_state_actor(), connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration() (+28 more)

### Community 67 - "Community 67"
Cohesion: 0.05
Nodes (31): BuiltinPermissionRole, fetchPermissionCatalog(), fetchPermissionMatrix(), fetchRolePermissionProfiles(), fetchUserPermissionOverrides(), fetchVisibilityWindows(), PermissionCatalogItem, PermissionMatrixResponse (+23 more)

### Community 68 - "Community 68"
Cohesion: 0.08
Nodes (34): _assert_manageable_membership(), consume_temporary_action_grant(), EffectivePermissionsResponse, fetchEffectivePermissions(), PermissionCatalogResponse, PermissionCell, PermissionDetail, PermissionMatrix (+26 more)

### Community 69 - "Community 69"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+24 more)

### Community 70 - "Community 70"
Cohesion: 0.09
Nodes (30): ActiveRoomBlockItem, AvailableWithReviewItem, CashSessionStatusRead, daily_report(), DailyOperationalReport, getDailyOperationalReport(), getOccupancyReport(), getOperationalAlerts() (+22 more)

### Community 71 - "Community 71"
Cohesion: 0.08
Nodes (30): audited_change(), _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity() (+22 more)

### Community 72 - "Community 72"
Cohesion: 0.13
Nodes (5): GemmaPolicyDraft, GemmaService, GemmaServiceError, Raised when a Gemma request cannot be completed safely., Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 73 - "Community 73"
Cohesion: 0.06
Nodes (20): AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsEnvelope, AnalyticsFilterState, AnalyticsFreshness(), AnalyticsHomePage(), AnalyticsStarterSummary, ChatMessage (+12 more)

### Community 74 - "Community 74"
Cohesion: 0.10
Nodes (27): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyPayload, createCompany(), createCompanyDocument() (+19 more)

### Community 75 - "Community 75"
Cohesion: 0.11
Nodes (26): configure_dedicated_baseline(), env_page(), FakeApi, fixtures(), Critical security tests for the read-only preview provider verifier., set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation() (+18 more)

### Community 76 - "Community 76"
Cohesion: 0.13
Nodes (32): create_restriction(), _get_tenant_guest(), list_restrictions(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, resolve_restriction(), GuestRestriction, GuestRestrictionStatusEnum (+24 more)

### Community 77 - "Community 77"
Cohesion: 0.07
Nodes (25): 1b6ca04 test(cash): verify session summary totals, 2fe25b3 Fix repeated MFA prompts on RBAC permission reads, 558d7ec test(qa): record non-certifying production RBAC smoke, ba3830a fix(security): redact complete authorization diagnostics, ActionStepUpTicketUse, Tenant-scoped replay ledger for MFA step-up tickets., Persist only the random ticket id and action binding after first use., action_step_up_ticket_matches() (+17 more)

### Community 78 - "Community 78"
Cohesion: 0.10
Nodes (30): _bootstrap_environment(), _local_evidence_payload(), _provider_manifest(), Safety contract for destructive PostgreSQL validation tests.  These tests never, _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence() (+22 more)

### Community 79 - "Community 79"
Cohesion: 0.20
Nodes (33): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _decode_lease_entropy(), _deployment_git_identity(), _deployment_hosts() (+25 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (20): _complete_master_login(), _configure_resend(), FakeResponse, _seed_platform_admin(), test_master_admin_absolute_ttl_expires_recently_active_session(), test_master_admin_accepts_configured_local_and_deployed_frontend_origins(), test_master_admin_allows_read_only_request_without_origin(), test_master_admin_mfa_is_mandatory_and_cannot_be_bypassed() (+12 more)

### Community 81 - "Community 81"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 82 - "Community 82"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider (+12 more)

### Community 83 - "Community 83"
Cohesion: 0.16
Nodes (29): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+21 more)

### Community 84 - "Community 84"
Cohesion: 0.07
Nodes (20): main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only., 218ef8b chore(graphify): regenerate graph after A2 reservation pagination/order, 2781ab8 feat(db): index reservations(hotel_id, created_at) for A2 recent-order paging, 2eccdd8 feat(reservations): add occupancy-grid endpoint for B2 planilla, 3a2821c feat(reservations): wire skip/limit/order into the frontend reservation list, 3c24834 perf(frontend): stop shipping sourcemaps to production (+12 more)

### Community 85 - "Community 85"
Cohesion: 0.11
Nodes (28): collaboration_websocket(), CollaborationPatchResponse, CollaborationResourceType, CollaborationTicket, collaborationWebSocketUrl(), CollaborationWsMessage, _consume_ticket(), create_collaboration_ticket() (+20 more)

### Community 86 - "Community 86"
Cohesion: 0.07
Nodes (28): db(), db_engine(), hotel_config(), _isolate_object_storage(), pg_engine(), Pytest configuration and fixtures. Uses an in-memory SQLite database for isolate, No real mail transport in tests — stub auth email senders.      Endpoints raise, Route every test's object storage (payment proofs, analytics exports)     to a p (+20 more)

### Community 87 - "Community 87"
Cohesion: 0.12
Nodes (26): Server-side, revocable sessions for the normal user auth plane., An opaque browser session whose raw token is never persisted., UserSession, _as_aware(), create_session(), csrf_double_submit_matches(), _device_label_from_request(), _hash_value() (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.11
Nodes (20): _event_engine(), FakeRedis, A minimal SQLite engine with just the tables the after_commit hook writes to., _settings(), test_nested_commit_publishes_only_after_root_commit(), test_nested_rollback_prunes_only_nested_realtime_signals(), test_optional_backend_degrades_without_fabricating_an_event(), test_permission_invalidation_publishes_without_error_logging() (+12 more)

### Community 89 - "Community 89"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_csv(), export_analytics_png(), export_analytics_xlsx()

### Community 90 - "Community 90"
Cohesion: 0.10
Nodes (20): Staff management endpoints for hotel public API keys., get_public_api_context(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val, require_public_api_purpose(), HotelAPIKey, Hotel API key model — v72 §16.  Each hotel can have multiple named API credentia (+12 more)

### Community 91 - "Community 91"
Cohesion: 0.09
Nodes (17): LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead, LaundryStatus, LaundryStatusUpdate (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 93 - "Community 93"
Cohesion: 0.15
Nodes (23): _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet(), get_connection_payload() (+15 more)

### Community 94 - "Community 94"
Cohesion: 0.09
Nodes (20): _make_guest(), _make_reservation(), Multi-tenancy isolation tests: Hotel A vs Hotel B.  Verifies that every domain t, Same document can exist in Hotel A and Hotel B — dedup is hotel-scoped., Same document within one hotel raises IntegrityError., Same key name in two hotels is allowed — uniqueness is per-hotel., Same OTA channel+external_id across different hotels is allowed., Creates Hotel A (id=1000) and Hotel B (id=1001) with minimal shared structure. (+12 more)

### Community 95 - "Community 95"
Cohesion: 0.17
Nodes (21): _apply_drift(), env_page(), FakeRender, FakeRenderCleanupFailure, FakeRenderPutResponseLost, HealthResponse, manifest(), _mutating_calls() (+13 more)

### Community 96 - "Community 96"
Cohesion: 0.14
Nodes (18): evidence_bytes(), FakeGitHub, iso(), prepare(), Security regression tests for the pull_request_target release gate., test_finalize_rejects_artifact_with_different_bytes(), test_github_client_error_never_discloses_token_or_body(), test_prepare_refuses_head_key_substitution_for_base_checkout_key() (+10 more)

### Community 97 - "Community 97"
Cohesion: 0.13
Nodes (22): PaymentLinkTest, _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _friendly_mercadopago_error(), _is_public_webhook_base(), _mercadopago_access_token(), _mercadopago_connection_payload() (+14 more)

### Community 98 - "Community 98"
Cohesion: 0.22
Nodes (16): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+8 more)

### Community 99 - "Community 99"
Cohesion: 0.09
Nodes (18): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS, buildChannelSummaries() (+10 more)

### Community 100 - "Community 100"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 101 - "Community 101"
Cohesion: 0.09
Nodes (10): _card_value(), _make_reservation(), _operations_analytics(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _request_context(), _starter_analytics() (+2 more)

### Community 102 - "Community 102"
Cohesion: 0.12
Nodes (26): D1: current_stock(location_id=...) narrows the balance to one location;     omit, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE, Owner: "quiero que se pueda poner en las cosas de stock... el costo     por unid, A retried request (flaky connection resends the same POST) must not     double-c, The same client-generated key from two different hotels must not     collide --, Movements with no key (the vast majority) must keep behaving like     before --, Two concurrent requests both pass the pre-insert existing-row check     (neither (+18 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (23): _action_step_up_tickets(), AuthContext, _authenticate_user(), authorize_permission(), _decode_authorization_header(), get_auth_context(), get_current_user(), get_current_user_optional() (+15 more)

### Community 104 - "Community 104"
Cohesion: 0.15
Nodes (22): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_object_key(), _flatten_payload_rows() (+14 more)

### Community 105 - "Community 105"
Cohesion: 0.20
Nodes (25): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _daily_report_key(), _date_token(), get_cached_availability_payload(), get_cached_daily_report_payload() (+17 more)

### Community 106 - "Community 106"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+16 more)

### Community 107 - "Community 107"
Cohesion: 0.20
Nodes (25): _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), Tests for check-in security enforcement:   - prohibido_alojar tag blocks check-i, VIP and other non-blocking tags must not prevent check-in., Guest without prohibido_alojar tag can check in normally., prohibido_alojar tag from a different hotel must not affect check-in. (+17 more)

### Community 108 - "Community 108"
Cohesion: 0.15
Nodes (17): acquire_lease(), env_page(), FakeRender, mutations(), Security contract for the dedicated Render QA baseline lease manager., release_lease(), Response, test_acquire_failure_rolls_back_marker_first_then_target_fields() (+9 more)

### Community 109 - "Community 109"
Cohesion: 0.26
Nodes (23): _approve(), _consume(), _create_reservation(), _request(), _reservation_id(), _set_cancel_permission(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied(), test_canonical_mutation_failure_rolls_back_grant_consumption() (+15 more)

### Community 110 - "Community 110"
Cohesion: 0.11
Nodes (17): _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_master_admin_bypass_migration(), _load_rls_migration(), _load_user_override_migration(), Return model relationships not covered by the core composite contract., Compile the additive RLS helpers through Alembic's PostgreSQL recorder.      Thi, C2: app/master_admin/router.py queries Subscription directly, and     transitive (+9 more)

### Community 111 - "Community 111"
Cohesion: 0.14
Nodes (11): ABC, BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, Acknowledge processed reservation messages in Booking's queue., A provider operation failed before it could return normalized data., NormalizedOTAReservation, OTAAdapterContext, OTAOperationResult (+3 more)

### Community 112 - "Community 112"
Cohesion: 0.22
Nodes (23): AttestationError, _b64url_decode(), _b64url_encode(), build_attestation(), _canonical_json(), _iso_utc(), _json_object(), _load_private_key() (+15 more)

### Community 113 - "Community 113"
Cohesion: 0.09
Nodes (7): 3be6190 fix: align retention timing with privacy notice, 6a4ec23 fix: align retention and login providers with product policy, _pg_cron_migration_enabled(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role., _secure_marketing_leads(), upgrade()

### Community 114 - "Community 114"
Cohesion: 0.09
Nodes (5): complete_mfa_login(), dashboard_summary(), login(), me(), _serialize_user()

### Community 115 - "Community 115"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product() (+12 more)

### Community 116 - "Community 116"
Cohesion: 0.17
Nodes (6): make_res(), make_rooms(), Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback)., TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 117 - "Community 117"
Cohesion: 0.15
Nodes (24): _image_base64(), _jpeg_with_exif_base64(), A .png-declared upload whose bytes are NOT actually a decodable image     (magic, Rows written before the object-storage migration have `content` set     and `obj, A .png-declared upload whose bytes are NOT actually a decodable image     (magic, A guest with real consumption charges (e.g. minibar) owes more than     total_am, Rows written before the object-storage migration have `content` set     and `obj, Money-risk regression (fase QA money-risk-payment-surcharge-daily-rate).      Tw (+16 more)

### Community 118 - "Community 118"
Cohesion: 0.14
Nodes (21): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), createPricePeriod(), DailyRateOut, DailyRatePrices (+13 more)

### Community 119 - "Community 119"
Cohesion: 0.11
Nodes (14): Reservation, cancelWaitlistEntry(), createWaitlistEntry(), listWaitlistEntries(), promoteWaitlistEntry(), API routes for reservation waitlist operations., WaitlistEntry, WaitlistEntryCreate (+6 more)

### Community 120 - "Community 120"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 121 - "Community 121"
Cohesion: 0.18
Nodes (19): Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, ReservationEmailDelivery, ReservationEmailKindEnum, ReservationEmailStatusEnum, _build_message(), ensure_hotel_gmail_ready(), HotelOutboundIdentity (+11 more)

### Community 122 - "Community 122"
Cohesion: 0.17
Nodes (22): TOTP MFA secrets and one-time recovery codes for normal user accounts., UserMfaRecoveryCode, UserMfaSecret, add_recovery_codes(), confirm_enrollment(), consume_mfa_code(), _consume_recovery_code(), _consume_totp_code() (+14 more)

### Community 123 - "Community 123"
Cohesion: 0.12
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 124 - "Community 124"
Cohesion: 0.17
Nodes (21): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _local_date() (+13 more)

### Community 125 - "Community 125"
Cohesion: 0.28
Nodes (23): _build_finish_gates(), _build_readiness_checklist(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status() (+15 more)

### Community 126 - "Community 126"
Cohesion: 0.15
Nodes (23): _available_provider_balance(), balance_due_from_transactions(), cancel_active_links_for_reservation(), cancel_link(), create_link(), _create_mercadopago_preference(), _default_email_delivery(), deliver_link() (+15 more)

### Community 127 - "Community 127"
Cohesion: 0.21
Nodes (23): _hotel(), A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash payment on a reservation must land in the open caja as an INCOME     move, A cash payment cannot be approved outside an explicitly opened caja.      proces, MercadoPago and bank-transfer payments settle the reservation balance     but mu, The live summary's expected_balance must equal the arqueo's expected     balance, A cash payment carrying a payment surcharge must post the GROSS amount     (base, _reservation() (+15 more)

### Community 128 - "Community 128"
Cohesion: 0.21
Nodes (23): _hotel(), _member(), Unit coverage for the notification outbox/service: dedupe, permission filtering,, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, test_daily_report_does_not_resend_same_local_date(), test_daily_report_dst_transition_shifts_the_utc_trigger_hour(), test_daily_report_uses_hotel_local_hour_not_utc() (+15 more)

### Community 129 - "Community 129"
Cohesion: 0.25
Nodes (23): _client_with_db(), _issue_permission_restore_ticket(), _override_auth(), Create an RBAC-read scope or action-bound ticket for focused API tests., _seed_permission_restore_state(), _step_up_headers(), test_effective_permissions_returns_only_current_role_capabilities(), test_override_in_hotel_a_does_not_affect_hotel_b() (+15 more)

### Community 130 - "Community 130"
Cohesion: 0.21
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 131 - "Community 131"
Cohesion: 0.12
Nodes (13): V72 feature tests ported from claude/fervent-jennings-1299c4 and adapted to main, _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled() (+5 more)

### Community 132 - "Community 132"
Cohesion: 0.26
Nodes (20): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+12 more)

### Community 133 - "Community 133"
Cohesion: 0.10
Nodes (18): create_remito(), create_vendor(), _default_currency(), get_vendor(), mark_vendor_settlement_paid(), _quarter_bounds(), Outsourced laundry vendors: vendor/price catalog + remito transfers.  A remito i, Record a remito as a pair of LinenMovements per line.      outbound: house_locat (+10 more)

### Community 134 - "Community 134"
Cohesion: 0.09
Nodes (21): PostgreSQL validation tests.  Run with:   DATABASE_URL_TEST=<isolated-qa-dsn> \, Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic downgrade to base then upgrade to head — idempotency check., Numeric(12,2) columns correctly store and return Decimal values., All PostgreSQL enum types are created by migrations., Critical unique constraints reject duplicates in PostgreSQL., EXPLAIN ANALYZE for guest search by last_name uses index ix_guest_hotel_last_nam, EXPLAIN ANALYZE for reservation date range uses ix_reservation_dates. (+13 more)

### Community 135 - "Community 135"
Cohesion: 0.10
Nodes (16): authed_client(), client_with_db(), get_auth_context_target(), get_db_override_target(), Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th (+8 more)

### Community 136 - "Community 136"
Cohesion: 0.15
Nodes (14): BrokenRedis, _cache_settings(), FakeRedis, _reset_cache_client_state(), test_analytics_home_cache_key_varies_by_filter(), test_availability_payload_is_cached(), test_cache_disabled_returns_computed_value_without_constructing_redis(), test_cache_miss_calls_producer() (+6 more)

### Community 137 - "Community 137"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 138 - "Community 138"
Cohesion: 0.10
Nodes (8): CacheStore, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, RenderRequester, JsonGetter, Protocol, AnalyticsAIProvider

### Community 139 - "Community 139"
Cohesion: 0.12
Nodes (15): email_status(), getHotelConfig(), HotelConfig, HotelConfigUpdate, FastAPI routes for Hotel Configuration (Admin Panel)., Lightweight status so the frontend can check the active system email provider., updateHotelConfig(), hotelConfigKey() (+7 more)

### Community 140 - "Community 140"
Cohesion: 0.10
Nodes (15): SingleRateInput, useBulkUpdateRateField(), useBulkUpsertRates(), useCategoryDailyRates(), usePricePeriodMutations(), usePricePeriods(), useRateCalendar(), useUpsertDailyRate() (+7 more)

### Community 141 - "Community 141"
Cohesion: 0.21
Nodes (12): _auth(), _client(), Issue a synthetic RBAC-read grant or action-bound ticket., _step_up_headers(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults(), test_owner_can_restore_one_role_override_to_catalog_default_with_audit(), test_owner_can_restore_one_user_override_to_role_default_with_audit() (+4 more)

### Community 142 - "Community 142"
Cohesion: 0.10
Nodes (14): CategoriesPayload, DepositPolicyPayload, HotelIdentityPayload, OnboardingStatus, OTAChannelsPayload, OwnerPayload, PaymentMethodsPayload, ProviderSetupPayload (+6 more)

### Community 143 - "Community 143"
Cohesion: 0.17
Nodes (16): _auth_headers(), _ensure_hotel(), A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, test_comped_override_is_idempotent_and_keeps_one_append_only_adjustment(), test_comped_override_records_audit_event(), test_comped_override_rejects_unknown_hotel_without_subscription_state(), test_comped_override_requires_master_admin_session_before_disclosing_hotel_state() (+8 more)

### Community 144 - "Community 144"
Cohesion: 0.22
Nodes (18): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+10 more)

### Community 145 - "Community 145"
Cohesion: 0.16
Nodes (18): _apply_setting(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Reapply stashed tenant settings directly on a just-begun ``Connection``.      Ca, Set the authenticated user id used by membership RLS policies. (+10 more)

### Community 146 - "Community 146"
Cohesion: 0.15
Nodes (9): Regression contracts for the repository's agent-operations setup., run_qa_evidence_check(), test_qa_evidence_rejects_malformed_result_without_traceback(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_schema_accepts_full_catalog(), test_raw_graphify_graph_is_not_tracked(), test_tracked_graphify_artifacts_stay_small(), _tracked_files() (+1 more)

### Community 147 - "Community 147"
Cohesion: 0.35
Nodes (18): _audit_for(), _category(), _context(), _guest(), _hotel(), _reservation(), _room(), test_daily_rate_upsert_creates_audit_log() (+10 more)

### Community 148 - "Community 148"
Cohesion: 0.25
Nodes (18): Owner's core requirement: a remito's cost is fixed at creation time.      The bi, _seed_hotels(), _seed_house_stock(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing(), test_create_remito_rolls_back_entirely_when_a_later_line_fails(), test_create_vendor_creates_its_own_linen_location() (+10 more)

### Community 149 - "Community 149"
Cohesion: 0.20
Nodes (16): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+8 more)

### Community 150 - "Community 150"
Cohesion: 0.15
Nodes (18): V72 §8.3 / §8.4 / §8.5 — Change reservation dates and extend stay tests.  Ported, §8.3 — Cannot change dates when another reservation occupies the room., §8.3 — Changing to a past check-in date is rejected., §8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserv, §8.4 — If new total <= amount_paid after date change, status auto-transitions to, §8.5 — extend_stay extends check-out, increases night count and total price., §8.5 — Cannot extend when another reservation occupies the room during extension, §8.5 — Extending by 0 or negative days (same or earlier date) is rejected. (+10 more)

### Community 151 - "Community 151"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 152 - "Community 152"
Cohesion: 0.16
Nodes (15): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), normalizeUrl(), PREVIEW_APP_HOST_SUFFIXES, PUBLIC_APP_URL, PUBLIC_SITE_URL, PublicCtaMode (+7 more)

### Community 153 - "Community 153"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 154 - "Community 154"
Cohesion: 0.25
Nodes (10): GCSObjectStorage, get_object_storage(), ObjectStat, ObjectStorageError, Minimal object-storage abstraction: put/get/delete bytes by key.  Why this exist, Google Cloud Storage adapter with lazy optional dependency loading., Backend picked by `settings.OBJECT_STORAGE_BACKEND` (default: local).      Uses, Raised when a storage backend cannot complete an operation. (+2 more)

### Community 155 - "Community 155"
Cohesion: 0.19
Nodes (15): _active_room_blocks(), _alerts(), _available_with_review(), _cash_session(), daily_report(), _group(), _guest_name(), is_review_for_today() (+7 more)

### Community 156 - "Community 156"
Cohesion: 0.24
Nodes (16): _auth_context(), _code_at(), _invalid_code(), _issue_ticket(), step_up_client(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_invalid_ticket_fails_closed_without_echoing_it() (+8 more)

### Community 157 - "Community 157"
Cohesion: 0.12
Nodes (7): api_client(), Spin up the real FastAPI app against an in-memory SQLite database., A legacy row with untrimmed whitespace must still be found by the     bulk looku, _seed_ota_no_guarantee_reservation(), test_add_reservation_guests_matches_existing_document_despite_whitespace(), test_release_no_guarantee_endpoint_forbidden_for_unauthorized_role(), test_release_no_guarantee_endpoint_releases_ota_reservation()

### Community 158 - "Community 158"
Cohesion: 0.11
Nodes (11): TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence., All AuditActionEnum values can be stored., Regression: hotel_id on transactions must have a DB-level FK., Reproduces the DELETE /api/stock/items/{id} incident: a stray NOT     NULL colum, test_audit_log_actor_nullable_for_system_actions(), test_audit_log_all_actions_persist() (+3 more)

### Community 159 - "Community 159"
Cohesion: 0.29
Nodes (16): _configured_settings(), _inquiry_rows(), _payload(), test_public_inquiry_collapses_newlines_in_single_line_email_fields(), test_public_inquiry_does_not_trust_spoofable_forwarded_for(), test_public_inquiry_has_global_limit_when_trusted_edge_ip_is_missing(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_not_stored_when_notification_recipient_is_unconfigured() (+8 more)

### Community 160 - "Community 160"
Cohesion: 0.12
Nodes (5): Room.status is a persisted column, not derived from reservations --     a checke, _seed_commercial_setup(), test_move_reservation_room_updates_room_status_for_checked_in_reservation(), test_preview_ota_rebook_as_direct_uses_commercial_quote(), test_rebook_ota_reservation_as_direct_persists_commercial_fields()

### Community 161 - "Community 161"
Cohesion: 0.11
Nodes (11): V72 §5.2 — Reoptimización continua del motor de asignación.  After each new rese, If run_persisted_allocation raises, rollback must be called (not commit)., §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation (+3 more)

### Community 162 - "Community 162"
Cohesion: 0.16
Nodes (10): CeleryJobDispatcher, dispatch_once(), JobDispatcher, JobSpec, Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica, JobDispatchRecord, Durable worker coordination records for portable job dispatch. (+2 more)

### Community 163 - "Community 163"
Cohesion: 0.23
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 164 - "Community 164"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 165 - "Community 165"
Cohesion: 0.19
Nodes (16): archiveHotelRole(), create_role(), createHotelRole(), CreateHotelRolePayload, delete_role(), HotelRole, HotelRoleCode, HotelRolesResponse (+8 more)

### Community 166 - "Community 166"
Cohesion: 0.20
Nodes (14): _credentials(), E2ESafetyError, main(), prepare_e2e_environment(), Prepare the fixed local SQLite database used by Playwright E2E tests.  The safet, Raised before any database-capable dependency is imported., Validate and normalize the only database target allowed for local E2E.      Both, Remove only the generated repository E2E database when explicitly requested. (+6 more)

### Community 167 - "Community 167"
Cohesion: 0.13
Nodes (6): opened_cash_register(), Tests for Check-in Service. Validates guest data requirements before allowing ch, Operational tests must prepare the caja before collecting cash., TestCheckIn, TestCheckOut, TestGuestValidation

### Community 168 - "Community 168"
Cohesion: 0.36
Nodes (16): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1) and the linen ite, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, _teardown(), test_housekeeping_can_operate_remitos_but_not_manage_vendors(), test_linen_items_and_locations_are_hotel_scoped(), test_linen_summary_is_hotel_scoped_and_denies_roles_without_laundry_permission() (+8 more)

### Community 169 - "Community 169"
Cohesion: 0.30
Nodes (16): _fresh_totp_code(), _lead(), _login(), test_hold_and_audit_are_one_transaction(), test_hold_can_protect_a_public_inquiry_without_copying_its_content(), test_hold_rejects_missing_targets_expired_dates_and_duplicate_active_holds(), test_hold_rejects_unsupported_resource_types(), test_marketing_lead_hold_is_audited_and_does_not_extend_the_retention_clock() (+8 more)

### Community 170 - "Community 170"
Cohesion: 0.27
Nodes (15): _enable_external_effects(), _fake_mp_gateway(), A public webhook endpoint must fail closed without a configured secret., _reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp(), test_create_payment_link_persists_link_without_transaction() (+7 more)

### Community 171 - "Community 171"
Cohesion: 0.24
Nodes (15): _link(), Re-delivering the SAME webhook must not create a 2nd transaction nor raise., Two distinct webhooks for the same completed payment id -> one transaction., A later-arriving webhook for the SAME payment reporting an earlier status     (n, A payment already recorded as rejected/failed must not silently become     compl, _reservation(), test_balance_due_uses_transactions_not_payments(), test_completed_gateway_payment_creates_one_transaction() (+7 more)

### Community 172 - "Community 172"
Cohesion: 0.12
Nodes (9): An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used., PricePeriod is NOT used for dates outside its range., Tier-1: explicit DailyRate row wins over everything else., Tier-2: active PricePeriod used when no DailyRate exists. (+1 more)

### Community 173 - "Community 173"
Cohesion: 0.14
Nodes (8): 2de6004 Add a leads page to the owner console and fix unreadable console styling, { code }, source, DATE, HEADERS, Lead, SOURCE_LABELS, toCsvCell()

### Community 174 - "Community 174"
Cohesion: 0.24
Nodes (13): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+5 more)

### Community 175 - "Community 175"
Cohesion: 0.13
Nodes (15): GemmaActionApplyDraftRequest, GemmaActionApplyDraftResponse, GemmaActionApproveRequest, GemmaActionApproveResponse, GemmaActionRejectRequest, GemmaActionRejectResponse, GemmaActionReviewDraftRequest, GemmaActionReviewDraftResponse (+7 more)

### Community 176 - "Community 176"
Cohesion: 0.28
Nodes (12): AllocationPolicyError, apply_policy_suggestion(), create_policy_version(), ensure_default_policy_profile(), ensure_default_policy_version(), get_active_policy_settings(), get_policy_suggestion(), list_policy_versions() (+4 more)

### Community 177 - "Community 177"
Cohesion: 0.26
Nodes (13): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts(), test_analytics_insights_status_and_payloads(), test_cleanup_expired_exports_task() (+5 more)

### Community 178 - "Community 178"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 179 - "Community 179"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, Fail-closed boundary tests: disabled lanes do no parsing, DB work or network., test_apple_login_stops_before_jwks_or_db(), test_connections_flag_alone_closes_credential_lane(), test_credential_access_and_email_stop_before_db_or_network(), test_google_login_stops_before_transport_or_db(), test_ota_callback_stops_before_json_parse() (+2 more)

### Community 180 - "Community 180"
Cohesion: 0.13
Nodes (9): Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify the hotel has exactly 38 rooms., Same room_number can exist in different hotels without conflict., Verify room string representation., Verify category string representation. (+1 more)

### Community 181 - "Community 181"
Cohesion: 0.28
Nodes (14): _manual_payload(), B4: the manual OTA form lets the receptionist type a total + currency     that d, The receptionist can type TWO independent prices (ARS and USD) for a     manual, Root-cause repro for the owner's report: a category with a RatePlan     that is, _seed_hotel(), test_duplicate_channel_external_id_updates_existing_reservation_and_audits(), test_manual_ota_cross_hotel_isolation(), test_manual_ota_dual_quoted_amounts_saved_independently_of_canonical_total() (+6 more)

### Community 182 - "Community 182"
Cohesion: 0.26
Nodes (11): _load_migration(), Unit coverage for the guarded PostgreSQL enum-label migration., _RecordingBind, _Result, test_downgrade_reverses_only_the_new_migration(), test_revision_fits_alembic_version_column(), test_sqlite_skips_postgresql_enum_ddl(), test_upgrade_fails_closed_if_both_enum_labels_exist() (+3 more)

### Community 183 - "Community 183"
Cohesion: 0.23
Nodes (14): Security regression tests for local QA operator attestations., tagged(), test_altered_signature_is_rejected(), test_attestation_older_than_24_hours_is_rejected(), test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_manifest_byte_change_after_signing_is_rejected() (+6 more)

### Community 184 - "Community 184"
Cohesion: 0.25
Nodes (14): Live PostgreSQL RLS behavioral verification.  Unlike tests/test_tenant_rls_contr, With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the     unp, Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak., C2: with app.master_admin='true', subscriptions across hotels are visible., C1: app.hotel_id must survive a commit within the same ORM session.      Uses th, A superuser engine whose commits are REAL, visible to other connections.      Se, _role_connection(), _seed_engine() (+6 more)

### Community 185 - "Community 185"
Cohesion: 0.21
Nodes (14): _headers(), Security settings API is tenant-scoped, redacted and revokes real JWTs., Audit evidence is readable only; there is no ordinary mutation route., Audit evidence is readable only; there is no ordinary mutation route., test_audit_surfaces_do_not_expose_mutating_methods(), test_manager_cannot_read_security_settings(), test_revoke_all_invalidates_the_callers_previous_token(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv() (+6 more)

### Community 186 - "Community 186"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 187 - "Community 187"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 188 - "Community 188"
Cohesion: 0.22
Nodes (13): availability(), _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), get_booking(), list_bookings() (+5 more)

### Community 189 - "Community 189"
Cohesion: 0.14
Nodes (10): RateCalendarResponse, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, RateEditorGrid(), RateEditorGridProps (+2 more)

### Community 190 - "Community 190"
Cohesion: 0.25
Nodes (11): admin_comped_override(), change_plan(), delete_override(), _master_admin_hotel_id(), Subscription status and entitlements endpoints., _remaining_trial_days(), _require_master_admin_write(), _serialize_status_payload() (+3 more)

### Community 191 - "Community 191"
Cohesion: 0.33
Nodes (14): DrillError, main(), _pg_command(), _pg_count(), _postgres_parts(), Expected, safe failure for a local drill., Verify every ready metadata row against the local blob before restore., _run_pg_command() (+6 more)

### Community 192 - "Community 192"
Cohesion: 0.17
Nodes (14): Pydantic schemas for Room and RoomCategory., Non-financial category metadata safe for housekeeping workflows., Room state without rates or free-text notes that may contain PII., RoomBase, RoomCategoryBase, RoomCategoryCreate, RoomCategoryOperationalRead, RoomCategoryRead (+6 more)

### Community 193 - "Community 193"
Cohesion: 0.29
Nodes (14): _active_tag_filter(), add_tag(), _audit(), _escape_like_term(), find_or_create_guest(), _get_guest(), _guest_search_rank(), list_active_tags() (+6 more)

### Community 194 - "Community 194"
Cohesion: 0.26
Nodes (13): _create_role(), Security and API contract tests for per-hotel custom roles., _step_up_headers(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), test_custom_role_downgrade_aborts_before_any_data_changes(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed(), test_custom_roles_can_be_assigned_and_invited_but_owner_transfer_stays_separate() (+5 more)

### Community 195 - "Community 195"
Cohesion: 0.40
Nodes (14): _build_client(), _cleanup_client(), _override_auth(), _payload(), Security gap: any role that can create a reservation (owner, co_owner, manager,, Owner explicitly asked that only the owner -- not even co_owner --     override, No regression: the gate only fires when total_amount is actually sent., _seed_bookable_state() (+6 more)

### Community 196 - "Community 196"
Cohesion: 0.31
Nodes (14): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- per-item stock consumption (out, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+6 more)

### Community 197 - "Community 197"
Cohesion: 0.42
Nodes (12): _make_reservation(), Tests for V72 §5 - Concurrency guards: double-booking and duplicate payments.  T, _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations() (+4 more)

### Community 198 - "Community 198"
Cohesion: 0.20
Nodes (13): Fase 3 (QA reservas): PATCH /api/reservations/{id} only understands     room_id/, Receptionists gain only the narrow, same-category move tier by default., B5: cross-category move via the endpoint enforces capacity and price_action., Same wiring as reservation_api_client, but a role without room_move by default (, reservation_api_client_as_receptionist(), _seed_reservation_prerequisites(), test_create_reservation_persists_mobility_restriction(), test_patch_reservation_silently_ignores_unsupported_category_and_status_fields() (+5 more)

### Community 199 - "Community 199"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification., Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 200 - "Community 200"
Cohesion: 0.20
Nodes (9): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+1 more)

### Community 201 - "Community 201"
Cohesion: 0.32
Nodes (11): acknowledge_shift_handoff(), _can(), _can_read_reservation_context(), _conflict(), create_operational_task(), get_operational_task_history(), get_operational_tasks(), _is_operator_scoped() (+3 more)

### Community 202 - "Community 202"
Cohesion: 0.14
Nodes (14): 2447732 fix(security): bump fastapi/starlette to clear starlette CVEs, 3574c6f qa(catalog): record Fase 14 data/logs/dependencies security findings, 45be255 qa(catalog): record Fase 14b dependency-CVE closure findings, 51c2d3a fix(security): bump react-router-dom 6.30.3 to 7.18.1, fix broken onboarding pill nav, 534f3e8 fix(security): bump Pillow 10.3.0 to 12.3.0 to clear CVEs, 672b76d chore(graphify): regenerate graph after Fase 14b CVE closure, 7eea9ed chore(graphify): regenerate graph after Fase 14 security hardening, 954f79c chore(graphify): regenerate graph after Fase 13 security fixes (+6 more)

### Community 203 - "Community 203"
Cohesion: 0.14
Nodes (3): OTAProviderAdapter, FakeBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event()

### Community 204 - "Community 204"
Cohesion: 0.19
Nodes (13): get_country_catalog(), get_timezone_catalog(), hotel_today(), is_valid_timezone(), local_today(), normalize_timezone(), Timezone catalog helpers.  Keeps timezone lookup out of Postgres/Supabase dashbo, Return the curated country -> timezone catalog as {code, name, timezone} dicts. (+5 more)

### Community 205 - "Community 205"
Cohesion: 0.22
Nodes (10): _date_window(), _decimal_total(), detect_no_shows(), _parse_datetime(), project_all_derived_facts_incremental(), _project_all_hotels_window(), project_operational_facts_to_clickhouse(), _project_operational_window() (+2 more)

### Community 206 - "Community 206"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 207 - "Community 207"
Cohesion: 0.46
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 208 - "Community 208"
Cohesion: 0.21
Nodes (9): Tests for B2: GET /api/reservations/occupancy-grid (planilla de ocupación).  Cro, Regression guard for the plan's explicit note: the naive `balance_due`     ignor, _reserve(), test_cancelled_reservation_is_excluded(), test_custom_housekeeping_role_gets_anonymized_occupancy_grid(), test_operational_balance_due_includes_consumption_charges(), test_query_count_is_bounded_not_scaling_with_rooms_or_reservations(), test_reservation_entirely_before_or_after_window_is_excluded() (+1 more)

### Community 209 - "Community 209"
Cohesion: 0.29
Nodes (12): _ctx(), _seed_hotel(), test_apply_promotions_never_goes_negative(), test_create_promotion_rejects_duplicate_code(), test_create_promotion_rejects_percentage_over_100(), test_deactivate_and_reactivate_promotion(), test_find_applicable_promotions_matches_guest_tag_type(), test_find_applicable_promotions_matches_typed_conditions() (+4 more)

### Community 210 - "Community 210"
Cohesion: 0.48
Nodes (12): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+4 more)

### Community 211 - "Community 211"
Cohesion: 0.16
Nodes (3): _bearer_headers(), test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_session_listing_individual_revoke_logout_and_revoke_all()

### Community 212 - "Community 212"
Cohesion: 0.31
Nodes (12): _delivery(), _message(), _post(), HTTP boundary tests for the Meta Cloud API WhatsApp webhook.  The endpoint had n, Regression: a bad phone used to raise 400 and roll the whole batch back.      Me, ``text`` and ``profile`` arriving as strings must not raise a 500., _signature(), test_ingests_a_signed_inbound_message() (+4 more)

### Community 213 - "Community 213"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), downgrade(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), _install_rls(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):, Create an active GuestRestriction for every currently-active (non-expired)     l (+5 more)

### Community 214 - "Community 214"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 215 - "Community 215"
Cohesion: 0.24
Nodes (9): create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_single_rate(), get_usd_oficial_rate() (+1 more)

### Community 216 - "Community 216"
Cohesion: 0.28
Nodes (12): BenchmarkResult, cleanup(), derive_test_dsn(), explain(), main(), measure(), percentile(), print_results() (+4 more)

### Community 217 - "Community 217"
Cohesion: 0.19
Nodes (6): _clean_optional(), _clean_required(), PublicInquiryAccepted, PublicInquiryCreate, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 218 - "Community 218"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 219 - "Community 219"
Cohesion: 0.22
Nodes (8): Mailer, Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists., send_generic_auth_notice_email(), send_platform_email(), send_reset_password_email(), send_verification_email(), send_verification_success_email()

### Community 220 - "Community 220"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 221 - "Community 221"
Cohesion: 0.37
Nodes (12): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id(), _normalize_required() (+4 more)

### Community 223 - "Community 223"
Cohesion: 0.32
Nodes (12): _client_with_db(), _override_auth(), B3: check-in must capture the guest's missing profile data (birth place/ country, Green case: same endpoint, now with `guest` in the payload, succeeds once., Red case: guest missing the 4 new mandatory fields cannot check in., _seed_fully_paid_reservation(), test_add_companion_during_checkin_flow_appears_in_additional_guests(), test_add_companion_exceeding_capacity_returns_clear_400() (+4 more)

### Community 224 - "Community 224"
Cohesion: 0.31
Nodes (9): _outbox_row(), _seed_hotels(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_task_drains_row_after_after_commit_failure(), test_old_pending_row_emits_stale_metric_alert(), test_rollback_removes_durable_event_row(), test_worker_is_tenant_scoped_and_uses_stored_revision() (+1 more)

### Community 225 - "Community 225"
Cohesion: 0.44
Nodes (12): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_overlapping_protected_reservation_requires_manual_resolution() (+4 more)

### Community 226 - "Community 226"
Cohesion: 0.21
Nodes (7): Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed., Resolving with a room of a different category must be blocked., Resolving with an already-occupied room must be blocked., Trying to resolve with a non-existent room raises ReservationError., After resolve, the DB row reflects the updated state., TestWaitlistResolveLogic

### Community 227 - "Community 227"
Cohesion: 0.24
Nodes (12): _backfill_defaults(), _contract_legacy_rows(), _copy_role_overrides(), downgrade(), _insert_permission_rows(), _install_user_override_rls(), expand RBAC catalog and add tenant-scoped user overrides  Revision ID: 20260813_, Install the PostgreSQL tenant policy; no-op on other dialects. (+4 more)

### Community 228 - "Community 228"
Cohesion: 0.20
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the

### Community 229 - "Community 229"
Cohesion: 0.36
Nodes (11): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+3 more)

### Community 230 - "Community 230"
Cohesion: 0.36
Nodes (11): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., _render(), _strong_password() (+3 more)

### Community 231 - "Community 231"
Cohesion: 0.21
Nodes (10): changeSubscriptionPlan(), startTrial(), SubscriptionPlan, CheckoutStub(), CheckoutStubProps, useSubscriptionPlans(), useSubscriptionStatus(), SettingsSubscriptionPage() (+2 more)

### Community 232 - "Community 232"
Cohesion: 0.27
Nodes (9): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, CompanyDocumentCreate, CompanyDocumentRead, CompanyDocumentStatusUpdate (+1 more)

### Community 233 - "Community 233"
Cohesion: 0.17
Nodes (9): LeadCreateRequest, LeadCreateResponse, MasterLeadListPayload, MasterLeadPayload, MasterPricingPlanListPayload, MasterPricingPlanPayload, PublicPricingPlan, PublicPricingResponse (+1 more)

### Community 234 - "Community 234"
Cohesion: 0.17
Nodes (10): DailyReportScheduleRead, DailyReportScheduleUpdate, NotificationListResponse, NotificationMarkReadRequest, NotificationPreferenceRead, NotificationPreferenceUpdate, NotificationRead, PushSubscriptionRegisterRequest (+2 more)

### Community 235 - "Community 235"
Cohesion: 0.23
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 236 - "Community 236"
Cohesion: 0.26
Nodes (7): client_with_db(), ctx(), get_auth_context_target(), get_db_override_target(), _override_role(), test_manager_without_config_manage_permission_is_denied(), test_owner_can_grant_manager_config_manage_override()

### Community 237 - "Community 237"
Cohesion: 0.36
Nodes (9): _create_link(), _post_webhook(), HTTP-level Mercado Pago webhook journey.  Exercises the real route (/api/payment, _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_rejected_webhook_records_payment_without_completing_a_transaction() (+1 more)

### Community 238 - "Community 238"
Cohesion: 0.44
Nodes (11): _seed_daily_rates(), _seed_hotel(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night(), test_canonical_pricing_manual_override_skips_promotions_entirely() (+3 more)

### Community 239 - "Community 239"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 240 - "Community 240"
Cohesion: 0.26
Nodes (9): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), test_listing_uses_one_scalar_reservation_query(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history() (+1 more)

### Community 241 - "Community 241"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 242 - "Community 242"
Cohesion: 0.21
Nodes (8): _pay_deposit(), §7.1: Reservation in DEPOSIT_PAID status raises CheckInError., §7.1: Error message tells the operator the required status is 'fully_paid'., §7.1: Error message also reveals the current (blocking) status., §7.1 positive: paying the remaining balance after deposit allows check-in., Pay only the deposit amount (30%) as a PARTIAL_PAYMENT → DEPOSIT_PAID.      Note, Deposit-only payment (30%) must NOT allow check-in., TestPaymentGateDepositPaid

### Community 243 - "Community 243"
Cohesion: 0.17
Nodes (7): Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest who has NOT accepted terms is blocked (terms_accepted=False)., When require_document_for_checkin=False, missing document is not an error., When require_terms_acceptance=False, missing terms is not an error., TestGuestValidationGates

### Community 244 - "Community 244"
Cohesion: 0.17
Nodes (6): apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price., TestApplyPricePeriod

### Community 245 - "Community 245"
Cohesion: 0.25
Nodes (7): e2ae869 Use Render production as cloud QA surface, example(), Regression tests for final provider-evidence continuity., test_any_provider_subject_drift_is_rejected(), test_cli_rejects_symlinked_manifest(), test_final_observation_cannot_predate_probes(), test_only_a_newer_observation_timestamp_may_change()

### Community 246 - "Community 246"
Cohesion: 0.40
Nodes (10): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _timestamp(), _validate_baseline_lease_id(), validate_manifest() (+2 more)

### Community 247 - "Community 247"
Cohesion: 0.33
Nodes (3): CollaborationManager, Process-local peers plus best-effort Redis pub/sub fan-out., _RoomTransport

### Community 248 - "Community 248"
Cohesion: 0.24
Nodes (10): getSubscriptionStatus(), listSubscriptionPlans(), SubscriptionLimit, SubscriptionStatus, buildMockStatus(), enrichPlans(), FALLBACK_PLANS, normalizeLimits() (+2 more)

### Community 249 - "Community 249"
Cohesion: 0.31
Nodes (10): channel_status(), complete_channel(), create_note(), inbox(), Authenticated human WhatsApp CRM inbox.  This router never calls Meta directly., Store metadata after the backend completes Embedded Signup.      No bearer token, _require_plan(), send_message() (+2 more)

### Community 250 - "Community 250"
Cohesion: 0.20
Nodes (11): _frontend_placeholder(), Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., SPA fallback for React Router.     Skips API/asset paths to avoid shadowing. (+3 more)

### Community 251 - "Community 251"
Cohesion: 0.24
Nodes (10): _client_signature(), get_async_redis_client(), get_sync_redis_client(), namespaced_key(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Clear process clients for tests and orderly shutdown., Return one sync client per process, or None for empty configuration., Return one async client per process for async transports. (+2 more)

### Community 252 - "Community 252"
Cohesion: 0.42
Nodes (10): clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret(), verify_stripe_signature() (+2 more)

### Community 253 - "Community 253"
Cohesion: 0.24
Nodes (7): Durable tenant-scoped metadata for private object-storage blobs., Metadata and lifecycle state; bytes remain outside PostgreSQL., StoredObject, StoredObjectStatusEnum, Upload/verify/register object-storage bytes without exposing them in events., Persist pending metadata, upload, stat and mark ready after verification., register_uploaded_object()

### Community 254 - "Community 254"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 255 - "Community 255"
Cohesion: 0.29
Nodes (10): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a short lease and release it only if this worker owns it.      Redis/Val, _required(), _settings() (+2 more)

### Community 256 - "Community 256"
Cohesion: 0.36
Nodes (10): _actor_name(), _area_for(), _bounds(), _date_filter(), list_operational_audit(), _matches(), _money(), _row() (+2 more)

### Community 257 - "Community 257"
Cohesion: 0.31
Nodes (9): approve_transfer_proof(), _decode_image(), _delete_uncommitted_object(), get_transfer_proof(), recover_failed_transfer_proof_commit(), reject_transfer_proof(), _reservation(), _safe_filename() (+1 more)

### Community 258 - "Community 258"
Cohesion: 0.38
Nodes (10): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _is_allowed_status_transition(), _normalize_status(), _payload_value() (+2 more)

### Community 259 - "Community 259"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 260 - "Community 260"
Cohesion: 0.35
Nodes (10): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), PostgresTargetSafetyError, Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, The PostgreSQL test target cannot be proven isolated and disposable. (+2 more)

### Community 261 - "Community 261"
Cohesion: 0.24
Nodes (4): _Client, _Response, test_provider_chat_uses_curated_hotel_context_and_controlled_message(), test_provider_receives_only_curated_hotel_analytics_payload()

### Community 262 - "Community 262"
Cohesion: 0.35
Nodes (7): FakeJwkClient, test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_valid_apple_token_is_verified(), _token(), _verify()

### Community 263 - "Community 263"
Cohesion: 0.38
Nodes (10): _create_payload(), _reservation(), _seed_guest_inventory(), _seed_hotel(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_receptionist_cannot_override_until_canonical_permission_is_granted(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(), test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass() (+2 more)

### Community 264 - "Community 264"
Cohesion: 0.18
Nodes (3): The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today, utc_server_clock()

### Community 266 - "Community 266"
Cohesion: 0.40
Nodes (8): _make_guest(), _make_reservation(), _make_room_set(), A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m, test_available_with_review_surfaces_in_report(), test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks(), test_daily_report_is_hotel_scoped(), test_daily_report_pending_payments_reflect_consumption_charges()

### Community 267 - "Community 267"
Cohesion: 0.18
Nodes (4): Tests for OTA Integration — Race condition handling and webhook processing., TestAvailabilityUpdate, TestBookingWebhook, TestExpediaWebhook

### Community 268 - "Community 268"
Cohesion: 0.25
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret()

### Community 269 - "Community 269"
Cohesion: 0.29
Nodes (8): A1: resolve() used to call seed_default_permissions() on every invocation      (, _seed_hotel(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default(), test_override_in_hotel_a_does_not_affect_hotel_b(), test_owner_override_can_grant_permission_missing_from_role_default(), test_permission_override_can_deny_receptionist_guest_edit(), test_resolve_seeds_the_matrix_once_per_engine_not_per_call()

### Community 270 - "Community 270"
Cohesion: 0.33
Nodes (8): _make_hotel(), _make_reservation(), R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).  No real em, test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 271 - "Community 271"
Cohesion: 0.22
Nodes (6): _count_queries(), _mk_reservation(), The real N+1 this fix targets: query count must track the number of     reservat, Every distinct way `_build_pending_actions` can produce an action must     still, test_pending_actions_prefilter_matches_unfiltered_scan_for_every_trigger_type(), test_pending_actions_query_count_scales_with_candidates_not_total_reservations()

### Community 272 - "Community 272"
Cohesion: 0.36
Nodes (7): _move(), _seed_move_shapes(), test_capacity_tier_alone_includes_each_narrower_tier(), test_existing_wide_roles_still_move_anywhere(), test_manager_can_move_each_shape(), test_manager_capacity_permission_does_not_bypass_occupancy_validation(), test_receptionist_is_limited_to_same_category_moves()

### Community 274 - "Community 274"
Cohesion: 0.25
Nodes (6): Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp., After checkout, the assigned room status is set to CLEANING., Calling perform_checkout twice on the same reservation raises CheckInError on se, TestCheckoutGate

### Community 275 - "Community 275"
Cohesion: 0.29
Nodes (6): _context(), _hotel_today(), Regression tests for tenant-scoped, per-role reservation visibility., _reserve(), test_in_house_guest_remains_visible_when_check_in_predates_window(), test_visibility_window_filters_far_future_and_null_is_unlimited()

### Community 276 - "Community 276"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 277 - "Community 277"
Cohesion: 0.38
Nodes (9): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+1 more)

### Community 278 - "Community 278"
Cohesion: 0.20
Nodes (7): DailyRateRangeRow, PriceField, DAY_LABEL, PRICE_FIELDS, RateEditorMobileCards(), RateEditorMobileCardsProps, WEEKDAY_LABEL

### Community 279 - "Community 279"
Cohesion: 0.31
Nodes (9): _cassandra_probe(), _close_clients(), _enable(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each, Avoid reusing a client created by another test or stale .env flags., reset_projection_clients(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), test_mongo_audit_projection_lands_document() (+1 more)

### Community 280 - "Community 280"
Cohesion: 0.44
Nodes (9): DocumentTypeEnum, GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate (+1 more)

### Community 281 - "Community 281"
Cohesion: 0.33
Nodes (1): OTAOrchestratorService

### Community 282 - "Community 282"
Cohesion: 0.20
Nodes (9): PermissionCatalogItem, PermissionDecision, Set both sides of one role's reservation visibility window., RolePermissionOverrideRequest, TemporaryActionGrantApproveRequest, TemporaryActionGrantRequest, UserPermissionOverrideRequest, VisibilityWindowRead (+1 more)

### Community 283 - "Community 283"
Cohesion: 0.38
Nodes (9): fetch_all_rates(), fetch_rate(), get_all_rates_snapshot(), _get_async(), get_cached_rates(), get_rate_sync(), get_usd_official_rate(), get_usd_rate_for_type() (+1 more)

### Community 284 - "Community 284"
Cohesion: 0.29
Nodes (9): ensure_active_owner(), _lock_active_owner_memberships(), Atomic invariants and lifecycle operations for hotel memberships., Lock the current owner set for the duration of the caller's transaction., Require at least one active owner while holding the owner-row lock., Validate a role/status mutation before changing the membership row.      The own, Transfer the single billing/property owner inside one transaction., transfer_primary_owner() (+1 more)

### Community 285 - "Community 285"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 286 - "Community 286"
Cohesion: 0.56
Nodes (8): _guest(), _reservation(), _seed_hotel(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_previous_completed_room_signal_requires_the_new_reservation_category()

### Community 287 - "Community 287"
Cohesion: 0.60
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+1 more)

### Community 289 - "Community 289"
Cohesion: 0.29
Nodes (5): _integration_client(), _Response, test_gmail_oauth_callback_uses_signed_state(), test_send_hotel_email_uses_connected_gmail(), test_validate_gmail_credentials_rejects_missing_send_scope()

### Community 290 - "Community 290"
Cohesion: 0.24
Nodes (5): _Response, _seed_gmail_connection(), _seed_mercadopago_connection(), test_payment_link_test_requires_hotel_gmail_connection(), test_send_hotel_email_uses_connected_gmail()

### Community 291 - "Community 291"
Cohesion: 0.31
Nodes (7): _login(), Public pricing is owner-editable from the master-admin console.  Reuses the mast, test_a_plan_dropped_from_the_payload_disappears(), test_negative_price_is_rejected(), test_owner_can_read_captured_leads(), test_owner_sets_a_price_and_the_public_endpoint_serves_it(), test_saving_pricing_writes_an_audit_event()

### Community 292 - "Community 292"
Cohesion: 0.20
Nodes (6): Verify auto-generated timestamps., Tests for Guest and GuestCompanion models., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Create companions and verify relationship., TestGuestModel

### Community 293 - "Community 293"
Cohesion: 0.20
Nodes (6): Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify can_transition_to method., Verify balance_due computed property., Verify nights calculation., TestReservationModel

### Community 294 - "Community 294"
Cohesion: 0.20
Nodes (9): Regression coverage for portable Graphify artifact normalization., A second normalizer run must leave already-portable artifacts unchanged., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten., test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized() (+1 more)

### Community 295 - "Community 295"
Cohesion: 0.33
Nodes (8): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement(), test_onboarding_cannot_activate_paid_plan_without_checkout()

### Community 296 - "Community 296"
Cohesion: 0.36
Nodes (8): test_handoff_is_tenant_scoped_and_acknowledged(), test_list_tasks_orders_priority_and_due_date(), test_maintenance_task_keeps_block_until_authorized_release(), test_operator_scope_matches_role_and_assignment(), test_report_only_custom_manager_cannot_read_or_mutate_out_of_scope_tasks(), test_task_lifecycle_history_and_stale_version(), test_task_links_cannot_cross_tenant(), _user()

### Community 297 - "Community 297"
Cohesion: 0.47
Nodes (7): _build_client(), _cleanup(), _override_auth(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_reactivate_deactivated_surcharge_via_patch()

### Community 298 - "Community 298"
Cohesion: 0.20
Nodes (1): TestLeadCapture

### Community 299 - "Community 299"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 300 - "Community 300"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 301 - "Community 301"
Cohesion: 0.22
Nodes (7): _make_reservation(), Verify the hotel config flag is respected (default = True → gate enforced)., Config flag is True by default; gate is active for PENDING reservation., Even if document/terms config flags are disabled, payment gate remains active., Cannot checkout a PENDING reservation., Create a PENDING reservation using the first available category., TestConfigFlag

### Community 302 - "Community 302"
Cohesion: 0.22
Nodes (6): _make_period(), When two PricePeriods overlap, the one with higher priority is returned., Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics)., DailyRate explicit row takes priority over an active PricePeriod., TestPricePeriodOverlap

### Community 303 - "Community 303"
Cohesion: 0.36
Nodes (8): _seed_group(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_revert_already_reverted_group_returns_400(), test_revert_group_service_conflict_does_not_overwrite_original_room(), test_revert_group_service_returns_reverted_without_conflicts(), test_revert_movement_group_restores_original_room_and_audits()

### Community 304 - "Community 304"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 305 - "Community 305"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 306 - "Community 306"
Cohesion: 0.31
Nodes (9): _create_linen_tables(), downgrade(), _drop_kind_column(), _finalize_laundry_vendor_columns(), _migrate_linen_data(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li, Reverse of _migrate_linen_data: every linen_items row moves back into     stock_ (+1 more)

### Community 307 - "Community 307"
Cohesion: 0.29
Nodes (9): downgrade(), _insert_default_rows(), _insert_permission_rows(), _install_rls(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls() (+1 more)

### Community 308 - "Community 308"
Cohesion: 0.40
Nodes (9): _create_and_secure_retention_holds(), _cron_is_required(), downgrade(), _downgrade_sqlite(), _install_purge_function(), Honor auditable legal holds in public-form retention.  Revision ID: 20260926_leg, _reschedule_purge_job(), upgrade() (+1 more)

### Community 309 - "Community 309"
Cohesion: 0.42
Nodes (8): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity()

### Community 310 - "Community 310"
Cohesion: 0.44
Nodes (8): _catalog(), initialize(), _json_bytes(), main(), OperationalQAError, _utc_now(), validate(), _write()

### Community 311 - "Community 311"
Cohesion: 0.50
Nodes (9): ArchiveCustomRoleRequest, CreateCustomRoleRequest, Tenant-scoped custom role catalog and lifecycle endpoints., RenameCustomRoleRequest, RoleCatalogItem, RoleListResponse, HotelRoleInUse, HotelRoleNameConflict (+1 more)

### Community 312 - "Community 312"
Cohesion: 0.22
Nodes (6): 00af83e chore(graphify): regenerate graph after B4 manual OTA + manual tarifa + B4.2, 09d638d fix(reservations): revalidate capacity and gate repricing on cross-category room move (B5), 2618f7c feat(rates): expose PayPal and credit card columns in the rate editor (B4.2), 2faa743 feat(reservations): wire "Cargar reserva de OTA" button + manual tarifa on reserva directa, e08928f chore(graphify): regenerate graph after B5 room-move capacity/pricing fix, credentials

### Community 313 - "Community 313"
Cohesion: 0.22
Nodes (9): 16fdc4a test(security): lock in cross-hotel id-collision isolation (Fase 12), 255306b test(payments): explicit evidence that proof uploads reject magic-byte spoofing and oversized payloads, 7040c65 fix(master-admin): Stripe webhook retry redelivery no longer 500s, 9c0cf78 chore(catalog): record commit sha for fase12 cross-hotel audit row, bcbaf10 fix(payments): unify dead MP webhook signature validator + guard payment status regressions, d190bed chore(graphify): regenerate graph after Fase 12 cross-hotel audit tests, d19fd80 fix(frontend): close double-submit race on reservation create/check-in/check-out and stock movements, e82f3cf chore(graphify): regenerate graph after regression-catalog update (+1 more)

### Community 314 - "Community 314"
Cohesion: 0.28
Nodes (4): 7b40538 Merge pull request #97 from Maximo-Paulos/fix/ota-lifecycle-enum-case-mismatch, e679aa5 fix(db): sync ota_reservation_lifecycle_enum labels with the ORM, Regression guard for a real bug: `dee1bd0660f6_ota_allocation_foundation` create, Fix ota_reservation_lifecycle_enum labels to match the ORM's values_callable.  `

### Community 315 - "Community 315"
Cohesion: 0.31
Nodes (6): jsonResponse(), permissionAdminReadStepUpRequired(), session, stepUpRequired(), tick(), waitFor()

### Community 316 - "Community 316"
Cohesion: 0.44
Nodes (8): BillingDecision, evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 317 - "Community 317"
Cohesion: 0.22
Nodes (6): GuestRestrictionCreate, GuestRestrictionOverrideRequest, GuestRestrictionRead, GuestRestrictionResolveRequest, Pydantic schemas for GuestRestriction (formal lodging-prohibition entity)., Carried on reservation/checkin/quote requests to authorize bypassing     an acti

### Community 318 - "Community 318"
Cohesion: 0.22
Nodes (8): AuditTimelineItemRead, AuditTimelineRead, Public, redacted contracts for hotel security settings., RevokeAllSessionsResponse, SecurityCurrentUserRead, SecurityEventRead, SecurityEventsRead, SecurityOverviewRead

### Community 319 - "Community 319"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, main(), missing_model_tables(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., repair_cash_handoff_schema()

### Community 320 - "Community 320"
Cohesion: 0.33
Nodes (2): LocalObjectStorage, Stores objects as files under a local directory root.      Generalizes the patte

### Community 321 - "Community 321"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 324 - "Community 324"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_surfaces_retryable_provider_outage()

### Community 325 - "Community 325"
Cohesion: 0.58
Nodes (8): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_has_no_access_to_commercial_configuration(), test_owner_can_create_and_update_commercial_configuration()

### Community 326 - "Community 326"
Cohesion: 0.28
Nodes (3): _read(), test_explicit_rotation_replaces_values_and_preserves_mode(), test_generates_only_allowed_synthetic_values_with_private_permissions()

### Community 327 - "Community 327"
Cohesion: 0.25
Nodes (9): C2 regression (SQLite, syntactic only -- RLS is a Postgres-only concern,     see, C2 regression (SQLite, syntactic only -- RLS is a Postgres-only concern,     see, C2 regression (SQLite, syntactic only -- RLS is a Postgres-only concern,     see, C2 regression (SQLite, syntactic only -- RLS is a Postgres-only concern,     see, _seed_hotel(), _seed_subscription(), test_master_dashboard_summary_counts_subscriptions_across_hotels(), test_master_policy_update_exempts_hotel_and_user() (+1 more)

### Community 328 - "Community 328"
Cohesion: 0.39
Nodes (8): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel()

### Community 329 - "Community 329"
Cohesion: 0.50
Nodes (8): _auth(), _client(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and, test_daily_report_schedule_is_owner_co_owner_only(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_preferences_crud(), test_push_subscription_register_and_unregister()

### Community 330 - "Community 330"
Cohesion: 0.50
Nodes (8): _outbox_event_types(), _owner(), Integration coverage: the real domain-event call sites (reservation lifecycle, c, test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), test_no_show_enqueues_notification(), test_reservation_lifecycle_enqueues_notifications()

### Community 331 - "Community 331"
Cohesion: 0.33
Nodes (8): client(), _complete_minimal_onboarding(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database., _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps(), test_rooms_require_existing_category()

### Community 332 - "Community 332"
Cohesion: 0.31
Nodes (4): _reservation(), test_payment_links_api_create_list_and_cancel(), test_payment_links_api_cross_hotel_isolation(), test_payment_links_api_rejects_manager_without_cash_operate()

### Community 333 - "Community 333"
Cohesion: 0.28
Nodes (4): _plan(), A deploy that has not run the migration yet must not 500 the page., A deploy that has not run the migration yet must not 500 the page., TestPublicPricing

### Community 334 - "Community 334"
Cohesion: 0.56
Nodes (8): _client(), _close(), test_checkin_checkout_and_force_checkout_use_distinct_action_permissions(), test_laundry_read_and_movement_follow_revocation_and_grant_without_partial_mutation(), test_rate_read_and_update_follow_revocation_and_grant_without_partial_mutation(), test_reservation_read_and_cancel_follow_individual_overrides_without_data_leak(), test_room_read_and_status_update_follow_revocation_and_grant_without_leak_or_mutation(), test_stock_read_movement_and_admin_are_independently_enforced_without_mutation()

### Community 335 - "Community 335"
Cohesion: 0.36
Nodes (6): _add_event(), test_missing_or_zero_cursor_requires_full_refetch(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch(), test_stale_cursor_requires_full_refetch()

### Community 336 - "Community 336"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 337 - "Community 337"
Cohesion: 0.44
Nodes (6): _override_auth(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_cannot_create_room_block_by_default(), test_receptionist_can_create_but_not_release_room_block_by_default(), test_room_block_api_is_hotel_scoped()

### Community 338 - "Community 338"
Cohesion: 0.33
Nodes (7): _override_auth(), Reception needs to read room data to build reservations (room picker, availabili, GET /api/rooms/categories feeds the category picker on both the     Reservations, test_custom_housekeeping_role_receives_safe_room_projection(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms()

### Community 339 - "Community 339"
Cohesion: 0.39
Nodes (8): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), Tests for v72 check-out balance reconciliation., Checkout balance scenarios collect cash through an open caja., test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid(), test_checkout_succeeds_with_force_even_when_balance_remains()

### Community 340 - "Community 340"
Cohesion: 0.22
Nodes (5): Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss., TestDailyRateModelConstraints

### Community 341 - "Community 341"
Cohesion: 0.42
Nodes (8): opened_cash_register(), _payment(), Immediate cash settlement scenarios require an operator-opened caja., _reservation(), test_no_future_conflict_extends_normally(), test_paid_future_conflict_reports_conflict_and_extension_does_not_proceed(), test_unpaid_future_conflict_moves_to_equivalent_room_and_extension_proceeds(), test_unpaid_future_conflict_upgrades_to_superior_when_no_equivalent_available()

### Community 342 - "Community 342"
Cohesion: 0.31
Nodes (5): _make_reservation(), Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted)., Helper — create a reservation through the service layer., TestWaitlistListing

### Community 343 - "Community 343"
Cohesion: 0.42
Nodes (8): _columns(), _create_index_if_missing(), downgrade(), _drop_index_if_present(), _indexes(), Operational audit fields, daily cash indexes, and audit read permission., _seed_audit_permission(), upgrade()

### Community 344 - "Community 344"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 345 - "Community 345"
Cohesion: 0.25
Nodes (5): main(), ProviderClients, Small GET-only API client with bounded retries and redacted failures., ReadOnlyJsonApi, VerificationConfig

### Community 346 - "Community 346"
Cohesion: 0.32
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 347 - "Community 347"
Cohesion: 0.46
Nodes (7): _attach_actor_names(), audit_timeline(), _build_audit_timeline_csv(), _current_user(), export_audit_timeline(), security_overview(), _validate_audit_timeline_range()

### Community 348 - "Community 348"
Cohesion: 0.25
Nodes (5): AppleAuthorization, AppleSignInResult, CLIENT_ID, REDIRECT_URI, Window

### Community 349 - "Community 349"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 350 - "Community 350"
Cohesion: 0.36
Nodes (6): MARKETING_ROUTES, marketingHtmlPlugin(), renderRouteHtml(), replaceTag(), indexHtml, vercel

### Community 351 - "Community 351"
Cohesion: 0.25
Nodes (5): AnalyticsAIChatRead, AnalyticsAIChatRequest, AnalyticsInsightRead, AnalyticsInsightRequest, AnalyticsInsightStatusRead

### Community 352 - "Community 352"
Cohesion: 0.29
Nodes (4): HotelConfigRead, HotelConfigUpdate, _normalize_currency(), Pydantic schemas for HotelConfiguration.

### Community 353 - "Community 353"
Cohesion: 0.46
Nodes (5): CompanyDocumentError, create_document(), _get_company(), _get_reservation(), set_signature_status()

### Community 354 - "Community 354"
Cohesion: 0.39
Nodes (7): apply_configuration_update(), Shared writes for hotel configuration concepts., Apply a validated Settings payload to one hotel configuration row., set_deposit_policy(), set_identity(), set_ota_channels(), set_payment_methods()

### Community 355 - "Community 355"
Cohesion: 0.25
Nodes (2): Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar, S3ObjectStorage

### Community 356 - "Community 356"
Cohesion: 0.46
Nodes (7): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations()

### Community 357 - "Community 357"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 358 - "Community 358"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 359 - "Community 359"
Cohesion: 0.25
Nodes (5): Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies., TestHotelConfigModel

### Community 360 - "Community 360"
Cohesion: 0.25
Nodes (5): Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship., TestTransactionModel

### Community 361 - "Community 361"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 362 - "Community 362"
Cohesion: 0.54
Nodes (6): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 363 - "Community 363"
Cohesion: 0.46
Nodes (7): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge(), test_reservation_lifecycle_optimistic_lock_conflict()

### Community 364 - "Community 364"
Cohesion: 0.43
Nodes (7): v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 365 - "Community 365"
Cohesion: 0.50
Nodes (6): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_lists_only_active_blocking_reservations_and_allows_delete_after_move(), test_room_delete_soft_deletes_hides_and_audits()

### Community 366 - "Community 366"
Cohesion: 0.25
Nodes (3): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 367 - "Community 367"
Cohesion: 0.25
Nodes (6): opened_cash_register(), _pay_full(), V72 §7.1 — Check-in Payment Gate Tests.  Requirement: "No se puede hacer check-i, Payment-gate scenarios start with an explicitly opened caja., Cannot checkout a FULLY_PAID reservation that was never checked in., Pay the full amount → FULLY_PAID.

### Community 368 - "Community 368"
Cohesion: 0.25
Nodes (5): is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati, A normal reservation blocks the room; a waitlisted one does not., TestWaitlistIsolation

### Community 369 - "Community 369"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 370 - "Community 370"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 371 - "Community 371"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 372 - "Community 372"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 373 - "Community 373"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 374 - "Community 374"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 375 - "Community 375"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state., _remove_rls(), upgrade()

### Community 376 - "Community 376"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add durable realtime domain event outbox  Revision ID: 20260901_domain_event_out, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 377 - "Community 377"
Cohesion: 0.36
Nodes (7): _assert_downgrade_lossless(), downgrade(), _install_rls(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins., _remove_rls(), upgrade()

### Community 378 - "Community 378"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 379 - "Community 379"
Cohesion: 0.46
Nodes (7): _alter_user_column(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2, _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade(), _user_fk()

### Community 380 - "Community 380"
Cohesion: 0.46
Nodes (7): downgrade(), _hotel_fk(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs., _replace_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade()

### Community 381 - "Community 381"
Cohesion: 0.39
Nodes (7): downgrade(), _ensure_subscription_composite_target(), _has_unique(), _install_rls(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b, _remove_rls(), upgrade()

### Community 382 - "Community 382"
Cohesion: 0.29
Nodes (3): LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default., Telemetry

### Community 383 - "Community 383"
Cohesion: 0.33
Nodes (2): mercadopago_payment_link_webhook(), _mercadopago_webhook_impl()

### Community 384 - "Community 384"
Cohesion: 0.48
Nodes (7): approve_temporary_action_grant(), create_temporary_action_grant(), deny_temporary_action_grant(), _raise_temporary_grant_http_error(), read_pending_temporary_action_grants(), _temporary_grant_actor(), _temporary_grant_response()

### Community 385 - "Community 385"
Cohesion: 0.33
Nodes (3): JobDispatcher, _FakeDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 386 - "Community 386"
Cohesion: 0.57
Nodes (6): command(), fenced(), frontend_routes(), heading(), main(), write()

### Community 387 - "Community 387"
Cohesion: 0.52
Nodes (5): main(), RealtimeMetrics, _run(), run_load(), validate_target()

### Community 388 - "Community 388"
Cohesion: 0.29
Nodes (6): Schemas for hotel-scoped waitlist entries., WaitlistEntryCreate, WaitlistEntryRead, WaitlistEntryUpdate, WaitlistPromoteRequest, WaitlistPromoteResponse

### Community 389 - "Community 389"
Cohesion: 0.33
Nodes (4): chat_completions(), ChatCompletionRequest, ChatMessage, _extract_latest_user_message()

### Community 390 - "Community 390"
Cohesion: 0.29
Nodes (2): ObjectStorage, Content-addressed-ish blob store: put/get/delete bytes by string key.

### Community 391 - "Community 391"
Cohesion: 0.43
Nodes (6): _active_reservation_conflicts_for_room(), create_grouped_room_move(), get_group(), list_groups(), revert_group(), sync_room_statuses_after_move()

### Community 392 - "Community 392"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 393 - "Community 393"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 394 - "Community 394"
Cohesion: 0.38
Nodes (3): _safe_worker_env(), test_celery_process_accepts_explicit_closed_production_profile(), test_celery_process_rejects_missing_production_policy_before_startup()

### Community 395 - "Community 395"
Cohesion: 0.71
Nodes (6): _client_with_db(), _override_auth(), _seed_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default()

### Community 396 - "Community 396"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 397 - "Community 397"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 399 - "Community 399"
Cohesion: 0.52
Nodes (5): _seed_hotel(), _seed_reservation(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner()

### Community 400 - "Community 400"
Cohesion: 0.52
Nodes (6): _auth_for(), A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) -- skip/, _seed_guests(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 401 - "Community 401"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_legacy_tags(), test_guest_restriction_migration_owns_reversible_postgresql_rls(), test_guest_restriction_upgrade_downgrade_upgrade_backfills_without_touching_tags()

### Community 402 - "Community 402"
Cohesion: 0.43
Nodes (6): _assert_migrated_state(), Regression/data-migration guard for 20260727_linen_split.  The owner explicitly, Hand-insert a real 'linen' StockItem plus movements and a laundry     vendor/pri, _run_alembic(), _seed_pre_split_data(), test_linen_split_migrates_real_data_and_survives_upgrade_downgrade_upgrade()

### Community 403 - "Community 403"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 404 - "Community 404"
Cohesion: 0.71
Nodes (6): _build_client(), _cleanup(), _override_auth(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 405 - "Community 405"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_pre_migration_surcharge(), test_promotions_migration_owns_reversible_postgresql_rls(), test_promotions_upgrade_downgrade_upgrade_preserves_surcharge_data()

### Community 406 - "Community 406"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_pre_revision(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions()

### Community 407 - "Community 407"
Cohesion: 0.48
Nodes (6): Tests for the reservation global search filter (B1 header search).  Search is a, _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 408 - "Community 408"
Cohesion: 0.29
Nodes (3): Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro, test_duplicate_room_number_returns_409()

### Community 409 - "Community 409"
Cohesion: 0.52
Nodes (6): _invitation(), Tenant-scoped staff aliases and user-management authorization., test_alias_edit_and_invite_alias_are_normalized_unique_and_hotel_scoped(), test_alias_roster_is_minimal_hotel_scoped_and_includes_active_and_invited_members(), test_user_management_mutations_require_effective_manage_permission(), _user()

### Community 410 - "Community 410"
Cohesion: 0.29
Nodes (4): PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on, TestPricePeriodModel

### Community 411 - "Community 411"
Cohesion: 0.29
Nodes (4): The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room., Verify is_wait_listed survives a round-trip through the database., TestWaitlistModelFields

### Community 412 - "Community 412"
Cohesion: 0.48
Nodes (5): _analytics_enum(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260, _reservation_status_enum_new(), _reservation_status_enum_old(), upgrade()

### Community 413 - "Community 413"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 414 - "Community 414"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 415 - "Community 415"
Cohesion: 0.52
Nodes (6): _backfill_authoritative_values(), _columns(), _decode(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea, upgrade()

### Community 416 - "Community 416"
Cohesion: 0.57
Nodes (6): downgrade(), _drop_index_if_present(), _ensure_index(), _index_map(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar, upgrade()

### Community 417 - "Community 417"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op, _remove_rls(), upgrade()

### Community 418 - "Community 418"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat, _remove_rls(), upgrade()

### Community 419 - "Community 419"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what, _remove_rls(), upgrade()

### Community 420 - "Community 420"
Cohesion: 0.48
Nodes (6): downgrade(), _enum_labels(), _quote_identifier(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:, _rename_enum_labels(), upgrade()

### Community 421 - "Community 421"
Cohesion: 0.43
Nodes (6): downgrade(), _event_id_type(), _install_rls(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i, _remove_rls(), upgrade()

### Community 422 - "Community 422"
Cohesion: 0.80
Nodes (5): build_sql(), _literal(), load_env(), main(), SharedSandboxBootstrapError

### Community 423 - "Community 423"
Cohesion: 0.47
Nodes (5): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 424 - "Community 424"
Cohesion: 0.53
Nodes (5): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online()

### Community 425 - "Community 425"
Cohesion: 0.47
Nodes (6): AnalyticsAIChatPage(), analyticsErrorMessage(), ReportScreen(), StarterLandingScreen(), useAnalyticsQuery(), usePersistedAnalyticsFilters()

### Community 426 - "Community 426"
Cohesion: 0.33
Nodes (1): credentials

### Community 427 - "Community 427"
Cohesion: 0.33
Nodes (5): LaundryRemito, LaundryRemitoLine, LaundryVendor, LaundryVendorPrice, Laundry vendor, pricing and remito (delivery note) models.  An outsourced laundr

### Community 428 - "Community 428"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 429 - "Community 429"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 430 - "Community 430"
Cohesion: 0.53
Nodes (5): _create_receptionist_user(), _open_cash_session(), POST /api/payments and GET /api/payments/summary/{id} only allowed     owner/co_, _receptionist_context(), test_receptionist_can_view_and_make_reservation_payments()

### Community 432 - "Community 432"
Cohesion: 0.60
Nodes (5): _link(), Cancelling a reservation must cancel its still-payable seña links (BR §M)., _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 434 - "Community 434"
Cohesion: 0.47
Nodes (4): _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_deferred_company_reservation_sets_settlement(), test_register_settlement_marks_settled()

### Community 435 - "Community 435"
Cohesion: 0.40
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 436 - "Community 436"
Cohesion: 0.40
Nodes (4): C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, _reset_and_migrate_to_head(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it()

### Community 437 - "Community 437"
Cohesion: 0.33
Nodes (4): Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room., TestOTARaceCondition

### Community 438 - "Community 438"
Cohesion: 0.60
Nodes (5): _seed_pricing_foundation(), test_quote_rate_plan_converts_currency_with_fx_policy_spread(), test_quote_rate_plan_enforces_stay_constraints_and_charged_night_validity(), test_quote_rate_plan_for_foreign_guest_respects_tax_exemption(), test_quote_rate_plan_for_local_booking_applies_taxes_fee_and_commission()

### Community 439 - "Community 439"
Cohesion: 0.60
Nodes (5): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_invalid_recipient_is_rejected_before_provider(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_unknown_provider_result_is_not_retried_implicitly()

### Community 440 - "Community 440"
Cohesion: 0.47
Nodes (3): _quote(), test_confirmed_reservation_stores_pricing_revision(), test_reservation_rejects_quote_after_pricing_revision_changes()

### Community 441 - "Community 441"
Cohesion: 0.73
Nodes (5): _client_with_db(), _override_auth(), _seed_group(), test_revert_movement_group_marks_reservations_protected(), test_room_movement_group_cross_hotel_isolation()

### Community 442 - "Community 442"
Cohesion: 0.40
Nodes (5): _create_rooms_with_soft_deleted_tail(), Regression coverage for room soft-delete visibility across count surfaces., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, test_soft_deleted_rooms_are_excluded_from_every_room_count_surface()

### Community 443 - "Community 443"
Cohesion: 0.53
Nodes (5): _migrate(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi, test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), _unique_column_sets()

### Community 444 - "Community 444"
Cohesion: 0.33
Nodes (4): PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., TestPaymentGatePending

### Community 445 - "Community 445"
Cohesion: 0.33
Nodes (2): V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai, TestResolveRateCalendar

### Community 446 - "Community 446"
Cohesion: 0.33
Nodes (4): When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., TestOverbookingBlocked

### Community 447 - "Community 447"
Cohesion: 0.33
Nodes (4): When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., TestWaitlistCreation

### Community 448 - "Community 448"
Cohesion: 0.60
Nodes (5): _request(), test_accepts_body_at_exact_limit(), test_rejects_chunked_body_that_exceeds_limit(), test_rejects_malformed_content_length(), test_rejects_oversized_content_length_before_reading_body()

### Community 449 - "Community 449"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 450 - "Community 450"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), downgrade(), _drop_successor_reference(), Add zero-balance cash rotation and custody handoffs., upgrade()

### Community 451 - "Community 451"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 452 - "Community 452"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 453 - "Community 453"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), seed section visibility permissions and their role defaults  Revision ID: 202608, upgrade()

### Community 454 - "Community 454"
Cohesion: 0.60
Nodes (5): downgrade(), _has_column(), _has_table(), Fold legacy category pricing into seasonal price periods., upgrade()

### Community 455 - "Community 455"
Cohesion: 0.60
Nodes (5): downgrade(), Align section defaults and remove the self-session catalog permission.  Revision, _restore_session_permission(), _set_role_default(), upgrade()

### Community 456 - "Community 456"
Cohesion: 0.47
Nodes (5): downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns., _set_role_default(), upgrade()

### Community 457 - "Community 457"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083, upgrade()

### Community 458 - "Community 458"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 459 - "Community 459"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 460 - "Community 460"
Cohesion: 0.40
Nodes (1): credentials

### Community 461 - "Community 461"
Cohesion: 0.60
Nodes (4): _migration_dsn(), Disposable live PostgreSQL proof for the forward Alembic release path.  The rele, _run_alembic(), test_fresh_postgres_migrations_upgrade_is_idempotent_and_current_head_round_trips()

### Community 462 - "Community 462"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 463 - "Community 463"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceRead, GuestRoomAvoidanceResolveRequest, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 464 - "Community 464"
Cohesion: 0.50
Nodes (3): _prepare_environment(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2, seed()

### Community 465 - "Community 465"
Cohesion: 0.60
Nodes (4): AllocationFeedbackDraft, AllocationQuestionnaireDraft, draft_policy_from_feedback(), draft_policy_from_questionnaire()

### Community 466 - "Community 466"
Cohesion: 0.50
Nodes (4): annotate_analytics_payload(), _as_utc_datetime(), Freshness metadata for analytics responses and derived read models., Add honest source freshness without changing the analytics data.      PostgreSQL

### Community 467 - "Community 467"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 468 - "Community 468"
Cohesion: 0.50
Nodes (3): _override_auth(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t, test_receptionist_can_get_price_quote()

### Community 469 - "Community 469"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 470 - "Community 470"
Cohesion: 0.40
Nodes (5): A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, test_master_stripe_webhook_retry_of_same_event_is_idempotent_not_500()

### Community 471 - "Community 471"
Cohesion: 0.40
Nodes (5): Wiring proof: every authenticated master-admin call must set the RLS     bypass, Wiring proof: every authenticated master-admin call must set the RLS     bypass, Wiring proof: every authenticated master-admin call must set the RLS     bypass, Wiring proof: every authenticated master-admin call must set the RLS     bypass, test_require_master_admin_sets_master_admin_rls_context()

### Community 472 - "Community 472"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 474 - "Community 474"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 475 - "Community 475"
Cohesion: 0.60
Nodes (4): Tests for operator-created reservation consumption charges., _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations()

### Community 477 - "Community 477"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 478 - "Community 478"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 479 - "Community 479"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 480 - "Community 480"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima, upgrade()

### Community 481 - "Community 481"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs, upgrade()

### Community 482 - "Community 482"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 483 - "Community 483"
Cohesion: 0.50
Nodes (3): Add durable job dedupe and worker heartbeat metadata., _rls(), upgrade()

### Community 484 - "Community 484"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 485 - "Community 485"
Cohesion: 0.83
Nodes (3): main(), run(), validate_json()

### Community 486 - "Community 486"
Cohesion: 0.83
Nodes (3): main(), _non_empty(), validate_manifest()

### Community 487 - "Community 487"
Cohesion: 0.67
Nodes (4): defaultAnalyticsFilters(), localDateIso(), parseAnalyticsFilters(), startOfCurrentLocalMonthIso()

### Community 488 - "Community 488"
Cohesion: 0.50
Nodes (4): Keep useful internal references while never exposing free-form details., Keep useful internal references while never exposing free-form details., recent_security_events(), _safe_resource_id()

### Community 489 - "Community 489"
Cohesion: 0.50
Nodes (3): StatCard(), StatCardProps, toneClasses

### Community 490 - "Community 490"
Cohesion: 0.50
Nodes (2): frontendRoot, publicRoot

### Community 491 - "Community 491"
Cohesion: 0.67
Nodes (3): build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 492 - "Community 492"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 494 - "Community 494"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 496 - "Community 496"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 497 - "Community 497"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 498 - "Community 498"
Cohesion: 0.50
Nodes (4): If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login     email (a, If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login     email (a, If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login     email (a, test_master_bootstrap_login_does_not_hijack_existing_non_admin_account()

### Community 499 - "Community 499"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t, test_process_outbox_delivers_across_every_active_hotel()

### Community 501 - "Community 501"
Cohesion: 0.67
Nodes (3): _index_names(), Focused regression tests for the TECH-0063 OLTP audit fixes., test_hot_path_composite_indexes_exist_in_models()

### Community 503 - "Community 503"
Cohesion: 0.50
Nodes (3): Tests for V72 §9 — Waitlist and Overbooking.  Key implementation details discove, Hotel with one Standard room.  Returns a dict with keys:       config, category_, tiny_hotel()

### Community 504 - "Community 504"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 505 - "Community 505"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 506 - "Community 506"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 507 - "Community 507"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 508 - "Community 508"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 509 - "Community 509"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 510 - "Community 510"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 511 - "Community 511"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 512 - "Community 512"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 513 - "Community 513"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 514 - "Community 514"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 515 - "Community 515"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 516 - "Community 516"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 517 - "Community 517"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 518 - "Community 518"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 519 - "Community 519"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 520 - "Community 520"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 521 - "Community 521"
Cohesion: 0.50
Nodes (1): v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event

### Community 522 - "Community 522"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 523 - "Community 523"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 524 - "Community 524"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 525 - "Community 525"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 526 - "Community 526"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 527 - "Community 527"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 528 - "Community 528"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 529 - "Community 529"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 530 - "Community 530"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 531 - "Community 531"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 532 - "Community 532"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 533 - "Community 533"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 534 - "Community 534"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 535 - "Community 535"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 536 - "Community 536"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 537 - "Community 537"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 538 - "Community 538"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 539 - "Community 539"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 540 - "Community 540"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 541 - "Community 541"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 542 - "Community 542"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 543 - "Community 543"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 544 - "Community 544"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 545 - "Community 545"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 546 - "Community 546"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 547 - "Community 547"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 548 - "Community 548"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 549 - "Community 549"
Cohesion: 0.50
Nodes (1): Persist short-lived MFA step-up ticket use to prevent cross-worker replay.

### Community 550 - "Community 550"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 551 - "Community 551"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 552 - "Community 552"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 553 - "Community 553"
Cohesion: 0.50
Nodes (1): laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre

### Community 554 - "Community 554"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 555 - "Community 555"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 556 - "Community 556"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 557 - "Community 557"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 558 - "Community 558"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 559 - "Community 559"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 560 - "Community 560"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 561 - "Community 561"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 562 - "Community 562"
Cohesion: 0.50
Nodes (1): Add tenant-scoped object metadata without deleting legacy file references.

### Community 563 - "Community 563"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 564 - "Community 564"
Cohesion: 1.00
Nodes (2): main(), validate()

### Community 565 - "Community 565"
Cohesion: 0.67
Nodes (3): Invalidate every access token previously issued to the caller., Invalidate every access token previously issued to the caller., revoke_current_user_sessions()

### Community 566 - "Community 566"
Cohesion: 0.67
Nodes (3): 393ea8c Refresh generated knowledge inventories, 7433859 Align generated inventories with graph refresh, c50af40 Refresh Graphify knowledge graph

### Community 567 - "Community 567"
Cohesion: 0.67
Nodes (1): credentials

### Community 568 - "Community 568"
Cohesion: 0.67
Nodes (1): owner

### Community 570 - "Community 570"
Cohesion: 0.67
Nodes (1): credentials

### Community 571 - "Community 571"
Cohesion: 0.67
Nodes (1): Persisted staff invitations and their one-time acceptance state.

### Community 572 - "Community 572"
Cohesion: 0.67
Nodes (1): Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati

### Community 573 - "Community 573"
Cohesion: 0.67
Nodes (1): One-shot notification cycle: generate due daily reports, then deliver pending ou

### Community 574 - "Community 574"
Cohesion: 1.00
Nodes (2): build_gemma_hotel_context(), _enum_value()

### Community 581 - "Community 581"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 582 - "Community 582"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 583 - "Community 583"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 586 - "Community 586"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 587 - "Community 587"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 588 - "Community 588"
Cohesion: 1.00
Nodes (1): Security / access audit log — free-form operational security events.  Distinct f

### Community 589 - "Community 589"
Cohesion: 1.00
Nodes (2): Metadata returned by the server-side Embedded Signup exchange., WhatsAppChannelComplete

## Knowledge Gaps
- **1330 isolated node(s):** `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.`, `guest checkin profile fields  Revision ID: 17f1689785f3 Revises: 20260725_res_ho` (+1325 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 81`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 153`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 186`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 187`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 281`** (1 nodes): `OTAOrchestratorService`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 298`** (1 nodes): `TestLeadCapture`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 320`** (2 nodes): `LocalObjectStorage`, `Stores objects as files under a local directory root.      Generalizes the patte`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 336`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 355`** (2 nodes): `Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar`, `S3ObjectStorage`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 383`** (2 nodes): `mercadopago_payment_link_webhook()`, `_mercadopago_webhook_impl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 390`** (2 nodes): `ObjectStorage`, `Content-addressed-ish blob store: put/get/delete bytes by string key.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 426`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 435`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 445`** (2 nodes): `V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai`, `TestResolveRateCalendar`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 460`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 490`** (2 nodes): `frontendRoot`, `publicRoot`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 496`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 505`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 506`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 507`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 508`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 509`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 510`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 511`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 512`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 513`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 514`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 515`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 516`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 517`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 518`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 519`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 520`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 521`** (1 nodes): `v72 gaps phase 6: payment tables (payments, payment_links, payment_webhook_event`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 522`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 523`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 524`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 525`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 526`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 527`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 528`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 529`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 530`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 531`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 532`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 533`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 534`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 535`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 536`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 537`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 538`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 539`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 540`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 541`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 542`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 543`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 544`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 545`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 546`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 547`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 548`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 549`** (1 nodes): `Persist short-lived MFA step-up ticket use to prevent cross-worker replay.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 550`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 551`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 552`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 553`** (1 nodes): `laundry vendors and remitos  Revision ID: 795e124adaad Revises: 62fddec52b79 Cre`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 554`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 555`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 556`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 557`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 558`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 559`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 560`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 561`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 562`** (1 nodes): `Add tenant-scoped object metadata without deleting legacy file references.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 563`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 564`** (2 nodes): `main()`, `validate()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 567`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 568`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 570`** (1 nodes): `credentials`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 571`** (1 nodes): `Persisted staff invitations and their one-time acceptance state.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 572`** (1 nodes): `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 573`** (1 nodes): `One-shot notification cycle: generate due daily reports, then deliver pending ou`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 574`** (2 nodes): `build_gemma_hotel_context()`, `_enum_value()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 581`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 582`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 583`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 586`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 587`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 588`** (1 nodes): `Security / access audit log — free-form operational security events.  Distinct f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 589`** (2 nodes): `Metadata returned by the server-side Embedded Signup exchange.`, `WhatsAppChannelComplete`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 2` to `Community 10`, `Community 424`, `Community 12`, `Community 71`, `Community 61`, `Community 39`, `Community 77`, `Community 174`, `Community 3`, `Community 17`, `Community 9`, `Community 0`, `Community 11`, `Community 232`, `Community 200`, `Community 47`, `Community 56`, `Community 215`, `Community 280`, `Community 76`, `Community 14`, `Community 90`, `Community 40`, `Community 4`, `Community 42`, `Community 33`, `Community 571`, `Community 162`, `Community 427`, `Community 37`, `Community 34`, `Community 153`, `Community 27`, `Community 30`, `Community 16`, `Community 97`, `Community 8`, `Community 64`, `Community 44`, `Community 121`, `Community 588`, `Community 5`, `Community 253`, `Community 21`, `Community 122`, `Community 1`, `Community 87`, `Community 319`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 11` to `Community 56`, `Community 2`, `Community 9`, `Community 26`, `Community 3`, `Community 190`, `Community 30`, `Community 90`, `Community 61`, `Community 17`, `Community 8`, `Community 14`, `Community 354`, `Community 121`, `Community 16`, `Community 37`, `Community 133`, `Community 284`, `Community 34`, `Community 125`, `Community 97`, `Community 45`, `Community 21`, `Community 204`, `Community 12`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 3` to `Community 17`, `Community 2`, `Community 26`, `Community 30`, `Community 8`, `Community 27`, `Community 14`, `Community 353`, `Community 232`, `Community 76`, `Community 125`, `Community 11`, `Community 16`, `Community 121`, `Community 45`, `Community 40`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 378 inferred relationships involving `Base` (e.g. with `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` and `Demo-only utilities: seed sample data and reset the database. Exposed only when`) actually correct?**
  _`Base` has 378 INFERRED edges - model-reasoned connections that need verification._
- **Are the 280 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Lightweight availability placeholder. When all parameters are provided,     it r`) actually correct?**
  _`Reservation` has 280 INFERRED edges - model-reasoned connections that need verification._
- **Are the 267 inferred relationships involving `HotelConfiguration` (e.g. with `AcceptPayload` and `GoogleInvitationAcceptPayload`) actually correct?**
  _`HotelConfiguration` has 267 INFERRED edges - model-reasoned connections that need verification._
- **Are the 223 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Lightweight availability placeholder. When all parameters are provided,     it r`) actually correct?**
  _`ReservationStatusEnum` has 223 INFERRED edges - model-reasoned connections that need verification._