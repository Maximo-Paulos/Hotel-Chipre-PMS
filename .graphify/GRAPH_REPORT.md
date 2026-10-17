# Graph Report - .  (2026-10-17)

## Corpus Check
- Large corpus: 1780 files · ~2,446,178 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 15575 nodes · 47291 edges · 652 communities detected
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 13929 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 13929 · contains: 9778 · calls: 7428 · MODIFIES: 5779 · rationale_for: 3089 · ON_BRANCH: 1791 · imports: 1721 · imports_from: 1360 · inherits: 955 · method: 921 · PARENT_OF: 532 · re_exports: 4 · reads_from: 4


## Input Scope
- Requested: auto
- Resolved: committed (source: default-auto)
- Included files: 1780 · Candidates: 1964
- Excluded: 21 untracked · 33472 ignored · 15 sensitive · 0 missing committed
- Recommendation: Use --scope all or graphify.yaml inputs.corpus for a knowledge-base folder.

## Graph Freshness
- Built from Git commit: `e088114`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `HotelConfiguration` - 608 edges
2. `Reservation` - 602 edges
3. `ReservationStatusEnum` - 484 edges
4. `Base` - 438 edges
5. `Room` - 431 edges
6. `RoomCategory` - 358 edges
7. `HotelMembership` - 345 edges
8. `SecurityAuditLog` - 343 edges
9. `AuditActionEnum` - 295 edges
10. `Company` - 266 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Rate limiter with DB-backed persistence for security-sensitive endpoints.  When` --uses--> `RateLimitEvent`  [INFERRED]
  app/adapters/rate_limiter.py → app/models/rate_limit_event.py
- `FastAPI routes for the commercial configuration domain.` --uses--> `CommercialConfigError`  [INFERRED]
  app/api/commercial.py → app/services/commercial_service.py
- `Manage and inspect per-night extras on corporate reservations.` --uses--> `CompanyNightChargeError`  [INFERRED]
  app/api/company_night_charges.py → app/services/company_night_charge_service.py
- `API routes for reservation waitlist operations.` --uses--> `WaitlistError`  [INFERRED]
  app/api/waitlist.py → app/services/waitlist_service.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.01
Nodes (126): authorize_manual_rate_scope(), Payload-conditional authorization for manual reservation rates., Return the strongest manual-rate capability the actor currently has., 074902a Stabilize cash receipt E2E response reads, 194af4d fix(reservations): search guests by name/DNI instead of raw ID field, 7899f9d Stabilize day 2 regression suite and mobile navigation, b329199 Implement hotel simulation day 0 and day 1 fixes, bf4a21f Fix day 0 and day 1 hotel simulation findings (+118 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (265): create_payment_surcharge(), deactivate_payment_surcharge(), _get_surcharge_or_404(), _has_per_method_nightly_price(), PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges (+257 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (86): main(), validate(), updateRoomCleaningStatus(), 9e4b357 Reduce PMS request load and complete simulation remediation, ef0aa41 Merge PR #125: week-two remediation [skip render], backendURL, Persona, personas (+78 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (225): Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., Authenticated field-level collaboration endpoints.  Drafts are ephemeral and saf, Keep collaboration permissions aligned with the normal resource API., Issue a short-lived, one-use ticket for one tenant resource., Persist an optimistic, field-level merge under the current tenant., Process-local peers plus best-effort Redis pub/sub fan-out., Authenticate with a one-use ticket, then exchange safe draft signals. (+217 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (217): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+209 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (120): Read and resolve the guest room-rejection lifecycle., Read-only integral operations audit endpoint., _backfill_not_null_nulls(), _collect_realtime_events_after_flush(), _column_fill_value(), _discard_realtime_events_after_rollback(), _discard_realtime_events_after_root_soft_rollback(), _estimate_parameter_bytes() (+112 more)

### Community 6 - "Community 6"
Cohesion: 0.01
Nodes (143): list_countries(), list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog., Return the curated country -> primary IANA timezone catalog., ReferenceCountry, listCountries(), ReferenceCountry (+135 more)

### Community 7 - "Community 7"
Cohesion: 0.05
Nodes (199): codex/production-render-qa, codex/public-site-inquiries, docs/auditoria-pms-20260908, feature/operational-audit-cash-daily, feature/secure-auth-marketing-release-20260926, main, 00af83e chore(graphify): regenerate graph after B4 manual OTA + manual tarifa + B4.2, 052b93d Merge branch 'agent-stockedit' into codex/feature/pms-e2e-scale-hardening (+191 more)

### Community 8 - "Community 8"
Cohesion: 0.01
Nodes (96): Manage and inspect per-night extras on corporate reservations., 46969e1 Improve PMS efficiency and deposit policies [skip render], 532a352 Fix local simulation email and guest search workflows, 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation, 5d43450 Merge pull request #112 from Maximo-Paulos/fix/day0-day1-simulation-feedback, 6022c36 Fix local simulation workflow regressions, 6871292 Fix day 0 and day 1 simulation findings (#113), 712d6ee Fix simulation day 0 and day 1 findings (+88 more)

### Community 9 - "Community 9"
Cohesion: 0.04
Nodes (187): Auth endpoints: register, login, email verification and password reset. Verifica, Remove the Google login only after proving control of the password.      Google-, Remove the Google login only after proving control of the password.      Google-, Complete Sign in with Apple from Apple JS SDK or another OIDC client., Start Apple's form_post redirect flow with a signed state and nonce., Complete Sign in with Apple from Apple JS SDK or another OIDC client., Start Apple's form_post redirect flow with a signed state and nonce., Complete Apple's server-side form_post redirect flow. (+179 more)

### Community 10 - "Community 10"
Cohesion: 0.02
Nodes (152): FxConversionQuoteRequest, BaseModel, ActiveAllocationPolicyRead, AllocationExplanationRead, AllocationFeedbackDraftRequest, AllocationPolicySuggestionApplyRequest, AllocationPolicySuggestionApplyResponse, AllocationPolicySuggestionCreate (+144 more)

### Community 11 - "Community 11"
Cohesion: 0.03
Nodes (143): fix/local-simulation-workflows, refactor/pms-efficiency-remediation, 009a9ed docs(tech-0140): pin final local verification, 0174f49 Document post-deploy read-only smoke results, 049af9d Add local simulation clock and payment receipt workflows, 0503c7f docs: clarify supported login and privacy terms, 0a37da4 Default read model cache to disabled, 0aff8e4 Merge pull request #120 from Maximo-Paulos/fix/reject-unverified-gateway-payments (+135 more)

### Community 12 - "Community 12"
Cohesion: 0.02
Nodes (151): Guard demo mutations behind both an approved runtime and an explicit flag., Guard endpoints so they only run in explicit demo mode or tests., Guard demo mutations behind both an approved runtime and an explicit flag., Populate the database with minimal demo data.     Idempotent: running twice simp, Populate the database with minimal demo data.     Idempotent: running twice simp, Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Drop and recreate all tables.     Keeps the app in a known-good empty state for (+143 more)

### Community 13 - "Community 13"
Cohesion: 0.02
Nodes (85): AuthUser, _assert_assignable_role(), _assert_manageable_membership(), _assert_manageable_role(), EmailDeliveryStatus, invite_user(), InviteResponse, inviteUser() (+77 more)

### Community 14 - "Community 14"
Cohesion: 0.02
Nodes (92): DailyReportSchedule, DailyReportScheduleUpdate, get_daily_report_schedule(), getDailyReportSchedule(), listNotificationPreferences(), listNotifications(), markAllNotificationsRead(), markNotificationRead() (+84 more)

### Community 15 - "Community 15"
Cohesion: 0.11
Nodes (113): availability(), price_quote(), FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Lightweight availability placeholder. When all parameters are provided,     it r, Lightweight availability placeholder. When all parameters are provided,     it r, Ensure computed fields land in the response., Calculate pricing for a potential booking without persisting it.     Uses the ca, Calculate pricing for a potential booking without persisting it.     Uses the ca (+105 more)

### Community 16 - "Community 16"
Cohesion: 0.03
Nodes (100): add_reservation_guests(), addReservationGuests(), buildQueryString(), cancelReservation(), change_dates(), CheckInPayload, checkInReservation(), checkOutReservation() (+92 more)

### Community 17 - "Community 17"
Cohesion: 0.02
Nodes (78): _consume_xlsx_export_queue(), _DecimalAwareEncoder, _InvitationAccessLogFilter, _is_database_pool_timeout(), _is_demo_mode_enabled(), lifespan(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_ (+70 more)

### Community 18 - "Community 18"
Cohesion: 0.03
Nodes (93): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), Category (+85 more)

### Community 19 - "Community 19"
Cohesion: 0.03
Nodes (90): createGuestRestriction(), getGuestProhibitedDetail(), GuestProhibitedErrorBody, GuestRestriction, GuestRestrictionCreatePayload, GuestRestrictionResolvePayload, GuestRestrictionStatus, listActiveGuestRestrictionGuestIds() (+82 more)

### Community 20 - "Community 20"
Cohesion: 0.02
Nodes (33): 218ef8b chore(graphify): regenerate graph after A2 reservation pagination/order, 2781ab8 feat(db): index reservations(hotel_id, created_at) for A2 recent-order paging, 2eccdd8 feat(reservations): add occupancy-grid endpoint for B2 planilla, 3a2821c feat(reservations): wire skip/limit/order into the frontend reservation list, a5ee7be fix(migrations): make schema-drift-era tables idempotent against self-healed production, v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin, v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_, v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus (+25 more)

### Community 21 - "Community 21"
Cohesion: 0.13
Nodes (98): HotelRole, A stable custom role code whose policy is scoped to one hotel., HotelRoleVisibilityWindow, Reservation visibility limits configured independently per hotel role.      A mi, StaffInvitation, HotelPermissionOverride, Permission, Configurable permission matrix models. (+90 more)

### Community 22 - "Community 22"
Cohesion: 0.02
Nodes (49): 4a4c34e Harden authorization and reservation integrity, 5616166 Merge pull request #90 from Maximo-Paulos/feature/realtime-collaboration, 9aee997 Implement real-time synchronization and collaboration, CollaborationPatchRequest, CollaborationTicketRequest, CollaborationTicketResponse, Transport schemas for authenticated field-level collaboration., consume_invitation() (+41 more)

### Community 23 - "Community 23"
Cohesion: 0.03
Nodes (45): build_sql(), _literal(), load_env(), main(), SharedSandboxBootstrapError, _archive_historical(), _build_cases(), main() (+37 more)

### Community 24 - "Community 24"
Cohesion: 0.03
Nodes (75): advance_business_clock_by_one_day(), getHotelConfig(), getHotelInterfaceLanguage(), HotelConfig, HotelConfigUpdate, HotelInterfaceLanguage, read_business_clock(), updateHotelConfig() (+67 more)

### Community 25 - "Community 25"
Cohesion: 0.03
Nodes (56): 222ef84 Fix auth bootstrap and harden rate limits, 230041e Fix E2E MFA journeys and clarify retention schedule, 25d09dc fix(mobile): replace two competing mobile nav mechanisms with one menu button, 2bbe038 Merge remote-tracking branch 'origin/main' into codex/clarify-mfa-code, 4e1faae feat(auth): harden hotel-scoped authorization, 616a398 test: scope RBAC and rate E2E selectors, 98dce04 feat(nav): collapse 29-item menu to 5 daily links + collapsible groups (B6.1), b64223d Merge branch 'agent-mobilenav' into codex/feature/pms-e2e-scale-hardening (+48 more)

### Community 26 - "Community 26"
Cohesion: 0.03
Nodes (55): HOTEL_ID_INDEX_BY_QUERY_PREFIX, hotelIdForQueryKey(), QUERY_PREFIXES_BY_DOMAIN, QueryDomain, ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, V72 §8.5 — Per-day pricing models.  DailyRate: explicit price for a (hotel, cate, Per-role reservation visibility windows for one hotel., ALL_DOMAINS (+47 more)

### Community 27 - "Community 27"
Cohesion: 0.09
Nodes (71): Operational task inbox and shift handoff endpoints., Match direct task access to the user's effective shared-read/manage grants., Match direct task access to the user's effective shared-read/manage grants., OperationalTask, OperationalTaskAttachment, OperationalTaskEvent, OperationalTaskPriorityEnum, OperationalTaskStatusEnum (+63 more)

### Community 28 - "Community 28"
Cohesion: 0.04
Nodes (79): _allow_mfa_attempt(), apple_callback(), _apple_full_name(), apple_login(), _apple_login_config(), apple_start(), _attach_user_session_cookies(), _audit_security_event() (+71 more)

### Community 29 - "Community 29"
Cohesion: 0.02
Nodes (78): PermissionGate(), MasterAdminProtectedShell(), MasterAdminRoot(), navItems, MasterAdminSessionProvider(), AcceptInvitationPage, AnalyticsAIChatPage, AnalyticsCategoryDetailPage (+70 more)

### Community 30 - "Community 30"
Cohesion: 0.05
Nodes (51): 654d69e Add reservation arrival metadata and internal comments, 8c239da Merge pull request #100 from Maximo-Paulos/feature/reservation-arrival-comment, APIKeyPurposeEnum, PaymentLinkRead, PublicReservationRead, HotelAPIKeyIssue, HotelAPIKeyIssued, HotelAPIKeyRead (+43 more)

### Community 31 - "Community 31"
Cohesion: 0.03
Nodes (39): DepositPolicyRule, DepositPolicyRules, CategoryPayload, DepositPolicyPayload, finishOnboarding(), getOnboardingStatus(), HotelIdentityPayload, OnboardingProviderSetup (+31 more)

### Community 32 - "Community 32"
Cohesion: 0.05
Nodes (65): _complete_master_login(), _configure_resend(), FakeResponse, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login     email (a (+57 more)

### Community 33 - "Community 33"
Cohesion: 0.05
Nodes (41): booking_webhook(), despegar_webhook(), expedia_webhook(), _guarded_json_payload(), _handle_ota_webhook(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com., Receive reservation notifications from Booking.com. (+33 more)

### Community 34 - "Community 34"
Cohesion: 0.05
Nodes (47): acceptInvitation(), acceptInvitationWithGoogle(), AuthResponse, completeMfaInvitationAcceptance(), getInvitationInfo(), isMfaChallenge(), ApiError, AuthResponsePayload (+39 more)

### Community 35 - "Community 35"
Cohesion: 0.05
Nodes (58): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), cancelPaymentLinkTest() (+50 more)

### Community 36 - "Community 36"
Cohesion: 0.05
Nodes (65): addCashMovement(), approveCashCloseDifference(), approveCashExpense(), CashCloseReport, CashCustodyHandoff, CashCustodyReceiptPayload, CashDailyCollector, CashDailyEntry (+57 more)

### Community 37 - "Community 37"
Cohesion: 0.12
Nodes (52): create_laundry_remito(), _housekeeping_remito(), LinenItemCreate, LinenItemRead, LinenLocationBalanceRead, LinenLocationCreate, LinenLocationRead, LinenMovementCreate (+44 more)

### Community 38 - "Community 38"
Cohesion: 0.08
Nodes (72): consume_temporary_action_grant(), create_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Keep ownership-role cells immutable except the owner's explicit rate control., Keep permission exceptions aligned with the staff-management boundary., Keep permission exceptions aligned with the staff-management boundary., Apply a user-reviewed set of permission changes atomically with one MFA ticket., Ask for one exceptional permission without changing the requester's role. (+64 more)

### Community 39 - "Community 39"
Cohesion: 0.09
Nodes (69): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+61 more)

### Community 40 - "Community 40"
Cohesion: 0.07
Nodes (70): active_reservations(), _apply_corporate_pricing(), _apply_custom_deposit_amount(), _apply_manual_total_override(), _apply_pricing_result_to_reservation(), assert_reservation_version(), calculate_reservation_pricing(), _calendar_pricing_source() (+62 more)

### Community 41 - "Community 41"
Cohesion: 0.05
Nodes (48): _event_engine(), FakeRedis, _isolate_realtime_configuration(), A minimal SQLite engine with just the tables the after_commit hook writes to., Keep Redis-default event tests independent of other test modules., A minimal SQLite engine with just the tables the after_commit hook writes to., Share the in-memory SQLite connection with async iterator worker threads., _settings() (+40 more)

### Community 42 - "Community 42"
Cohesion: 0.07
Nodes (46): fetchPublicPricing(), LeadPayload, PublicPricing, PublicPricingPlan, submitLead(), differentiators, faqItems, founder (+38 more)

### Community 43 - "Community 43"
Cohesion: 0.14
Nodes (62): AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum, AnalyticsExportJobRead, AnalyticsExportRequest, get_export_bytes(), get_export_file(), _iter_csv_chunks() (+54 more)

### Community 44 - "Community 44"
Cohesion: 0.08
Nodes (62): ArchiveCustomRoleRequest, CreateCustomRoleRequest, Tenant-scoped custom role catalog and lifecycle endpoints., RenameCustomRoleRequest, RoleCatalogItem, RoleListResponse, LookupError, _active_membership() (+54 more)

### Community 45 - "Community 45"
Cohesion: 0.05
Nodes (50): assignWhatsAppConversation(), completeWhatsAppChannel(), createWhatsAppNote(), fetchWhatsAppChannel(), fetchWhatsAppConversations(), sendWhatsAppMessage(), WhatsAppChannelStatus, WhatsAppConversation (+42 more)

### Community 46 - "Community 46"
Cohesion: 0.12
Nodes (57): ReservationAllocationLock, GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum, RoomMovementGroup, ReservationStatusEnum, AllocationError, AllocationResult, apply_allocation_result() (+49 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (52): _clickhouse_healthcheck(), _critical_lock_readiness(), _database_healthcheck(), datastores_healthcheck(), live_healthcheck(), _postgres_healthcheck(), Report whether the API can safely accept critical writes., Process liveness only; never depends on PostgreSQL or Redis. (+44 more)

### Community 48 - "Community 48"
Cohesion: 0.05
Nodes (41): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsEnvelope, analyticsErrorMessage(), AnalyticsFilterState, AnalyticsFreshness(), AnalyticsHomePage() (+33 more)

### Community 49 - "Community 49"
Cohesion: 0.04
Nodes (31): create_movement(), createStockItem(), createStockLocation(), createStockMovement(), createStockOpeningCount(), createStockTransfer(), CurrentStock, deleteStockItem() (+23 more)

### Community 50 - "Community 50"
Cohesion: 0.08
Nodes (54): Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., Apply the separate approval capability only when closing requires it., _require_cash_difference_approval_when_requested(), CashExpense, CashExpenseStatusEnum, Hotel-scoped manual cash expenses awaiting explicit approval., A proposed drawer expense; approved expenses create one cash movement. (+46 more)

### Community 51 - "Community 51"
Cohesion: 0.05
Nodes (47): ActiveRoomBlockItem, ArrivalCount, AvailableWithReviewItem, booked_value_report(), BookedValueReport, CashSessionStatusRead, CurrencyAmount, DailyOperationalReport (+39 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (27): GCSObjectStorage, get_object_storage(), LocalObjectStorage, ObjectStat, ObjectStorage, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar, Google Cloud Storage adapter with lazy optional dependency loading. (+19 more)

### Community 53 - "Community 53"
Cohesion: 0.07
Nodes (50): getMfaStatus(), mfaStatusQueryKey(), ActionStepUpChallenge, ActionStepUpHandler, actionStepUpQueue, ActionStepUpTicket, apiFetch(), buildAuthHeaders() (+42 more)

### Community 54 - "Community 54"
Cohesion: 0.06
Nodes (45): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyDocumentUploadPayload, CompanyNightlyRate, CompanyNightlyRatePayload (+37 more)

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (58): _client(), _close(), _patch_legacy_booking(), test_bounded_unpaid_total_adjustment_fails_closed_without_manual_rate_policy(), test_bounded_unpaid_total_adjustment_fails_closed_without_trusted_quote(), test_bounded_unpaid_total_adjustment_rejects_amount_outside_configured_range(), test_bounded_unpaid_total_adjustment_requires_same_currency_as_current_quote(), test_category_product_compatibility_is_checked_after_permission() (+50 more)

### Community 56 - "Community 56"
Cohesion: 0.06
Nodes (51): _cors_contains_wildcard(), get_settings(), _gmail_is_active(), _has_value(), is_demo_environment_allowed(), is_demo_mode(), is_preview_qa_mode(), is_production_mode() (+43 more)

### Community 57 - "Community 57"
Cohesion: 0.05
Nodes (45): createLaundryRemito(), createLaundryVendor(), getLaundryVendorBalance(), getLaundryVendorSettlements(), getLaundryVendorSpend(), LaundryMissingFollowUp, LaundryMissingFollowUpStatus, LaundryMissingFollowUpUpdate (+37 more)

### Community 58 - "Community 58"
Cohesion: 0.05
Nodes (33): clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminLoginResult, MasterAdminMfaChallengeResponse, MasterAdminMfaEnrollment, MasterAdminMfaRecoveryCodes, MasterAdminMfaSetupResponse (+25 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (53): client_with_db(), _enable_test_google(), get_auth_context_target(), get_db_override_target(), _google_claims(), _invitation_token(), _manage_users_request(), owner_ctx() (+45 more)

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (42): CompanyNightCharge, CompanyNightChargeAmount, CompanyNightChargeAmountAdjustment, CompanyNightChargeCorrection, CompanyNightChargesSummary, correctCompanyNightChargeAmounts(), createCompanyNightCharges(), getCompanyNightCharges() (+34 more)

### Community 61 - "Community 61"
Cohesion: 0.09
Nodes (18): _add_cash_movement(), _auth_context(), _http_request(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session() (+10 more)

### Community 62 - "Community 62"
Cohesion: 0.10
Nodes (43): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, LLMFeedbackEvent (+35 more)

### Community 63 - "Community 63"
Cohesion: 0.11
Nodes (48): Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, SubscriptionAdjustment, SubscriptionEvent, _actor_payload(), _actor_role(), _actor_user_id(), _apply_plan() (+40 more)

### Community 64 - "Community 64"
Cohesion: 0.05
Nodes (41): insert_historical_hotel_config(), Helpers for seeding schemas before a migration under test., Insert the hotel-config shape that existed before the 2026-08 changes.      Migr, _alembic(), Migration coverage for the deduplication sweep., test_category_pricing_rows_are_folded_into_hotel_scoped_price_periods(), SQLite migration round-trip for hotel-local check-in and check-out times., _run_alembic() (+33 more)

### Community 65 - "Community 65"
Cohesion: 0.24
Nodes (38): CompanyOptionRead, Return only the names needed to link a reservation to a company., AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, FactReservationDaily, FactRoomOccupancyDaily, HotelAuditEvent (+30 more)

### Community 66 - "Community 66"
Cohesion: 0.07
Nodes (36): collaboration_websocket(), CollaborationManager, CollaborationPatchResponse, CollaborationResourceType, CollaborationTicket, collaborationWebSocketUrl(), CollaborationWsMessage, _consume_ticket() (+28 more)

### Community 67 - "Community 67"
Cohesion: 0.06
Nodes (33): createPromotion(), deactivatePromotion(), FxQuoteDetails, listPromotions(), Promotion, PromotionAppliedEntry, PromotionBenefitType, PromotionConditions (+25 more)

### Community 68 - "Community 68"
Cohesion: 0.10
Nodes (37): Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, mask_to_weekdays(), PromotionConditions, PromotionCreate (+29 more)

### Community 69 - "Community 69"
Cohesion: 0.09
Nodes (46): _hotel(), A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash payment on a reservation must land in the open caja as an INCOME     move, A cash payment on a reservation must land in the open caja as an INCOME     move, A cash payment cannot be approved outside an explicitly opened caja.      proces, A cash payment cannot be approved outside an explicitly opened caja.      proces (+38 more)

### Community 70 - "Community 70"
Cohesion: 0.09
Nodes (26): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, Public contact form endpoint for the marketing site., PublicInquiryPayload, PublicInquiryResponse, submitPublicInquiry(), 09d0b08 feat(marketing): secure inquiries and enforce 90-day retention, 9306eb5 Add public marketing inquiry flow and SEO, b48fd42 Add public marketing inquiry flow and SEO (+18 more)

### Community 71 - "Community 71"
Cohesion: 0.11
Nodes (41): create_restriction(), _get_tenant_guest(), list_active_restriction_guest_ids(), list_restrictions(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, Return restricted guest IDs for one page of the guest list.      The bounded sum (+33 more)

### Community 72 - "Community 72"
Cohesion: 0.06
Nodes (16): _make_hotel_guest_reservation(), Database business-requirement tests.  Verifies that ALL tables required to fulfi, Gate assertion: all tables required by the business requirements exist.     This, test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict() (+8 more)

### Community 73 - "Community 73"
Cohesion: 0.08
Nodes (34): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+26 more)

### Community 74 - "Community 74"
Cohesion: 0.09
Nodes (38): _authorize_oauth_state_actor(), connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration() (+30 more)

### Community 75 - "Community 75"
Cohesion: 0.15
Nodes (38): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _decode_lease_entropy(), _deployment_git_identity(), _deployment_hosts() (+30 more)

### Community 76 - "Community 76"
Cohesion: 0.08
Nodes (34): audited_change(), _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity() (+26 more)

### Community 77 - "Community 77"
Cohesion: 0.05
Nodes (31): BuiltinPermissionRole, fetchPermissionCatalog(), fetchPermissionMatrix(), fetchRolePermissionProfiles(), fetchUserPermissionOverrides(), fetchVisibilityWindows(), PermissionMatrixResponse, PermissionOverrideBatchChange (+23 more)

### Community 78 - "Community 78"
Cohesion: 0.05
Nodes (41): 02102f9 docs(audit): incorpora la verificación por un segundo lector (262 afirmaciones: 198 confirmadas, 64 corregidas), 1197de3 docs(audit): notas de cobertura de lectura en curso [skip ci], 171f582 docs(audit): notas de frontend parte 6 (en curso), 1e22910 docs(audit): notas de frontend partes 3 y 4 (lectura completa y correcciones de la verificación), 1e7d787 docs(audit): notas de cobertura de lectura en curso (más lotes), 2b8290a docs(audit): presupuesto de consumo hoy vs objetivo en el informe, 2f5a4cd docs(audit): notas de cobertura de lectura en curso (lotes de tests y e2e), 3116e30 docs(audit): notas de frontend en curso (partes 3 y siguientes) (+33 more)

### Community 79 - "Community 79"
Cohesion: 0.16
Nodes (34): DailyReportSchedule, Notification, NotificationChannelEnum, NotificationOutbox, NotificationOutboxStatusEnum, NotificationPreference, PushSubscription, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre (+26 more)

### Community 80 - "Community 80"
Cohesion: 0.12
Nodes (39): _b64url_decode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), canonical_provider_evidence_json(), cli(), database_connection_fingerprint(), _decode_baseline_lease_entropy() (+31 more)

### Community 81 - "Community 81"
Cohesion: 0.13
Nodes (34): cancel_draft(), confirm_draft(), create_draft(), get_draft(), _raise_draft_http(), RateChangeDecisionIn, RateChangeDraftIn, RateChangeDraftOut (+26 more)

### Community 82 - "Community 82"
Cohesion: 0.13
Nodes (26): preview_room_block_conflicts_endpoint(), Return counts only; guest identity and reservation IDs are not needed for this w, RoomBlockConflictPreview, RoomBlockCreate, RoomBlockExtensionConflictPreview, RoomBlockExtensionInput, RoomBlockRead, RoomBlock — date-ranged blocks on a specific room (v72 §14). Blocks affect avail (+18 more)

### Community 83 - "Community 83"
Cohesion: 0.10
Nodes (28): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_ai_quota_is_read_only_and_enforced_before_provider_calls(), test_analytics_breakdowns_reuse_facts_and_room_detail_filters_by_room(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts() (+20 more)

### Community 84 - "Community 84"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+24 more)

### Community 85 - "Community 85"
Cohesion: 0.08
Nodes (38): D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE, Owner: "quiero que se pueda poner en las cosas de stock... el costo     por unid, Owner: "quiero que se pueda poner en las cosas de stock... el costo     por unid (+30 more)

### Community 86 - "Community 86"
Cohesion: 0.06
Nodes (18): bootstrap_configuration_fingerprint(), BootstrapConfigurationError, Shared, secret-safe binding for the Render QA bootstrap configuration., Hash the exact provider-observed values without exposing them individually., 8a53fc3 feat(auth): add Sign in with Apple, symmetric to Google OIDC (TECH-0024) (#77), AppleAuthorization, AppleSignInResult, CLIENT_ID (+10 more)

### Community 87 - "Community 87"
Cohesion: 0.07
Nodes (26): confirmMfaEnrollment(), currentUser(), disableMfa(), enrollMfa(), getAuthProviders(), linkGoogle(), MfaEnrollment, regenerateMfaRecoveryCodes() (+18 more)

### Community 88 - "Community 88"
Cohesion: 0.11
Nodes (29): CompanyDocument, CompanyDocumentStatusEnum, CompanyDocumentTypeEnum, CompanyDocument — attachments/vouchers for company reservations (v72 §3.6). Trac, Document/voucher associated with a company reservation (v72 §3.6).     If requir, StoredObjectStatusEnum, CompanyDocumentCreate, CompanyDocumentRead (+21 more)

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (37): anchor_hotel_day_to_fixture_arrival(), _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), Tests for check-in security enforcement:   - prohibido_alojar tag blocks check-i, Guest with active prohibido_alojar tag cannot check in., VIP and other non-blocking tags must not prevent check-in. (+29 more)

### Community 90 - "Community 90"
Cohesion: 0.07
Nodes (15): 150ca64 Reduce PMS request load and keep analytics facts fresh, clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret() (+7 more)

### Community 91 - "Community 91"
Cohesion: 0.10
Nodes (33): channel_status(), complete_channel(), create_note(), inbox(), Authenticated human WhatsApp CRM inbox.  This router never calls Meta directly., Store metadata after the backend completes Embedded Signup.      No bearer token, Store metadata after the backend completes Embedded Signup.      No bearer token, _require_plan() (+25 more)

### Community 92 - "Community 92"
Cohesion: 0.11
Nodes (26): configure_dedicated_baseline(), env_page(), FakeApi, fixtures(), Critical security tests for the read-only preview provider verifier., set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation() (+18 more)

### Community 93 - "Community 93"
Cohesion: 0.09
Nodes (27): _load_company_night_charge_tenant_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_master_admin_bypass_migration(), _load_rls_migration(), _load_user_override_migration(), Return model relationships not covered by the core composite contract., Return model relationships not covered by the core composite contract. (+19 more)

### Community 94 - "Community 94"
Cohesion: 0.08
Nodes (33): HotelBusinessClock, Opt-in local business date for one synthetic hotel., Persist the latest simulated business date for a single hotel.      The row is i, advance_business_clock(), Business-date read and controlled one-day advancement for local simulation., Advance exactly one business day and append a real-time audit event.      SQLite, business_clock_enabled_for_hotel(), get_country_catalog() (+25 more)

### Community 95 - "Community 95"
Cohesion: 0.11
Nodes (34): An opaque browser session whose raw token is never persisted., UserSession, _as_aware(), create_session(), csrf_double_submit_matches(), _device_label_from_request(), _hash_value(), _issue_rotation_successor() (+26 more)

### Community 96 - "Community 96"
Cohesion: 0.16
Nodes (35): _client_with_db(), _enable_whatsapp_plan_for_api_test(), _issue_permission_restore_ticket(), _override_auth(), Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests. (+27 more)

### Community 97 - "Community 97"
Cohesion: 0.10
Nodes (31): _bootstrap_environment(), _local_evidence_payload(), _provider_manifest(), Safety contract for destructive PostgreSQL validation tests.  These tests never, _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence() (+23 more)

### Community 98 - "Community 98"
Cohesion: 0.14
Nodes (27): SimpleRateLimiter, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, MasterBillingPolicy, MasterStripeSettings, MasterSystemEmailConnection, authenticate_master_mfa_login() (+19 more)

### Community 99 - "Community 99"
Cohesion: 0.11
Nodes (34): 62f0868 fix(payments): record WHO triggered a payment state change, not just when, add_reservation_charge(), _available_room_for_conflict(), change_reservation_dates(), _compute_deposit_amount(), enforce_room_move_permission(), extend_reservation_stay(), _extension_amount() (+26 more)

### Community 100 - "Community 100"
Cohesion: 0.08
Nodes (29): APP_URL_HOSTNAME, buildAbsoluteUrl(), ensureLeadingSlash(), isAppHostname(), normalizeUrl(), PREVIEW_APP_HOST_SUFFIXES, PUBLIC_APP_URL, PUBLIC_SITE_URL (+21 more)

### Community 101 - "Community 101"
Cohesion: 0.11
Nodes (32): LinenItem, apply_resource_changes(), _CashSessionDraft, editable_resource_values(), get_resource(), get_resource_spec(), _json_safe(), _LaundryVendorDraft (+24 more)

### Community 102 - "Community 102"
Cohesion: 0.11
Nodes (28): admin_comped_override(), change_plan(), changeSubscriptionPlan(), delete_override(), getSubscriptionStatus(), listSubscriptionPlans(), _master_admin_hotel_id(), _remaining_trial_days() (+20 more)

### Community 103 - "Community 103"
Cohesion: 0.15
Nodes (30): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), _build_xlsx_spool(), create_xlsx_export_job(), _ensure_utc(), expire_export_job_if_needed(), _export_object_key() (+22 more)

### Community 104 - "Community 104"
Cohesion: 0.09
Nodes (18): _enable_test_mfa(), _manual_payment(), Regression coverage for in-person payments and financial step-up controls., _step_up_header(), test_both_cancel_routes_protect_legacy_paid_reservations(), test_cancelling_paid_reservation_requires_manager_step_up_without_auto_refund(), test_financial_summary_is_readable_without_cash_operation(), test_manual_in_person_payment_requires_reference_and_records_actor() (+10 more)

### Community 105 - "Community 105"
Cohesion: 0.07
Nodes (32): PostgreSQL validation tests.  Run with:   DATABASE_URL_TEST=<isolated-qa-dsn> \, Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic downgrade to base then upgrade to head — idempotency check., Alembic downgrade to base then upgrade to head — idempotency check., Numeric(12,2) columns correctly store and return Decimal values., Numeric(12,2) columns correctly store and return Decimal values., All PostgreSQL enum types are created by migrations. (+24 more)

### Community 106 - "Community 106"
Cohesion: 0.10
Nodes (29): _count_queries(), _legacy_operations_summary_reference(), _mk_reservation(), The real N+1 this fix targets: query count must track the number of     reservat, Old terminal cases remain actionable without materializing clean history., Every distinct way `_build_pending_actions` can produce an action must     still, The real N+1 this fix targets: query count must track the number of     reservat, Every distinct way `_build_pending_actions` can produce an action must     still (+21 more)

### Community 107 - "Community 107"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 108 - "Community 108"
Cohesion: 0.08
Nodes (28): approve_temporary_action_grant(), deny_temporary_action_grant(), EffectivePermissionsResponse, fetchEffectivePermissions(), PermissionCatalogItem, PermissionCatalogResponse, PermissionCell, PermissionDetail (+20 more)

### Community 109 - "Community 109"
Cohesion: 0.09
Nodes (18): 788d35b Stop tracking the raw Graphify graph before it hits GitHub's 100 MB limit, 8850d76 Merge branch 'agent-stocksplit' into codex/feature/pms-e2e-scale-hardening, 8877bc8 Merge branch 'agent-linensplit' into codex/feature/pms-e2e-scale-hardening, b6a1271 feat(linen): split ropa blanca into physically separate tables from stock, ed918c6 Make the whole app one visual system and fix what the e2e journeys exposed, f2dd2fe fix(stock): allow reusing a deleted item's name; separate stock/lavanderia catalogs, ConfirmDialogProps, housekeeping (+10 more)

### Community 110 - "Community 110"
Cohesion: 0.14
Nodes (31): allow_master_admin_mfa_attempt(), _as_aware(), audit_master_action(), authenticate_master_login(), _authorize_user_for_master_panel(), _bootstrap_master_credentials_match(), create_master_session(), _hash_value() (+23 more)

### Community 111 - "Community 111"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider (+12 more)

### Community 112 - "Community 112"
Cohesion: 0.09
Nodes (14): client_with_db(), ctx(), get_auth_context_target(), get_db_override_target(), _manual_rate_policy_step_up_headers(), _override_role(), test_clearing_manual_rate_policy_requires_clearing_both_bounds(), test_co_owner_can_change_fx_market_after_step_up() (+6 more)

### Community 113 - "Community 113"
Cohesion: 0.16
Nodes (29): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+21 more)

### Community 114 - "Community 114"
Cohesion: 0.09
Nodes (24): b0217a2 fix(security): close secrets/logging/rate-limit gaps (TECH-0111) (#68), cassandra_healthcheck(), _contact_points(), get_cassandra_session(), get_mongo_db(), mongo_healthcheck(), get_neo4j_driver(), neo4j_healthcheck() (+16 more)

### Community 115 - "Community 115"
Cohesion: 0.10
Nodes (25): acknowledgeShiftHandoff(), createOperationalTask(), createShiftHandoff(), getOperationalTaskAttachmentContent(), listOperationalTaskAttachments(), listOperationalTaskHistory(), listOperationalTasks(), listShiftHandoffs() (+17 more)

### Community 116 - "Community 116"
Cohesion: 0.13
Nodes (24): PrivacyRetentionHold, Current legal-retention exception for one public lead or inquiry.      Changes a, Current legal-retention exception for one public lead or inquiry.      Changes a, _as_utc(), create_retention_hold(), _effective(), _lock_hold_table_for_write(), _mask_email() (+16 more)

### Community 117 - "Community 117"
Cohesion: 0.14
Nodes (28): LinenLocation, LinenMovement, LinenParLevel, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Configured minimum quantity for one linen item at one hotel location., create_linen_item(), create_location(), current_stock() (+20 more)

### Community 118 - "Community 118"
Cohesion: 0.15
Nodes (30): Payment, PaymentLink, PaymentWebhookEvent, Payment gateway tracking models: PaymentLink, Payment, PaymentWebhookEvent.  Sou, One gateway payment object (MP preference / PayPal order / Stripe intent)., Raw webhook log per payment — idempotent on (hotel_id, provider, webhook_id)., Guest-facing pre-payment object (checkout URL / QR). May collect partial payment, ExternalEffectsDisabled (+22 more)

### Community 119 - "Community 119"
Cohesion: 0.15
Nodes (4): GemmaPolicyDraft, GemmaService, Adapter for Gemma-backed policy suggestions.      The service can talk to either, Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 120 - "Community 120"
Cohesion: 0.27
Nodes (30): _build_client(), _cleanup_client(), _manual_ota_payload(), _override_auth(), _payload(), Security gap: any role that can create a reservation (owner, co_owner, manager,, Owner explicitly asked that only the owner -- not even co_owner --     override, No regression: the gate only fires when total_amount is actually sent. (+22 more)

### Community 121 - "Community 121"
Cohesion: 0.12
Nodes (25): PaymentLinkTest, _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _friendly_mercadopago_error(), _is_public_webhook_base(), list_payment_link_tests(), _mercadopago_access_token() (+17 more)

### Community 122 - "Community 122"
Cohesion: 0.13
Nodes (24): _active_push_subscriptions(), _actor_role(), _build_daily_report_body(), _deliver_email(), _deliver_in_app(), _deliver_push(), enqueue_notifications_for_event(), generate_due_daily_reports() (+16 more)

### Community 123 - "Community 123"
Cohesion: 0.15
Nodes (8): make_res(), make_rooms(), Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback)., test_overlapping_reservation_pairs_use_half_open_dates_and_keep_original_indexes(), test_reservation_day_index_clips_to_half_open_horizon(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 124 - "Community 124"
Cohesion: 0.10
Nodes (10): _fact_business_snapshot(), _make_fact_refresh_reservation(), test_explicit_fact_refresh_repairs_legacy_currency_fact(), test_fact_touch_failure_propagates_for_atomic_source_write(), test_room_state_event_create_and_close_refresh_only_materialized_room_horizon(), test_room_state_event_fact_refresh_failure_propagates_for_source_rollback(), test_targeted_refresh_preserves_facts_outside_union_window(), test_targeted_reservation_fact_touch_isolated_by_hotel() (+2 more)

### Community 125 - "Community 125"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_csv(), export_analytics_png(), export_analytics_xlsx()

### Community 126 - "Community 126"
Cohesion: 0.09
Nodes (17): LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead, LaundryStatus, LaundryStatusUpdate (+9 more)

### Community 127 - "Community 127"
Cohesion: 0.19
Nodes (28): _cache_key(), _cache_key_for_display_rate(), _cached_quote_matches(), _cached_rate(), _cached_supported_rates(), _derive_blue_equivalent(), _extract_direct_quotes(), fetch_all_rates() (+20 more)

### Community 128 - "Community 128"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 129 - "Community 129"
Cohesion: 0.15
Nodes (23): _account_label_from_payload(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet(), get_connection_payload() (+15 more)

### Community 130 - "Community 130"
Cohesion: 0.17
Nodes (28): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _daily_report_key(), _date_token(), get_cached_availability_payload(), get_cached_daily_report_payload() (+20 more)

### Community 131 - "Community 131"
Cohesion: 0.08
Nodes (7): _complete_onboarding(), _fake_apple_claims(), test_apple_login_creates_account_and_persists_first_authorization_name(), test_apple_login_reclaims_matching_local_email_after_verified_claims(), test_apple_login_rejects_different_subject_claiming_linked_email(), test_apple_unlink_requires_password_and_revokes_session(), test_login_prefers_a_completed_hotel_when_multiple_memberships_exist()

### Community 132 - "Community 132"
Cohesion: 0.19
Nodes (28): Owner's core requirement: a remito's cost is fixed at creation time.      The bi, Owner's core requirement: a remito's cost is fixed at creation time.      The bi, _seed_hotels(), _seed_house_stock(), _set_test_vendor_price(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total(), test_create_remito_rejects_insufficient_stock_at_source_and_creates_nothing() (+20 more)

### Community 133 - "Community 133"
Cohesion: 0.09
Nodes (20): _make_guest(), _make_reservation(), Multi-tenancy isolation tests: Hotel A vs Hotel B.  Verifies that every domain t, Same document can exist in Hotel A and Hotel B — dedup is hotel-scoped., Same document within one hotel raises IntegrityError., Same key name in two hotels is allowed — uniqueness is per-hotel., Same OTA channel+external_id across different hotels is allowed., Creates Hotel A (id=1000) and Hotel B (id=1001) with minimal shared structure. (+12 more)

### Community 134 - "Community 134"
Cohesion: 0.17
Nodes (21): _apply_drift(), env_page(), FakeRender, FakeRenderCleanupFailure, FakeRenderPutResponseLost, HealthResponse, manifest(), _mutating_calls() (+13 more)

### Community 135 - "Community 135"
Cohesion: 0.13
Nodes (20): BrokenRedis, _cache_settings(), FakeRedis, isolate_read_model_cache(), _reset_cache_client_state(), test_analytics_home_cache_key_varies_by_filter(), test_availability_is_not_cached_in_process_when_redis_is_disabled(), test_availability_payload_is_cached() (+12 more)

### Community 136 - "Community 136"
Cohesion: 0.07
Nodes (17): Tests for reservation creation logic., Create a standard reservation and verify computed fields., B4: manual tarifa on a direct reservation with no company_id -- the         auto, Reserve a specific room., Should fail for non-existent guest., Should fail when check-out is before check-in., Should fail when room doesn't match the requested category., Tests for reservation creation logic. (+9 more)

### Community 137 - "Community 137"
Cohesion: 0.14
Nodes (18): evidence_bytes(), FakeGitHub, iso(), prepare(), Security regression tests for the pull_request_target release gate., test_finalize_rejects_artifact_with_different_bytes(), test_github_client_error_never_discloses_token_or_body(), test_prepare_refuses_head_key_substitution_for_base_checkout_key() (+10 more)

### Community 138 - "Community 138"
Cohesion: 0.09
Nodes (28): V72 §8.3 / §8.4 / §8.5 — Change reservation dates and extend stay tests.  Ported, §8.3 — Cannot change dates when another reservation occupies the room., §8.3 — Changing to a past check-in date is rejected., §8.3 — Cannot change dates when another reservation occupies the room., §8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserv, §8.3 — Changing to a past check-in date is rejected., §8.4 — If new total <= amount_paid after date change, status auto-transitions to, §8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserv (+20 more)

### Community 139 - "Community 139"
Cohesion: 0.10
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 140 - "Community 140"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 141 - "Community 141"
Cohesion: 0.23
Nodes (25): _approve(), _consume(), _create_reservation(), _request(), _reservation_id(), _set_cancel_permission(), test_active_mfa_requires_totp_but_accounts_without_mfa_can_approve(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied() (+17 more)

### Community 142 - "Community 142"
Cohesion: 0.15
Nodes (13): ABC, BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, Acknowledge processed reservation messages in Booking's queue., Acknowledge processed reservation messages in Booking's queue., A provider operation failed before it could return normalized data., A provider operation failed before it could return normalized data., NormalizedOTAReservation (+5 more)

### Community 143 - "Community 143"
Cohesion: 0.13
Nodes (21): _catalog(), initialize(), _json_bytes(), main(), OperationalQAError, _utc_now(), validate(), _write() (+13 more)

### Community 144 - "Community 144"
Cohesion: 0.22
Nodes (16): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+8 more)

### Community 145 - "Community 145"
Cohesion: 0.12
Nodes (19): approve_cash_close_difference(), approve_cash_expense_route(), _cash_expense_read(), cash_session_close_report(), close_cash_session(), _close_report_read(), confirm_cash_custody_receipt(), _csv_decimal() (+11 more)

### Community 146 - "Community 146"
Cohesion: 0.09
Nodes (9): createTaxPolicy(), listTaxPolicies(), FastAPI routes for the commercial configuration domain., TaxPolicy, TaxPolicyWrite, TaxRule, updateTaxPolicy(), RuleDraft (+1 more)

### Community 147 - "Community 147"
Cohesion: 0.11
Nodes (19): Staff management endpoints for hotel public API keys., get_public_api_context(), _public_api_rate_limit_for_hotel(), Public API-key authentication, separate from staff JWT auth., Authorize a public key for a specific external product surface.      Purpose val, require_public_api_purpose(), HotelAPIKey, Per-hotel API credential. `key_hash` stores a hashed version of the secret; (+11 more)

### Community 148 - "Community 148"
Cohesion: 0.07
Nodes (24): createLinenItem(), createLinenLocation(), createLinenMovement(), createLinenOpeningCounts(), createLinenTransfer(), CurrentLinenStock, getLinenSummary(), LinenItem (+16 more)

### Community 149 - "Community 149"
Cohesion: 0.09
Nodes (18): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS, buildChannelSummaries() (+10 more)

### Community 150 - "Community 150"
Cohesion: 0.26
Nodes (26): BillingDecision, MasterStripeWebhookEvent, put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi (+18 more)

### Community 151 - "Community 151"
Cohesion: 0.10
Nodes (25): ActionStepUpTicketUse, Tenant-scoped replay ledger for MFA step-up tickets., Persist only the random ticket id and action binding after first use., action_step_up_ticket_matches(), consume_action_step_up_tickets(), create_action_step_up_ticket(), create_permission_admin_read_step_up_ticket(), is_permission_admin_read_action() (+17 more)

### Community 152 - "Community 152"
Cohesion: 0.09
Nodes (26): ActiveRoomBlockItem, ArrivalCountRead, AvailableWithReviewItem, BookedValueCurrencyRead, BookedValueRead, CashSessionStatusRead, DailyOperationalReportRead, ExpectedCurrencyRead (+18 more)

### Community 153 - "Community 153"
Cohesion: 0.16
Nodes (24): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _load_category_cost_rows() (+16 more)

### Community 154 - "Community 154"
Cohesion: 0.09
Nodes (13): api_client(), Spin up the real FastAPI app against an in-memory SQLite database., Spin up the real FastAPI app against an in-memory SQLite database., Spin up the real FastAPI app against an in-memory SQLite database., A legacy row with untrimmed whitespace must still be found by the     bulk looku, A legacy row with untrimmed whitespace must still be found by the     bulk looku, A legacy row with untrimmed whitespace must still be found by the     bulk looku, _seed_ota_no_guarantee_reservation() (+5 more)

### Community 155 - "Community 155"
Cohesion: 0.18
Nodes (26): _hotel(), _member(), Unit coverage for the notification outbox/service: dedupe, permission filtering,, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, test_daily_report_does_not_resend_same_local_date() (+18 more)

### Community 156 - "Community 156"
Cohesion: 0.15
Nodes (14): _auth(), _client(), Issue a synthetic RBAC-read grant or action-bound ticket., Issue a synthetic RBAC-read grant or action-bound ticket., _step_up_headers(), test_only_owner_can_use_administration_catalog_and_co_owner_is_denied(), test_owner_and_co_owner_can_use_administration_catalog_but_manager_is_denied(), test_owner_can_grant_and_revoke_user_override_then_restore_defaults() (+6 more)

### Community 157 - "Community 157"
Cohesion: 0.08
Nodes (20): authed_client(), client_with_db(), get_auth_context_target(), get_db_override_target(), Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, validate-reset (no-op check) and reset-password (consumes the code)     guess th (+12 more)

### Community 158 - "Community 158"
Cohesion: 0.09
Nodes (10): _card_value(), _make_reservation(), _operations_analytics(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _request_context(), _starter_analytics() (+2 more)

### Community 159 - "Community 159"
Cohesion: 0.12
Nodes (15): _make_reservation(), _pay_deposit(), §7.1: Reservation in DEPOSIT_PAID status raises CheckInError., A legacy per-hotel setting cannot bypass the full-payment rule., A legacy per-hotel setting cannot bypass the full-payment rule., §7.1: Error message tells the operator the required status is 'fully_paid'., §7.1: Error message also reveals the current (blocking) status., Create a PENDING reservation using the first available category. (+7 more)

### Community 160 - "Community 160"
Cohesion: 0.09
Nodes (21): _pay_full(), Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp., After checkout, the assigned room status is set to CLEANING., Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., Checkout after successful check-in, and failure when not checked_in. (+13 more)

### Community 161 - "Community 161"
Cohesion: 0.13
Nodes (23): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), createPricePeriod(), DailyRateOut, DailyRatePrices (+15 more)

### Community 162 - "Community 162"
Cohesion: 0.08
Nodes (6): 1d53db9 Secure local simulation clock and tenant isolation, 82ae784 Report accurate database and lock health, _existing_table_matches(), _install_tenant_rls(), Persist the local synthetic hotel business date.  Revision ID: 20261017_local_bu, upgrade()

### Community 163 - "Community 163"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+16 more)

### Community 164 - "Community 164"
Cohesion: 0.25
Nodes (25): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1) and the linen ite, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, _teardown(), test_duplicate_remito_returns_conflict_but_other_direction_is_allowed(), test_housekeeping_can_operate_remitos_but_not_manage_vendors() (+17 more)

### Community 165 - "Community 165"
Cohesion: 0.15
Nodes (17): acquire_lease(), env_page(), FakeRender, mutations(), Security contract for the dedicated Render QA baseline lease manager., release_lease(), Response, test_acquire_failure_rolls_back_marker_first_then_target_fields() (+9 more)

### Community 166 - "Community 166"
Cohesion: 0.22
Nodes (23): AttestationError, _b64url_decode(), _b64url_encode(), build_attestation(), _canonical_json(), _iso_utc(), _json_object(), _load_private_key() (+15 more)

### Community 167 - "Community 167"
Cohesion: 0.11
Nodes (24): 2447732 fix(security): bump fastapi/starlette to clear starlette CVEs, 3574c6f qa(catalog): record Fase 14 data/logs/dependencies security findings, 45be255 qa(catalog): record Fase 14b dependency-CVE closure findings, 51c2d3a fix(security): bump react-router-dom 6.30.3 to 7.18.1, fix broken onboarding pill nav, 534f3e8 fix(security): bump Pillow 10.3.0 to 12.3.0 to clear CVEs, 672b76d chore(graphify): regenerate graph after Fase 14b CVE closure, 7eea9ed chore(graphify): regenerate graph after Fase 14 security hardening, 954f79c chore(graphify): regenerate graph after Fase 13 security fixes (+16 more)

### Community 168 - "Community 168"
Cohesion: 0.09
Nodes (5): complete_mfa_login(), dashboard_summary(), login(), me(), _serialize_user()

### Community 169 - "Community 169"
Cohesion: 0.18
Nodes (24): _assert_postgres_e2e_database_empty(), _credentials(), E2ESafetyError, _enabled(), _is_postgres_e2e_target(), main(), _postgres_e2e_connection(), _postgres_e2e_seed_connection() (+16 more)

### Community 170 - "Community 170"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 171 - "Community 171"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product() (+12 more)

### Community 172 - "Community 172"
Cohesion: 0.25
Nodes (24): _build_finish_gates(), _build_readiness_checklist(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status() (+16 more)

### Community 173 - "Community 173"
Cohesion: 0.15
Nodes (22): _active_room_blocks(), _alerts(), _arrivals_query(), _available_with_review(), _candidate_summary(), _cash_session(), company_night_extra_balances_by_reservation(), daily_report() (+14 more)

### Community 174 - "Community 174"
Cohesion: 0.16
Nodes (24): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+16 more)

### Community 175 - "Community 175"
Cohesion: 0.15
Nodes (24): _image_base64(), _jpeg_with_exif_base64(), A .png-declared upload whose bytes are NOT actually a decodable image     (magic, Rows written before the object-storage migration have `content` set     and `obj, A .png-declared upload whose bytes are NOT actually a decodable image     (magic, A guest with real consumption charges (e.g. minibar) owes more than     total_am, Rows written before the object-storage migration have `content` set     and `obj, Money-risk regression (fase QA money-risk-payment-surcharge-daily-rate).      Tw (+16 more)

### Community 176 - "Community 176"
Cohesion: 0.13
Nodes (21): _auth_headers(), _ensure_hotel(), A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A settings read should not issue one entitlement query per plan/code., A hotel can carry the canonical v2 row without its legacy projection.      ensur, _step_up_headers() (+13 more)

### Community 177 - "Community 177"
Cohesion: 0.12
Nodes (13): V72 feature tests ported from claude/fervent-jennings-1299c4 and adapted to main, _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later(), test_extend_stay_fails_on_cancelled() (+5 more)

### Community 178 - "Community 178"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 179 - "Community 179"
Cohesion: 0.20
Nodes (22): PaymentProof, PaymentProofBlob, PaymentProofStatusEnum, Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., approve_transfer_proof(), _decode_image(), _delete_uncommitted_object() (+14 more)

### Community 180 - "Community 180"
Cohesion: 0.17
Nodes (22): TOTP MFA secrets and one-time recovery codes for normal user accounts., UserMfaRecoveryCode, UserMfaSecret, add_recovery_codes(), confirm_enrollment(), consume_mfa_code(), _consume_recovery_code(), _consume_totp_code() (+14 more)

### Community 181 - "Community 181"
Cohesion: 0.08
Nodes (16): TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence., Deleting a hotel cannot destroy its audit-log evidence., All AuditActionEnum values can be stored., All AuditActionEnum values can be stored., Regression: hotel_id on transactions must have a DB-level FK. (+8 more)

### Community 182 - "Community 182"
Cohesion: 0.21
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 183 - "Community 183"
Cohesion: 0.26
Nodes (20): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+12 more)

### Community 184 - "Community 184"
Cohesion: 0.10
Nodes (12): _authorize_override(), checkin(), checkin_partial(), 0a457cb feat(checkin): B3 partial check-in + mandatory guest profile capture + companions, compute_missing_guest_fields(), get_profile(), JurisdictionProfile, Jurisdiction profiles for guest/check-in validation.  AR remains the only launch (+4 more)

### Community 185 - "Community 185"
Cohesion: 0.17
Nodes (23): get_stock_summary(), FastAPI routes for stock and inventory operations., Every item's current balance in one request -- avoids the N+1     per-item item, Every item's current balance in one request -- avoids the N+1     per-item /item, StockConsumptionItem, StockConsumptionReportRead, StockItemCreate, StockItemRead (+15 more)

### Community 186 - "Community 186"
Cohesion: 0.11
Nodes (13): cancelWaitlistEntry(), createWaitlistEntry(), listWaitlistEntries(), promoteWaitlistEntry(), API routes for reservation waitlist operations., WaitlistEntry, WaitlistEntryCreate, WaitlistPromotePayload (+5 more)

### Community 187 - "Community 187"
Cohesion: 0.10
Nodes (17): useBulkUpdateRateField(), useBulkUpsertRates(), useCategoryDailyRates(), usePricePeriodMutations(), usePricePeriods(), useRateCalendar(), useRatePaymentMethodOptions(), useUpsertDailyRate() (+9 more)

### Community 188 - "Community 188"
Cohesion: 0.25
Nodes (20): _make_guest(), _make_reservation(), _make_room_set(), A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m, Exercise Numeric SUM and tenant scoping on the real PostgreSQL dialect., A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m, test_available_with_review_surfaces_in_report(), test_billing_adjustment_aggregation_executes_on_postgres() (+12 more)

### Community 189 - "Community 189"
Cohesion: 0.15
Nodes (19): MarketingPricingPlan, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, admin_pricing(), _decode_features(), hash_source(), _ordered_plans(), _plan_catalog_fallback() (+11 more)

### Community 190 - "Community 190"
Cohesion: 0.19
Nodes (20): PaymentReceiptEmailDelivery, One attempted receipt email, without retaining the guest's email address.      `, HotelEmailAttachment, Bytes attached to a hotel email without re-rendering the document., _existing_delivery(), _format_money(), _is_reserved_test_recipient(), _key_hash() (+12 more)

### Community 191 - "Community 191"
Cohesion: 0.11
Nodes (17): create_remito(), create_vendor(), _default_currency(), is_duplicate_remito_integrity_error(), mark_vendor_settlement_paid(), _quarter_bounds(), Record a remito as a pair of LinenMovements per line.      outbound: house_locat, What is physically at the vendor's laundry right now, per item. (+9 more)

### Community 192 - "Community 192"
Cohesion: 0.17
Nodes (21): _available_provider_balance(), balance_due_from_transactions(), cancel_active_links_for_reservation(), cancel_link(), create_link(), _create_mercadopago_preference(), deliver_link(), expire_link() (+13 more)

### Community 193 - "Community 193"
Cohesion: 0.29
Nodes (21): _audit_for(), _category(), _context(), _guest(), _hotel(), _post_request(), _reservation(), _room() (+13 more)

### Community 194 - "Community 194"
Cohesion: 0.18
Nodes (16): _outbox_row(), Exercise the retained Redis recovery path explicitly, independent of deployment, _seed_hotels(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_replay_stops_after_first_redis_failure(), test_celery_task_drains_row_after_after_commit_failure(), test_domain_event_only_emits_origin_key_when_present() (+8 more)

### Community 195 - "Community 195"
Cohesion: 0.10
Nodes (6): _plan(), The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page., A deploy that has not run the migration yet must not 500 the page., TestLeadCapture, TestPublicPricing

### Community 196 - "Community 196"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 197 - "Community 197"
Cohesion: 0.12
Nodes (20): Fase 3 (QA reservas): PATCH api/reservations/{id} only understands     room_id/, Fase 3 (QA reservas): PATCH api/reservations/{id} only understands     room_id/, Fase 3 (QA reservas): PATCH /api/reservations/{id} only understands     room_id/, Receptionists gain only the narrow, same-category move tier by default., Receptionists gain only the narrow, same-category move tier by default., Receptionists gain only the narrow, same-category move tier by default., B5: cross-category move via the endpoint enforces capacity and price_action., B5: cross-category move via the endpoint enforces capacity and price_action. (+12 more)

### Community 198 - "Community 198"
Cohesion: 0.10
Nodes (8): CacheStore, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, RenderRequester, JsonGetter, Protocol, AnalyticsAIProvider

### Community 199 - "Community 199"
Cohesion: 0.24
Nodes (17): Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, ReservationEmailDelivery, ReservationEmailKindEnum, ReservationEmailStatusEnum, HotelOutboundSendResult, build_reservation_email(), _clean_email() (+9 more)

### Community 200 - "Community 200"
Cohesion: 0.10
Nodes (20): channel_for_hotel(), format_sse(), get_domain_event_recovery(), iter_event_stream(), iter_postgres_event_stream(), _notification_to_stream_row(), _outbox_sse_payload(), _PostgresOutboxStreamRow (+12 more)

### Community 201 - "Community 201"
Cohesion: 0.24
Nodes (20): _collect_plan_entitlements(), delete_entitlement_override(), ensure_entitlements_seeded(), ensure_room_within_limit(), ensure_staff_within_limit(), ensure_subscription(), entitlements_payload(), get_effective_room_limit() (+12 more)

### Community 202 - "Community 202"
Cohesion: 0.19
Nodes (20): _company_reservation(), test_adding_company_night_due_removes_stale_fully_paid_status(), test_company_charge_quantity_cannot_exceed_registered_additional_people(), test_company_night_charge_batch_resolves_rate_history_with_bounded_queries(), test_company_night_charge_corrections_lock_ledger_rows_as_one_batch(), test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(), test_company_night_charges_use_effective_rate_and_extra_person_quantity(), test_company_night_payment_requires_exact_selected_nights_and_tracks_pending_then_paid() (+12 more)

### Community 203 - "Community 203"
Cohesion: 0.27
Nodes (19): _completed_payment(), _mock_receipt_email(), Receipt PDF and email API tests use mocked provider/local transports only., _receipt_headers(), test_local_simulation_captures_test_email_and_pdf_without_provider_calls(), test_local_simulation_hotel_mismatch_fails_closed_without_provider_fallback(), test_local_simulation_rejects_non_test_recipient_and_never_falls_back_to_gmail(), test_receipt_email_accepts_a_refunded_receipt_transaction() (+11 more)

### Community 204 - "Community 204"
Cohesion: 0.10
Nodes (13): Availability lookup must not issue one reservation query per room., Find available rooms after booking some., Availability checks must not eagerly load room reservation histories., Tests for room availability checking., Tests for room availability checking., A room with no reservations should be available., A room with no reservations should be available., A room with an overlapping reservation should not be available. (+5 more)

### Community 205 - "Community 205"
Cohesion: 0.26
Nodes (19): _accept_invitation(), _accept_invitation_with_google(), _activate_invitation_for_user(), _activate_invitation_for_user_audited(), _audit_invitation_accept_denial(), _audit_invitation_mfa_challenge(), _available_invitation(), _build_invitation_mfa_challenge() (+11 more)

### Community 206 - "Community 206"
Cohesion: 0.20
Nodes (17): _action_step_up_tickets(), AuthContext, _authenticate_user(), _decode_authorization_header(), get_auth_context(), get_current_user(), get_current_user_optional(), _matching_action_step_up_ticket() (+9 more)

### Community 207 - "Community 207"
Cohesion: 0.19
Nodes (19): BenchmarkResult, cleanup(), derive_test_dsn(), explain(), explain_query(), _format_plan_nodes(), index_usage_for_operation(), main() (+11 more)

### Community 208 - "Community 208"
Cohesion: 0.17
Nodes (11): aiter_postgres_event_stream(), _deliver_postgres_notification(), _forget_postgres_event_stream_hub(), _get_postgres_event_stream_hub(), _PostgresEventStreamHub, Share PostgreSQL notifications and a bounded poll fallback per hotel., Stream tenant-scoped outbox invalidations without blocking the event loop., _record_postgres_fallback_poll() (+3 more)

### Community 209 - "Community 209"
Cohesion: 0.11
Nodes (13): coalesce_model_change_family(), _OutboxPublishPermit, A durable Redis attempt, optionally owning the single recovery probe., Close any lazy PostgreSQL notification connections at app shutdown., Collapse bulk ORM invalidations to one safe signal per domain.      The persiste, shutdown_postgres_event_listeners(), listener_connection_string(), parse_domain_event_notification() (+5 more)

### Community 210 - "Community 210"
Cohesion: 0.16
Nodes (19): billing_adjustment_totals_by_reservation(), completed_paid_amount(), completed_paid_amounts_by_reservation(), external_paid_balance_credit(), has_payment_history_for_cancellation(), operational_balance_due(), paid_amount_with_legacy_fallback(), paid_amounts_by_reservation() (+11 more)

### Community 211 - "Community 211"
Cohesion: 0.15
Nodes (16): consumption_report(), _consumption_totals_by_item(), create_stock_item(), current_stock(), delete_stock_item(), _get_item(), get_location(), get_stock_item() (+8 more)

### Community 212 - "Community 212"
Cohesion: 0.22
Nodes (17): _auth_context(), _code_at(), _invalid_code(), _issue_ticket(), step_up_client(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_invalid_ticket_fails_closed_without_echoing_it() (+9 more)

### Community 213 - "Community 213"
Cohesion: 0.10
Nodes (9): client(), FastAPI client backed by an isolated SQLite database., FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Demo endpoints must be off unless explicitly enabled., Demo utilities work once DEMO_MODE=true is set., Explicit development environments retain the DEMO_MODE workflow., test_seed_and_reset_allowed_when_demo_enabled() (+1 more)

### Community 214 - "Community 214"
Cohesion: 0.22
Nodes (18): _link(), Re-delivering the SAME webhook must not create a 2nd transaction nor raise., Two distinct webhooks for the same completed payment id -> one transaction., A later-arriving webhook for the SAME payment reporting an earlier status     (n, A payment already recorded as rejected/failed must not silently become     compl, _reservation(), test_balance_due_uses_transactions_not_payments(), test_cancelled_payment_link_rejects_unverified_success_event() (+10 more)

### Community 215 - "Community 215"
Cohesion: 0.16
Nodes (17): A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, _seed_hotel(), test_company_night_rate_permission_defaults_allow_management_roles(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default() (+9 more)

### Community 216 - "Community 216"
Cohesion: 0.16
Nodes (18): archiveHotelRole(), create_role(), createHotelRole(), CreateHotelRolePayload, delete_role(), fetchHotelRoles(), HotelRole, HotelRoleCode (+10 more)

### Community 217 - "Community 217"
Cohesion: 0.12
Nodes (15): 0ce7072 fix(tech-0140): preserve compatibility during rollout, _client_signature(), get_async_redis_client(), get_sync_redis_client(), namespaced_key(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Clear process clients for tests and orderly shutdown., Return one async client per process for async transports. (+7 more)

### Community 218 - "Community 218"
Cohesion: 0.16
Nodes (18): _apply_setting(), Bind a SQLAlchemy transaction to the authenticated tenant.  PostgreSQL RLS polic, Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Reapply stashed tenant settings directly on a just-begun ``Connection``.      Ca, Set the authenticated user id used by membership RLS policies. (+10 more)

### Community 219 - "Community 219"
Cohesion: 0.15
Nodes (9): Regression contracts for the repository's agent-operations setup., run_qa_evidence_check(), test_qa_evidence_rejects_malformed_result_without_traceback(), test_qa_evidence_rejects_result_rows_outside_verified_preview(), test_qa_evidence_schema_accepts_full_catalog(), test_raw_graphify_graph_is_not_tracked(), test_tracked_graphify_artifacts_stay_small(), _tracked_files() (+1 more)

### Community 220 - "Community 220"
Cohesion: 0.23
Nodes (16): _company_reservation(), _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies(), test_deferred_company_extension_cannot_collect_base_rate_in_pms(), test_deferred_company_extension_does_not_calculate_or_record_base_price(), test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(), test_deferred_company_payment_api_rejects_base_balance_without_writes() (+8 more)

### Community 221 - "Community 221"
Cohesion: 0.21
Nodes (17): _manual_payload(), B4: the manual OTA form lets the receptionist type a total + currency     that d, B4: the manual OTA form lets the receptionist type a total + currency     that d, The receptionist can type TWO independent prices (ARS and USD) for a     manual, The receptionist can type TWO independent prices (ARS and USD) for a     manual, Root-cause repro for the owner's report: a category with a RatePlan     that is, Root-cause repro for the owner's report: a category with a RatePlan     that is, _seed_hotel() (+9 more)

### Community 222 - "Community 222"
Cohesion: 0.23
Nodes (17): _enable_external_effects(), _fake_mp_gateway(), A public webhook endpoint must fail closed without a configured secret., A public webhook endpoint must fail closed without a configured secret., _reservation(), test_connections_flag_closed_forces_local_only_before_gateway(), test_create_link_best_effort_when_gateway_fails(), test_create_link_fills_checkout_url_with_mocked_mp() (+9 more)

### Community 223 - "Community 223"
Cohesion: 0.11
Nodes (16): Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest with no document_type set is blocked by validate_guest_for_checkin., Separate coverage of document-not-verified vs terms-not-signed blocks., Separate coverage of document-not-verified vs terms-not-signed blocks., When require_terms_acceptance=False, missing terms is not an error., Guest with no document_type set is blocked by validate_guest_for_checkin. (+8 more)

### Community 224 - "Community 224"
Cohesion: 0.11
Nodes (10): An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used., When two PricePeriods overlap, the one with higher priority is returned., PricePeriod is NOT used for dates outside its range., Tier-1: explicit DailyRate row wins over everything else. (+2 more)

### Community 225 - "Community 225"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 226 - "Community 226"
Cohesion: 0.25
Nodes (15): acknowledge_shift_handoff(), _authorize_task_photo_scope(), _can(), _can_read_reservation_context(), _conflict(), create_operational_task(), get_operational_task_history(), get_operational_task_photo_content() (+7 more)

### Community 227 - "Community 227"
Cohesion: 0.24
Nodes (11): LocalizedDateFieldProps, dateInputCursorPosition(), formatDateInputValue(), formatDateTimeInputValue(), formatNativeDateTimeValue(), formatNativeDateValue(), maskDateInputValue(), maskDateTimeInputValue() (+3 more)

### Community 228 - "Community 228"
Cohesion: 0.16
Nodes (14): ApiRequestMetric, ApiResponseMetric, browseUntil(), createOneReservation(), createReservationBatch(), durationSeconds, measureUiAction(), navigate() (+6 more)

### Community 229 - "Community 229"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 230 - "Community 230"
Cohesion: 0.17
Nodes (17): _fake_google_claims(), test_auth_flows_fail_without_connected_mail_provider(), test_auth_providers_exposes_only_public_google_capabilities(), test_google_account_can_set_password_only_with_linked_google_proof_and_csrf(), test_google_link_wrong_password_does_not_mutate_or_invalidate_the_local_session(), test_google_login_creates_new_user_when_email_unknown(), test_google_login_does_not_replace_another_linked_subject(), test_google_login_rejects_invalid_issuer_audience_or_expiry() (+9 more)

### Community 231 - "Community 231"
Cohesion: 0.21
Nodes (16): test_handoff_is_tenant_scoped_and_acknowledged(), test_housekeeping_can_read_all_general_tasks_but_cannot_operate_them(), test_list_tasks_does_not_query_unreturned_relationships(), test_list_tasks_orders_priority_and_due_date(), test_maintenance_task_keeps_block_until_authorized_release(), test_operator_scope_matches_role_and_assignment(), test_report_only_custom_manager_cannot_read_or_mutate_out_of_scope_tasks(), test_task_author_fallback_is_hotel_scoped_and_used_by_list_create_and_update() (+8 more)

### Community 232 - "Community 232"
Cohesion: 0.29
Nodes (16): _configured_settings(), _inquiry_rows(), _payload(), test_public_inquiry_collapses_newlines_in_single_line_email_fields(), test_public_inquiry_does_not_trust_spoofable_forwarded_for(), test_public_inquiry_has_global_limit_when_trusted_edge_ip_is_missing(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_not_stored_when_notification_recipient_is_unconfigured() (+8 more)

### Community 233 - "Community 233"
Cohesion: 0.27
Nodes (17): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- ordinary out movements for a pe, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+9 more)

### Community 234 - "Community 234"
Cohesion: 0.12
Nodes (5): _bearer_headers(), Real row locks serialize overlapping refreshes without losing the cookie., test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_postgres_concurrent_refreshes_recover_the_same_successor(), test_session_listing_individual_revoke_logout_and_revoke_all()

### Community 235 - "Community 235"
Cohesion: 0.23
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 236 - "Community 236"
Cohesion: 0.24
Nodes (16): apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run(), get_policy_suggestions() (+8 more)

### Community 237 - "Community 237"
Cohesion: 0.22
Nodes (16): _booking_status_label_es(), _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), delete_booking(), _ensure_permission_tier() (+8 more)

### Community 238 - "Community 238"
Cohesion: 0.20
Nodes (17): _assert_manageable_membership(), _assert_role_profile_mutation_allowed(), preview_effective_permissions(), Keep permission exceptions aligned with the staff-management boundary., read_user_overrides(), restore_role_permission_defaults(), restore_role_permission_override(), restore_user_permission_defaults() (+9 more)

### Community 239 - "Community 239"
Cohesion: 0.13
Nodes (17): _frontend_placeholder(), Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., SPA fallback for React Router.     Skips API/asset paths to avoid shadowing. (+9 more)

### Community 240 - "Community 240"
Cohesion: 0.25
Nodes (14): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+6 more)

### Community 241 - "Community 241"
Cohesion: 0.18
Nodes (17): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., discard_queued_domain_changes(), get_domain_event_outbox_metrics(), queue_domain_change(), QueuedDomainChange, Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, A safe invalidation signal waiting for the surrounding DB commit. (+9 more)

### Community 242 - "Community 242"
Cohesion: 0.13
Nodes (13): _OutboxPublishAttempt, _OutboxPublishCooldown, publish_queued_domain_changes(), Redis outcome to persist after every publish in the batch has finished., Process-local gate for durable after-commit Redis publishes only., Return a permit, or skip while cooling down / another probe runs., A successful recovery probe closes only the cooldown it owns., Open or extend the cooldown after an actual durable publish fails. (+5 more)

### Community 243 - "Community 243"
Cohesion: 0.18
Nodes (15): apple_login_enabled(), dolarapi_rates_enabled(), DolarApiRatesDisabled, external_effects_enabled(), google_login_enabled(), inbound_provider_events_enabled(), Fail-closed policy gates for provider traffic and provider-originated events.  T, Raised when public DolarAPI market-data reads are disabled. (+7 more)

### Community 244 - "Community 244"
Cohesion: 0.18
Nodes (7): _CachedFailure, CachedOutboxPollFailure, OutboxPollBatchCache, _PollEntry, Short-lived singleflight cache for PostgreSQL event-outbox polling.  The Postgre, A same-window poll failed already; wait for the next bounded retry., Deduplicate concurrent per-process polls without extending freshness.

### Community 245 - "Community 245"
Cohesion: 0.24
Nodes (16): _client_with_db(), _override_auth(), B3: check-in must capture the guest's missing profile data (birth place/ country, Green case: same endpoint, now with `guest` in the payload, succeeds once., Green case: same endpoint, now with `guest` in the payload, succeeds once., Red case: guest missing the 4 new mandatory fields cannot check in., Red case: guest missing the 4 new mandatory fields cannot check in., _seed_fully_paid_reservation() (+8 more)

### Community 246 - "Community 246"
Cohesion: 0.16
Nodes (7): _postgres_e2e_environment(), test_reset_e2e_database_never_deletes_postgres_target_files(), test_seed_guard_accepts_explicit_high_local_postgres_port(), test_seed_guard_accepts_only_explicit_loopback_postgres_e2e_database(), test_seed_guard_accepts_secondary_ipv4_loopback_for_isolated_postgres(), test_seed_guard_rejects_postgres_without_the_dedicated_local_test_boundary(), test_seed_guard_requires_a_distinct_explicit_seed_role_on_the_same_local_database()

### Community 247 - "Community 247"
Cohesion: 0.12
Nodes (8): Tests for OTA Integration — Race condition handling and webhook processing., Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room., TestAvailabilityUpdate, TestBookingWebhook, TestExpediaWebhook, TestOTARaceCondition

### Community 248 - "Community 248"
Cohesion: 0.22
Nodes (15): _seed_group(), test_company_grouped_move_preserves_sold_category_and_revert_checks_physical_capacity(), test_housekeeping_cannot_list_read_or_revert_movement_groups(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_receptionist_can_list_movement_groups_but_cannot_revert_them(), test_revert_already_reverted_group_returns_400() (+7 more)

### Community 249 - "Community 249"
Cohesion: 0.22
Nodes (16): _auth_headers(), _enroll_and_confirm_mfa(), _next_totp_code(), test_disable_mfa_requires_current_password_and_a_valid_factor(), test_google_only_account_can_disable_mfa_with_fresh_linked_google_proof(), test_google_only_account_needs_fresh_linked_provider_proof_to_enroll_mfa(), test_login_without_mfa_keeps_returning_the_normal_auth_response(), test_mfa_enroll_confirm_uses_encrypted_secret_and_requires_second_login_step() (+8 more)

### Community 250 - "Community 250"
Cohesion: 0.26
Nodes (14): _create_role(), Security and API contract tests for per-hotel custom roles., _step_up_headers(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), test_custom_role_downgrade_aborts_before_any_data_changes(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed(), test_custom_roles_can_be_assigned_and_invited_but_owner_transfer_stays_separate() (+6 more)

### Community 251 - "Community 251"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 252 - "Community 252"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, Fail-closed boundary tests: disabled lanes do no parsing, DB work or network., test_apple_login_stops_before_jwks_or_db(), test_connections_flag_alone_closes_credential_lane(), test_credential_access_and_email_stop_before_db_or_network(), test_google_login_stops_before_transport_or_db(), test_ota_callback_stops_before_json_parse() (+2 more)

### Community 253 - "Community 253"
Cohesion: 0.21
Nodes (11): _make_completed_transaction(), Regression coverage for app/api/reports.py's financial endpoints (/api/reports/d, _reservation_for_report(), test_booked_value_endpoint_matches_full_report_with_bounded_query_count(), test_booked_value_includes_and_prorates_stays_overlapping_the_report_window(), test_daily_report_totals_a_completed_transaction_without_crashing(), test_revenue_csv_groups_by_method_category_channel_and_currency(), test_revenue_keeps_currencies_separate_and_uses_reportable_channel() (+3 more)

### Community 254 - "Community 254"
Cohesion: 0.18
Nodes (11): Tests for B2: GET /api/reservations/occupancy-grid (planilla de ocupación).  Cro, Regression guard for the plan's explicit note: the naive `balance_due`     ignor, Regression guard for the plan's explicit note: the naive `balance_due`     ignor, _reserve(), test_cancelled_reservation_is_excluded(), test_checked_out_reservation_does_not_reduce_free_room_count(), test_custom_housekeeping_role_gets_anonymized_occupancy_grid(), test_operational_balance_due_includes_consumption_charges() (+3 more)

### Community 255 - "Community 255"
Cohesion: 0.26
Nodes (11): _load_migration(), Unit coverage for the guarded PostgreSQL enum-label migration., _RecordingBind, _Result, test_downgrade_reverses_only_the_new_migration(), test_revision_fits_alembic_version_column(), test_sqlite_skips_postgresql_enum_ddl(), test_upgrade_fails_closed_if_both_enum_labels_exist() (+3 more)

### Community 256 - "Community 256"
Cohesion: 0.24
Nodes (15): _seed_pricing_foundation(), test_all_supported_fx_pairs_use_directional_quotes_via_ars(), test_blue_non_usd_conversion_does_not_use_official_currency_snapshot(), test_blue_non_usd_conversion_uses_only_matching_derived_snapshot(), test_conversion_returns_the_full_precision_rate_used_for_amount(), test_global_blue_market_dominates_fx_policy_source_and_side(), test_missing_selected_blue_market_does_not_fall_back_to_official_snapshot(), test_negative_fx_spread_is_rejected_instead_of_reducing_hotel_quote() (+7 more)

### Community 257 - "Community 257"
Cohesion: 0.27
Nodes (14): _ctx(), _seed_hotel(), test_apply_promotions_never_goes_negative(), test_create_promotion_rejects_duplicate_code(), test_create_promotion_rejects_percentage_over_100(), test_deactivate_and_reactivate_promotion(), test_find_applicable_promotions_for_many_nights_uses_bounded_queries(), test_find_applicable_promotions_for_nights_batches_rules_and_guest_tags() (+6 more)

### Community 259 - "Community 259"
Cohesion: 0.23
Nodes (14): Security regression tests for local QA operator attestations., tagged(), test_altered_signature_is_rejected(), test_attestation_older_than_24_hours_is_rejected(), test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_manifest_byte_change_after_signing_is_rejected() (+6 more)

### Community 260 - "Community 260"
Cohesion: 0.45
Nodes (14): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+6 more)

### Community 261 - "Community 261"
Cohesion: 0.32
Nodes (14): _period_draft_payload(), _period_values(), seed_rate_context(), test_price_period_create_is_draft_until_confirm_and_preserves_reservation_total(), test_price_period_draft_rejects_daily_rate_changed_after_preview(), test_price_period_draft_rejects_impact_scope_over_366_nights(), test_price_period_preview_excludes_explicit_daily_rate_nights(), test_price_period_update_and_delete_are_staged_and_confirmed_as_soft_delete() (+6 more)

### Community 262 - "Community 262"
Cohesion: 0.25
Nodes (14): Live PostgreSQL RLS behavioral verification.  Unlike tests/test_tenant_rls_contr, With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the     unp, Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak., C2: with app.master_admin='true', subscriptions across hotels are visible., C1: app.hotel_id must survive a commit within the same ORM session.      Uses th, A superuser engine whose commits are REAL, visible to other connections.      Se, _role_connection(), _seed_engine() (+6 more)

### Community 263 - "Community 263"
Cohesion: 0.21
Nodes (14): _headers(), Security settings API is tenant-scoped, redacted and revokes real JWTs., Audit evidence is readable only; there is no ordinary mutation route., Audit evidence is readable only; there is no ordinary mutation route., test_audit_surfaces_do_not_expose_mutating_methods(), test_manager_cannot_read_security_settings(), test_revoke_all_invalidates_the_callers_previous_token(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv() (+6 more)

### Community 264 - "Community 264"
Cohesion: 0.30
Nodes (15): _client_with_db(), _override_auth(), API-level coverage for stock items: delete-then-recreate (owner-reported bug), u, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Same convention as POST /api/payment-links: a client resending the     same POST, _second_hotel(), _teardown(), test_duplicate_active_name_returns_clean_409_not_a_500() (+7 more)

### Community 265 - "Community 265"
Cohesion: 0.13
Nodes (13): PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., The default full-payment policy blocks check-in without payment., The default full-payment policy blocks check-in without payment. (+5 more)

### Community 266 - "Community 266"
Cohesion: 0.13
Nodes (13): Verify the hotel config flag is respected (default = True → gate enforced)., Config flag is True by default; gate is active for PENDING reservation., Even if documentterms config flags are disabled, payment gate remains active., Verify payment and guest-data gates remain separate., Config flag is True by default; gate is active for PENDING reservation., Verify payment and guest-data gates remain separate., Verify payment and guest-data gates remain separate., Even if documentterms config flags are disabled, payment gate remains active. (+5 more)

### Community 267 - "Community 267"
Cohesion: 0.16
Nodes (11): Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed., Resolving with a room of a different category must be blocked., Resolving with an already-occupied room must be blocked., After resolve, the DB row reflects the updated state., Service-level tests for the resolve logic (mirrors what the API endpoint does)., Resolving a waitlisted reservation sets room_id and clears is_wait_listed., Resolving with a room of a different category must be blocked. (+3 more)

### Community 268 - "Community 268"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 269 - "Community 269"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 270 - "Community 270"
Cohesion: 0.14
Nodes (10): RateCalendarResponse, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, RateEditorGrid(), RateEditorGridProps (+2 more)

### Community 271 - "Community 271"
Cohesion: 0.33
Nodes (14): DrillError, main(), _pg_command(), _pg_count(), _postgres_parts(), Expected, safe failure for a local drill., Verify every ready metadata row against the local blob before restore., _run_pg_command() (+6 more)

### Community 272 - "Community 272"
Cohesion: 0.20
Nodes (7): EmailProvider, get_email_provider(), _mask_email(), _mask_recipients(), _normalize_display_from(), NullEmailProvider, ResendEmailProvider

### Community 273 - "Community 273"
Cohesion: 0.19
Nodes (13): DomainEvent, get_realtime_client(), _get_realtime_fast_fail_client(), _get_redis_client(), publish_domain_event(), Get the short-timeout Redis client used only by post-commit signals., Return a configured client after a bounded connectivity check., Publish one event. ``revision``/``occurred_at`` let an outbox replay     reuse t (+5 more)

### Community 274 - "Community 274"
Cohesion: 0.29
Nodes (14): _active_tag_filter(), add_tag(), _audit(), _escape_like_term(), find_or_create_guest(), _get_guest(), _guest_search_rank(), list_active_tags() (+6 more)

### Community 275 - "Community 275"
Cohesion: 0.18
Nodes (7): _FakeResponse, _quote(), test_blue_equivalent_fails_closed_when_any_source_quote_is_stale(), test_blue_equivalent_for_non_usd_currency_is_explicitly_derived(), test_fresh_quote_rejects_crossed_buy_sell_values(), test_stale_selected_usd_quote_fails_closed_without_requesting_official_fallback(), test_usd_conversion_rejects_provider_quote_for_wrong_currency_or_market()

### Community 276 - "Community 276"
Cohesion: 0.41
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 277 - "Community 277"
Cohesion: 0.13
Nodes (11): Verify auto-generated timestamps., Verify auto-generated timestamps., Tests for Guest and GuestCompanion models., Tests for Guest and GuestCompanion models., Verify guest with full data., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Verify the has_valid_identity property detects missing documents. (+3 more)

### Community 278 - "Community 278"
Cohesion: 0.13
Nodes (11): Tests for Reservation model and state machine., Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify the state machine transition map is correct., Verify can_transition_to method., Verify can_transition_to method., Verify balance_due computed property., Verify balance_due computed property. (+3 more)

### Community 279 - "Community 279"
Cohesion: 0.13
Nodes (11): Tests for Room and RoomCategory models., Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify bidirectional Room ↔ RoomCategory relationship. (+3 more)

### Community 280 - "Community 280"
Cohesion: 0.42
Nodes (14): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_block_extension_rejects_protected_reservation_and_shorter_end() (+6 more)

### Community 281 - "Community 281"
Cohesion: 0.31
Nodes (12): _override_auth(), _seed_reservation(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(), test_housekeeping_cannot_create_room_block_by_default(), test_housekeeping_only_reads_operational_room_block_reasons(), test_receptionist_can_create_but_not_release_room_block_by_default() (+4 more)

### Community 282 - "Community 282"
Cohesion: 0.29
Nodes (11): _move(), _seed_move_shapes(), test_capacity_tier_alone_includes_each_narrower_tier(), test_company_move_preserves_contracted_category_and_extra_guest_capacity_is_physical(), test_existing_wide_roles_still_move_anywhere(), test_manager_can_move_each_shape(), test_manager_capacity_permission_does_not_bypass_occupancy_validation(), test_receptionist_can_complete_company_guest_records_and_extension_request_but_cannot_edit_booking_terms() (+3 more)

### Community 283 - "Community 283"
Cohesion: 0.13
Nodes (14): postgres_isolated_client(), Forward tests for the scalable data-architecture specialist workflow.  These are, A tariff revision change invalidates the quote before any write., A changed PostgreSQL tariff invalidates the quote before any insert., A valid entity id from hotel 2 cannot cross hotel 1's API boundary., Bind the API to the isolated PostgreSQL session for forward contracts., A valid entity id from hotel 2 cannot cross hotel 1's API boundary., A tariff revision change invalidates the quote before any write. (+6 more)

### Community 284 - "Community 284"
Cohesion: 0.42
Nodes (12): _make_reservation(), Tests for V72 §5 - Concurrency guards: double-booking and duplicate payments.  T, _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations() (+4 more)

### Community 285 - "Community 285"
Cohesion: 0.17
Nodes (8): _make_period(), apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price., Applying a second period to overlapping dates updates those dates., TestApplyPricePeriod

### Community 286 - "Community 286"
Cohesion: 0.21
Nodes (9): CeleryJobDispatcher, dispatch_once(), JobDispatcher, JobSpec, Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica, JobDispatchRecord, Durable worker coordination records for portable job dispatch. (+1 more)

### Community 287 - "Community 287"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification., Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 288 - "Community 288"
Cohesion: 0.20
Nodes (9): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+1 more)

### Community 289 - "Community 289"
Cohesion: 0.19
Nodes (5): ccfccdf Add performance/architecture audit with reproducible measurements, e088114 Merge remote-tracking branch 'origin/claude/modest-goldberg-5dd5am', Introspect the real SQLAlchemy metadata: tables, columns, types, indexes, FKs., Seed a realistic one-hotel history for profiling (disposable local DB only).  Us, Seed a realistic one-hotel history for profiling (disposable local DB only).  Us

### Community 290 - "Community 290"
Cohesion: 0.26
Nodes (13): PublicInquiryNotificationStatus, create_public_inquiry(), _digest_key(), _notification_body(), _notify_inquiry(), PublicInquiryRateLimitError, PublicInquiryUnavailableError, _rate_limit_keys() (+5 more)

### Community 291 - "Community 291"
Cohesion: 0.22
Nodes (4): OTAOrchestratorService, build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 292 - "Community 292"
Cohesion: 0.14
Nodes (3): OTAProviderAdapter, FakeBookingAdapter, test_ota_orchestrator_verifies_connection_and_persists_event()

### Community 293 - "Community 293"
Cohesion: 0.15
Nodes (11): formatDate(), Hold, HoldReason, MasterAdminPrivacyRetentionPage(), PublicInquiry, reasonLabels, releaseLabels, ReleaseReason (+3 more)

### Community 294 - "Community 294"
Cohesion: 0.14
Nodes (11): PermissionCatalogItem, PermissionDecision, PermissionOverrideBatchChange, PermissionOverrideBatchRequest, Set both sides of one role's reservation visibility window., RolePermissionOverrideRequest, TemporaryActionGrantApproveRequest, TemporaryActionGrantRequest (+3 more)

### Community 295 - "Community 295"
Cohesion: 0.21
Nodes (13): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a short lease and release it only if this worker owns it.      Redis/Val (+5 more)

### Community 296 - "Community 296"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 297 - "Community 297"
Cohesion: 0.14
Nodes (1): Local hotel-scoped business clock API and date isolation coverage.

### Community 298 - "Community 298"
Cohesion: 0.14
Nodes (7): opened_cash_register(), Tests for Check-in Service. Validates guest data requirements before allowing ch, Operational tests must prepare the caja before collecting cash., Operational tests must prepare the caja before collecting cash., Operational tests must prepare the caja before collecting cash., TestCheckOut, TestGuestValidation

### Community 299 - "Community 299"
Cohesion: 0.38
Nodes (13): _seed_daily_rates(), _seed_hotel(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_extracts_included_tax_from_daily_price(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night() (+5 more)

### Community 300 - "Community 300"
Cohesion: 0.14
Nodes (9): If run_persisted_allocation raises, rollback must be called (not commit)., If run_persisted_allocation raises, rollback must be called (not commit)., §5.2 — Integration: after new booking, allocation engine receives correct args., §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, The background task must commit and close its own DB session., The background task must commit and close its own DB session. (+1 more)

### Community 301 - "Community 301"
Cohesion: 0.31
Nodes (12): _delivery(), _message(), _post(), HTTP boundary tests for the Meta Cloud API WhatsApp webhook.  The endpoint had n, Regression: a bad phone used to raise 400 and roll the whole batch back.      Me, ``text`` and ``profile`` arriving as strings must not raise a 500., _signature(), test_ingests_a_signed_inbound_message() (+4 more)

### Community 302 - "Community 302"
Cohesion: 0.30
Nodes (12): addDaysIso(), browserTimeZone(), formatHotelDate(), formatHotelDateTime(), formatHotelTime(), formatLocalIsoDate(), normalizedTimeZone(), pad() (+4 more)

### Community 303 - "Community 303"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), downgrade(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), _install_rls(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):, Create an active GuestRestriction for every currently-active (non-expired)     l (+5 more)

### Community 304 - "Community 304"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 305 - "Community 305"
Cohesion: 0.21
Nodes (12): _build_authorization_check(), Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Adapt sync and async streams to ASGI disconnects and always close them., Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Revalidate stream access while tolerating a brief database pool outage.      The, recover_domain_events() (+4 more)

### Community 306 - "Community 306"
Cohesion: 0.22
Nodes (11): create_fx_snapshot(), FxConversionQuoteRead, FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse, FxSnapshotRead, get_all_rates(), get_conversion_quote() (+3 more)

### Community 307 - "Community 307"
Cohesion: 0.27
Nodes (9): _build_unavailable_message(), _current_status(), _dev_outbox_path(), get_system_email_status(), _normalize_account_email(), _record_dev_email(), send_system_email(), _sender_parts() (+1 more)

### Community 308 - "Community 308"
Cohesion: 0.15
Nodes (2): HotelConfigUpdate, _normalize_currency()

### Community 309 - "Community 309"
Cohesion: 0.19
Nodes (6): _clean_optional(), _clean_required(), PublicInquiryAccepted, PublicInquiryCreate, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 310 - "Community 310"
Cohesion: 0.28
Nodes (11): _adjacency_bonus_for_room(), _check_overlap(), _guest_room_signal_score(), _is_protected_reservation(), _lowest_available_compatible_floor(), _lowest_compatible_floor(), _one_night_gap_penalty_for_room(), _overlapping_reservation_pairs() (+3 more)

### Community 311 - "Community 311"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 312 - "Community 312"
Cohesion: 0.35
Nodes (11): add_company_night_charges(), _company(), _company_night_charges_summary(), correct_company_night_charge_amounts(), create_company_nightly_surcharge_rate(), get_company_night_charges(), list_company_nightly_surcharge_rates(), _paid_and_pending_by_charge() (+3 more)

### Community 313 - "Community 313"
Cohesion: 0.22
Nodes (8): Mailer, Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists., send_generic_auth_notice_email(), send_platform_email(), send_reset_password_email(), send_verification_email(), send_verification_success_email()

### Community 314 - "Community 314"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 315 - "Community 315"
Cohesion: 0.31
Nodes (12): _actor_name(), _area_for(), _bounds(), _date_filter(), list_operational_audit(), _matches(), _money(), _row() (+4 more)

### Community 316 - "Community 316"
Cohesion: 0.37
Nodes (12): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id(), _normalize_required() (+4 more)

### Community 317 - "Community 317"
Cohesion: 0.28
Nodes (12): _body_size_estimate(), _fallback_url(), _json_size_estimate(), observed_async_http_call(), observed_http_call(), Privacy-safe size and latency telemetry for outbound HTTP calls., Call an HTTP client and log only destination, byte counts, time and status., Async equivalent of :func:`observed_http_call`. (+4 more)

### Community 318 - "Community 318"
Cohesion: 0.29
Nodes (12): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), _quote_provenance(), quote_rate_plan_stay(), _record_conversion_snapshot(), _resolve_commission_amount() (+4 more)

### Community 319 - "Community 319"
Cohesion: 0.22
Nodes (13): _configure_resend(), JWTs are stateless with no server-side blacklist, so a password reset -     the, JWTs are stateless with no server-side blacklist, so a password reset -     the, JWTs are stateless with no server-side blacklist, so a password reset -     the, _register_owner(), test_google_account_link_waits_for_mfa_and_preserves_password(), test_google_link_rejects_mismatched_email_without_mutation(), test_google_link_requires_password_and_matching_verified_identity() (+5 more)

### Community 320 - "Community 320"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 321 - "Community 321"
Cohesion: 0.15
Nodes (11): A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A payment state change is a money-moving event and must record WHO     triggered, A gateway webhook has no human actor -- it must stay None, never         silentl, A payment state change is a money-moving event and must record WHO     triggered (+3 more)

### Community 322 - "Community 322"
Cohesion: 0.15
Nodes (5): Edge case tests for the payment engine., Edge case tests for the payment engine., Edge case tests for the payment engine., Edge case tests for the payment engine., TestPaymentEdgeCases

### Community 323 - "Community 323"
Cohesion: 0.28
Nodes (12): opened_cash_register(), _payment(), Immediate cash settlement scenarios require an operator-opened caja., Immediate cash settlement scenarios require an operator-opened caja., _reservation(), test_direct_extension_can_leave_balance_pending_without_a_payment(), test_extension_card_payment_with_pos_reference_is_completed_and_audited(), test_extension_manual_card_payment_requires_reference_before_mutating_stay() (+4 more)

### Community 324 - "Community 324"
Cohesion: 0.24
Nodes (12): _backfill_defaults(), _contract_legacy_rows(), _copy_role_overrides(), downgrade(), _insert_permission_rows(), _install_user_override_rls(), expand RBAC catalog and add tenant-scoped user overrides  Revision ID: 20260813_, Install the PostgreSQL tenant policy; no-op on other dialects. (+4 more)

### Community 325 - "Community 325"
Cohesion: 0.20
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the

### Community 326 - "Community 326"
Cohesion: 0.36
Nodes (11): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+3 more)

### Community 327 - "Community 327"
Cohesion: 0.36
Nodes (11): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., _render(), _strong_password() (+3 more)

### Community 328 - "Community 328"
Cohesion: 0.26
Nodes (10): createPaymentSurcharge(), deactivatePaymentSurcharge(), grossWithSurcharge(), listPaymentSurcharges(), PaymentSurcharge, PaymentSurchargeCreatePayload, PaymentSurchargeType, surchargesKey() (+2 more)

### Community 329 - "Community 329"
Cohesion: 0.17
Nodes (9): LeadCreateRequest, LeadCreateResponse, MasterLeadListPayload, MasterLeadPayload, MasterPricingPlanListPayload, MasterPricingPlanPayload, PublicPricingPlan, PublicPricingResponse (+1 more)

### Community 330 - "Community 330"
Cohesion: 0.24
Nodes (6): chain_names(), FuncScan, is_db_call(), names of methods in a call chain, outer->inner, root_name(), scan_file()

### Community 331 - "Community 331"
Cohesion: 0.21
Nodes (5): _build_dry_run_report(), _hotel_ranges(), main(), _parser(), Idempotently rebuild reservation and room analytics facts for a bounded scope.

### Community 332 - "Community 332"
Cohesion: 0.38
Nodes (10): _aggregate_rows(), _booked_amount_in_window(), _booked_nights_in_window(), _build_booked_value_projection(), build_booked_value_report(), build_financial_report(), _hotel_bounds(), _local_day() (+2 more)

### Community 333 - "Community 333"
Cohesion: 0.23
Nodes (9): InvitationMailer, Send staff invitations and keep the reusable sign-in route visible., Notify an existing staff member after their role change is committed., Send a best-effort staff access notice without logging provider data., Notify an invitee after the hotel membership and invitation are committed., send_staff_invitation_email(), _send_staff_notice(), send_staff_role_changed_email() (+1 more)

### Community 334 - "Community 334"
Cohesion: 0.23
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 336 - "Community 336"
Cohesion: 0.42
Nodes (10): _seed_hotel(), _seed_reservation(), _step_up_headers(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_excludes_soft_deleted_guest_identity(), test_guest_export_neutralizes_formula_like_guest_fields(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner() (+2 more)

### Community 337 - "Community 337"
Cohesion: 0.36
Nodes (9): _create_link(), _post_webhook(), HTTP-level Mercado Pago webhook journey.  Exercises the real route (/api/payment, _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_rejected_webhook_records_payment_without_completing_a_transaction() (+1 more)

### Community 338 - "Community 338"
Cohesion: 0.17
Nodes (9): Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies., Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies. (+1 more)

### Community 339 - "Community 339"
Cohesion: 0.17
Nodes (8): Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship., Verify Transaction → Reservation relationship., TestTransactionModel

### Community 340 - "Community 340"
Cohesion: 0.24
Nodes (10): client(), _complete_minimal_onboarding(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database., Provide a TestClient backed by an in-memory SQLite database., _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps() (+2 more)

### Community 341 - "Community 341"
Cohesion: 0.26
Nodes (7): Focused coverage for the operational audit and hotel-local cash projection., _reservation(), test_daily_summary_uses_hotel_local_day_and_separates_physical_cash(), test_operational_audit_filters_only_successful_logins(), test_operational_audit_unifies_sources_filters_and_preserves_tenant_boundary(), _transaction(), _user()

### Community 342 - "Community 342"
Cohesion: 0.23
Nodes (5): _seed_hotel(), test_booking_webhook_scopes_by_hotel_and_secret(), test_despegar_webhook_scopes_by_hotel_and_secret(), test_expedia_webhook_scopes_by_hotel_and_secret(), test_ota_webhook_rejects_invalid_secret()

### Community 343 - "Community 343"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 344 - "Community 344"
Cohesion: 0.39
Nodes (9): _add_reservation(), _rows(), _seed_hotel(), _step_up_headers(), test_reservation_export_neutralizes_formula_like_text(), test_reservation_export_rejects_invalid_and_overlong_date_ranges(), test_reservation_export_rejects_results_over_cap_without_truncating(), test_reservation_export_requires_dedicated_permission() (+1 more)

### Community 345 - "Community 345"
Cohesion: 0.26
Nodes (9): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), test_listing_uses_one_scalar_reservation_query(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history() (+1 more)

### Community 346 - "Community 346"
Cohesion: 0.26
Nodes (10): _override_auth(), Reception needs to read room data to build reservations (room picker, availabili, GET api/rooms/categories feeds the category picker on both the     Reservations, GET /api/rooms/categories feeds the category picker on both the     Reservations, test_custom_housekeeping_role_receives_safe_room_projection(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms() (+2 more)

### Community 347 - "Community 347"
Cohesion: 0.17
Nodes (6): Reservation has nullable joined relations, so payment locks must name the row., BillingAdjustment also eager-loads optional relations used by night-charge corre, The payment helper must lock the reservation despite joined optional relations., test_company_night_charge_billing_adjustment_lock_targets_only_adjustment(), test_company_night_charge_payment_path_uses_reservation_lock_target(), test_company_night_charge_reservation_lock_targets_only_reservation()

### Community 348 - "Community 348"
Cohesion: 0.17
Nodes (9): §5.2 — Motor reoptimizes after every new reservation., §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — The service layer create_reservation has no reoptimization side effect. (+1 more)

### Community 349 - "Community 349"
Cohesion: 0.17
Nodes (9): is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati, A normal reservation blocks the room; a waitlisted one does not., is_wait_listed=True reservations with room_id=None must not affect availability., A waitlisted reservation (room_id=None) must not block room availability., find_available_rooms should still return the room when only waitlisted reservati, A normal reservation blocks the room; a waitlisted one does not. (+1 more)

### Community 350 - "Community 350"
Cohesion: 0.40
Nodes (10): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _timestamp(), _validate_baseline_lease_id(), validate_manifest() (+2 more)

### Community 351 - "Community 351"
Cohesion: 0.22
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 352 - "Community 352"
Cohesion: 0.18
Nodes (8): DailyRateRangeRow, PriceField, DAY_LABEL, PRICE_FIELDS, RateEditorMobileCards(), RateEditorMobileCardsProps, WEEKDAY_LABEL, SingleRateInput

### Community 353 - "Community 353"
Cohesion: 0.33
Nodes (10): _attach_actor_names(), audit_timeline(), _build_audit_timeline_csv(), _current_user(), export_audit_timeline(), recent_security_events(), revoke_current_user_sessions(), _safe_resource_id() (+2 more)

### Community 354 - "Community 354"
Cohesion: 0.18
Nodes (5): 76e00e3 docs(audit): verificación empírica de hallazgos (limitador, API pública, PII, onboarding, health), measured(), Mide, sobre PostgreSQL real, el costo de cuatro rutas calientes que la lectura c, Ejecuta ``fn`` ``repeat`` veces en una sesión nueva y devuelve sentencias/commit, Verifica si una clave de API pública `web_engine` puede leer el documento de un

### Community 355 - "Community 355"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 356 - "Community 356"
Cohesion: 0.18
Nodes (10): HousekeepingBoardRead, HousekeepingBoardRoomRead, Non-financial category metadata safe for housekeeping workflows., Room state without rates or free-text notes that may contain PII., RoomCategoryOperationalRead, RoomCategoryUpdate, RoomHousekeepingRead, RoomHousekeepingStatusUpdate (+2 more)

### Community 357 - "Community 357"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 358 - "Community 358"
Cohesion: 0.35
Nodes (10): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), PostgresTargetSafetyError, Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, The PostgreSQL test target cannot be proven isolated and disposable. (+2 more)

### Community 359 - "Community 359"
Cohesion: 0.55
Nodes (9): _guest(), _reservation(), _seed_hotel(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_previous_completed_room_signal_requires_the_new_reservation_category() (+1 more)

### Community 360 - "Community 360"
Cohesion: 0.24
Nodes (4): _Client, _Response, test_provider_chat_uses_curated_hotel_context_and_controlled_message(), test_provider_receives_only_curated_hotel_analytics_payload()

### Community 361 - "Community 361"
Cohesion: 0.35
Nodes (7): FakeJwkClient, test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_valid_apple_token_is_verified(), _token(), _verify()

### Community 362 - "Community 362"
Cohesion: 0.22
Nodes (3): _Response, test_validate_gmail_credentials_requires_send_scope(), test_verify_connection_health_for_gmail_updates_connection()

### Community 363 - "Community 363"
Cohesion: 0.38
Nodes (10): _create_payload(), _reservation(), _seed_guest_inventory(), _seed_hotel(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_receptionist_cannot_override_until_canonical_permission_is_granted(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(), test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass() (+2 more)

### Community 364 - "Community 364"
Cohesion: 0.18
Nodes (3): The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today, utc_server_clock()

### Community 365 - "Community 365"
Cohesion: 0.25
Nodes (6): _Response, _seed_gmail_connection(), _seed_mercadopago_connection(), test_payment_link_test_requires_hotel_gmail_connection(), test_send_hotel_email_preserves_pdf_attachment_bytes_in_gmail_mime(), test_send_hotel_email_uses_connected_gmail()

### Community 366 - "Community 366"
Cohesion: 0.31
Nodes (10): Same per-location bug as stock_service: an 'out' at location B must be     valid, Same per-location bug as stock_service: an 'out' at location B must be     valid, _seed_hotels(), test_linen_minimums_are_location_specific_and_allow_zero(), test_linen_opening_count_batch_is_atomic_and_only_applies_before_location_history(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_marks_zero_balance_as_having_history(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped() (+2 more)

### Community 367 - "Community 367"
Cohesion: 0.27
Nodes (6): _reservation(), test_sweep_excludes_checked_in_and_is_idempotent(), test_sweep_is_tenant_scoped(), test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(), test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(), test_sweep_sql_cutoff_filter_matches_elapsed_utc_hours_across_dst()

### Community 368 - "Community 368"
Cohesion: 0.31
Nodes (9): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement(), test_new_hotel_starts_with_cash_only() (+1 more)

### Community 369 - "Community 369"
Cohesion: 0.20
Nodes (8): _assign_hotel(), Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1)., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status →, Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1)., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status →, Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status →

### Community 370 - "Community 370"
Cohesion: 0.18
Nodes (9): Tests for full payment flow., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Pay the full amount at once → status should go directly to fully_paid., Tests for full payment flow., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Pay the full amount at once → status should go directly to fully_paid. (+1 more)

### Community 371 - "Community 371"
Cohesion: 0.18
Nodes (9): Critical test: Simulates web booking with deposit, then balance payment at check, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Critical test: Simulates web booking with deposit, then balance payment at check, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi (+1 more)

### Community 372 - "Community 372"
Cohesion: 0.33
Nodes (8): _make_hotel(), _make_reservation(), R6b: scheduled report tasks (§15.1) + manual-review routing (§13.3).  No real em, test_one_hotel_failure_does_not_abort_the_rest(), test_review_for_future_does_not_trigger_immediate_alert(), test_review_for_today_triggers_immediate_alert(), test_review_routing_swallows_email_errors(), test_send_morning_reports_iterates_active_hotels()

### Community 373 - "Community 373"
Cohesion: 0.36
Nodes (10): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_rejects_checkout_not_after_current_checkout_in_spanish(), test_extension_rejects_refund_as_immediate_payment_without_mutating_reservation(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge() (+2 more)

### Community 374 - "Community 374"
Cohesion: 0.24
Nodes (7): _make_reservation(), Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted)., Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted)., Helper — create a reservation through the service layer., TestWaitlistListing

### Community 375 - "Community 375"
Cohesion: 0.29
Nodes (6): _context(), _hotel_today(), Regression tests for tenant-scoped, per-role reservation visibility., _reserve(), test_in_house_guest_remains_visible_when_check_in_predates_window(), test_visibility_window_filters_far_future_and_null_is_unlimited()

### Community 376 - "Community 376"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 377 - "Community 377"
Cohesion: 0.38
Nodes (9): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+1 more)

### Community 378 - "Community 378"
Cohesion: 0.27
Nodes (4): _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), _serialize_reservation_status()

### Community 379 - "Community 379"
Cohesion: 0.24
Nodes (3): _env_value(), _render_service_block(), test_render_pool_budget_is_bounded_for_one_api_and_one_cron()

### Community 380 - "Community 380"
Cohesion: 0.31
Nodes (9): _cassandra_probe(), _close_clients(), _enable(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each, Avoid reusing a client created by another test or stale .env flags., reset_projection_clients(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), test_mongo_audit_projection_lands_document() (+1 more)

### Community 381 - "Community 381"
Cohesion: 0.44
Nodes (9): DocumentTypeEnum, GuestBase, GuestCompanionBase, GuestCompanionCreate, GuestCompanionRead, GuestCreate, GuestRead, GuestUpdate (+1 more)

### Community 382 - "Community 382"
Cohesion: 0.20
Nodes (5): Request and read contracts for one group collection with child allocations., ReservationGroupPaymentAllocationRead, ReservationGroupPaymentAllocationRequest, ReservationGroupPaymentCreate, ReservationGroupPaymentRead

### Community 383 - "Community 383"
Cohesion: 0.44
Nodes (9): _completed_at(), _ensure_completed_transaction(), _find_existing_event(), ingest_webhook(), _insert_event(), _is_allowed_status_transition(), _normalize_status(), _payload_value() (+1 more)

### Community 384 - "Community 384"
Cohesion: 0.44
Nodes (8): add_to_waitlist(), cancel_waitlist_entry(), expire_waitlist_entry(), _get_waitlist_entry(), promote_from_waitlist(), request_payment_link_for_waitlist(), update_waitlist_entry(), WaitlistError

### Community 385 - "Community 385"
Cohesion: 0.24
Nodes (3): BodyLimitMiddleware, Tope global de tamaño de cuerpo como middleware ASGI puro (hallazgo N13 del info, _TooLarge

### Community 386 - "Community 386"
Cohesion: 0.60
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+1 more)

### Community 387 - "Community 387"
Cohesion: 0.42
Nodes (9): _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_run_creates_movement_group_and_events(), test_mobility_restriction_prefers_lowest_compatible_floor(), test_persisted_allocation_batches_reservation_entity_reads(), test_score_only_breaks_equivalent_room_tie(), test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations() (+1 more)

### Community 388 - "Community 388"
Cohesion: 0.42
Nodes (9): _legacy_deferred_reservation(), _payment(), test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(), test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(), test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(), test_deferred_reservation_group_masks_legacy_group_total(), test_deferred_reservation_read_and_list_mask_legacy_lodging_money(), test_paid_total_adjustment_cannot_restore_a_deferred_lodging_amount() (+1 more)

### Community 389 - "Community 389"
Cohesion: 0.29
Nodes (5): _integration_client(), _Response, test_gmail_oauth_callback_uses_signed_state(), test_send_hotel_email_uses_connected_gmail(), test_validate_gmail_credentials_rejects_missing_send_scope()

### Community 390 - "Community 390"
Cohesion: 0.42
Nodes (9): _auth(), _client(), _isolate_realtime_configuration(), The event assertion below requires the Redis realtime path explicitly., test_active_restriction_summary_is_batched_tenant_scoped_and_nondisclosing(), test_checkin_reuses_explicit_override_contract_and_never_discloses_reason(), test_internal_reservation_and_quote_return_stable_nondisclosing_409_then_audit_override(), test_restriction_api_permissions_tenant_isolation_and_event() (+1 more)

### Community 391 - "Community 391"
Cohesion: 0.31
Nodes (7): _login(), Public pricing is owner-editable from the master-admin console.  Reuses the mast, test_a_plan_dropped_from_the_payload_disappears(), test_negative_price_is_rejected(), test_owner_can_read_captured_leads(), test_owner_sets_a_price_and_the_public_endpoint_serves_it(), test_saving_pricing_writes_an_audit_event()

### Community 392 - "Community 392"
Cohesion: 0.20
Nodes (9): Regression coverage for portable Graphify artifact normalization., A second normalizer run must leave already-portable artifacts unchanged., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten., test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized() (+1 more)

### Community 393 - "Community 393"
Cohesion: 0.24
Nodes (3): _create_task_context(), MemoryObjectStorage, test_task_photo_is_private_tenant_scoped_and_integrity_checked()

### Community 394 - "Community 394"
Cohesion: 0.20
Nodes (9): opened_cash_register(), Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Tests for deposit (señas) payment flow., Tests for deposit (señas) payment flow., Tests for deposit (señas) payment flow. (+1 more)

### Community 395 - "Community 395"
Cohesion: 0.47
Nodes (7): _build_client(), _cleanup(), _override_auth(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_reactivate_deactivated_surcharge_via_patch()

### Community 396 - "Community 396"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 397 - "Community 397"
Cohesion: 0.38
Nodes (9): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_invalid_recipient_is_rejected_before_provider(), test_local_example_test_address_is_accepted_but_never_forwarded(), test_production_rejects_example_test_recipient(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_synthetic_email_does_not_expand_reservation_tenant_scope(), test_test_mode_never_sends_example_test_even_if_provider_flags_are_enabled() (+1 more)

### Community 398 - "Community 398"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 399 - "Community 399"
Cohesion: 0.20
Nodes (4): Tests for Reservation Service — booking creation, availability checks, state tra, Tests for confirmation code generation., Tests for confirmation code generation., TestConfirmationCode

### Community 400 - "Community 400"
Cohesion: 0.60
Nodes (9): _client_with_db(), _override_auth(), _seed_group(), test_company_group_revert_denies_reception_even_with_individual_company_manage_override(), test_explicit_receptionist_grant_can_revert_group(), test_housekeeping_cannot_read_or_revert_room_movement_group(), test_receptionist_can_read_but_cannot_revert_room_movement_group(), test_revert_movement_group_marks_reservations_protected() (+1 more)

### Community 401 - "Community 401"
Cohesion: 0.33
Nodes (9): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), Tests for v72 check-out balance reconciliation., Checkout balance scenarios collect cash through an open caja., Checkout balance scenarios collect cash through an open caja., test_checkout_blocked_when_reservation_has_operational_balance(), test_checkout_succeeds_when_operational_balance_is_fully_paid() (+1 more)

### Community 402 - "Community 402"
Cohesion: 0.20
Nodes (4): V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai, No duplicate rows after two overlapping period applies (upsert semantics)., TestPricePeriodOverlap, TestResolveRateCalendar

### Community 403 - "Community 403"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 404 - "Community 404"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 405 - "Community 405"
Cohesion: 0.31
Nodes (9): _create_linen_tables(), downgrade(), _drop_kind_column(), _finalize_laundry_vendor_columns(), _migrate_linen_data(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li, Reverse of _migrate_linen_data: every linen_items row moves back into     stock_ (+1 more)

### Community 406 - "Community 406"
Cohesion: 0.29
Nodes (9): downgrade(), _insert_default_rows(), _insert_permission_rows(), _install_rls(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls() (+1 more)

### Community 407 - "Community 407"
Cohesion: 0.40
Nodes (9): _create_and_secure_retention_holds(), _cron_is_required(), downgrade(), _downgrade_sqlite(), _install_purge_function(), Honor auditable legal holds in public-form retention.  Revision ID: 20260926_leg, _reschedule_purge_job(), upgrade() (+1 more)

### Community 408 - "Community 408"
Cohesion: 0.42
Nodes (8): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity()

### Community 409 - "Community 409"
Cohesion: 0.31
Nodes (8): Demo-only utilities: seed sample data and reset the database. Exposed only when, assert_demo_database_target_is_safe(), assert_demo_reset_is_safe(), DemoResetSafetyError, Fail-closed safety checks for destructive local demo database resets., The runtime or database target is not explicitly safe for a demo reset., Allow demo data operations only against an explicitly local database., Allow destructive demo resets only in development against a local DB.      The e

### Community 410 - "Community 410"
Cohesion: 0.22
Nodes (4): backendURL, ownerCredentials, receptionistCredentials, TestSession

### Community 411 - "Community 411"
Cohesion: 0.31
Nodes (6): jsonResponse(), permissionAdminReadStepUpRequired(), session, stepUpRequired(), tick(), waitFor()

### Community 412 - "Community 412"
Cohesion: 0.22
Nodes (6): GuestRestrictionCreate, GuestRestrictionOverrideRequest, GuestRestrictionRead, GuestRestrictionResolveRequest, Pydantic schemas for GuestRestriction (formal lodging-prohibition entity)., Carried on reservation/checkin/quote requests to authorize bypassing     an acti

### Community 413 - "Community 413"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 414 - "Community 414"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, main(), missing_model_tables(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., repair_cash_handoff_schema()

### Community 415 - "Community 415"
Cohesion: 0.25
Nodes (7): create_apple_client_secret(), exchange_apple_code(), Apple OIDC verification and authorization-code helpers.  The identity token is a, Verify Apple signature, issuer, audience, expiry and optional nonce., Verify Apple signature, issuer, audience, expiry and optional nonce., _read_private_key(), verify_apple_id_token()

### Community 416 - "Community 416"
Cohesion: 0.31
Nodes (3): GemmaServiceError, Raised when a Gemma request cannot be completed safely., Raised when a Gemma request cannot be completed safely.

### Community 417 - "Community 417"
Cohesion: 0.39
Nodes (8): _build_email_message(), _build_message(), capture_hotel_email(), _dev_outbox_path(), ensure_hotel_gmail_ready(), HotelOutboundIdentity, Append a complete MIME message to the protected local development outbox.      T, send_hotel_email()

### Community 418 - "Community 418"
Cohesion: 0.33
Nodes (8): _amount(), generate_payment_receipt_pdf(), _local_created_at(), _pdf_text(), _rate(), Generate a downloadable PDF from the persisted payment receipt snapshot., Keep core-font text safe while retaining Spanish Latin-1 characters., Render one page from ``get_payment_receipt_data`` output.      The function acce

### Community 419 - "Community 419"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 421 - "Community 421"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_surfaces_retryable_provider_outage()

### Community 422 - "Community 422"
Cohesion: 0.58
Nodes (8): _build_client(), _cleanup_client(), _get_db_override_target(), _override_auth(), _seed_hotel(), test_commercial_lists_are_hotel_scoped_and_validate_foreign_categories(), test_manager_has_no_access_to_commercial_configuration(), test_owner_can_create_and_update_commercial_configuration()

### Community 423 - "Community 423"
Cohesion: 0.64
Nodes (8): _client_with_db(), _override_auth(), _seed_reservation(), test_company_document_cannot_be_attached_to_unlinked_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_uploaded_company_voucher_is_private_signature_aware_and_tenant_scoped()

### Community 424 - "Community 424"
Cohesion: 0.44
Nodes (8): _create_remitos(), _load_migration(), test_day2_downgrade_refuses_to_discard_persisted_operational_data(), test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint(), test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved(), test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace(), test_remito_preflight_is_empty_when_no_duplicate_exists(), test_remito_preflight_reports_ids_and_trimmed_duplicates()

### Community 425 - "Community 425"
Cohesion: 0.33
Nodes (5): _store_expired_display_quote(), _supported_official_quote(), test_disabled_async_fx_uses_cache_without_constructing_client(), test_disabled_sync_fx_uses_stale_cache_without_network(), test_production_sandbox_can_read_dolarapi_without_enabling_integrations()

### Community 426 - "Community 426"
Cohesion: 0.28
Nodes (3): _read(), test_explicit_rotation_replaces_values_and_preserves_mode(), test_generates_only_allowed_synthetic_values_with_private_permissions()

### Community 427 - "Community 427"
Cohesion: 0.28
Nodes (7): C2 evidence: master-admin RLS bypass, against a REAL PostgreSQL target only.  SQ, A master-admin dashboard read may seed a missing subscription safely.      Snaps, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, Reproduce the pre-fix bug, then prove the fix, on a real Postgres target.      1, _reset_and_migrate_to_head(), test_master_admin_dashboard_reads_hotels_without_outbox_rls_failure(), test_master_admin_reproduces_the_bug_then_the_bypass_fixes_it()

### Community 428 - "Community 428"
Cohesion: 0.39
Nodes (8): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel()

### Community 429 - "Community 429"
Cohesion: 0.50
Nodes (8): _auth(), _client(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and, test_daily_report_schedule_is_owner_co_owner_only(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_preferences_crud(), test_push_subscription_register_and_unregister()

### Community 430 - "Community 430"
Cohesion: 0.50
Nodes (8): _outbox_event_types(), _owner(), Integration coverage: the real domain-event call sites (reservation lifecycle, c, test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), test_no_show_enqueues_notification(), test_reservation_lifecycle_enqueues_notifications()

### Community 431 - "Community 431"
Cohesion: 0.50
Nodes (7): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_with_confirmed_external_payment_requires_settlement_review(), test_booking_modify_updates_existing_reservation_and_guest(), test_duplicate_booking_webhook_does_not_duplicate_reservation_or_guest()

### Community 432 - "Community 432"
Cohesion: 0.36
Nodes (6): _add_event(), test_missing_or_zero_cursor_requires_full_refetch(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch(), test_stale_cursor_requires_full_refetch()

### Community 433 - "Community 433"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 434 - "Community 434"
Cohesion: 0.22
Nodes (5): Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss., TestDailyRateModelConstraints

### Community 435 - "Community 435"
Cohesion: 0.22
Nodes (7): When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., TestWaitlistCreation

### Community 436 - "Community 436"
Cohesion: 0.31
Nodes (8): _is_example_test_address(), is_local_synthetic_reservation_email(), local_synthetic_email_addresses_enabled(), normalize_reservation_email(), Validation helpers for reservation communication email addresses., Allow reserved synthetic addresses only in isolated local/test modes., Validate and normalize an email, narrowly allowing local ``example.test``., Return whether a validated recipient belongs to the local reserved domain.

### Community 437 - "Community 437"
Cohesion: 0.42
Nodes (8): _columns(), _create_index_if_missing(), downgrade(), _drop_index_if_present(), _indexes(), Operational audit fields, daily cash indexes, and audit read permission., _seed_audit_permission(), upgrade()

### Community 438 - "Community 438"
Cohesion: 0.50
Nodes (8): _backfill_external_ota_credits(), downgrade(), _has_columns(), Backfill legacy OTA credits and operational role defaults.  This data migration, _set_global_role_defaults(), _set_housekeeping_whatsapp_defaults(), _set_manager_operational_defaults(), upgrade()

### Community 439 - "Community 439"
Cohesion: 0.33
Nodes (8): _assert_no_duplicate_remitos(), downgrade(), _guard_day2_downgrade_data(), _install_rls(), Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, a, Refuse rollback when it would discard operational data or session state., _remove_rls(), upgrade()

### Community 440 - "Community 440"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 441 - "Community 441"
Cohesion: 0.25
Nodes (2): 35c9420 docs(audit): lectura completa de modelos, servicios, API, tareas, adapters, schemas y panel master, Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post

### Community 442 - "Community 442"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 443 - "Community 443"
Cohesion: 0.29
Nodes (5): flattenKeys(), frontendRoot, loadKeys(), pluralSuffixes, sourceRoot

### Community 444 - "Community 444"
Cohesion: 0.36
Nodes (6): MARKETING_ROUTES, marketingHtmlPlugin(), renderRouteHtml(), replaceTag(), indexHtml, vercel

### Community 445 - "Community 445"
Cohesion: 0.50
Nodes (7): evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 446 - "Community 446"
Cohesion: 0.25
Nodes (5): AnalyticsAIChatRead, AnalyticsAIChatRequest, AnalyticsInsightRead, AnalyticsInsightRequest, AnalyticsInsightStatusRead

### Community 447 - "Community 447"
Cohesion: 0.25
Nodes (5): ReservationEmailDeliveryRead, ReservationEmailKind, ReservationEmailSendRequest, ReservationEmailSendResponse, ReservationEmailStatus

### Community 448 - "Community 448"
Cohesion: 0.50
Nodes (7): _actor_name(), _db_utc_bounds(), _decimal(), get_daily_summary(), _utc(), _utc_bounds(), _value()

### Community 449 - "Community 449"
Cohesion: 0.32
Nodes (7): _enum_value(), get_guest_profile(), GuestProfile, GuestProfileError, Jurisdiction-agnostic guest profile rules.  The profile layer keeps legal-field, Raised when a requested guest profile is not available., validate_primary_guest_record()

### Community 450 - "Community 450"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 451 - "Community 451"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 452 - "Community 452"
Cohesion: 0.46
Nodes (6): SQLite upgrade coverage for company nightly rate cutover and rollback guard., _run_alembic(), _seed_legacy_company(), test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only(), test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots(), test_company_nightly_rate_downgrade_refuses_to_discard_user_history()

### Community 453 - "Community 453"
Cohesion: 0.43
Nodes (7): _load_data_migration(), _load_migration(), SQLite contract test for the new manual-payment/check-in-policy migration., A payment committed after candidate discovery must be in the backfill snapshot., test_migration_backfills_default_policy_and_is_idempotent(), test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(), test_ota_backfill_locks_row_before_recomputing_completed_ledger()

### Community 454 - "Community 454"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 456 - "Community 456"
Cohesion: 0.43
Nodes (7): v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 457 - "Community 457"
Cohesion: 0.25
Nodes (3): Tests for reservation state machine transitions., Tests for reservation state machine transitions., TestStateTransitions

### Community 458 - "Community 458"
Cohesion: 0.29
Nodes (7): _create_rooms_with_soft_deleted_tail(), Regression coverage for room soft-delete visibility across count surfaces., Create the reported 42-room case, leaving three soft-deleted rows active., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, test_soft_deleted_rooms_are_excluded_from_every_room_count_surface()

### Community 459 - "Community 459"
Cohesion: 0.50
Nodes (6): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_lists_only_active_blocking_reservations_and_allows_delete_after_move(), test_room_delete_soft_deletes_hides_and_audits()

### Community 460 - "Community 460"
Cohesion: 0.25
Nodes (3): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 461 - "Community 461"
Cohesion: 0.25
Nodes (5): When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., Six physical Twin rooms hold six overlapping stays; the seventh is         rejec, TestOverbookingBlocked

### Community 462 - "Community 462"
Cohesion: 0.43
Nodes (6): _hotel_and_user(), test_assign_and_note_are_auditable_and_cross_tenant_safe(), test_inbound_message_is_idempotent_and_keeps_tenant_scope(), test_list_conversations_filters_by_hotel_and_status(), test_outbound_message_is_queued_in_durable_outbox(), test_provider_route_is_unique_and_resolves_to_its_hotel()

### Community 463 - "Community 463"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 464 - "Community 464"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 465 - "Community 465"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 466 - "Community 466"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 467 - "Community 467"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 468 - "Community 468"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state., _remove_rls(), upgrade()

### Community 469 - "Community 469"
Cohesion: 0.36
Nodes (7): _assert_downgrade_lossless(), downgrade(), _install_rls(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins., _remove_rls(), upgrade()

### Community 470 - "Community 470"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 471 - "Community 471"
Cohesion: 0.46
Nodes (7): _alter_user_column(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2, _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade(), _user_fk()

### Community 472 - "Community 472"
Cohesion: 0.46
Nodes (7): downgrade(), _hotel_fk(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs., _replace_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade()

### Community 473 - "Community 473"
Cohesion: 0.39
Nodes (7): downgrade(), _ensure_subscription_composite_target(), _has_unique(), _install_rls(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b, _remove_rls(), upgrade()

### Community 474 - "Community 474"
Cohesion: 0.29
Nodes (3): LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default., Telemetry

### Community 475 - "Community 475"
Cohesion: 0.33
Nodes (2): mercadopago_payment_link_webhook(), _mercadopago_webhook_impl()

### Community 476 - "Community 476"
Cohesion: 0.29
Nodes (3): backendURL, receptionistCredentials, TestSession

### Community 477 - "Community 477"
Cohesion: 0.33
Nodes (3): JobDispatcher, _FakeDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 478 - "Community 478"
Cohesion: 0.48
Nodes (6): main(), _peak_resident_bytes(), _percentile(), Measure allocation solver time and process memory on synthetic hotel data.  Run, _resident_bytes(), _scenario()

### Community 479 - "Community 479"
Cohesion: 0.52
Nodes (5): main(), RealtimeMetrics, _run(), run_load(), validate_target()

### Community 480 - "Community 480"
Cohesion: 0.33
Nodes (4): chat_completions(), ChatCompletionRequest, ChatMessage, _extract_latest_user_message()

### Community 481 - "Community 481"
Cohesion: 0.57
Nodes (6): availability_lookup(), create_reservation(), generate_payment_link(), options_with_prices(), price_quote(), WhatsAppBookingError

### Community 482 - "Community 482"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 483 - "Community 483"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 484 - "Community 484"
Cohesion: 0.33
Nodes (1): TestCheckIn

### Community 485 - "Community 485"
Cohesion: 0.57
Nodes (6): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 486 - "Community 486"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 488 - "Community 488"
Cohesion: 0.52
Nodes (6): _auth_for(), A5: GET /api/guests/ already paginated (app/api/guests.py::list_guests) -- skip/, _seed_guests(), test_guest_search_is_partial_ranked_and_searches_phone_without_cross_tenant_leak(), test_list_guests_defaults_to_50_and_pages_through_the_rest(), test_list_guests_pagination_stays_scoped_to_hotel_id()

### Community 489 - "Community 489"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 490 - "Community 490"
Cohesion: 0.29
Nodes (5): Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., TestHotelIsolation

### Community 491 - "Community 491"
Cohesion: 0.71
Nodes (6): _build_client(), _cleanup(), _override_auth(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 492 - "Community 492"
Cohesion: 0.48
Nodes (6): _alembic(), _engine(), _load_migration(), _seed_pre_revision(), test_postgresql_rls_contract_executes_enable_policy_and_downgrade_removal(), test_rbac_expand_contract_round_trip_preserves_safe_legacy_decisions()

### Community 493 - "Community 493"
Cohesion: 0.48
Nodes (6): Tests for the reservation global search filter (B1 header search).  Search is a, _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 494 - "Community 494"
Cohesion: 0.29
Nodes (3): Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro, test_duplicate_room_number_returns_409()

### Community 495 - "Community 495"
Cohesion: 0.43
Nodes (4): RecordingMailer, test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details(), test_staff_role_notice_names_the_hotel_and_both_roles(), test_staff_welcome_notice_contains_access_details_without_capabilities()

### Community 496 - "Community 496"
Cohesion: 0.33
Nodes (2): _Session, test_subscription_session_closes_before_asgi_work()

### Community 497 - "Community 497"
Cohesion: 0.29
Nodes (4): PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on, TestPricePeriodModel

### Community 498 - "Community 498"
Cohesion: 0.29
Nodes (4): The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room., Verify is_wait_listed survives a round-trip through the database., TestWaitlistModelFields

### Community 499 - "Community 499"
Cohesion: 0.48
Nodes (5): _analytics_enum(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260, _reservation_status_enum_new(), _reservation_status_enum_old(), upgrade()

### Community 500 - "Community 500"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 501 - "Community 501"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 502 - "Community 502"
Cohesion: 0.52
Nodes (6): _backfill_authoritative_values(), _columns(), _decode(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea, upgrade()

### Community 503 - "Community 503"
Cohesion: 0.57
Nodes (6): downgrade(), _drop_index_if_present(), _ensure_index(), _index_map(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar, upgrade()

### Community 504 - "Community 504"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op, _remove_rls(), upgrade()

### Community 505 - "Community 505"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat, _remove_rls(), upgrade()

### Community 506 - "Community 506"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what, _remove_rls(), upgrade()

### Community 507 - "Community 507"
Cohesion: 0.48
Nodes (6): downgrade(), _enum_labels(), _quote_identifier(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:, _rename_enum_labels(), upgrade()

### Community 508 - "Community 508"
Cohesion: 0.38
Nodes (5): _pg_cron_migration_enabled(), Delete public form data after 90 days using Supabase Postgres Cron.  Revision ID, Keep early-access lead data behind the trusted application database role., _secure_marketing_leads(), upgrade()

### Community 509 - "Community 509"
Cohesion: 0.43
Nodes (5): _enable_tenant_rls(), _has_fk(), _has_unique(), Harden company nightly charge tenant keys and row level security., upgrade()

### Community 510 - "Community 510"
Cohesion: 0.43
Nodes (6): downgrade(), _event_id_type(), _install_rls(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i, _remove_rls(), upgrade()

### Community 511 - "Community 511"
Cohesion: 0.47
Nodes (5): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 512 - "Community 512"
Cohesion: 0.53
Nodes (5): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online()

### Community 513 - "Community 513"
Cohesion: 0.33
Nodes (5): LaundryRemito, LaundryRemitoLine, LaundryVendor, LaundryVendorPrice, Laundry vendor, pricing and remito (delivery note) models.  An outsourced laundr

### Community 514 - "Community 514"
Cohesion: 0.40
Nodes (6): _model_event_payload(), _model_hotel_id(), queue_model_changes(), Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends., _scalar_event_value()

### Community 515 - "Community 515"
Cohesion: 0.33
Nodes (6): _outbox_backoff_seconds(), publish_pending_domain_events(), Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th

### Community 516 - "Community 516"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 517 - "Community 517"
Cohesion: 0.47
Nodes (5): list_missing_follow_ups(), Neutral operational follow-up for declared laundry remito shortages.  This servi, Return operational details only; deliberately omit all price fields., _serialize_follow_up(), update_missing_follow_up()

### Community 518 - "Community 518"
Cohesion: 0.40
Nodes (5): derive_pepper(), hash_code(), Hash de secretos de corta vida con HMAC-SHA256 (hallazgo N8 del informe).  Hoy `, Deriva el pepper de la clave Fernet existente: no agrega una variable de entorno, verify_code()

### Community 519 - "Community 519"
Cohesion: 0.60
Nodes (5): hotel_chipre_private.purge_operational_data(), PUBLIC, public.domain_event_outbox, public.rate_limit_events, public.security_tokens

### Community 520 - "Community 520"
Cohesion: 0.60
Nodes (5): _link(), Cancelling a reservation must cancel its still-payable seña links (BR §M)., _reservation(), test_cancel_active_links_cancels_payable_and_leaves_terminal(), test_cancel_active_links_noop_when_none_payable()

### Community 522 - "Community 522"
Cohesion: 0.60
Nodes (5): _f003_environment(), test_f003_seed_accepts_only_dedicated_local_fixture_target(), test_f003_seed_rejects_database_outside_its_dedicated_namespace(), test_f003_seed_rejects_sqlite_even_with_opt_in(), test_f003_seed_requires_explicit_opt_in()

### Community 523 - "Community 523"
Cohesion: 0.73
Nodes (5): _manual_payload(), _seed_hotel(), test_foreign_currency_ota_prepayment_is_reported_without_reducing_local_balance(), test_legacy_api_omission_defaults_external_payment_to_reservation_currency(), test_same_currency_ota_prepayment_keeps_existing_balance_credit_behavior()

### Community 524 - "Community 524"
Cohesion: 0.40
Nodes (2): FailingBookingAdapter, test_ota_orchestrator_records_failed_verification()

### Community 526 - "Community 526"
Cohesion: 0.60
Nodes (5): _job_block(), _load_workflow(), Contracts for opting provider-bound PR evidence checks in by label., test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes(), test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled()

### Community 527 - "Community 527"
Cohesion: 0.33
Nodes (1): One operator-entered collection stays idempotent across grouped reservations.

### Community 528 - "Community 528"
Cohesion: 0.53
Nodes (5): _group_payloads(), Atomic multi-room reservation grouping and aggregate balance contracts., test_create_four_room_company_group_and_aggregate_summary(), test_group_rejects_inconsistent_company_and_manual_totals(), test_group_rejects_room_count_outside_bounds()

### Community 529 - "Community 529"
Cohesion: 0.53
Nodes (4): test_env_file_requires_owner_only_permissions(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), _values()

### Community 530 - "Community 530"
Cohesion: 0.53
Nodes (5): _migrate(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi, test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), _unique_column_sets()

### Community 531 - "Community 531"
Cohesion: 0.73
Nodes (5): _plan_values(), _run_alembic(), test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(), test_price_migration_downgrade_restores_preexisting_currency_and_period(), test_publishes_approved_prices_without_overwriting_admin_values()

### Community 532 - "Community 532"
Cohesion: 0.33
Nodes (5): Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in.

### Community 533 - "Community 533"
Cohesion: 0.33
Nodes (5): Cannot checkout a PENDING reservation., Cannot checkout a PENDING reservation., Cannot checkout a PENDING reservation., Cannot checkout a PENDING reservation., Cannot checkout a PENDING reservation.

### Community 534 - "Community 534"
Cohesion: 0.33
Nodes (5): Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se

### Community 535 - "Community 535"
Cohesion: 0.60
Nodes (5): _request(), test_accepts_body_at_exact_limit(), test_rejects_chunked_body_that_exceeds_limit(), test_rejects_malformed_content_length(), test_rejects_oversized_content_length_before_reading_body()

### Community 536 - "Community 536"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 537 - "Community 537"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 538 - "Community 538"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 539 - "Community 539"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), seed section visibility permissions and their role defaults  Revision ID: 202608, upgrade()

### Community 540 - "Community 540"
Cohesion: 0.60
Nodes (5): downgrade(), _has_column(), _has_table(), Fold legacy category pricing into seasonal price periods., upgrade()

### Community 541 - "Community 541"
Cohesion: 0.60
Nodes (5): downgrade(), Align section defaults and remove the self-session catalog permission.  Revision, _restore_session_permission(), _set_role_default(), upgrade()

### Community 542 - "Community 542"
Cohesion: 0.47
Nodes (5): downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns., _set_role_default(), upgrade()

### Community 543 - "Community 543"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083, upgrade()

### Community 544 - "Community 544"
Cohesion: 0.53
Nodes (5): downgrade(), _has_columns(), _indexes(), Add check-in policy, manual receipt references, and auditable refunds., upgrade()

### Community 545 - "Community 545"
Cohesion: 0.47
Nodes (5): downgrade(), _install_rls(), Add tenant-scoped groups for multi-room reservations., _remove_rls(), upgrade()

### Community 546 - "Community 546"
Cohesion: 0.47
Nodes (5): downgrade(), _install_rls(), linen location par levels  Revision ID: 41d66acfb13a Revises: 015f7e36b9cd Creat, _remove_rls(), upgrade()

### Community 547 - "Community 547"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 548 - "Community 548"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 549 - "Community 549"
Cohesion: 0.50
Nodes (3): create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, _request_source()

### Community 550 - "Community 550"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 551 - "Community 551"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceRead, GuestRoomAvoidanceResolveRequest, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 552 - "Community 552"
Cohesion: 0.60
Nodes (4): login(), Closed-loop load test: N virtual users, each loops over a request mix with think, run(), vu()

### Community 553 - "Community 553"
Cohesion: 0.50
Nodes (3): _prepare_environment(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2, seed()

### Community 554 - "Community 554"
Cohesion: 0.60
Nodes (4): flush(), handle(), main(), pipe()

### Community 555 - "Community 555"
Cohesion: 0.40
Nodes (3): duplicate_laundry_remitos(), Read-only duplicate detection shared by migration and operator tooling., Return normalized duplicate remito groups, including every row id.      Service

### Community 556 - "Community 556"
Cohesion: 0.80
Nodes (4): ensure_active_owner(), _lock_active_owner_memberships(), transfer_primary_owner(), validate_membership_change()

### Community 557 - "Community 557"
Cohesion: 0.70
Nodes (4): _canonical_hash(), create_reservation_group_payment(), get_group_payment_batch(), _read_batch()

### Community 558 - "Community 558"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 559 - "Community 559"
Cohesion: 0.50
Nodes (3): _override_auth(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t, test_receptionist_can_get_price_quote()

### Community 560 - "Community 560"
Cohesion: 0.60
Nodes (4): Alembic round-trip for the additive local business-clock table., _run_alembic(), test_local_business_clock_migration_adds_and_drops_only_its_table(), test_local_business_clock_migration_adopts_existing_bootstrap_table()

### Community 561 - "Community 561"
Cohesion: 0.60
Nodes (4): _assert_columns(), SQLite round-trip for company extension request fields., _run_alembic(), test_company_extension_request_migration_upgrade_downgrade_upgrade()

### Community 562 - "Community 562"
Cohesion: 0.60
Nodes (4): _load_migration(), SQLite migration coverage for configurable USD conversion sides., _side_columns(), test_fx_conversion_side_migration_backfills_defaults_and_round_trips_safely()

### Community 563 - "Community 563"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 564 - "Community 564"
Cohesion: 0.60
Nodes (4): _assert_schema(), SQLite migration round-trip for bounded manual reservation rates., _run_alembic(), test_manual_rate_policy_migration_upgrade_downgrade_upgrade()

### Community 565 - "Community 565"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 567 - "Community 567"
Cohesion: 0.40
Nodes (4): Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING.

### Community 568 - "Community 568"
Cohesion: 0.40
Nodes (4): Cannot pay more than the outstanding balance., Cannot pay more than the outstanding balance., Cannot pay more than the outstanding balance., Cannot pay more than the outstanding balance.

### Community 569 - "Community 569"
Cohesion: 0.40
Nodes (4): Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation.

### Community 570 - "Community 570"
Cohesion: 0.40
Nodes (4): Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method.

### Community 571 - "Community 571"
Cohesion: 0.40
Nodes (4): Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials.

### Community 572 - "Community 572"
Cohesion: 0.40
Nodes (4): A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t

### Community 573 - "Community 573"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 574 - "Community 574"
Cohesion: 0.60
Nodes (4): _assert_permission_defaults(), SQLite round-trip for the configurable reservation price permission., _run_alembic(), test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade()

### Community 575 - "Community 575"
Cohesion: 0.60
Nodes (4): _assert_transfer_schema(), SQLite migration round-trip for linked stock transfer movements., _run_alembic(), test_stock_transfer_migration_upgrade_downgrade_upgrade()

### Community 576 - "Community 576"
Cohesion: 0.40
Nodes (4): §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in.

### Community 577 - "Community 577"
Cohesion: 0.40
Nodes (4): Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False).

### Community 578 - "Community 578"
Cohesion: 0.40
Nodes (4): When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error.

### Community 580 - "Community 580"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 581 - "Community 581"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 582 - "Community 582"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 583 - "Community 583"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima, upgrade()

### Community 584 - "Community 584"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs, upgrade()

### Community 585 - "Community 585"
Cohesion: 0.60
Nodes (4): downgrade(), _install_purge_function(), Backfill the public inquiry retention clock and update the purge function.  Revi, upgrade()

### Community 586 - "Community 586"
Cohesion: 0.60
Nodes (4): _check_clause(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in, upgrade()

### Community 587 - "Community 587"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 588 - "Community 588"
Cohesion: 0.50
Nodes (3): Add durable job dedupe and worker heartbeat metadata., _rls(), upgrade()

### Community 589 - "Community 589"
Cohesion: 0.67
Nodes (3): main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only.

### Community 590 - "Community 590"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 591 - "Community 591"
Cohesion: 0.83
Nodes (3): main(), run(), validate_json()

### Community 592 - "Community 592"
Cohesion: 0.83
Nodes (3): main(), _non_empty(), validate_manifest()

### Community 593 - "Community 593"
Cohesion: 0.83
Nodes (3): outbox_count(), step(), timing()

### Community 594 - "Community 594"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 595 - "Community 595"
Cohesion: 0.50
Nodes (4): RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, test_register_rejects_malformed_email()

### Community 596 - "Community 596"
Cohesion: 0.50
Nodes (4): .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, test_register_rejects_reserved_test_tld_outside_test_mode()

### Community 597 - "Community 597"
Cohesion: 0.50
Nodes (4): The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, test_register_accepts_reserved_test_tld_in_test_mode()

### Community 598 - "Community 598"
Cohesion: 0.50
Nodes (4): A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j, test_self_registration_cannot_grant_platform_admin_role()

### Community 599 - "Community 599"
Cohesion: 0.83
Nodes (3): _load_migration(), _market_columns(), test_fx_direction_market_migration_preserves_global_market_and_guards_downgrade()

### Community 600 - "Community 600"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 602 - "Community 602"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 603 - "Community 603"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 604 - "Community 604"
Cohesion: 0.67
Nodes (3): _alembic(), Regression coverage for the additive movement-group permission migration., test_migration_seeds_dedicated_permission_and_safe_role_defaults()

### Community 605 - "Community 605"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t, test_process_outbox_delivers_across_every_active_hotel()

### Community 607 - "Community 607"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 608 - "Community 608"
Cohesion: 0.67
Nodes (3): _index_names(), Focused regression tests for the TECH-0063 OLTP audit fixes., test_hot_path_composite_indexes_exist_in_models()

### Community 609 - "Community 609"
Cohesion: 0.50
Nodes (3): Tests for V72 §9 — Waitlist and Overbooking.  Key implementation details discove, Hotel with one Standard room.  Returns a dict with keys:       config, category_, tiny_hotel()

### Community 610 - "Community 610"
Cohesion: 0.83
Nodes (3): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link()

### Community 611 - "Community 611"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 612 - "Community 612"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 613 - "Community 613"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 614 - "Community 614"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 615 - "Community 615"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 616 - "Community 616"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 617 - "Community 617"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 618 - "Community 618"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 619 - "Community 619"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 620 - "Community 620"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 621 - "Community 621"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 622 - "Community 622"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 623 - "Community 623"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 624 - "Community 624"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 625 - "Community 625"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 626 - "Community 626"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 627 - "Community 627"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 628 - "Community 628"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 629 - "Community 629"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 630 - "Community 630"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 631 - "Community 631"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 632 - "Community 632"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 633 - "Community 633"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 634 - "Community 634"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 635 - "Community 635"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 636 - "Community 636"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 637 - "Community 637"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 638 - "Community 638"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 639 - "Community 639"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 640 - "Community 640"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 641 - "Community 641"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 642 - "Community 642"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 643 - "Community 643"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 644 - "Community 644"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 645 - "Community 645"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 646 - "Community 646"
Cohesion: 0.67
Nodes (1): owner

### Community 647 - "Community 647"
Cohesion: 0.67
Nodes (1): Tenant-scoped custom roles layered over a built-in permission profile.

### Community 648 - "Community 648"
Cohesion: 0.67
Nodes (1): Persisted staff invitations and their one-time acceptance state.

### Community 649 - "Community 649"
Cohesion: 0.67
Nodes (1): Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati

### Community 650 - "Community 650"
Cohesion: 0.67
Nodes (3): Metadata returned by the server-side Embedded Signup exchange., Metadata returned by the server-side Embedded Signup exchange., WhatsAppChannelComplete

### Community 651 - "Community 651"
Cohesion: 1.00
Nodes (2): build_gemma_hotel_context(), _enum_value()

### Community 653 - "Community 653"
Cohesion: 0.67
Nodes (1): FakeResponse

### Community 655 - "Community 655"
Cohesion: 0.67
Nodes (2): Verify the hotel has exactly 38 rooms., Verify the hotel has exactly 38 rooms.

### Community 656 - "Community 656"
Cohesion: 0.67
Nodes (2): Same room_number can exist in different hotels without conflict., Same room_number can exist in different hotels without conflict.

### Community 657 - "Community 657"
Cohesion: 0.67
Nodes (2): Verify room string representation., Verify room string representation.

### Community 659 - "Community 659"
Cohesion: 0.67
Nodes (2): Trying to resolve with a non-existent room raises ReservationError., Trying to resolve with a non-existent room raises ReservationError.

### Community 661 - "Community 661"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 662 - "Community 662"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 663 - "Community 663"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 665 - "Community 665"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 666 - "Community 666"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 674 - "Community 674"
Cohesion: 1.00
Nodes (1): Tier-2: active PricePeriod used when no DailyRate exists.

## Knowledge Gaps
- **2268 isolated node(s):** `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.` (+2263 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 107`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 229`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 268`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 269`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 297`** (1 nodes): `Local hotel-scoped business clock API and date isolation coverage.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 308`** (2 nodes): `HotelConfigUpdate`, `_normalize_currency()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 433`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 441`** (2 nodes): `35c9420 docs(audit): lectura completa de modelos, servicios, API, tareas, adapters, schemas y panel master`, `Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 475`** (2 nodes): `mercadopago_payment_link_webhook()`, `_mercadopago_webhook_impl()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 484`** (1 nodes): `TestCheckIn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 496`** (2 nodes): `_Session`, `test_subscription_session_closes_before_asgi_work()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 524`** (2 nodes): `FailingBookingAdapter`, `test_ota_orchestrator_records_failed_verification()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 527`** (1 nodes): `One operator-entered collection stays idempotent across grouped reservations.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 602`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 611`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 612`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 613`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 614`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 615`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 616`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 617`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 618`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 619`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 620`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 621`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 622`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 623`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 624`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 625`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 626`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 627`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 628`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 629`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 630`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 631`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 632`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 633`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 634`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 635`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 636`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 637`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 638`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 639`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 640`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 641`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 642`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 643`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 644`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 645`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 646`** (1 nodes): `owner`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 647`** (1 nodes): `Tenant-scoped custom roles layered over a built-in permission profile.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 648`** (1 nodes): `Persisted staff invitations and their one-time acceptance state.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 649`** (1 nodes): `Fast server-side EXPLAIN ANALYZE probe for hot queries on real PostgreSQL.  Rati`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 651`** (2 nodes): `build_gemma_hotel_context()`, `_enum_value()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 653`** (1 nodes): `FakeResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 655`** (2 nodes): `Verify the hotel has exactly 38 rooms.`, `Verify the hotel has exactly 38 rooms.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 656`** (2 nodes): `Same room_number can exist in different hotels without conflict.`, `Same room_number can exist in different hotels without conflict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 657`** (2 nodes): `Verify room string representation.`, `Verify room string representation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 659`** (2 nodes): `Trying to resolve with a non-existent room raises ReservationError.`, `Trying to resolve with a non-existent room raises ReservationError.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 661`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 662`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 663`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 665`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 666`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 674`** (1 nodes): `Tier-2: active PricePeriod used when no DailyRate exists.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 12` to `Community 5`, `Community 512`, `Community 409`, `Community 76`, `Community 98`, `Community 150`, `Community 116`, `Community 151`, `Community 240`, `Community 62`, `Community 46`, `Community 65`, `Community 4`, `Community 43`, `Community 3`, `Community 94`, `Community 50`, `Community 88`, `Community 1`, `Community 8`, `Community 288`, `Community 26`, `Community 241`, `Community 6`, `Community 381`, `Community 7`, `Community 71`, `Community 30`, `Community 147`, `Community 9`, `Community 13`, `Community 21`, `Community 647`, `Community 45`, `Community 648`, `Community 286`, `Community 513`, `Community 101`, `Community 117`, `Community 189`, `Community 79`, `Community 229`, `Community 27`, `Community 33`, `Community 121`, `Community 118`, `Community 179`, `Community 190`, `Community 2`, `Community 68`, `Community 290`, `Community 70`, `Community 199`, `Community 0`, `Community 82`, `Community 109`, `Community 63`, `Community 38`, `Community 180`, `Community 95`, `Community 414`?**
  _High betweenness centrality (0.097) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 4` to `Community 8`, `Community 12`, `Community 15`, `Community 50`, `Community 3`, `Community 9`, `Community 1`, `Community 13`, `Community 147`, `Community 150`, `Community 43`, `Community 65`, `Community 101`, `Community 190`, `Community 417`, `Community 199`, `Community 33`, `Community 37`, `Community 46`, `Community 79`, `Community 121`, `Community 2`, `Community 185`, `Community 63`, `Community 201`, `Community 6`, `Community 94`, `Community 191`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 1` to `Community 5`, `Community 12`, `Community 15`, `Community 50`, `Community 3`, `Community 27`, `Community 46`, `Community 62`, `Community 4`, `Community 65`, `Community 101`, `Community 88`, `Community 449`, `Community 71`, `Community 33`, `Community 118`, `Community 179`, `Community 81`, `Community 199`, `Community 82`, `Community 38`, `Community 481`, `Community 190`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Are the 601 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`HotelConfiguration` has 601 INFERRED edges - model-reasoned connections that need verification._
- **Are the 593 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Reservation` has 593 INFERRED edges - model-reasoned connections that need verification._
- **Are the 482 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`ReservationStatusEnum` has 482 INFERRED edges - model-reasoned connections that need verification._
- **Are the 434 inferred relationships involving `Base` (e.g. with `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` and `Demo-only utilities: seed sample data and reset the database. Exposed only when`) actually correct?**
  _`Base` has 434 INFERRED edges - model-reasoned connections that need verification._