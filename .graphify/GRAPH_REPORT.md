# Graph Report - .  (2026-10-25)

## Corpus Check
- Large corpus: 1755 files · ~2,556,575 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 18248 nodes · 70677 edges · 750 communities detected
- Extraction: 53% EXTRACTED · 47% INFERRED · 0% AMBIGUOUS · INFERRED: 33064 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: uses: 33064 · contains: 10719 · calls: 8389 · MODIFIES: 5839 · rationale_for: 4686 · ON_BRANCH: 2001 · imports: 1911 · imports_from: 1503 · inherits: 1038 · method: 976 · PARENT_OF: 543 · re_exports: 4 · reads_from: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 1755 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 15 sensitive · 0 missing committed

## Graph Freshness
- Built from Git commit: `563ddc0`
- Compare this hash to `git rev-parse HEAD` before trusting freshness-sensitive graph output.
## God Nodes (most connected - your core abstractions)
1. `Reservation` - 1413 edges
2. `HotelConfiguration` - 1363 edges
3. `ReservationStatusEnum` - 1288 edges
4. `Room` - 1026 edges
5. `RoomCategory` - 820 edges
6. `Guest` - 757 edges
7. `Company` - 755 edges
8. `ReservationSourceEnum` - 708 edges
9. `AuditActionEnum` - 704 edges
10. `SecurityAuditLog` - 698 edges

## Surprising Connections (you probably didn't know these)
- `Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som` --uses--> `Base`  [INFERRED]
  alembic/env.py → app/database.py
- `Introspect the real SQLAlchemy metadata: tables, columns, types, indexes, FKs.` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/schema_audit.py → app/database.py
- `Comprueba tres hallazgos de la lectura completa contra la app real (PostgreSQL m` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/verify_misc_findings.py → app/database.py
- `Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post` --uses--> `Base`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/audit_loss_repro.py → app/database.py
- `Repro: el registro de auditoría escrito DESPUÉS de db.commit() se pierde en Post` --uses--> `AuditLog`  [INFERRED]
  docs/audits/perf-2026-10-13/scripts/audit_loss_repro.py → app/models/audit_log.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (478): availability(), price_quote(), Lightweight availability placeholder. When all parameters are provided,     it r, Lightweight availability placeholder. When all parameters are provided,     it r, Ensure computed fields land in the response., Ensure computed fields land in the response., Calculate pricing for a potential booking without persisting it.     Uses the ca, Lightweight availability placeholder. When all parameters are provided,     it r (+470 more)

### Community 1 - "Community 1"
Cohesion: 0.01
Nodes (194): authorize_manual_rate_scope(), Payload-conditional authorization for manual reservation rates., Return the strongest manual-rate capability the actor currently has., 0ddeb59 Fix day 2 hotel simulation findings (#114), 194af4d fix(reservations): search guests by name/DNI instead of raw ID field, 2bbe038 Merge remote-tracking branch 'origin/main' into codex/clarify-mfa-code, 7899f9d Stabilize day 2 regression suite and mobile navigation, 98dce04 feat(nav): collapse 29-item menu to 5 daily links + collapsible groups (B6.1) (+186 more)

### Community 2 - "Community 2"
Cohesion: 0.01
Nodes (316): ApiKeyPurpose, HotelApiKey, HotelApiKeyIssued, issueApiKey(), IssueHotelApiKeyPayload, listApiKeys(), revokeApiKey(), AuthUser (+308 more)

### Community 3 - "Community 3"
Cohesion: 0.01
Nodes (163): main(), validate(), _DecimalAwareEncoder, _is_database_pool_timeout(), Hotel PMS — FastAPI Main Application. Serves the API + bundled frontend files., security_headers(), 46969e1 Improve PMS efficiency and deposit policies [skip render], 56a2230 Merge pull request #127 from Maximo-Paulos/refactor/pms-efficiency-remediation (+155 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (372): PaymentSurchargeCreate, PaymentSurchargeRead, PaymentSurchargeUpdate, Payment surcharges API - v72 section 12.3.  GET    /api/payment-surcharges, Return the exact amount to collect and any FX/cash suggestion details., download_payment_receipt_pdf(), email_payment_receipt(), payment_receipt_data() (+364 more)

### Community 5 - "Community 5"
Cohesion: 0.01
Nodes (303): AllocationRunPayload, AllocationRunResponse, listRoomMovementGroups(), revertRoomMovementGroup(), RoomMoveEvent, RoomMovementGroup, triggerAllocationRecalculation(), SessionLike (+295 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (365): apply_period_to_daily_rates(), ApplyPeriodOut, _bulk_field_value(), bulk_update_daily_rate_field(), bulk_upsert_daily_rates(), BulkFieldRateIn, BulkRateIn, BulkRateOut (+357 more)

### Community 7 - "Community 7"
Cohesion: 0.01
Nodes (169): bootstrap_configuration_fingerprint(), BootstrapConfigurationError, Shared, secret-safe binding for the Render QA bootstrap configuration., Hash the exact provider-observed values without exposing them individually., create_fx_snapshot(), FxRateItem, FxRateUsdOficial, FxSnapshotCreateResponse (+161 more)

### Community 8 - "Community 8"
Cohesion: 0.02
Nodes (316): Apply the separate approval capability only when closing requires it., Apply the separate approval capability only when closing requires it., Export the existing transaction/cash ledger without creating a second balance., Export the existing transaction/cash ledger without creating a second balance., Apply the separate approval capability only when closing requires it., Apply the separate approval capability only when closing requires it., _require_cash_difference_approval_when_requested(), CashExpense (+308 more)

### Community 9 - "Community 9"
Cohesion: 0.01
Nodes (176): Manage and inspect per-night extras on corporate reservations., Staff management endpoints for hotel public API keys., _collect_realtime_events_after_flush(), _discard_realtime_events_after_rollback(), _discard_realtime_events_after_root_soft_rollback(), _estimate_parameter_bytes(), finish_request_db_metrics(), _publish_realtime_events_after_commit() (+168 more)

### Community 10 - "Community 10"
Cohesion: 0.10
Nodes (298): FastAPI routes for Booking management (thin layer over Reservation). Provides ba, Ensure computed fields land in the response., Ensure computed fields land in the response., Ensure computed fields land in the response., Create and inspect groups of independently billed hotel reservations., add_reservation_guests(), _authorize_company_reservation_management(), _can_view_guest_documents() (+290 more)

### Community 11 - "Community 11"
Cohesion: 0.02
Nodes (248): Demo-only utilities: seed sample data and reset the database. Exposed only when, fix/local-simulation-workflows, main, refactor/app-quality-audit, refactor/pms-efficiency-remediation, 009a9ed docs(tech-0140): pin final local verification, 0174f49 Document post-deploy read-only smoke results, 02102f9 docs(audit): incorpora la verificación por un segundo lector (262 afirmaciones: 198 confirmadas, 64 corregidas) (+240 more)

### Community 12 - "Community 12"
Cohesion: 0.03
Nodes (241): codex/production-render-qa, codex/public-site-inquiries, docs/auditoria-pms-20260908, feature/operational-audit-cash-daily, feature/secure-auth-marketing-release-20260926, 00af83e chore(graphify): regenerate graph after B4 manual OTA + manual tarifa + B4.2, 0254334 Merge branch 'agent-ux' into codex/feature/pms-e2e-scale-hardening, 04cd07c feat(reservations): wire global reservation access into header, dashboard and guests (+233 more)

### Community 13 - "Community 13"
Cohesion: 0.01
Nodes (194): FxConversionQuoteRequest, BaseModel, ActiveAllocationPolicyRead, AllocationFeedbackDraftRequest, AllocationPolicySuggestionApplyRequest, AllocationPolicySuggestionApplyResponse, AllocationPolicySuggestionCreate, AllocationPolicySuggestionRead (+186 more)

### Community 14 - "Community 14"
Cohesion: 0.01
Nodes (126): _authorize_override(), checkin(), checkin_guest(), checkout(), _reservation_read(), DailyReportSchedule, DailyReportScheduleUpdate, get_daily_report_schedule() (+118 more)

### Community 15 - "Community 15"
Cohesion: 0.02
Nodes (172): Base, Base class for all ORM models., Base class for all ORM models., Base, DeclarativeBase, Auditable, tenant-scoped approval records for manual reservation cancellation., CashCloseReport, CashCustodyHandoff (+164 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (174): _assert_manageable_membership(), _assert_role_profile_mutation_allowed(), consume_temporary_action_grant(), Thin FastAPI transport for the tenant-scoped permission service., Keep ownership-role cells immutable except the owner's explicit rate control., Keep ownership-role cells immutable except the owner's explicit rate control., Keep permission exceptions aligned with the staff-management boundary., Keep permission exceptions aligned with the staff-management boundary. (+166 more)

### Community 17 - "Community 17"
Cohesion: 0.02
Nodes (103): list_countries(), list_timezones(), Reference data endpoints used by the frontend., Return the cached IANA timezone catalog., Return the curated country -> primary IANA timezone catalog., ReferenceCountry, listCountries(), ReferenceCountry (+95 more)

### Community 18 - "Community 18"
Cohesion: 0.03
Nodes (139): _allow_mfa_attempt(), apple_callback(), _apple_full_name(), apple_login(), _apple_login_config(), apple_start(), _attach_user_session_cookies(), _audit_security_event() (+131 more)

### Community 19 - "Community 19"
Cohesion: 0.05
Nodes (134): _build_authorization_check(), Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Adapt sync and async streams to ASGI disconnects and always close them., Recover invalidation domains after a cursor without exposing payloads., Stream tenant-scoped invalidation signals; clients refetch from Postgres-backed, Revalidate stream access while tolerating a brief database pool outage.      The, recover_domain_events() (+126 more)

### Community 20 - "Community 20"
Cohesion: 0.02
Nodes (44): approve_cash_close_difference(), approve_cash_expense_route(), _cash_expense_read(), cash_session_close_report(), close_cash_session(), _close_report_read(), confirm_cash_custody_receipt(), _csv_decimal() (+36 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (120): Public booking-engine API authenticated only with hotel API keys., Coarse payment status derived from amounts (no sensitive detail)., Read-only reservation/payment status by confirmation code (v72 §16).      Scoped, Read-only reservation/payment status by id (v72 §16).      Scoped to the API key, PublicAPIContext, BillingAdjustmentTypeEnum, Operational reservation models for adjustments, room moves and audit history., ReservationAdjustment (+112 more)

### Community 22 - "Community 22"
Cohesion: 0.04
Nodes (75): ApiError, fetchPublicPricing(), LeadPayload, PublicPricing, PublicPricingPlan, submitLead(), getOnboardingStatus(), BrandMark() (+67 more)

### Community 23 - "Community 23"
Cohesion: 0.03
Nodes (62): _derive_payment_status(), public_reservation_status(), public_reservation_status_by_code(), _serialize_reservation_status(), 654d69e Add reservation arrival metadata and internal comments, 8845d08 Fix eight real defects found auditing the whole project, 8c239da Merge pull request #100 from Maximo-Paulos/feature/reservation-arrival-comment, frontendRoot (+54 more)

### Community 24 - "Community 24"
Cohesion: 0.05
Nodes (65): booking_webhook(), despegar_webhook(), expedia_webhook(), _guarded_json_payload(), _handle_ota_webhook(), _log_ota_processing_failure(), FastAPI Webhook endpoints for OTA integrations., Receive reservation notifications from Booking.com. (+57 more)

### Community 25 - "Community 25"
Cohesion: 0.09
Nodes (89): AnalyticsExportFormatEnum, AnalyticsExportJob, AnalyticsExportStatusEnum, StoredObjectStatusEnum, AnalyticsExportJobRead, AnalyticsExportRequest, get_export_bytes(), get_export_file() (+81 more)

### Community 26 - "Community 26"
Cohesion: 0.06
Nodes (90): Lightweight subscription tracking for enforcement and auditing (v2 tables)., Immutable ledger entry for a subscription discount or override.      This table, Subscription, SubscriptionAdjustment, SubscriptionEvent, _actor_payload(), _actor_role(), _actor_user_id() (+82 more)

### Community 27 - "Community 27"
Cohesion: 0.03
Nodes (66): AnalyticsAIChatPage(), AnalyticsAIChatResponse, AnalyticsAIStatus, AnalyticsEnvelope, analyticsErrorMessage(), AnalyticsFilterState, AnalyticsFreshness(), AnalyticsHomePage() (+58 more)

### Community 28 - "Community 28"
Cohesion: 0.04
Nodes (76): assignWhatsAppConversation(), completeWhatsAppChannel(), createWhatsAppNote(), channel_status(), complete_channel(), create_note(), inbox(), Authenticated human WhatsApp CRM inbox.  This router never calls Meta directly. (+68 more)

### Community 29 - "Community 29"
Cohesion: 0.08
Nodes (83): ReservationAllocationLock, FxRateSnapshot, GuestRoomAvoidance, GuestRoomAvoidanceStatusEnum, Tenant-scoped room rejections recorded for an individual guest., A guest's active or resolved rejection of one physical room.      ``RoomMoveEven, Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).     Suppo, Groups multiple RoomMoveEvents triggered by the same cause (v72 §5.4).     Suppo (+75 more)

### Community 30 - "Community 30"
Cohesion: 0.02
Nodes (82): 9899fcf Add the master-admin pricing editor, PermissionGate(), MasterAdminProtectedShell(), MasterAdminRoot(), navItems, MasterAdminSessionProvider(), PricingPage(), TermsPage() (+74 more)

### Community 31 - "Community 31"
Cohesion: 0.07
Nodes (83): ActionStepUpTicketUse, Tenant-scoped replay ledger for MFA step-up tickets., Persist only the random ticket id and action binding after first use., Permission, Security / access audit log — free-form operational security events.  Distinct f, SecurityAuditLog, Tenant-scoped, single-use temporary authorization grants., One short-lived authorization for one requester and one permission. (+75 more)

### Community 32 - "Community 32"
Cohesion: 0.17
Nodes (80): OTAConnection, OTAProvider, OTARatePlanMapping, OTAReservationLifecycleEnum, OTAReservationLink, OTARoomMapping, OTAReservationMapping, OTASyncStatusEnum (+72 more)

### Community 33 - "Community 33"
Cohesion: 0.04
Nodes (73): BuiltinPermissionRole, EffectivePermissionsResponse, fetchEffectivePermissions(), fetchPermissionCatalog(), fetchPermissionMatrix(), fetchRolePermissionProfiles(), fetchUserPermissionOverrides(), fetchVisibilityWindows() (+65 more)

### Community 34 - "Community 34"
Cohesion: 0.14
Nodes (56): create_laundry_remito(), _housekeeping_remito(), LaundryDiscrepancyAction, LaundryDiscrepancyRead, LaundryDiscrepancyResolve, LinenItemCreate, LinenItemRead, LinenLocationBalanceRead (+48 more)

### Community 35 - "Community 35"
Cohesion: 0.04
Nodes (50): main(), normalize_instruction_paths(), Replace this repository's absolute root in generated instructions only., ca694f7 feat(rbac,config,perf): permission-driven visibility, dedup sweep and infra readiness, Per-role reservation visibility windows for one hotel., _active_tag_filter(), add_tag(), _audit() (+42 more)

### Community 36 - "Community 36"
Cohesion: 0.05
Nodes (65): _complete_master_login(), _configure_resend(), FakeResponse, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, A genuine Stripe retry (network timeout, no ack received) redelivers the     SAM, If MASTER_ADMIN_EMAIL happens to collide with a real tenant's login     email (a (+57 more)

### Community 37 - "Community 37"
Cohesion: 0.05
Nodes (69): addCashMovement(), approveCashCloseDifference(), approveCashExpense(), CashCloseReport, CashCustodyHandoff, CashCustodyReceiptPayload, CashDailyCollector, CashDailyEntry (+61 more)

### Community 38 - "Community 38"
Cohesion: 0.04
Nodes (37): DepositPolicyRule, DepositPolicyRules, CategoryPayload, DepositPolicyPayload, finishOnboarding(), HotelIdentityPayload, OnboardingProviderSetup, OnboardingStatus (+29 more)

### Community 39 - "Community 39"
Cohesion: 0.05
Nodes (53): Rate limiter with DB-backed persistence for security-sensitive endpoints.  When, PublicInquiryPayload, PublicInquiryResponse, submitPublicInquiry(), 09d0b08 feat(marketing): secure inquiries and enforce 90-day retention, 9306eb5 Add public marketing inquiry flow and SEO, b48fd42 Add public marketing inquiry flow and SEO, APP_URL_HOSTNAME (+45 more)

### Community 40 - "Community 40"
Cohesion: 0.04
Nodes (39): confirm_stock_count(), create_movement(), createStockItem(), createStockLocation(), createStockMovement(), createStockOpeningCount(), createStockTransfer(), CurrentStock (+31 more)

### Community 41 - "Community 41"
Cohesion: 0.05
Nodes (66): LaundryDiscrepancyAction, LaundryRemitoDiscrepancy, Auditable custody records for linen differences reported on laundry remitos.  Di, Immutable action history and hotel-scoped idempotency for discrepancy decisions., _action_replay(), approve_discrepancy(), _audit_discrepancy(), confirm_discrepancy_return_to_laundry() (+58 more)

### Community 42 - "Community 42"
Cohesion: 0.09
Nodes (69): _analytics_window(), build_category_detail_payload(), build_channels_breakdown(), build_channels_payload(), build_home_payload(), build_operations_payload(), build_room_detail_payload(), build_rooms_detail_breakdown() (+61 more)

### Community 43 - "Community 43"
Cohesion: 0.09
Nodes (59): _json_dict(), preview_room_block_allocation(), preview_room_block_conflicts_endpoint(), preview_room_block_extension_allocation(), Return counts only; guest identity and reservation IDs are not needed for this w, Return counts only; guest identity and reservation IDs are not needed for this w, RoomBlockAllocationPreviewRead, RoomBlockConflictPreview (+51 more)

### Community 44 - "Community 44"
Cohesion: 0.04
Nodes (44): clearMasterAdminCsrfToken(), masterAdminFetch(), MasterAdminLoginResponse, MasterAdminLoginResult, MasterAdminMfaChallengeResponse, MasterAdminMfaEnrollment, MasterAdminMfaRecoveryCodes, MasterAdminMfaSetupResponse (+36 more)

### Community 45 - "Community 45"
Cohesion: 0.04
Nodes (56): approveLaundryDiscrepancy(), confirmLaundryDiscrepancyReturn(), createLaundryRemito(), createLaundryVendor(), getLaundryVendorBalance(), getLaundryVendorSettlements(), getLaundryVendorSpend(), LaundryDiscrepancy (+48 more)

### Community 46 - "Community 46"
Cohesion: 0.05
Nodes (48): _event_engine(), FakeRedis, _isolate_realtime_configuration(), A minimal SQLite engine with just the tables the after_commit hook writes to., Keep Redis-default event tests independent of other test modules., A minimal SQLite engine with just the tables the after_commit hook writes to., Share the in-memory SQLite connection with async iterator worker threads., _settings() (+40 more)

### Community 47 - "Community 47"
Cohesion: 0.06
Nodes (56): getMfaStatus(), mfaStatusQueryKey(), ActionStepUpChallenge, ActionStepUpHandler, actionStepUpQueue, ActionStepUpTicket, apiFetch(), buildAuthHeaders() (+48 more)

### Community 48 - "Community 48"
Cohesion: 0.04
Nodes (32): GCSObjectStorage, get_object_storage(), LocalObjectStorage, ObjectStat, ObjectStorage, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar, Stub for a real S3-compatible bucket. Not wired to a live bucket --     there ar, Google Cloud Storage adapter with lazy optional dependency loading. (+24 more)

### Community 49 - "Community 49"
Cohesion: 0.10
Nodes (64): _client(), _close(), _patch_legacy_booking(), test_bounded_unpaid_total_adjustment_fails_closed_without_manual_rate_policy(), test_bounded_unpaid_total_adjustment_fails_closed_without_trusted_quote(), test_bounded_unpaid_total_adjustment_rejects_amount_outside_configured_range(), test_bounded_unpaid_total_adjustment_requires_same_currency_as_current_quote(), test_category_product_compatibility_is_checked_after_permission() (+56 more)

### Community 50 - "Community 50"
Cohesion: 0.18
Nodes (52): CompanyOptionRead, Return only the names needed to link a reservation to a company., AnalyticsAIUsageMonthly, AnalyticsAlertSetting, AnalyticsAlertSnooze, AnalyticsCurrencyDisplayEnum, FactReservationDaily, FactReservationRowKindEnum (+44 more)

### Community 51 - "Community 51"
Cohesion: 0.06
Nodes (52): _clickhouse_healthcheck(), _critical_lock_readiness(), _database_healthcheck(), datastores_healthcheck(), live_healthcheck(), _postgres_healthcheck(), Report whether the API can safely accept critical writes., Process liveness only; never depends on PostgreSQL or Redis. (+44 more)

### Community 52 - "Community 52"
Cohesion: 0.05
Nodes (47): ActiveRoomBlockItem, ArrivalCount, AvailableWithReviewItem, booked_value_report(), BookedValueReport, CashSessionStatusRead, CurrencyAmount, DailyOperationalReport (+39 more)

### Community 53 - "Community 53"
Cohesion: 0.07
Nodes (59): _apply_corporate_pricing(), _apply_custom_deposit_amount(), _apply_date_change_pricing(), _apply_manual_total_override(), _apply_pricing_result_to_reservation(), assert_reservation_version(), calculate_reservation_pricing(), _calendar_pricing_source() (+51 more)

### Community 54 - "Community 54"
Cohesion: 0.05
Nodes (48): collaboration_websocket(), CollaborationManager, CollaborationPatchResponse, CollaborationResourceType, CollaborationTicket, collaborationWebSocketUrl(), CollaborationWsMessage, _consume_ticket() (+40 more)

### Community 55 - "Community 55"
Cohesion: 0.06
Nodes (45): Company, CompanyDocument, CompanyDocumentPayload, CompanyDocumentStatus, CompanyDocumentType, CompanyDocumentUploadPayload, CompanyNightlyRate, CompanyNightlyRatePayload (+37 more)

### Community 56 - "Community 56"
Cohesion: 0.11
Nodes (54): LinenItem, LinenLocation, LinenMovement, LinenParLevel, Linen (ropa blanca) inventory models -- physically separate tables from app/mode, Configured minimum quantity for one linen item at one hotel location., Configured minimum quantity for one linen item at one hotel location., Raised when an operational follow-up cannot be read or updated. (+46 more)

### Community 57 - "Community 57"
Cohesion: 0.08
Nodes (53): client_with_db(), _enable_test_google(), get_auth_context_target(), get_db_override_target(), _google_claims(), _invitation_token(), _manage_users_request(), owner_ctx() (+45 more)

### Community 58 - "Community 58"
Cohesion: 0.08
Nodes (49): create_restriction(), _get_tenant_guest(), list_active_restriction_guest_ids(), list_restrictions(), FastAPI routes for GuestRestriction (formal lodging-prohibition entity)., Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, Tenant-scoped lookup. Cross-hotel access must 404, never 403 --     existence of, Return restricted guest IDs for one page of the guest list.      The bounded sum (+41 more)

### Community 59 - "Community 59"
Cohesion: 0.08
Nodes (53): _hotel(), A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash surplus (counted > expected) is exactly as much a discrepancy as     a sh, A cash payment on a reservation must land in the open caja as an INCOME     move, A cash payment on a reservation must land in the open caja as an INCOME     move, A cash payment cannot be approved outside an explicitly opened caja.      proces, A cash payment cannot be approved outside an explicitly opened caja.      proces (+45 more)

### Community 60 - "Community 60"
Cohesion: 0.05
Nodes (53): _cors_contains_wildcard(), get_settings(), _gmail_is_active(), _has_value(), is_demo_environment_allowed(), is_demo_mode(), is_preview_qa_mode(), is_production_mode() (+45 more)

### Community 61 - "Community 61"
Cohesion: 0.17
Nodes (53): AllocationAssignment, AllocationAssignmentStatusEnum, AllocationExplanation, AllocationPolicyProfile, AllocationPolicyVersion, AllocationRun, AllocationRunStatusEnum, SolverMetric (+45 more)

### Community 62 - "Community 62"
Cohesion: 0.14
Nodes (47): DailyReportSchedule, Notification, NotificationOutbox, NotificationOutboxStatusEnum, NotificationPreference, PushSubscription, Notification backend: in-app inbox, Web Push subscriptions, per-user channel pre, Per-user, per-event-type channel toggles and quiet hours.      `event_type == "" (+39 more)

### Community 63 - "Community 63"
Cohesion: 0.07
Nodes (45): HOTEL_ID_INDEX_BY_QUERY_PREFIX, hotelIdForQueryKey(), QUERY_PREFIXES_BY_DOMAIN, QueryDomain, ALL_DOMAINS, beginLocalDomainMutation(), broadcastDomainChange(), createDomainRefreshScheduler() (+37 more)

### Community 64 - "Community 64"
Cohesion: 0.08
Nodes (50): _link(), _management_member(), _provider_result(), Re-delivering the SAME webhook must not create a 2nd transaction nor raise., Re-delivering the SAME webhook must not create a 2nd transaction nor raise., Re-delivering the SAME webhook must not create a 2nd transaction nor raise., Two distinct webhooks for the same completed payment id -> one transaction., Two distinct webhooks for the same completed payment id -> one transaction. (+42 more)

### Community 65 - "Community 65"
Cohesion: 0.09
Nodes (18): _add_cash_movement(), _auth_context(), _http_request(), _make_hotel(), _make_reservation(), _make_transaction(), _make_user(), _open_cash_session() (+10 more)

### Community 66 - "Community 66"
Cohesion: 0.09
Nodes (41): acknowledge_shift_handoff(), _authorize_task_photo_scope(), _can(), _can_read_reservation_context(), _conflict(), create_operational_task(), get_operational_task_history(), get_operational_task_photo_content() (+33 more)

### Community 67 - "Community 67"
Cohesion: 0.06
Nodes (50): D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, D1: current_stock(location_id=...) narrows the balance to one location;     omit, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, Owner-reported bug: deleting an item ("producto que ya no se usa") is     a soft, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE, A real (non-deleted) duplicate must still be rejected -- with a clean     StockE, Owner: "quiero que se pueda poner en las cosas de stock... el costo     por unid (+42 more)

### Community 68 - "Community 68"
Cohesion: 0.09
Nodes (47): ArchiveCustomRoleRequest, CreateCustomRoleRequest, Tenant-scoped custom role catalog and lifecycle endpoints., RenameCustomRoleRequest, RoleCatalogItem, RoleListResponse, LookupError, _active_membership() (+39 more)

### Community 69 - "Community 69"
Cohesion: 0.05
Nodes (33): _make_reservation(), The Reservation model must have is_wait_listed and wait_list_reason fields., A reservation can be created with is_wait_listed=True and no room., Verify is_wait_listed survives a round-trip through the database., Only is_wait_listed=True reservations should appear in the waitlist query., Create one normal and one waitlisted reservation, return (normal, waitlisted)., Service-level tests for the resolve logic (mirrors what the API endpoint does)., Only is_wait_listed=True reservations should appear in the waitlist query. (+25 more)

### Community 70 - "Community 70"
Cohesion: 0.05
Nodes (17): create_lead(), Unauthenticated endpoints the marketing site calls.  Nothing here touches hotel, _request_source(), Bound inbound webhook bodies before parsing or signature verification., d82558f Harden RBAC and add auditable privacy retention, The marketing site's own origin must not depend on an env var being set.  hotels, _request(), test_accepts_body_at_exact_limit() (+9 more)

### Community 71 - "Community 71"
Cohesion: 0.06
Nodes (33): createPromotion(), deactivatePromotion(), FxQuoteDetails, listPromotions(), Promotion, PromotionAppliedEntry, PromotionBenefitType, PromotionConditions (+25 more)

### Community 72 - "Community 72"
Cohesion: 0.10
Nodes (37): Promotion, PromotionBenefitTypeEnum, PromotionScopeEnum, Promotion — versioned, hotel-scoped promotional pricing rule (v72 mobile-first p, A versioned, hotel-scoped promotional discount rule.      One row = one immutabl, mask_to_weekdays(), PromotionConditions, PromotionCreate (+29 more)

### Community 73 - "Community 73"
Cohesion: 0.09
Nodes (42): get_stock_summary(), FastAPI routes for stock and inventory operations., Every item's current balance in one request -- avoids the N+1     per-item item, Every item's current balance in one request -- avoids the N+1     per-item item, Every item's current balance in one request -- avoids the N+1     per-item /item, StockConsumptionItem, StockConsumptionReportRead, StockCountConfirmation (+34 more)

### Community 74 - "Community 74"
Cohesion: 0.08
Nodes (39): _authorize_oauth_state_actor(), connect_integration(), connectIntegration(), _connection_error_message(), _ensure_enabled(), fetchIntegrations(), finalizeIntegrationOAuth(), _find_integration() (+31 more)

### Community 75 - "Community 75"
Cohesion: 0.06
Nodes (16): _make_hotel_guest_reservation(), Database business-requirement tests.  Verifies that ALL tables required to fulfi, Gate assertion: all tables required by the business requirements exist.     This, test_database_foundation_complete(), test_hotel_voucher_persists(), test_hotel_voucher_unique_code_per_hotel(), test_pending_action_all_types_persist(), test_pending_action_ota_conflict() (+8 more)

### Community 76 - "Community 76"
Cohesion: 0.21
Nodes (37): OperationalTaskAttachment, OperationalTaskEvent, OperationalTaskPriorityEnum, OperationalTaskStatusEnum, OperationalTaskTypeEnum, ShiftHandoff, ShiftHandoffStatusEnum, Metadata and lifecycle state; bytes remain outside PostgreSQL. (+29 more)

### Community 77 - "Community 77"
Cohesion: 0.07
Nodes (33): _load_company_night_charge_tenant_migration(), _load_composite_fk_migration(), _load_extended_composite_fk_migration(), _load_master_admin_bypass_migration(), _load_rls_migration(), _load_user_override_migration(), Return model relationships not covered by the core composite contract., Return model relationships not covered by the core composite contract. (+25 more)

### Community 78 - "Community 78"
Cohesion: 0.12
Nodes (39): _b64url_decode(), bootstrap_database(), build_provider_evidence_payload(), _canonical_database_host(), canonical_provider_evidence_json(), cli(), database_connection_fingerprint(), _decode_baseline_lease_entropy() (+31 more)

### Community 79 - "Community 79"
Cohesion: 0.09
Nodes (28): assert_freshness_metadata(), _seed_analytics_data(), test_alert_settings_ai_config_and_breakdowns(), test_analytics_ai_quota_is_read_only_and_enforced_before_provider_calls(), test_analytics_breakdowns_reuse_facts_and_room_detail_filters_by_room(), test_analytics_dashboard_and_ai_chat_without_provider(), test_analytics_exports_png_csv_xlsx(), test_analytics_freshness_reflects_stale_derived_facts() (+20 more)

### Community 80 - "Community 80"
Cohesion: 0.15
Nodes (33): complete_housekeeping_checklist_item(), get_housekeeping_checklists(), Tenant-scoped API for fixed post-checkout housekeeping checklists., List open checklists for the caller's hotel without guest data., Complete one fixed item; all PostgreSQL state changes commit together., HousekeepingChecklist, HousekeepingChecklistItem, HousekeepingChecklistItemCodeEnum (+25 more)

### Community 81 - "Community 81"
Cohesion: 0.13
Nodes (34): cancel_draft(), confirm_draft(), create_draft(), get_draft(), _raise_draft_http(), RateChangeDecisionIn, RateChangeDraftIn, RateChangeDraftOut (+26 more)

### Community 82 - "Community 82"
Cohesion: 0.10
Nodes (32): _bootstrap_values(), _cloud_env(), _env(), _provider_manifest(), test_cli_refusal_does_not_echo_rejected_dsn_or_credentials(), test_config_repr_redacts_dsn_emails_passwords_and_pin(), test_consumer_rejects_signed_manifest_fingerprint_for_another_target(), test_dedicated_baseline_refuses_missing_runtime_lease_key() (+24 more)

### Community 83 - "Community 83"
Cohesion: 0.09
Nodes (37): Live PostgreSQL RLS behavioral verification.  Unlike tests/test_tenant_rls_contr, With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the     unp, With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the     unp, With app.hotel_id set to hotel A, hotel B's rows are invisible -- as the     unp, Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak., Without app.hotel_id set at all, RLS default-denies -- zero rows, not a leak., Correction history is isolated for a real NOSUPERUSER/NOBYPASSRLS role., C2: with app.master_admin='true', subscriptions across hotels are visible. (+29 more)

### Community 84 - "Community 84"
Cohesion: 0.09
Nodes (31): acceptAllocationRun(), ActiveAllocationPolicy, AllocationAssignment, AllocationExplanation, AllocationObjective, AllocationPolicyVersion, AllocationPolicyVersionCreate, AllocationRunDetail (+23 more)

### Community 85 - "Community 85"
Cohesion: 0.11
Nodes (37): anchor_hotel_day_to_fixture_arrival(), _make_guest(), _make_hotel(), _make_paid_reservation(), _make_room(), Tests for check-in security enforcement:   - prohibido_alojar tag blocks check-i, Guest with active prohibido_alojar tag cannot check in., VIP and other non-blocking tags must not prevent check-in. (+29 more)

### Community 86 - "Community 86"
Cohesion: 0.07
Nodes (28): cancelRateChangeDraft(), confirmRateChangeDraft(), createRateChangeDraft(), listRateChangeDrafts(), RateChangeDraft, RateChangeDraftInput, RateChangeField, RateChangeImpact (+20 more)

### Community 87 - "Community 87"
Cohesion: 0.16
Nodes (36): _client_with_db(), _enable_whatsapp_plan_for_api_test(), _issue_permission_restore_ticket(), _override_auth(), Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests., Create an RBAC-read scope or action-bound ticket for focused API tests. (+28 more)

### Community 88 - "Community 88"
Cohesion: 0.11
Nodes (26): configure_dedicated_baseline(), env_page(), FakeApi, fixtures(), Critical security tests for the read-only preview provider verifier., set_render_preview_env(), test_concurrent_target_cannot_reuse_an_existing_baseline_lease(), test_dedicated_baseline_refuses_missing_render_lease_observation() (+18 more)

### Community 89 - "Community 89"
Cohesion: 0.11
Nodes (34): An opaque browser session whose raw token is never persisted., UserSession, _as_aware(), create_session(), csrf_double_submit_matches(), _device_label_from_request(), _hash_value(), _issue_rotation_successor() (+26 more)

### Community 90 - "Community 90"
Cohesion: 0.14
Nodes (35): _cache_key(), _cache_key_for_display_rate(), _cached_quote_matches(), _cached_rate(), _cached_supported_rates(), _derive_blue_equivalent(), _extract_direct_quotes(), fetch_all_rates() (+27 more)

### Community 91 - "Community 91"
Cohesion: 0.10
Nodes (31): _bootstrap_environment(), _local_evidence_payload(), _provider_manifest(), Safety contract for destructive PostgreSQL validation tests.  These tests never, _safe_environment(), test_accepts_direct_supabase_branch_host_with_postgres_role(), test_accepts_explicit_local_disposable_database_with_local_evidence(), test_accepts_explicit_supabase_qa_branch_with_signed_provider_evidence() (+23 more)

### Community 92 - "Community 92"
Cohesion: 0.10
Nodes (30): applyGemmaDraft(), approveGemmaAction(), archiveGemmaChatSession(), fetchGemmaChatHistory(), fetchGemmaChatSession(), fetchGemmaInsights(), fetchGemmaRuntimeStatus(), GemmaApplyDraftPayload (+22 more)

### Community 93 - "Community 93"
Cohesion: 0.12
Nodes (30): add_companions(), FastAPI routes for Guest management., Add new companions to an existing guest., Add new companions to an existing guest., Add new companions to an existing guest., Add new companions to an existing guest., DocumentTypeEnum, GuestCompanion (+22 more)

### Community 94 - "Community 94"
Cohesion: 0.06
Nodes (34): _backfill_not_null_nulls(), _column_fill_value(), get_db(), _get_db_session(), get_engine(), get_session_factory(), get_websocket_db(), init_db() (+26 more)

### Community 95 - "Community 95"
Cohesion: 0.07
Nodes (32): PostgreSQL validation tests.  Run with:   DATABASE_URL_TEST=<isolated-qa-dsn> \, Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic upgrade head succeeds on fresh PostgreSQL database., Alembic downgrade to base then upgrade to head — idempotency check., Alembic downgrade to base then upgrade to head — idempotency check., Numeric(12,2) columns correctly store and return Decimal values., Numeric(12,2) columns correctly store and return Decimal values., All PostgreSQL enum types are created by migrations. (+24 more)

### Community 96 - "Community 96"
Cohesion: 0.10
Nodes (29): _count_queries(), _legacy_operations_summary_reference(), _mk_reservation(), The real N+1 this fix targets: query count must track the number of     reservat, Old terminal cases remain actionable without materializing clean history., Every distinct way `_build_pending_actions` can produce an action must     still, The real N+1 this fix targets: query count must track the number of     reservat, Every distinct way `_build_pending_actions` can produce an action must     still (+21 more)

### Community 97 - "Community 97"
Cohesion: 0.14
Nodes (1): BookingAdapter

### Community 98 - "Community 98"
Cohesion: 0.21
Nodes (32): build_manifest(), _canonical_hostname(), _connection_fingerprint(), _database_identity(), _database_password(), _decode_lease_entropy(), _deployment_git_identity(), _deployment_hosts() (+24 more)

### Community 99 - "Community 99"
Cohesion: 0.08
Nodes (23): acceptInvitation(), acceptInvitationWithGoogle(), AuthResponse, completeMfaInvitationAcceptance(), confirmMfaEnrollment(), currentUser(), disableMfa(), enrollMfa() (+15 more)

### Community 100 - "Community 100"
Cohesion: 0.12
Nodes (29): _assert_postgres_e2e_database_empty(), _credentials(), E2ESafetyError, _enabled(), _is_postgres_e2e_target(), main(), _postgres_e2e_connection(), _postgres_e2e_seed_connection() (+21 more)

### Community 101 - "Community 101"
Cohesion: 0.12
Nodes (20): AnalyticsAIProviderConfig, AnalyticsAIProviderError, AnalyticsAIProviderStatus, AnalyticsAIRequest, AnalyticsAIResult, build_analytics_ai_config(), _build_analytics_messages(), DisabledAnalyticsAIProvider (+12 more)

### Community 102 - "Community 102"
Cohesion: 0.15
Nodes (30): build_export_payload(), _build_payload_for_request(), _build_xlsx_bytes(), _build_xlsx_spool(), create_xlsx_export_job(), delete_export_file(), _ensure_utc(), expire_export_job_if_needed() (+22 more)

### Community 103 - "Community 103"
Cohesion: 0.14
Nodes (31): _apply_manual_amounts(), _attempt_waitlist_promotion_after_release(), _audit(), _audit_waitlist_promotion(), _audit_waitlist_suggestion(), _clean(), create_or_update_manual_ota_reservation(), _existing_user_id() (+23 more)

### Community 104 - "Community 104"
Cohesion: 0.07
Nodes (16): api_client(), Spin up the real FastAPI app against an in-memory SQLite database., Spin up the real FastAPI app against an in-memory SQLite database., Spin up the real FastAPI app against an in-memory SQLite database., Spin up the real FastAPI app against an in-memory SQLite database., A legacy row with untrimmed whitespace must still be found by the     bulk looku, A legacy row with untrimmed whitespace must still be found by the     bulk looku, A legacy row with untrimmed whitespace must still be found by the     bulk looku (+8 more)

### Community 105 - "Community 105"
Cohesion: 0.16
Nodes (26): SimpleRateLimiter, MasterAdminAuditEvent, MasterAdminAuthLockout, MasterAdminSession, audit_master_action(), authenticate_master_mfa_login(), create_master_admin_mfa_challenge(), _json_or_null() (+18 more)

### Community 106 - "Community 106"
Cohesion: 0.16
Nodes (29): acquire(), acquire_to_github_output(), _canonical_json(), _cleanup(), _common_arguments(), _env_values(), _lease_id(), LeaseError (+21 more)

### Community 107 - "Community 107"
Cohesion: 0.17
Nodes (31): Owner's core requirement: a remito's cost is fixed at creation time.      The bi, Owner's core requirement: a remito's cost is fixed at creation time.      The bi, Owner's core requirement: a remito's cost is fixed at creation time.      The bi, _seed_hotels(), _seed_house_stock(), _set_test_vendor_price(), test_create_remito_inbound_reverses_the_transfer(), test_create_remito_outbound_transfers_between_locations_without_changing_hotel_total() (+23 more)

### Community 108 - "Community 108"
Cohesion: 0.10
Nodes (25): acknowledgeShiftHandoff(), createOperationalTask(), createShiftHandoff(), getOperationalTaskAttachmentContent(), listOperationalTaskAttachments(), listOperationalTaskHistory(), listOperationalTasks(), listShiftHandoffs() (+17 more)

### Community 109 - "Community 109"
Cohesion: 0.15
Nodes (29): allow_master_admin_mfa_attempt(), _as_aware(), authenticate_master_login(), _authorize_user_for_master_panel(), _bootstrap_master_credentials_match(), create_master_session(), _hash_value(), _idle_expiry() (+21 more)

### Community 110 - "Community 110"
Cohesion: 0.15
Nodes (4): GemmaPolicyDraft, GemmaService, Adapter for Gemma-backed policy suggestions.      The service can talk to either, Adapter for Gemma-backed policy suggestions.      The service can talk to either

### Community 111 - "Community 111"
Cohesion: 0.15
Nodes (30): _hotel(), _member(), Unit coverage for the notification outbox/service: dedupe, permission filtering,, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in, A DST-observing timezone (America/New_York) must fire at a different     UTC ins, Buenos Aires currently observes UTC-3 year-round (Argentina abolished     DST in (+22 more)

### Community 112 - "Community 112"
Cohesion: 0.27
Nodes (30): _build_client(), _cleanup_client(), _manual_ota_payload(), _override_auth(), _payload(), Security gap: any role that can create a reservation (owner, co_owner, manager,, Owner explicitly asked that only the owner -- not even co_owner --     override, No regression: the gate only fires when total_amount is actually sent. (+22 more)

### Community 113 - "Community 113"
Cohesion: 0.08
Nodes (26): Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT., perform_checkout sets actual_check_out timestamp., After checkout, the assigned room status is set to CLEANING., Checkout transitions status from CHECKED_IN → CHECKED_OUT., Checkout after successful check-in, and failure when not checked_in., Checkout after successful check-in, and failure when not checked_in., Checkout transitions status from CHECKED_IN → CHECKED_OUT. (+18 more)

### Community 114 - "Community 114"
Cohesion: 0.09
Nodes (18): LaundryBatch, LaundryBatchCreate, LaundryBatchRead, LaundryItem, LaundryItemCreate, LaundryItemRead, LaundryStatus, LaundryStatusUpdate (+10 more)

### Community 115 - "Community 115"
Cohesion: 0.16
Nodes (24): LLMFeedbackEvent, LLMPolicySuggestion, LLMPolicySuggestionStatusEnum, ManualOverrideReason, Allocation, solver and LLM policy models.  The deterministic solver remains the, AllocationFeedbackDraft, AllocationQuestionnaireDraft, draft_policy_from_feedback() (+16 more)

### Community 116 - "Community 116"
Cohesion: 0.15
Nodes (8): make_res(), make_rooms(), Tests for the Allocation Engine (OR-Tools CP-SAT + greedy fallback)., test_overlapping_reservation_pairs_use_half_open_dates_and_keep_original_indexes(), test_reservation_day_index_clips_to_half_open_horizon(), TestCPSATAllocation, TestGreedyAllocation, TestOverlap

### Community 117 - "Community 117"
Cohesion: 0.10
Nodes (10): _fact_business_snapshot(), _make_fact_refresh_reservation(), test_explicit_fact_refresh_repairs_legacy_currency_fact(), test_fact_touch_failure_propagates_for_atomic_source_write(), test_room_state_event_create_and_close_refresh_only_materialized_room_horizon(), test_room_state_event_fact_refresh_failure_propagates_for_source_rollback(), test_targeted_refresh_preserves_facts_outside_union_window(), test_targeted_reservation_fact_touch_isolated_by_hotel() (+2 more)

### Community 118 - "Community 118"
Cohesion: 0.23
Nodes (27): _approve(), _consume(), _create_reservation(), _request(), _reservation_id(), _set_cancel_permission(), test_active_mfa_requires_totp_but_accounts_without_mfa_can_approve(), test_approved_grant_allows_only_denied_exact_booking_cancel_and_replay_is_denied() (+19 more)

### Community 119 - "Community 119"
Cohesion: 0.08
Nodes (4): _authorize_sensitive_company_export(), export_analytics_csv(), export_analytics_png(), export_analytics_xlsx()

### Community 120 - "Community 120"
Cohesion: 0.13
Nodes (22): PrivacyRetentionHold, Current legal-retention exception for one public lead or inquiry.      Changes a, Current legal-retention exception for one public lead or inquiry.      Changes a, _as_utc(), create_retention_hold(), _effective(), _lock_hold_table_for_write(), _mask_email() (+14 more)

### Community 121 - "Community 121"
Cohesion: 0.12
Nodes (25): AuditLog, Append-only record of every significant mutation within a hotel tenant.     Do N, create_audit_log(), model_snapshot(), payload_json(), queue_audit_log(), Best-effort audit log: a failure here must never discard the caller's     real,, Best-effort audit log: a failure here must never discard the caller's     real, (+17 more)

### Community 122 - "Community 122"
Cohesion: 0.15
Nodes (25): Auditable guest communications initiated from a reservation., One attempted reservation email, scoped to the owning hotel.      ``accepted`` m, ReservationEmailDelivery, ReservationEmailKindEnum, ReservationEmailStatusEnum, _build_email_message(), _build_message(), capture_hotel_email() (+17 more)

### Community 123 - "Community 123"
Cohesion: 0.13
Nodes (8): _build_session_title(), _coerce_action_list(), _coerce_float(), _coerce_string_list(), _derive_models_endpoint(), GemmaOrchestrator, _resolve_existing_user_id(), _safe_text()

### Community 124 - "Community 124"
Cohesion: 0.15
Nodes (24): _account_label_from_payload(), build_redirect_url(), connection_account_label(), decrypt_payload(), derive_expires_at(), encrypt_payload(), ensure_provider_payload(), _fernet() (+16 more)

### Community 125 - "Community 125"
Cohesion: 0.17
Nodes (28): _analytics_home_key(), _analytics_starter_key(), _availability_key(), _cache_enabled(), _daily_report_key(), _date_token(), get_cached_availability_payload(), get_cached_daily_report_payload() (+20 more)

### Community 126 - "Community 126"
Cohesion: 0.08
Nodes (7): _complete_onboarding(), _fake_apple_claims(), test_apple_login_creates_account_and_persists_first_authorization_name(), test_apple_login_reclaims_matching_local_email_after_verified_claims(), test_apple_login_rejects_different_subject_claiming_linked_email(), test_apple_unlink_requires_password_and_revokes_session(), test_login_prefers_a_completed_hotel_when_multiple_memberships_exist()

### Community 127 - "Community 127"
Cohesion: 0.22
Nodes (28): _client_with_db(), _override_auth(), API-level coverage for outsourced laundry vendors/remitos (D1) and the linen ite, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, Backend counterpart of avoiding LaundryPage.tsx's per-item     getCurrentLinenSt, _teardown(), test_discrepancy_approval_permission_is_separate_from_remito_creation_and_configurable() (+20 more)

### Community 128 - "Community 128"
Cohesion: 0.09
Nodes (20): _make_guest(), _make_reservation(), Multi-tenancy isolation tests: Hotel A vs Hotel B.  Verifies that every domain t, Same document can exist in Hotel A and Hotel B — dedup is hotel-scoped., Same document within one hotel raises IntegrityError., Same key name in two hotels is allowed — uniqueness is per-hotel., Same OTA channel+external_id across different hotels is allowed., Creates Hotel A (id=1000) and Hotel B (id=1001) with minimal shared structure. (+12 more)

### Community 129 - "Community 129"
Cohesion: 0.17
Nodes (21): _apply_drift(), env_page(), FakeRender, FakeRenderCleanupFailure, FakeRenderPutResponseLost, HealthResponse, manifest(), _mutating_calls() (+13 more)

### Community 130 - "Community 130"
Cohesion: 0.13
Nodes (20): BrokenRedis, _cache_settings(), FakeRedis, isolate_read_model_cache(), _reset_cache_client_state(), test_analytics_home_cache_key_varies_by_filter(), test_availability_is_not_cached_in_process_when_redis_is_disabled(), test_availability_payload_is_cached() (+12 more)

### Community 131 - "Community 131"
Cohesion: 0.07
Nodes (15): Reservation has nullable joined relations, so payment locks must name the row., BillingAdjustment also eager-loads optional relations used by night-charge corre, The payment helper must lock the reservation despite joined optional relations., Reservation has nullable joined relations, so payment locks must name the row., BillingAdjustment also eager-loads optional relations used by night-charge corre, The payment helper must lock the reservation despite joined optional relations., Reservation has nullable joined relations, so payment locks must name the row., BillingAdjustment also eager-loads optional relations used by night-charge corre (+7 more)

### Community 132 - "Community 132"
Cohesion: 0.14
Nodes (18): evidence_bytes(), FakeGitHub, iso(), prepare(), Security regression tests for the pull_request_target release gate., test_finalize_rejects_artifact_with_different_bytes(), test_github_client_error_never_discloses_token_or_body(), test_prepare_refuses_head_key_substitution_for_base_checkout_key() (+10 more)

### Community 133 - "Community 133"
Cohesion: 0.09
Nodes (28): V72 §8.3 / §8.4 / §8.5 — Change reservation dates and extend stay tests.  Ported, §8.3 — Cannot change dates when another reservation occupies the room., §8.3 — Changing to a past check-in date is rejected., §8.3 — Cannot change dates when another reservation occupies the room., §8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserv, §8.3 — Changing to a past check-in date is rejected., §8.4 — If new total <= amount_paid after date change, status auto-transitions to, §8.4 — DEPOSIT_PAID reservation can change dates; deposit amount_paid is preserv (+20 more)

### Community 134 - "Community 134"
Cohesion: 0.08
Nodes (19): RateCalendarChannelDay, RateCalendarChannelPrice, RateCalendarDay, RateCalendarResponse, InfoTip(), InfoTipProps, PopoverPosition, ARRIVAL_LABELS (+11 more)

### Community 135 - "Community 135"
Cohesion: 0.10
Nodes (23): FxPolicyBase, FxPolicyCreate, FxPolicyRead, FxPolicyUpdate, ProductRoomCompatibilityRead, ProductRoomCompatibilityWrite, RatePlanBase, RatePlanCreate (+15 more)

### Community 136 - "Community 136"
Cohesion: 0.08
Nodes (4): Fase 12 — cross-hotel ID-collision regression suite (security-auditor).  Reserva, _proof(), test_financial_view_alone_cannot_approve_a_payment_proof(), test_manager_review_capability_covers_list_image_approve_and_reject()

### Community 137 - "Community 137"
Cohesion: 0.11
Nodes (16): V72 feature tests ported from claude/fervent-jennings-1299c4 and adapted to main, _reservation(), test_checkin_allowed_with_prohibited_override(), test_checkin_blocked_by_is_prohibited_stay_flag(), test_checkin_blocked_by_prohibido_alojar(), test_edit_room_change_does_not_implicitly_lock_reservation(), test_extend_stay_basic(), test_extend_stay_fails_if_new_date_not_later() (+8 more)

### Community 138 - "Community 138"
Cohesion: 0.22
Nodes (16): changed_blob_paths(), finalize_gate(), full_sha(), GitHubClient, main(), positive_integer(), prepare_gate(), PreparedEvidence (+8 more)

### Community 139 - "Community 139"
Cohesion: 0.07
Nodes (24): createLinenItem(), createLinenLocation(), createLinenMovement(), createLinenOpeningCounts(), createLinenTransfer(), CurrentLinenStock, getLinenSummary(), LinenItem (+16 more)

### Community 140 - "Community 140"
Cohesion: 0.26
Nodes (26): BillingDecision, MasterStripeWebhookEvent, put_pricing_plans(), Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi, Replace the public pricing table.      The landing page renders exactly what thi (+18 more)

### Community 141 - "Community 141"
Cohesion: 0.16
Nodes (24): calculate_pickup_30d(), _currency_pair(), _date_range(), _decimal_or_none(), _decimal_or_zero(), detect_no_shows(), _event_overlaps_date(), _load_category_cost_rows() (+16 more)

### Community 142 - "Community 142"
Cohesion: 0.14
Nodes (21): _active_push_subscriptions(), _actor_role(), _deliver_email(), _deliver_in_app(), _deliver_push(), enqueue_notifications_for_event(), get_daily_report_schedule(), get_effective_notification_preference() (+13 more)

### Community 143 - "Community 143"
Cohesion: 0.07
Nodes (19): Availability lookup must not issue one reservation query per room., Find available rooms after booking some., Find available rooms after booking some., Availability checks must not eagerly load room reservation histories., Availability checks must not eagerly load room reservation histories., Tests for room availability checking., Tests for room availability checking., Tests for room availability checking. (+11 more)

### Community 144 - "Community 144"
Cohesion: 0.09
Nodes (10): _card_value(), _make_reservation(), _operations_analytics(), _reports_daily(), _reports_occupancy(), _reports_revenue(), _request_context(), _starter_analytics() (+2 more)

### Community 145 - "Community 145"
Cohesion: 0.09
Nodes (15): _pay_deposit(), §7.1: Reservation in DEPOSIT_PAID status raises CheckInError., A legacy per-hotel setting cannot bypass the full-payment rule., A legacy per-hotel setting cannot bypass the full-payment rule., Final check-in requires an assigned, available, ready room., §7.1: Error message also reveals the current (blocking) status., A legacy per-hotel setting cannot bypass the full-payment rule., A legacy per-hotel setting cannot bypass the full-payment rule. (+7 more)

### Community 146 - "Community 146"
Cohesion: 0.15
Nodes (12): BookingAdapterError, Booking.com Connectivity adapter.  The adapter keeps provider traffic behind a s, Acknowledge processed reservation messages in Booking's queue., Acknowledge processed reservation messages in Booking's queue., A provider operation failed before it could return normalized data., A provider operation failed before it could return normalized data., NormalizedOTAReservation, OTAAdapterContext (+4 more)

### Community 147 - "Community 147"
Cohesion: 0.13
Nodes (23): BulkRateField, BulkRateFieldMode, BulkRateResult, bulkUpdateDailyRateField(), bulkUpsertDailyRates(), createPricePeriod(), DailyRateOut, DailyRatePrices (+15 more)

### Community 148 - "Community 148"
Cohesion: 0.14
Nodes (24): accept_allocation_run(), _active_policy_version_id_for_acceptance(), _allocation_fx_configuration_snapshot(), _create_assignment_explanation(), _create_unassigned_explanation(), get_allocation_run_details(), get_latest_allocation_run_details(), _load_json_dict() (+16 more)

### Community 149 - "Community 149"
Cohesion: 0.25
Nodes (25): _build_finish_gates(), _build_readiness_checklist(), can_finish_onboarding(), _current_subscription_context(), finish_onboarding(), _get_or_create_config(), get_or_create_state(), get_status() (+17 more)

### Community 150 - "Community 150"
Cohesion: 0.18
Nodes (22): _create_pending_reallocation_proposal(), _reservation(), _seed_hotel_rooms_guests(), _slot(), test_allocation_proposal_is_rejected_after_fx_configuration_changes(), test_allocation_proposal_is_rejected_when_policy_version_is_no_longer_active(), test_allocation_proposal_requires_fresh_hotel_scoped_fx_snapshot(), test_allocation_run_creates_movement_group_and_events() (+14 more)

### Community 151 - "Community 151"
Cohesion: 0.20
Nodes (24): _make_reservation(), _states_for_first_day(), test_cell_states_isolated_per_hotel(), test_fully_paid_direct_marks_nothing(), test_ota_with_balance_marks_ota_unpaid(), test_pending_payment_marks_cell(), test_requires_manual_review_marks_available_with_review(), _ensure_hotel() (+16 more)

### Community 152 - "Community 152"
Cohesion: 0.15
Nodes (17): acquire_lease(), env_page(), FakeRender, mutations(), Security contract for the dedicated Render QA baseline lease manager., release_lease(), Response, test_acquire_failure_rolls_back_marker_first_then_target_fields() (+9 more)

### Community 153 - "Community 153"
Cohesion: 0.22
Nodes (23): AttestationError, _b64url_decode(), _b64url_encode(), build_attestation(), _canonical_json(), _iso_utc(), _json_object(), _load_private_key() (+15 more)

### Community 154 - "Community 154"
Cohesion: 0.09
Nodes (5): complete_mfa_login(), dashboard_summary(), login(), me(), _serialize_user()

### Community 155 - "Community 155"
Cohesion: 0.16
Nodes (24): PaymentReceiptEmailDelivery, One attempted receipt email, without retaining the guest's email address.      `, HotelEmailAttachment, Bytes attached to a hotel email without re-rendering the document., _existing_delivery(), _format_money(), _is_reserved_test_recipient(), _key_hash() (+16 more)

### Community 156 - "Community 156"
Cohesion: 0.17
Nodes (24): _allocate_monetary_totals(), backfill_channel_code(), build_analytics_window(), build_comparison_state(), build_comparison_window(), build_reservation_nightly_facts(), build_room_occupancy_nightly_fact(), calculate_physical_room_nights() (+16 more)

### Community 157 - "Community 157"
Cohesion: 0.16
Nodes (20): CommercialConfigError, create_fx_policy(), create_rate_plan(), create_sellable_product(), create_tax_policy(), _get_fx_policy(), _get_rate_plan(), _get_sellable_product() (+12 more)

### Community 158 - "Community 158"
Cohesion: 0.15
Nodes (22): _active_room_blocks(), _alerts(), _arrivals_query(), _available_with_review(), _candidate_summary(), _cash_session(), company_night_extra_balances_by_reservation(), daily_report() (+14 more)

### Community 159 - "Community 159"
Cohesion: 0.15
Nodes (24): _assert_reservation_response(), _client_with_db(), _override_auth(), B3: check-in must capture the guest's missing profile data (birth place/ country, Green case: same endpoint, now with `guest` in the payload, succeeds once., Green case: same endpoint, now with `guest` in the payload, succeeds once., Red case: guest missing the 4 new mandatory fields cannot check in., Red case: guest missing the 4 new mandatory fields cannot check in. (+16 more)

### Community 160 - "Community 160"
Cohesion: 0.15
Nodes (24): _image_base64(), _jpeg_with_exif_base64(), A .png-declared upload whose bytes are NOT actually a decodable image     (magic, Rows written before the object-storage migration have `content` set     and `obj, A .png-declared upload whose bytes are NOT actually a decodable image     (magic, A guest with real consumption charges (e.g. minibar) owes more than     total_am, Rows written before the object-storage migration have `content` set     and `obj, Money-risk regression (fase QA money-risk-payment-surcharge-daily-rate).      Tw (+16 more)

### Community 161 - "Community 161"
Cohesion: 0.13
Nodes (21): _auth_headers(), _ensure_hotel(), A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A hotel can carry the canonical v2 row without its legacy projection.      ensur, A settings read should not issue one entitlement query per plan/code., A hotel can carry the canonical v2 row without its legacy projection.      ensur, _step_up_headers() (+13 more)

### Community 162 - "Community 162"
Cohesion: 0.08
Nodes (22): Verify the hotel config flag is respected (default = True → gate enforced)., Config flag is True by default; gate is active for PENDING reservation., Even if documentterms config flags are disabled, payment gate remains active., Verify payment and guest-data gates remain separate., Config flag is True by default; gate is active for PENDING reservation., Verify payment and guest-data gates remain separate., Verify payment and guest-data gates remain separate., Even if documentterms config flags are disabled, payment gate remains active. (+14 more)

### Community 163 - "Community 163"
Cohesion: 0.20
Nodes (23): _accept_invitation(), accept_invitation_legacy_path(), _accept_invitation_with_google(), accept_invitation_with_google_legacy_path(), _activate_invitation_for_user(), _activate_invitation_for_user_audited(), _audit_invitation_accept_denial(), _audit_invitation_mfa_challenge() (+15 more)

### Community 164 - "Community 164"
Cohesion: 0.10
Nodes (16): DailyRateRangeRow, Column, currencySymbol(), INTEGER_LABEL, MONTH, PRICE_ROWS, PriceField, RateEditorGrid() (+8 more)

### Community 165 - "Community 165"
Cohesion: 0.23
Nodes (18): GemmaOrchestrator, _build_client(), _cleanup_client(), _override_auth(), _StubGemmaOrchestrator, test_gemma_chat_can_archive_session_and_hide_it_from_history(), test_gemma_chat_can_confirm_preview_into_policy_suggestion_draft(), test_gemma_chat_can_reject_pending_action() (+10 more)

### Community 166 - "Community 166"
Cohesion: 0.20
Nodes (22): PaymentProof, PaymentProofBlob, PaymentProofStatusEnum, Private image evidence awaiting explicit staff confirmation., Private binary payload kept separately from queryable proof metadata., approve_transfer_proof(), _decode_image(), _delete_uncommitted_object() (+14 more)

### Community 167 - "Community 167"
Cohesion: 0.17
Nodes (22): TOTP MFA secrets and one-time recovery codes for normal user accounts., UserMfaRecoveryCode, UserMfaSecret, add_recovery_codes(), confirm_enrollment(), consume_mfa_code(), _consume_recovery_code(), _consume_totp_code() (+14 more)

### Community 168 - "Community 168"
Cohesion: 0.16
Nodes (23): _assert_mercadopago_preference_identity(), _available_provider_balance(), balance_due_from_transactions(), cancel_link(), create_link(), _enqueue_provider_revocation_failure(), _ensure_utc(), expire_link() (+15 more)

### Community 169 - "Community 169"
Cohesion: 0.08
Nodes (16): TDD tests for the AuditLog model.  Invariants:   - AuditLog is hotel-scoped (hot, System-triggered events (e.g. OTA sync) have no human actor., System-triggered events (e.g. OTA sync) have no human actor., Deleting a hotel cannot destroy its audit-log evidence., Deleting a hotel cannot destroy its audit-log evidence., All AuditActionEnum values can be stored., All AuditActionEnum values can be stored., Regression: hotel_id on transactions must have a DB-level FK. (+8 more)

### Community 170 - "Community 170"
Cohesion: 0.21
Nodes (22): example_manifest(), Regression tests for the isolated preview evidence contract., test_api_base_may_equal_origin_without_breaking_health_url(), test_api_base_rejects_arbitrary_path_and_health_under_api(), test_backend_sha_and_preview_service_must_be_distinct(), test_database_branch_and_connection_must_differ_from_production(), test_dedicated_baseline_rejects_missing_lease_field(), test_dedicated_baseline_rejects_weak_lease_id() (+14 more)

### Community 171 - "Community 171"
Cohesion: 0.16
Nodes (12): _make_reservation(), _pay_full(), Final check-in requires an assigned, available, ready room., Final check-in requires an assigned, available, ready room., Create a PENDING reservation using the first available category., Create a PENDING reservation using the first available category., Create a PENDING reservation using the first available category., Create a PENDING reservation using the first available category. (+4 more)

### Community 172 - "Community 172"
Cohesion: 0.08
Nodes (21): PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., PENDING status (no payment at all) must NOT allow check-in., §7.1: Error message mentions current status 'pending' when no payment made., §7.1: A CANCELLED reservation cannot be checked in regardless of payment., The default full-payment policy blocks check-in without payment., The default full-payment policy blocks check-in without payment. (+13 more)

### Community 173 - "Community 173"
Cohesion: 0.09
Nodes (9): CacheStore, EventBus, LockManager, Ports for infrastructure that is safe to lose and rebuild.  These protocols deli, RenderRequester, JsonGetter, Protocol, AnalyticsAIProvider (+1 more)

### Community 174 - "Community 174"
Cohesion: 0.26
Nodes (20): _canonical_hostname(), _canonical_json(), _connection_fingerprint(), _database_identity(), _decode_token_payload(), _deployment_became_live(), _github_repository(), _https_origin() (+12 more)

### Community 175 - "Community 175"
Cohesion: 0.09
Nodes (23): _frontend_placeholder(), Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Fallback page shown when the Vite build is missing., Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, Serve the SPA shell. We no longer block by onboarding here to avoid     returnin, SPA fallback for React Router.     Skips API/asset paths to avoid shadowing., SPA fallback for React Router.     Skips API/asset paths to avoid shadowing. (+15 more)

### Community 176 - "Community 176"
Cohesion: 0.18
Nodes (22): _build_pending_actions(), _candidate_reservation_ids(), clear_reservation_manual_review(), _decorate_action(), _dedupe_candidates(), _fmt_date(), _get_latest_ota_link(), _get_latest_room_move() (+14 more)

### Community 177 - "Community 177"
Cohesion: 0.25
Nodes (20): _make_guest(), _make_reservation(), _make_room_set(), A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m, Exercise Numeric SUM and tenant scoping on the real PostgreSQL dialect., A fully-paid stay that later gets a consumption charge (BillingAdjustment)     m, test_available_with_review_surfaces_in_report(), test_billing_adjustment_aggregation_executes_on_postgres() (+12 more)

### Community 178 - "Community 178"
Cohesion: 0.15
Nodes (19): MarketingPricingPlan, Public marketing surfaces: the pricing the landing page shows, and the early-acc, A plan card as the public site renders it.      `price_amount` is nullable on pu, admin_pricing(), _decode_features(), hash_source(), _ordered_plans(), _plan_catalog_fallback() (+11 more)

### Community 179 - "Community 179"
Cohesion: 0.29
Nodes (21): _audit_for(), _category(), _context(), _guest(), _hotel(), _post_request(), _reservation(), _room() (+13 more)

### Community 180 - "Community 180"
Cohesion: 0.18
Nodes (16): _outbox_row(), Exercise the retained Redis recovery path explicitly, independent of deployment, _seed_hotels(), _successful_event(), test_after_commit_publish_failure_leaves_row_for_worker_restart(), test_celery_replay_stops_after_first_redis_failure(), test_celery_task_drains_row_after_after_commit_failure(), test_domain_event_only_emits_origin_key_when_present() (+8 more)

### Community 181 - "Community 181"
Cohesion: 0.25
Nodes (19): _completed_payment(), _mock_receipt_email(), Receipt PDF and email API tests use mocked provider/local transports only., _receipt_headers(), test_local_simulation_captures_test_email_and_pdf_without_provider_calls(), test_local_simulation_hotel_mismatch_fails_closed_without_provider_fallback(), test_local_simulation_rejects_non_test_recipient_and_never_falls_back_to_gmail(), test_receipt_email_accepts_a_refunded_receipt_transaction() (+11 more)

### Community 182 - "Community 182"
Cohesion: 0.10
Nodes (6): _plan(), The two endpoints the public website calls, and the ways an anonymous caller cou, A deploy that has not run the migration yet must not 500 the page., A deploy that has not run the migration yet must not 500 the page., TestLeadCapture, TestPublicPricing

### Community 183 - "Community 183"
Cohesion: 0.24
Nodes (17): errors_for(), iso(), Regression tests for the provider-bound release evidence gate., rewrite_manifest(), rewrite_summary(), test_complete_bundle_is_bound_to_manifest_and_provider_identity(), test_duplicate_or_weakened_catalog_rows_are_rejected(), test_each_evidence_reference_is_a_real_sha256_shape() (+9 more)

### Community 184 - "Community 184"
Cohesion: 0.09
Nodes (20): Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with document_type but no document_number is blocked., Guest with no document_type set is blocked by validate_guest_for_checkin., Separate coverage of document-not-verified vs terms-not-signed blocks., Separate coverage of document-not-verified vs terms-not-signed blocks., Guest with no document_type set is blocked by validate_guest_for_checkin., Guest with no document_type set is blocked by validate_guest_for_checkin. (+12 more)

### Community 185 - "Community 185"
Cohesion: 0.12
Nodes (20): Fase 3 (QA reservas): PATCH api/reservations/{id} only understands     room_id/, Fase 3 (QA reservas): PATCH api/reservations/{id} only understands     room_id/, Fase 3 (QA reservas): PATCH /api/reservations/{id} only understands     room_id/, Receptionists gain only the narrow, same-category move tier by default., Receptionists gain only the narrow, same-category move tier by default., Receptionists gain only the narrow, same-category move tier by default., B5: cross-category move via the endpoint enforces capacity and price_action., B5: cross-category move via the endpoint enforces capacity and price_action. (+12 more)

### Community 186 - "Community 186"
Cohesion: 0.10
Nodes (20): channel_for_hotel(), format_sse(), get_domain_event_recovery(), iter_event_stream(), iter_postgres_event_stream(), _notification_to_stream_row(), _outbox_sse_payload(), _PostgresOutboxStreamRow (+12 more)

### Community 187 - "Community 187"
Cohesion: 0.18
Nodes (19): _apply_terminal_dates(), cancel_mercadopago_payment_link_test(), create_mercadopago_payment_link_test(), _ensure_utc(), _friendly_mercadopago_error(), _is_public_webhook_base(), _mercadopago_access_token(), _money() (+11 more)

### Community 188 - "Community 188"
Cohesion: 0.19
Nodes (20): _company_reservation(), test_adding_company_night_due_removes_stale_fully_paid_status(), test_company_charge_quantity_cannot_exceed_registered_additional_people(), test_company_night_charge_batch_resolves_rate_history_with_bounded_queries(), test_company_night_charge_corrections_lock_ledger_rows_as_one_batch(), test_company_night_charges_snapshot_configured_rate_and_skip_duplicates(), test_company_night_charges_use_effective_rate_and_extra_person_quantity(), test_company_night_payment_requires_exact_selected_nights_and_tracks_pending_then_paid() (+12 more)

### Community 189 - "Community 189"
Cohesion: 0.20
Nodes (17): _cancelled_provider_link(), _GatewayResponse, _link(), _management_member(), _mock_revocation_http(), _preference_identity(), Deterministic coverage for best-effort Mercado Pago preference revocation., Replace requests at the adapter boundary; never permit a real request. (+9 more)

### Community 190 - "Community 190"
Cohesion: 0.10
Nodes (10): Edge case tests for the payment engine., Edge case tests for the payment engine., Cannot pay more than the outstanding balance., Cannot pay more than the outstanding balance., Edge case tests for the payment engine., Edge case tests for the payment engine., Edge case tests for the payment engine., Cannot pay more than the outstanding balance. (+2 more)

### Community 191 - "Community 191"
Cohesion: 0.19
Nodes (18): accept_run(), apply_suggestion(), create_feedback_draft(), create_questionnaire_draft(), create_suggestion(), create_version(), get_active_policy(), get_latest_run() (+10 more)

### Community 192 - "Community 192"
Cohesion: 0.13
Nodes (19): Guard demo mutations behind both an approved runtime and an explicit flag., Guard endpoints so they only run in explicit demo mode or tests., Guard demo mutations behind both an approved runtime and an explicit flag., Populate the database with minimal demo data.     Idempotent: running twice simp, Populate the database with minimal demo data.     Idempotent: running twice simp, Populate the database with minimal demo data.     Idempotent: running twice simp, Drop and recreate all tables.     Keeps the app in a known-good empty state for, Drop and recreate all tables.     Keeps the app in a known-good empty state for (+11 more)

### Community 193 - "Community 193"
Cohesion: 0.20
Nodes (17): _action_step_up_tickets(), AuthContext, _authenticate_user(), _decode_authorization_header(), get_auth_context(), get_current_user(), get_current_user_optional(), _matching_action_step_up_ticket() (+9 more)

### Community 194 - "Community 194"
Cohesion: 0.19
Nodes (19): BenchmarkResult, cleanup(), derive_test_dsn(), explain(), explain_query(), _format_plan_nodes(), index_usage_for_operation(), main() (+11 more)

### Community 195 - "Community 195"
Cohesion: 0.17
Nodes (11): aiter_postgres_event_stream(), _deliver_postgres_notification(), _forget_postgres_event_stream_hub(), _get_postgres_event_stream_hub(), _PostgresEventStreamHub, Share PostgreSQL notifications and a bounded poll fallback per hotel., Stream tenant-scoped outbox invalidations without blocking the event loop., _record_postgres_fallback_poll() (+3 more)

### Community 196 - "Community 196"
Cohesion: 0.11
Nodes (13): coalesce_model_change_family(), _OutboxPublishPermit, A durable Redis attempt, optionally owning the single recovery probe., Close any lazy PostgreSQL notification connections at app shutdown., Collapse bulk ORM invalidations to one safe signal per domain.      The persiste, shutdown_postgres_event_listeners(), listener_connection_string(), parse_domain_event_notification() (+5 more)

### Community 197 - "Community 197"
Cohesion: 0.22
Nodes (17): _auth_context(), _code_at(), _invalid_code(), _issue_ticket(), step_up_client(), test_cash_custody_confirmation_requires_a_fresh_action_bound_mfa_ticket(), test_cash_difference_approval_requires_a_fresh_action_bound_mfa_ticket(), test_invalid_ticket_fails_closed_without_echoing_it() (+9 more)

### Community 198 - "Community 198"
Cohesion: 0.10
Nodes (9): client(), FastAPI client backed by an isolated SQLite database., FastAPI client backed by an isolated SQLite database., Demo endpoints must be off unless explicitly enabled., Demo endpoints must be off unless explicitly enabled., Demo utilities work once DEMO_MODE=true is set., Explicit development environments retain the DEMO_MODE workflow., test_seed_and_reset_allowed_when_demo_enabled() (+1 more)

### Community 199 - "Community 199"
Cohesion: 0.21
Nodes (18): _manual_payload(), B4: the manual OTA form lets the receptionist type a total + currency     that d, B4: the manual OTA form lets the receptionist type a total + currency     that d, The receptionist can type TWO independent prices (ARS and USD) for a     manual, The receptionist can type TWO independent prices (ARS and USD) for a     manual, Root-cause repro for the owner's report: a category with a RatePlan     that is, Root-cause repro for the owner's report: a category with a RatePlan     that is, _seed_hotel() (+10 more)

### Community 200 - "Community 200"
Cohesion: 0.16
Nodes (17): A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, A1: resolve() used to call seed_default_permissions() on every invocation      (, _seed_hotel(), test_company_night_rate_permission_defaults_allow_management_roles(), test_get_matrix_includes_hotel_overrides(), test_housekeeping_cannot_create_reservation_by_default() (+9 more)

### Community 201 - "Community 201"
Cohesion: 0.18
Nodes (19): opened_cash_register(), _payment(), Immediate cash settlement scenarios require an operator-opened caja., Immediate cash settlement scenarios require an operator-opened caja., Immediate cash settlement scenarios require an operator-opened caja., _reservation(), test_direct_extension_can_leave_balance_pending_without_a_payment(), test_extension_card_payment_with_pos_reference_is_completed_and_audited() (+11 more)

### Community 202 - "Community 202"
Cohesion: 0.20
Nodes (16): Public contact form endpoint for the marketing site., PublicInquiry, PublicInquiryNotificationStatus, A contact request captured by the public marketing site.      The table is inten, create_public_inquiry(), _digest_key(), _notification_body(), _notify_inquiry() (+8 more)

### Community 203 - "Community 203"
Cohesion: 0.12
Nodes (5): _fix_operational_clock_time(), Local hotel-scoped business clock API and date isolation coverage., test_laundry_batch_uses_business_date_for_timestamps_and_batch_code(), test_stock_and_linen_ledger_timestamps_use_hotel_business_clock(), test_task_events_and_shift_handoffs_use_business_clock()

### Community 204 - "Community 204"
Cohesion: 0.23
Nodes (16): _company_reservation(), _deferred_company(), v72 §3.5 corporate deferred billing flow (R5b ITEM C).  A company reservation wi, test_company_account_extension_rejects_tourist_disabled_and_cross_hotel_companies(), test_deferred_company_extension_cannot_collect_base_rate_in_pms(), test_deferred_company_extension_does_not_calculate_or_record_base_price(), test_deferred_company_extension_keeps_request_pending_when_conflict_is_unresolved(), test_deferred_company_payment_api_rejects_base_balance_without_writes() (+8 more)

### Community 205 - "Community 205"
Cohesion: 0.17
Nodes (11): _FakeResponse, _quote(), _seed_expired_conversion_cache(), test_blue_equivalent_fails_closed_when_any_source_quote_is_stale(), test_blue_equivalent_for_non_usd_currency_is_explicitly_derived(), test_fresh_quote_rejects_crossed_buy_sell_values(), test_provider_outage_returns_none_without_a_fresh_cached_quote(), test_provider_outage_uses_cached_exact_market_quote_up_to_24_hours() (+3 more)

### Community 206 - "Community 206"
Cohesion: 0.37
Nodes (18): _category(), _guest(), _hotel(), _reservation(), _room(), test_active_room_block_excludes_room_from_availability(), test_allocation_candidates_exclude_blocked_rooms(), test_allocation_candidates_scope_room_blocks_to_overlapping_stays() (+10 more)

### Community 207 - "Community 207"
Cohesion: 0.22
Nodes (15): _move(), _seed_move_shapes(), test_capacity_tier_alone_includes_each_narrower_tier(), test_checked_in_room_move_returns_conflict_when_destination_checklist_is_open(), test_company_move_preserves_contracted_category_and_extra_guest_capacity_is_physical(), test_existing_wide_roles_still_move_anywhere(), test_manager_can_move_each_shape(), test_manager_can_override_open_checklist_for_checked_in_move_with_audited_reason() (+7 more)

### Community 208 - "Community 208"
Cohesion: 0.19
Nodes (16): _seed_group(), test_company_grouped_move_preserves_sold_category_and_revert_checks_physical_capacity(), test_housekeeping_cannot_list_read_or_revert_movement_groups(), test_list_movement_groups_with_filters(), test_movement_group_hotel_isolation(), test_read_movement_group_detail_includes_movements(), test_receptionist_can_list_movement_groups_but_cannot_revert_them(), test_revert_already_reverted_group_returns_400() (+8 more)

### Community 209 - "Community 209"
Cohesion: 0.14
Nodes (18): advance_business_clock_by_one_day(), email_status(), Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider., Lightweight status so the frontend can check the active system email provider. (+10 more)

### Community 210 - "Community 210"
Cohesion: 0.20
Nodes (11): archive_chat_session(), get_chat_history(), get_chat_insights(), get_chat_session(), _load_payload(), send_chat_message(), _serialize_actions(), _serialize_insight() (+3 more)

### Community 211 - "Community 211"
Cohesion: 0.18
Nodes (17): archiveHotelRole(), create_role(), createHotelRole(), CreateHotelRolePayload, delete_role(), fetchHotelRoles(), HotelRole, HotelRoleCode (+9 more)

### Community 212 - "Community 212"
Cohesion: 0.24
Nodes (11): LocalizedDateFieldProps, dateInputCursorPosition(), formatDateInputValue(), formatDateTimeInputValue(), formatNativeDateTimeValue(), formatNativeDateValue(), maskDateInputValue(), maskDateTimeInputValue() (+3 more)

### Community 213 - "Community 213"
Cohesion: 0.16
Nodes (14): ApiRequestMetric, ApiResponseMetric, browseUntil(), createOneReservation(), createReservationBatch(), durationSeconds, measureUiAction(), navigate() (+6 more)

### Community 214 - "Community 214"
Cohesion: 0.19
Nodes (2): OnboardingState, Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr

### Community 215 - "Community 215"
Cohesion: 0.17
Nodes (17): _fake_google_claims(), test_auth_flows_fail_without_connected_mail_provider(), test_auth_providers_exposes_only_public_google_capabilities(), test_google_account_can_set_password_only_with_linked_google_proof_and_csrf(), test_google_link_wrong_password_does_not_mutate_or_invalidate_the_local_session(), test_google_login_creates_new_user_when_email_unknown(), test_google_login_does_not_replace_another_linked_subject(), test_google_login_rejects_invalid_issuer_audience_or_expiry() (+9 more)

### Community 217 - "Community 217"
Cohesion: 0.28
Nodes (16): _legacy_rounding_credit_payment(), _mock_usd_to_ars_quote(), _open_cash(), Focused tests for exact FX settlement, cash change and historical refunds., Seed a historical payment row so the old credit-refund path stays covered., _reservation(), test_arbitrary_fx_overpayment_is_rejected_even_when_rounding_is_configured(), test_configured_rounding_never_changes_exact_fx_principal_or_issues_credit() (+8 more)

### Community 218 - "Community 218"
Cohesion: 0.21
Nodes (16): test_handoff_is_tenant_scoped_and_acknowledged(), test_housekeeping_can_read_all_general_tasks_but_cannot_operate_them(), test_list_tasks_does_not_query_unreturned_relationships(), test_list_tasks_orders_priority_and_due_date(), test_maintenance_task_keeps_block_until_authorized_release(), test_operator_scope_matches_role_and_assignment(), test_report_only_custom_manager_cannot_read_or_mutate_out_of_scope_tasks(), test_task_author_fallback_is_hotel_scoped_and_used_by_list_create_and_update() (+8 more)

### Community 219 - "Community 219"
Cohesion: 0.29
Nodes (16): _configured_settings(), _inquiry_rows(), _payload(), test_public_inquiry_collapses_newlines_in_single_line_email_fields(), test_public_inquiry_does_not_trust_spoofable_forwarded_for(), test_public_inquiry_has_global_limit_when_trusted_edge_ip_is_missing(), test_public_inquiry_honeypot_is_silently_accepted_without_storage(), test_public_inquiry_is_not_stored_when_notification_recipient_is_unconfigured() (+8 more)

### Community 220 - "Community 220"
Cohesion: 0.27
Nodes (17): _client_with_db(), _override_auth(), API-level coverage for stock items: delete-then-recreate (owner-reported bug), u, Owner: "editar el producto por las dudas" -- PATCH already accepted     every fi, Same convention as POST /api/payment-links: a client resending the     same POST, _second_hotel(), _teardown(), test_duplicate_active_name_returns_clean_409_not_a_500() (+9 more)

### Community 221 - "Community 221"
Cohesion: 0.27
Nodes (17): _client_with_db(), _movement(), _override_auth(), D5 (Via D): GET /api/stock/consumption-report -- ordinary out movements for a pe, _seed_hotels(), _teardown(), test_consumption_report_api_is_hotel_isolated(), test_consumption_report_api_requires_stock_permission() (+9 more)

### Community 222 - "Community 222"
Cohesion: 0.12
Nodes (5): _bearer_headers(), Real row locks serialize overlapping refreshes without losing the cookie., test_login_json_and_bearer_contract_remain_unchanged_while_cookie_is_additive(), test_postgres_concurrent_refreshes_recover_the_same_successor(), test_session_listing_individual_revoke_logout_and_revoke_all()

### Community 223 - "Community 223"
Cohesion: 0.16
Nodes (10): CeleryJobDispatcher, dispatch_once(), JobDispatcher, JobSpec, Portable job-dispatch port with Celery as the first implementation., Create one durable intent per tenant/task/key before dispatching.      A duplica, JobDispatchRecord, Durable worker coordination records for portable job dispatch. (+2 more)

### Community 224 - "Community 224"
Cohesion: 0.23
Nodes (13): _asset_entries(), BundleVerificationError, _discover(), discover_script_urls(), fetch_assets(), main(), _NoRedirect, _origin() (+5 more)

### Community 225 - "Community 225"
Cohesion: 0.22
Nodes (16): _booking_status_label_es(), _booking_to_read(), cancel_booking(), checkin_booking(), checkout_booking(), create_booking(), delete_booking(), _ensure_permission_tier() (+8 more)

### Community 226 - "Community 226"
Cohesion: 0.12
Nodes (17): _consume_xlsx_export_queue(), _is_demo_mode_enabled(), lifespan(), Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Initialize database on application startup., Initialize database on application startup., Seed the permission matrix once at boot (per worker process).      A1 fix: seed_, Seed the permission matrix once at boot (per worker process).      A1 fix: seed_ (+9 more)

### Community 227 - "Community 227"
Cohesion: 0.25
Nodes (14): AIAssistantActionRun, AIAssistantInsight, AIAssistantMessage, AIAssistantSession, AI assistant session and message models.  Phase 1 keeps Gemma in read-only/propo, Raised when a suggested action cannot be persisted or executed safely., classify_gemma_intent(), _extract_keywords() (+6 more)

### Community 228 - "Community 228"
Cohesion: 0.18
Nodes (17): DomainEventOutbox, One durable delivery attempt for one hotel/domain invalidation., discard_queued_domain_changes(), get_domain_event_outbox_metrics(), queue_domain_change(), QueuedDomainChange, Report pending-outbox depth/age for one tenant; warn when stale.      "Stale" me, A safe invalidation signal waiting for the surrounding DB commit. (+9 more)

### Community 229 - "Community 229"
Cohesion: 0.12
Nodes (5): OTAProviderAdapter, FailingBookingAdapter, FakeBookingAdapter, test_ota_orchestrator_records_failed_verification(), test_ota_orchestrator_verifies_connection_and_persists_event()

### Community 230 - "Community 230"
Cohesion: 0.13
Nodes (13): _OutboxPublishAttempt, _OutboxPublishCooldown, publish_queued_domain_changes(), Redis outcome to persist after every publish in the batch has finished., Process-local gate for durable after-commit Redis publishes only., Return a permit, or skip while cooling down / another probe runs., A successful recovery probe closes only the cooldown it owns., Open or extend the cooldown after an actual durable publish fails. (+5 more)

### Community 231 - "Community 231"
Cohesion: 0.18
Nodes (7): _CachedFailure, CachedOutboxPollFailure, OutboxPollBatchCache, _PollEntry, Short-lived singleflight cache for PostgreSQL event-outbox polling.  The Postgre, A same-window poll failed already; wait for the next bounded retry., Deduplicate concurrent per-process polls without extending freshness.

### Community 232 - "Community 232"
Cohesion: 0.24
Nodes (16): _completed_at(), _duplicate_webhook_result(), _enqueue_provider_payment_reconciliation_alert(), _ensure_completed_transaction(), _existing_reconciliation_review_code(), _find_existing_event(), ingest_webhook(), _insert_event() (+8 more)

### Community 233 - "Community 233"
Cohesion: 0.13
Nodes (17): _apply_setting(), Set both principals for a request or a single-hotel worker job., Flag the transaction as a verified master-admin session.      RLS policies that, Issue ``set_config`` for one setting.      ``connection`` is passed by ``reapply, Stash the last value applied for ``setting_name`` on this session.      ``sessio, Reapply stashed tenant settings directly on a just-begun ``Connection``.      Ca, Set the authenticated user id used by membership RLS policies., Set or clear the current hotel id for tenant-scoped RLS policies. (+9 more)

### Community 234 - "Community 234"
Cohesion: 0.16
Nodes (7): _postgres_e2e_environment(), test_reset_e2e_database_never_deletes_postgres_target_files(), test_seed_guard_accepts_explicit_high_local_postgres_port(), test_seed_guard_accepts_only_explicit_loopback_postgres_e2e_database(), test_seed_guard_accepts_secondary_ipv4_loopback_for_isolated_postgres(), test_seed_guard_rejects_postgres_without_the_dedicated_local_test_boundary(), test_seed_guard_requires_a_distinct_explicit_seed_role_on_the_same_local_database()

### Community 235 - "Community 235"
Cohesion: 0.13
Nodes (15): opened_cash_register(), Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Payment lifecycle tests explicitly model an operator-opened caja., Tests for deposit (señas) payment flow., Payment lifecycle tests explicitly model an operator-opened caja., Scenario: $1000 reservation. Pay 30% deposit ($300).         Expected: Status → (+7 more)

### Community 236 - "Community 236"
Cohesion: 0.12
Nodes (9): An inactive PricePeriod must not be used as fallback., Archived CategoryPricing rows no longer override the category base., Final tier: with no DailyRate or PricePeriod the resolver         returns the ca, per-method column (price_cash) wins over base price when specified., When requested payment method column is NULL, base DailyRate price is used., When two PricePeriods overlap, the one with higher priority is returned., Tier-1: explicit DailyRate row wins over everything else., DailyRate explicit row takes priority over an active PricePeriod. (+1 more)

### Community 237 - "Community 237"
Cohesion: 0.14
Nodes (11): Enum, PendingActionPriorityEnum, PendingActionStatusEnum, PendingActionTypeEnum, PendingOperationalAction — the "pending_actions" table referenced throughout the, Durable tenant-scoped metadata for private object-storage blobs., ReservationEmailDeliveryRead, ReservationEmailKind (+3 more)

### Community 238 - "Community 238"
Cohesion: 0.21
Nodes (16): HotelBusinessClock, Persist the latest simulated business date for a single hotel.      The row is i, business_clock_enabled_for_hotel(), hotel_business_now(), hotel_timezone_name(), Return whether the explicitly selected local synthetic hotel may use     its per, Return a valid timezone for this hotel, using UTC for legacy gaps., Return a valid timezone for this hotel, using UTC for legacy gaps. (+8 more)

### Community 239 - "Community 239"
Cohesion: 0.13
Nodes (2): HotelConfigUpdate, _normalize_currency()

### Community 240 - "Community 240"
Cohesion: 0.22
Nodes (16): _auth_headers(), _enroll_and_confirm_mfa(), _next_totp_code(), test_disable_mfa_requires_current_password_and_a_valid_factor(), test_google_only_account_can_disable_mfa_with_fresh_linked_google_proof(), test_google_only_account_needs_fresh_linked_provider_proof_to_enroll_mfa(), test_login_without_mfa_keeps_returning_the_normal_auth_response(), test_mfa_enroll_confirm_uses_encrypted_secret_and_requires_second_login_step() (+8 more)

### Community 241 - "Community 241"
Cohesion: 0.26
Nodes (14): _create_role(), Security and API contract tests for per-hotel custom roles., _step_up_headers(), test_authenticated_context_resolves_custom_role_base_and_fails_closed_for_missing_role(), test_custom_role_downgrade_aborts_before_any_data_changes(), test_custom_role_permission_precedence_invariants_and_tenant_isolation(), test_custom_role_visibility_inherits_base_and_unknown_roles_fail_closed(), test_custom_roles_can_be_assigned_and_invited_but_owner_transfer_stays_separate() (+6 more)

### Community 242 - "Community 242"
Cohesion: 0.21
Nodes (9): FakePostgresSession, FakeRedis, _settings(), test_decorator_passes_the_database_session_to_postgres_lock(), test_lock_is_exclusive_and_releases_only_when_owned(), test_optional_lock_can_degrade_when_redis_is_unavailable(), test_required_lock_fails_closed_when_redis_is_unavailable(), test_required_lock_reports_busy_postgres_advisory_lock() (+1 more)

### Community 243 - "Community 243"
Cohesion: 0.19
Nodes (10): ExplodingDB, ExplodingRequest, Fail-closed boundary tests: disabled lanes do no parsing, DB work or network., test_apple_login_stops_before_jwks_or_db(), test_connections_flag_alone_closes_credential_lane(), test_credential_access_and_email_stop_before_db_or_network(), test_google_login_stops_before_transport_or_db(), test_ota_callback_stops_before_json_parse() (+2 more)

### Community 244 - "Community 244"
Cohesion: 0.18
Nodes (11): Tests for B2: GET /api/reservations/occupancy-grid (planilla de ocupación).  Cro, Regression guard for the plan's explicit note: the naive `balance_due`     ignor, Regression guard for the plan's explicit note: the naive `balance_due`     ignor, _reserve(), test_cancelled_reservation_is_excluded(), test_checked_out_reservation_does_not_reduce_free_room_count(), test_custom_housekeeping_role_gets_anonymized_occupancy_grid(), test_operational_balance_due_includes_consumption_charges() (+3 more)

### Community 245 - "Community 245"
Cohesion: 0.26
Nodes (11): _load_migration(), Unit coverage for the guarded PostgreSQL enum-label migration., _RecordingBind, _Result, test_downgrade_reverses_only_the_new_migration(), test_revision_fits_alembic_version_column(), test_sqlite_skips_postgresql_enum_ddl(), test_upgrade_fails_closed_if_both_enum_labels_exist() (+3 more)

### Community 246 - "Community 246"
Cohesion: 0.24
Nodes (15): _seed_pricing_foundation(), test_all_supported_fx_pairs_use_directional_quotes_via_ars(), test_blue_non_usd_conversion_does_not_use_official_currency_snapshot(), test_blue_non_usd_conversion_uses_only_matching_derived_snapshot(), test_conversion_returns_the_full_precision_rate_used_for_amount(), test_global_blue_market_dominates_fx_policy_source_and_side(), test_missing_selected_blue_market_does_not_fall_back_to_official_snapshot(), test_negative_fx_spread_is_rejected_instead_of_reducing_hotel_quote() (+7 more)

### Community 247 - "Community 247"
Cohesion: 0.27
Nodes (14): _ctx(), _seed_hotel(), test_apply_promotions_never_goes_negative(), test_create_promotion_rejects_duplicate_code(), test_create_promotion_rejects_percentage_over_100(), test_deactivate_and_reactivate_promotion(), test_find_applicable_promotions_for_many_nights_uses_bounded_queries(), test_find_applicable_promotions_for_nights_batches_rules_and_guest_tags() (+6 more)

### Community 248 - "Community 248"
Cohesion: 0.23
Nodes (14): Security regression tests for local QA operator attestations., tagged(), test_altered_signature_is_rejected(), test_attestation_older_than_24_hours_is_rejected(), test_issuer_cannot_refresh_qa_executed_more_than_24_hours_ago(), test_issuer_refuses_evidence_hash_without_a_real_local_artifact(), test_issuer_refuses_symlinked_artifact_even_when_target_bytes_match(), test_manifest_byte_change_after_signing_is_rejected() (+6 more)

### Community 249 - "Community 249"
Cohesion: 0.45
Nodes (14): _build_client(), _cleanup_client(), _override_auth(), _seed_hotel(), test_bulk_field_percent_update_preserves_base_prices_and_excludes_dates(), test_date_to_before_date_from_returns_422(), test_endpoint_rejects_forbidden_role(), test_endpoint_requires_authentication() (+6 more)

### Community 250 - "Community 250"
Cohesion: 0.32
Nodes (14): _period_draft_payload(), _period_values(), seed_rate_context(), test_price_period_create_is_draft_until_confirm_and_preserves_reservation_total(), test_price_period_draft_rejects_daily_rate_changed_after_preview(), test_price_period_draft_rejects_impact_scope_over_366_nights(), test_price_period_preview_excludes_explicit_daily_rate_nights(), test_price_period_update_and_delete_are_staged_and_confirmed_as_soft_delete() (+6 more)

### Community 251 - "Community 251"
Cohesion: 0.31
Nodes (14): _cleanup_room_block_case(), _hold_room_for_checkin(), PostgreSQL regression for a room block encountered during check-in., Observe the exact PostgreSQL lock dependency, without SQL-text filters., _seed_room_block_checkin_case(), _start_block_mutation(), test_postgres_create_block_rejects_existing_reservation_during_checkin(), test_postgres_create_block_requires_allocation_proposal_to_clear_reservation() (+6 more)

### Community 252 - "Community 252"
Cohesion: 0.31
Nodes (13): _override_auth(), _seed_reservation(), _seed_room(), test_create_and_resolve_room_block_api(), test_housekeeping_can_read_active_blocks_but_cannot_extend_them_by_default(), test_housekeeping_cannot_create_room_block_by_default(), test_housekeeping_only_reads_operational_room_block_reasons(), test_receptionist_can_create_but_not_release_room_block_by_default() (+5 more)

### Community 253 - "Community 253"
Cohesion: 0.21
Nodes (14): _headers(), Security settings API is tenant-scoped, redacted and revokes real JWTs., Audit evidence is readable only; there is no ordinary mutation route., Audit evidence is readable only; there is no ordinary mutation route., test_audit_surfaces_do_not_expose_mutating_methods(), test_manager_cannot_read_security_settings(), test_revoke_all_invalidates_the_callers_previous_token(), test_security_actor_labels_use_the_current_tenant_alias_in_events_timeline_and_csv() (+6 more)

### Community 254 - "Community 254"
Cohesion: 0.13
Nodes (14): §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., §7.1 positive: paying the remaining balance after deposit allows check-in., Cannot checkout a PENDING reservation., §7.1 positive: paying the remaining balance after deposit allows check-in. (+6 more)

### Community 255 - "Community 255"
Cohesion: 0.15
Nodes (1): DespegarAdapter

### Community 256 - "Community 256"
Cohesion: 0.15
Nodes (1): ExpediaAdapter

### Community 257 - "Community 257"
Cohesion: 0.19
Nodes (7): Public WhatsApp bot hooks authenticated only by hotel API key., availability_lookup(), create_reservation(), generate_payment_link(), options_with_prices(), price_quote(), WhatsAppBookingError

### Community 258 - "Community 258"
Cohesion: 0.33
Nodes (14): DrillError, main(), _pg_command(), _pg_count(), _postgres_parts(), Expected, safe failure for a local drill., Verify every ready metadata row against the local blob before restore., _run_pg_command() (+6 more)

### Community 259 - "Community 259"
Cohesion: 0.30
Nodes (13): add_company_night_charges(), _company(), _company_night_charges_summary(), correct_company_night_charge_amounts(), create_company_nightly_surcharge_rate(), get_company_night_charges(), list_company_nightly_surcharge_rates(), _paid_and_pending_by_charge() (+5 more)

### Community 260 - "Community 260"
Cohesion: 0.19
Nodes (13): DomainEvent, get_realtime_client(), _get_realtime_fast_fail_client(), _get_redis_client(), publish_domain_event(), Get the short-timeout Redis client used only by post-commit signals., Return a configured client after a bounded connectivity check., Publish one event. ``revision``/``occurred_at`` let an outbox replay     reuse t (+5 more)

### Community 261 - "Community 261"
Cohesion: 0.41
Nodes (13): _guest(), _hotel(), _reservation(), _room(), test_authorized_override_allows_checkin_and_audits(), test_guest_quick_profile_returns_recent_stays_and_tags(), test_guest_search_matches_document_phone_email_name(), test_prohibido_alojar_blocks_checkin_without_override() (+5 more)

### Community 262 - "Community 262"
Cohesion: 0.23
Nodes (10): _checked_in_reservation(), _checkout(), _complete(), Fixed, tenant-scoped post-checkout housekeeping checklist regressions., test_checkout_creates_fixed_checklist_and_final_item_releases_cleaning_room(), test_complete_item_is_tenant_scoped(), test_completing_checklist_preserves_maintenance_and_blocked_rooms(), test_item_completion_is_idempotent_and_does_not_increment_version() (+2 more)

### Community 263 - "Community 263"
Cohesion: 0.13
Nodes (11): Verify auto-generated timestamps., Verify auto-generated timestamps., Tests for Guest and GuestCompanion models., Tests for Guest and GuestCompanion models., Verify guest with full data., Verify guest with full data., Verify the has_valid_identity property detects missing documents., Verify the has_valid_identity property detects missing documents. (+3 more)

### Community 264 - "Community 264"
Cohesion: 0.13
Nodes (11): Tests for Reservation model and state machine., Tests for Reservation model and state machine., Verify the state machine transition map is correct., Verify the state machine transition map is correct., Verify can_transition_to method., Verify can_transition_to method., Verify balance_due computed property., Verify balance_due computed property. (+3 more)

### Community 265 - "Community 265"
Cohesion: 0.13
Nodes (11): Tests for Room and RoomCategory models., Tests for Room and RoomCategory models., Verify categories are created with correct attributes., Verify categories are created with correct attributes., Verify rooms are created and linked to categories., Verify rooms are created and linked to categories., Verify bidirectional Room ↔ RoomCategory relationship., Verify bidirectional Room ↔ RoomCategory relationship. (+3 more)

### Community 266 - "Community 266"
Cohesion: 0.15
Nodes (3): _FakeSession, _HotelRowsQuery, test_enabled_task_visits_active_and_inactive_hotels_under_each_context()

### Community 267 - "Community 267"
Cohesion: 0.30
Nodes (13): _auth(), cancellation_client(), Coverage for the manual cancellation review workflow and its access boundary., _seed_reservation(), _set_now(), test_free_window_cancels_without_review(), test_historical_reservation_requires_review_and_approval_does_not_apply_current_policy(), test_legacy_bookings_cancel_route_uses_the_same_penalty_review_flow() (+5 more)

### Community 268 - "Community 268"
Cohesion: 0.27
Nodes (11): _authorization(), _install_recording_dependencies(), _RecordingSession, _reservation_for_preparation(), test_manual_total_update_mutation_and_audit_share_one_commit(), test_mutator_failure_propagates_without_audit_or_commit(), test_paid_total_adjustment_keeps_legacy_audit_key(), test_prepare_deferred_billing_conflict_precedes_payment_and_later_checks() (+3 more)

### Community 269 - "Community 269"
Cohesion: 0.42
Nodes (12): _make_reservation(), Tests for V72 §5 - Concurrency guards: double-booking and duplicate payments.  T, _seed_category(), _seed_guest(), _seed_hotel(), _seed_room(), test_allocation_overflow_can_be_waitlisted(), test_allocation_respects_existing_reservations() (+4 more)

### Community 270 - "Community 270"
Cohesion: 0.18
Nodes (8): get_paypal_adapter(), PayPalAdapter, PayPal Payment Adapter. Wraps the PayPal REST SDK to create orders and capture p, Execute (capture) a PayPal payment after customer approval.         Called when, Process a PayPal webhook notification., Service adapter for PayPal payment integration.     Creates orders and processes, Lazy-initialize the PayPal API., Create a PayPal payment (order).         Returns a redirect URL for the customer

### Community 271 - "Community 271"
Cohesion: 0.20
Nodes (9): FastAPI routes for provider connections. Exposes /api/connections/{provider}/con, Connection, Connection model for external provider integrations. Stores credentials/settings, ConnectionError, Connection service to manage external provider credentials/settings. Provides an, Raised for validation problems while creating/updating a connection., Create or update a provider connection while keeping JSON fields intact.     - N, upsert_connection() (+1 more)

### Community 272 - "Community 272"
Cohesion: 0.14
Nodes (14): Hide invitation/OTA capabilities from application logs., Hide invitation capabilities from application logs for legacy/malformed paths., Hide invitation/OTA capabilities from application logs., Emit bounded HTTP timing fields and make correlation IDs observable., Emit bounded HTTP timing fields and make correlation IDs observable., Emit bounded HTTP timing fields and make correlation IDs observable., Hide invitation/OTA capabilities from application logs., Hide invitation/OTA capabilities from application logs. (+6 more)

### Community 273 - "Community 273"
Cohesion: 0.18
Nodes (13): _client_signature(), get_async_redis_client(), get_sync_redis_client(), namespaced_key(), Shared Redis/Valkey client construction.  Redis is a best-effort layer in this a, Clear process clients for tests and orderly shutdown., Return one async client per process for async transports., Clear process clients for tests and orderly shutdown. (+5 more)

### Community 274 - "Community 274"
Cohesion: 0.22
Nodes (4): OTAOrchestratorService, build_default_ota_orchestrator(), get_default_adapter(), Default OTA adapter registry.  This keeps provider construction in one place so

### Community 275 - "Community 275"
Cohesion: 0.14
Nodes (11): PermissionCatalogItem, PermissionDecision, PermissionOverrideBatchChange, PermissionOverrideBatchRequest, Set both sides of one role's reservation visibility window., RolePermissionOverrideRequest, TemporaryActionGrantApproveRequest, TemporaryActionGrantRequest (+3 more)

### Community 276 - "Community 276"
Cohesion: 0.35
Nodes (13): approve_cash_expense(), CashExpenseError, create_cash_expense(), _decode_receipt(), _delete_object_key(), get_cash_expense(), get_cash_expense_receipt_bytes(), list_cash_expenses() (+5 more)

### Community 277 - "Community 277"
Cohesion: 0.21
Nodes (13): distributed_lock(), _get_redis_client(), Small Redis/Valkey lease used to serialize cross-worker critical paths., Decorate a service operation with a deterministic hotel-scoped lease., Decorate a service operation with a deterministic hotel-scoped lease., Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a transaction-scoped PostgreSQL advisory lock when available.      ``Tru, Acquire a short lease and release it only if this worker owns it.      Redis/Val (+5 more)

### Community 278 - "Community 278"
Cohesion: 0.21
Nodes (6): FakeWarehouseClient, _settings(), test_clickhouse_schema_is_derived_and_tenant_partitioned(), test_operational_schema_covers_dimensions_and_non_pii_facts(), test_reconcile_compares_source_and_derived_counts(), test_required_warehouse_configuration_fails_closed()

### Community 279 - "Community 279"
Cohesion: 0.36
Nodes (12): _booking_payload(), _seed_booking_secret(), test_booking_cancel_after_checkin_requires_manual_resolution(), test_booking_cancel_cancels_existing_pre_checkin_reservation(), test_booking_cancel_with_confirmed_external_payment_requires_settlement_review(), test_booking_modify_after_checkin_or_checkout_rejects_stay_or_room_changes(), test_booking_modify_after_checkin_preserves_room_for_same_stay_and_category(), test_booking_modify_rechecks_current_room_after_lock_and_reassigns_on_conflict() (+4 more)

### Community 280 - "Community 280"
Cohesion: 0.38
Nodes (13): _seed_daily_rates(), _seed_hotel(), test_canonical_pricing_applies_per_night_promotion_and_clamps_at_zero(), test_canonical_pricing_applies_tax_policy(), test_canonical_pricing_base_only_no_promotions(), test_canonical_pricing_converts_currency_with_fx_snapshot(), test_canonical_pricing_extracts_included_tax_from_daily_price(), test_canonical_pricing_from_night_n_scope_only_applies_from_that_night() (+5 more)

### Community 281 - "Community 281"
Cohesion: 0.26
Nodes (13): _add_billing_charge(), _create_checked_in_reservation(), opened_cash_register(), Tests for v72 check-out balance reconciliation., Checkout balance scenarios collect cash through an open caja., Checkout balance scenarios collect cash through an open caja., Checkout balance scenarios collect cash through an open caja., test_checkout_allows_deferred_company_balance_without_changing_financial_records() (+5 more)

### Community 282 - "Community 282"
Cohesion: 0.14
Nodes (9): If run_persisted_allocation raises, rollback must be called (not commit)., If run_persisted_allocation raises, rollback must be called (not commit)., §5.2 — Integration: after new booking, allocation engine receives correct args., §5.2 — Integration: after new booking, allocation engine receives correct args., When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, When _trigger_reoptimization_bg runs, it must call run_persisted_allocation, The background task must commit and close its own DB session., The background task must commit and close its own DB session. (+1 more)

### Community 283 - "Community 283"
Cohesion: 0.31
Nodes (12): _delivery(), _message(), _post(), HTTP boundary tests for the Meta Cloud API WhatsApp webhook.  The endpoint had n, Regression: a bad phone used to raise 400 and roll the whole batch back.      Me, ``text`` and ``profile`` arriving as strings must not raise a 500., _signature(), test_ingests_a_signed_inbound_message() (+4 more)

### Community 284 - "Community 284"
Cohesion: 0.20
Nodes (13): _backfill_from_legacy_tags(), downgrade(), _ensure_guest_hotel_id_unique(), _ensure_guest_tags_hotel_id_unique(), _install_rls(), add guest_restrictions table with tenant-scoped composite FK and legacy backfill, Same rationale as `_ensure_guest_hotel_id_unique`, for guest_tags(hotel_id, id):, Create an active GuestRestriction for every currently-active (non-expired)     l (+5 more)

### Community 285 - "Community 285"
Cohesion: 0.19
Nodes (8): EmailSendResponse, EmailVerifyResponse, Legacy public email endpoints.  The system transactional mail now lives exclusiv, _retired(), send_reset(), send_verification(), SmtpStatus, verify_code()

### Community 286 - "Community 286"
Cohesion: 0.22
Nodes (9): audited_change(), _extract_actor_user_id(), _extract_db(), _extract_entity_arg(), _extract_record_id(), _first_bound_value(), _get_model_for_table(), _load_entity() (+1 more)

### Community 287 - "Community 287"
Cohesion: 0.19
Nodes (6): _clean_optional(), _clean_required(), PublicInquiryAccepted, PublicInquiryCreate, PublicInquiryRead, Validation and response contracts for public marketing inquiries.

### Community 288 - "Community 288"
Cohesion: 0.32
Nodes (12): _assert_analytics_chat_domain(), build_analytics_chat_answer(), build_anomalies_insight(), build_home_insight(), _build_insight(), build_pricing_insight(), _chat_context(), _fallback_insight_summary() (+4 more)

### Community 289 - "Community 289"
Cohesion: 0.22
Nodes (8): Mailer, Platform email service facade backed by the system transactional provider., Send a neutral notice without revealing whether an account exists., send_generic_auth_notice_email(), send_platform_email(), send_reset_password_email(), send_verification_email(), send_verification_success_email()

### Community 290 - "Community 290"
Cohesion: 0.45
Nodes (11): _append_action_event_message(), apply_action_run_draft(), approve_action_run(), _coerce_numeric_dict(), _enum_value_or_text(), GemmaActionRunError, get_action_run(), _get_created_suggestion_id() (+3 more)

### Community 291 - "Community 291"
Cohesion: 0.31
Nodes (12): _actor_name(), _area_for(), _bounds(), _date_filter(), list_operational_audit(), _matches(), _money(), _row() (+4 more)

### Community 292 - "Community 292"
Cohesion: 0.28
Nodes (12): _body_size_estimate(), _fallback_url(), _json_size_estimate(), observed_async_http_call(), observed_http_call(), Privacy-safe size and latency telemetry for outbound HTTP calls., Call an HTTP client and log only destination, byte counts, time and status., Async equivalent of :func:`observed_http_call`. (+4 more)

### Community 293 - "Community 293"
Cohesion: 0.29
Nodes (12): _apply_tax_policy(), _calculate_rule_amount(), _convert_amount(), _load_json_dict(), _quote_provenance(), quote_rate_plan_stay(), _record_conversion_snapshot(), _resolve_commission_amount() (+4 more)

### Community 294 - "Community 294"
Cohesion: 0.24
Nodes (9): _date_window(), _decimal_total(), detect_no_shows(), _parse_datetime(), project_all_derived_facts_incremental(), _project_all_hotels_window(), project_operational_facts_to_clickhouse(), _project_operational_window() (+1 more)

### Community 295 - "Community 295"
Cohesion: 0.22
Nodes (13): _configure_resend(), JWTs are stateless with no server-side blacklist, so a password reset -     the, JWTs are stateless with no server-side blacklist, so a password reset -     the, JWTs are stateless with no server-side blacklist, so a password reset -     the, _register_owner(), test_google_account_link_waits_for_mfa_and_preserves_password(), test_google_link_rejects_mismatched_email_without_mutation(), test_google_link_requires_password_and_matching_verified_identity() (+5 more)

### Community 296 - "Community 296"
Cohesion: 0.44
Nodes (12): _close(), _guest(), _override_auth(), Per-person arrival recording, hotel policy, and tenant isolation., _seed_reservation(), _test_app(), test_each_guest_arrival_is_idempotent_and_only_first_occupies_room(), test_first_arrival_keeps_assigned_and_ready_room_gate() (+4 more)

### Community 297 - "Community 297"
Cohesion: 0.36
Nodes (11): _get_db_override_target(), isolated_client(), _seed_hotel(), _seed_hotel_payload(), _seed_membership(), _set_auth_context_override(), test_checkin_guest_validation_should_not_leak_foreign_guest(), test_foreign_room_and_reservation_details_are_hidden() (+3 more)

### Community 298 - "Community 298"
Cohesion: 0.15
Nodes (11): Critical test: Simulates web booking with deposit, then balance payment at check, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi, Critical test: Simulates web booking with deposit, then balance payment at check, Critical test: Simulates web booking with deposit, then balance payment at check, Critical test: Simulates web booking with deposit, then balance payment at check, Requirement test:         1. Web booking of $1000         2. Pay $300 deposit vi (+3 more)

### Community 299 - "Community 299"
Cohesion: 0.24
Nodes (12): _backfill_defaults(), _contract_legacy_rows(), _copy_role_overrides(), downgrade(), _insert_permission_rows(), _install_user_override_rls(), expand RBAC catalog and add tenant-scoped user overrides  Revision ID: 20260813_, Install the PostgreSQL tenant policy; no-op on other dialects. (+4 more)

### Community 300 - "Community 300"
Cohesion: 0.20
Nodes (6): ABC, EmailProvider, EmailProviderError, get_email_provider(), NullEmailProvider, ResendEmailProvider

### Community 301 - "Community 301"
Cohesion: 0.20
Nodes (7): get_mercadopago_adapter(), MercadoPagoAdapter, MercadoPago Payment Adapter. Wraps the MercadoPago SDK to create payment prefere, Process fields delivered by a Mercado Pago callback without querying         the, Service adapter for MercadoPago payment integration.     Creates checkout prefer, Lazy-initialize the MercadoPago SDK., Create a MercadoPago checkout preference.         Returns a redirect URL for the

### Community 302 - "Community 302"
Cohesion: 0.36
Nodes (11): fail(), load_json_object(), main(), mapping(), nested_value(), positive_integer(), preview_origin(), Return the normalized origin for a credential-free HTTPS preview URL. (+3 more)

### Community 303 - "Community 303"
Cohesion: 0.36
Nodes (11): _assert_replaceable(), build_values(), main(), _new_run_id(), QALocalEnvError, Raised when the local persona file cannot be created safely., _render(), _strong_password() (+3 more)

### Community 304 - "Community 304"
Cohesion: 0.24
Nodes (6): chain_names(), FuncScan, is_db_call(), names of methods in a call chain, outer->inner, root_name(), scan_file()

### Community 305 - "Community 305"
Cohesion: 0.32
Nodes (9): create_document(), _decode_company_pdf(), _get_company(), get_company_document_bytes(), _get_reservation(), _get_reservation_company(), _safe_company_filename(), set_signature_status() (+1 more)

### Community 306 - "Community 306"
Cohesion: 0.23
Nodes (8): _About, create_access_token(), create_signed_token(), decode_access_token(), decode_signed_token(), _jwt_secret(), Security helpers: password hashing and JWT issuing/validation., Derive a token-specific secret from the master JWT secret so access and     invi

### Community 307 - "Community 307"
Cohesion: 0.33
Nodes (9): _pending_requests(), _reservation_payload(), test_background_worker_generates_only_a_reviewable_run_and_preserves_first_fit(), test_direct_and_inbound_ota_bookings_request_one_coalesced_proposal(), test_pending_proposal_coalesces_different_automatic_triggers(), test_real_background_solver_stores_room_moves_as_proposals(), test_waitlisted_or_out_of_horizon_reservation_does_not_request_current_run(), test_worker_defers_when_allocation_lock_is_busy_and_keeps_request_retryable() (+1 more)

### Community 309 - "Community 309"
Cohesion: 0.42
Nodes (10): _seed_hotel(), _seed_reservation(), _step_up_headers(), test_guest_export_allows_owner_and_excludes_other_hotels(), test_guest_export_denies_unpermitted_role_without_csv_pii(), test_guest_export_excludes_soft_deleted_guest_identity(), test_guest_export_neutralizes_formula_like_guest_fields(), test_guest_export_permission_can_be_granted_to_receptionist_by_owner() (+2 more)

### Community 310 - "Community 310"
Cohesion: 0.38
Nodes (12): _create_link(), _post_webhook(), _reservation(), _sign(), test_approved_webhook_completes_transaction_and_updates_reservation(), test_duplicate_webhook_delivery_does_not_double_charge(), test_event_and_payment_ids_remain_distinct_and_replays_are_idempotent(), test_outbound_disabled_route_rejects_unverified_payment() (+4 more)

### Community 311 - "Community 311"
Cohesion: 0.17
Nodes (9): Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies., Tests for HotelConfiguration model., Verify default configuration values., Verify the is_payment_method_enabled helper., Verify JSON serialization for extra_policies. (+1 more)

### Community 312 - "Community 312"
Cohesion: 0.17
Nodes (8): Tests for database models — validates schema creation, constraints, relationship, Tests for Transaction model., Create a transaction and verify attributes., Tests for Transaction model., Create a transaction and verify attributes., Verify Transaction → Reservation relationship., Verify Transaction → Reservation relationship., TestTransactionModel

### Community 313 - "Community 313"
Cohesion: 0.26
Nodes (7): _reservation(), test_sweep_anchors_configured_no_show_window_to_hotel_checkin_time(), test_sweep_excludes_checked_in_and_is_idempotent(), test_sweep_is_tenant_scoped(), test_sweep_marks_pending_and_paid_as_no_show_without_changing_money(), test_sweep_respects_local_cutoff_boundary_and_uses_hotel_timezone(), test_sweep_sql_cutoff_filter_matches_elapsed_utc_hours_across_dst()

### Community 314 - "Community 314"
Cohesion: 0.24
Nodes (10): client(), _complete_minimal_onboarding(), End-to-end onboarding flow exposed through the FastAPI routers., Provide a TestClient backed by an in-memory SQLite database., Provide a TestClient backed by an in-memory SQLite database., _register_owner(), test_dashboard_is_blocked_until_onboarding_finishes(), test_finish_requires_all_steps() (+2 more)

### Community 315 - "Community 315"
Cohesion: 0.42
Nodes (11): _add_manager_actor(), _payment(), Regression coverage for manager-approved, atomic payment corrections., _target_reservation(), test_audit_failure_rolls_back_the_entire_correction(), test_cash_duplicate_reversal_is_rejected_when_session_is_not_open(), test_cash_duplicate_reversal_voids_movement_and_excludes_it_from_drawer_totals(), test_cash_reassignment_moves_existing_movement_and_preserves_drawer_totals() (+3 more)

### Community 316 - "Community 316"
Cohesion: 0.29
Nodes (9): _post(), _signature(), test_mismatched_canonical_provider_data_does_not_change_test_row(), test_older_provider_snapshot_cannot_regress_a_newer_payment_state(), test_provider_amount_matches_cents_sent_for_payment_link_test(), test_retryable_provider_fetch_failure_returns_503(), test_unknown_provider_status_preserves_state_and_records_diagnostic(), test_unsigned_reference_cannot_redirect_signed_payment_to_another_test_record() (+1 more)

### Community 317 - "Community 317"
Cohesion: 0.18
Nodes (10): Tests for full payment flow., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid., Pay the full amount at once → status should go directly to fully_paid., Tests for full payment flow., Tests for full payment flow., Tests for full payment flow., Pay the full amount at once → status should go directly to fully_paid. (+2 more)

### Community 318 - "Community 318"
Cohesion: 0.44
Nodes (9): _build_client(), _cleanup(), _override_auth(), test_create_payment_surcharge_allows_a_different_payment_method_than_the_nightly_override(), test_create_payment_surcharge_rejects_percentage_over_100(), test_create_payment_surcharge_rejects_when_hotel_already_has_per_method_nightly_price(), test_payment_surcharge_quote_endpoint_returns_exact_maximum_and_cash_suggestion(), test_payment_surcharge_quote_requires_permission_and_tenant_scopes_reservation() (+1 more)

### Community 319 - "Community 319"
Cohesion: 0.47
Nodes (10): _headers(), _issue_public_key(), _seed_hotel(), _seed_reservation(), test_public_api_rate_limit_is_per_hotel_key(), test_public_availability_requires_active_api_key(), test_public_reservation_is_scoped_to_key_hotel(), test_public_reservation_status_other_hotel_is_404() (+2 more)

### Community 320 - "Community 320"
Cohesion: 0.39
Nodes (9): _add_reservation(), _rows(), _seed_hotel(), _step_up_headers(), test_reservation_export_neutralizes_formula_like_text(), test_reservation_export_rejects_invalid_and_overlong_date_ranges(), test_reservation_export_rejects_results_over_cap_without_truncating(), test_reservation_export_requires_dedicated_permission() (+1 more)

### Community 321 - "Community 321"
Cohesion: 0.26
Nodes (9): _make_reservations(), Tests for A2: paginated + orderable reservation listing.  app/services/reservati, A2 hidden cost: additional_guests/guest.companions/guest.tags are     lazy="sele, test_default_limit_caps_result_at_50(), test_list_projection_keeps_human_room_and_category_fields_in_api_response(), test_listing_uses_one_scalar_reservation_query(), test_order_recent_is_created_at_desc_id_desc(), test_selectin_fan_out_is_bounded_by_limit_not_by_hotel_history() (+1 more)

### Community 322 - "Community 322"
Cohesion: 0.26
Nodes (10): _override_auth(), Reception needs to read room data to build reservations (room picker, availabili, GET api/rooms/categories feeds the category picker on both the     Reservations, GET /api/rooms/categories feeds the category picker on both the     Reservations, test_custom_housekeeping_role_receives_safe_room_projection(), test_receptionist_can_check_room_availability(), test_receptionist_can_list_room_categories(), test_receptionist_can_list_rooms() (+2 more)

### Community 323 - "Community 323"
Cohesion: 0.32
Nodes (11): _dependency_call_name(), _dependency_call_qualname(), _endpoint_source_mentions(), _is_route_secured(), _path_is_allowlisted(), PublicRoute, _route_has_auth_dependency(), _route_has_master_admin_session_gate() (+3 more)

### Community 324 - "Community 324"
Cohesion: 0.52
Nodes (11): _client_with_db(), _create_item(), _override_auth(), Stock count sessions: audited confirmation, recount protection, and tenancy., _start_session(), _teardown(), test_count_confirmation_requires_configurable_permission_and_is_tenant_scoped(), test_count_quantities_and_reasons_are_validated_before_writing() (+3 more)

### Community 325 - "Community 325"
Cohesion: 0.17
Nodes (6): apply_price_period materialises one DailyRate per day in the period., apply_price_period updates an existing DailyRate (always upsert)., A period where start_date == end_date creates exactly 1 row., apply_price_period raises ValueError for an unknown period_id., After apply_price_period, get_price_for_date returns the materialised price., TestApplyPricePeriod

### Community 326 - "Community 326"
Cohesion: 0.17
Nodes (9): §5.2 — Motor reoptimizes after every new reservation., §5.2 — Motor reoptimizes after every new reservation., _trigger_reoptimization_bg is a callable in app.api.reservations., _trigger_reoptimization_bg is a callable in app.api.reservations., §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — Reoptimization failures must NEVER break the booking flow.         If the, §5.2 — The service layer create_reservation has no reoptimization side effect., §5.2 — The service layer create_reservation has no reoptimization side effect. (+1 more)

### Community 327 - "Community 327"
Cohesion: 0.25
Nodes (7): e2ae869 Use Render production as cloud QA surface, example(), Regression tests for final provider-evidence continuity., test_any_provider_subject_drift_is_rejected(), test_cli_rejects_symlinked_manifest(), test_final_observation_cannot_predate_probes(), test_only_a_newer_observation_timestamp_may_change()

### Community 328 - "Community 328"
Cohesion: 0.40
Nodes (10): _canonical_host(), _https_preview_url(), main(), _mapping(), _non_empty(), _timestamp(), _validate_baseline_lease_id(), validate_manifest() (+2 more)

### Community 329 - "Community 329"
Cohesion: 0.22
Nodes (3): delete_company_document(), get_company_document(), _get_document_or_404()

### Community 330 - "Community 330"
Cohesion: 0.40
Nodes (10): Read and resolve the guest room-rejection lifecycle., get_active_guest_room_avoidances(), _get_tenant_guest(), _get_tenant_room(), GuestRoomAvoidanceConflictError, GuestRoomAvoidanceNotFoundError, GuestRoomAvoidanceServiceError, _now() (+2 more)

### Community 331 - "Community 331"
Cohesion: 0.24
Nodes (10): approveTemporaryActionGrant(), denyTemporaryActionGrant(), fetchActiveTemporaryActionGrants(), revokeTemporaryActionGrant(), dateTime(), errorText(), grantsQueryKey(), IssuedToken (+2 more)

### Community 332 - "Community 332"
Cohesion: 0.18
Nodes (5): fixtures, ids, manager, owner, transactionsByReservation

### Community 333 - "Community 333"
Cohesion: 0.42
Nodes (10): clear_stripe_settings(), _get_settings_row(), get_stripe_status(), save_stripe_settings(), _stripe_secret(), stripe_secret_configured(), _validate_stripe_secret(), verify_stripe_signature() (+2 more)

### Community 334 - "Community 334"
Cohesion: 0.33
Nodes (8): LoadConfig, main(), _parse_paths(), percentile(), PhaseMetrics, _run(), run_phase(), safe_headers()

### Community 335 - "Community 335"
Cohesion: 0.36
Nodes (10): _cql_identifier(), _daily_rate_change_row(), ensure_cassandra_schema(), _enum_value(), _json_payload(), project_daily_rate_change(), project_room_state_event(), _room_state_event_row() (+2 more)

### Community 336 - "Community 336"
Cohesion: 0.18
Nodes (11): hotel_today(), local_today(), Return the hotel's current business date.      Prefer `local_today(config.hotel_, Return the hotel's current business date.      Prefer `local_today(config.hotel_, Return the hotel's current business date.      Prefer `local_today(config.hotel_, Return the hotel's current business date.      Prefer `local_today(config.hotel_, Today's calendar date in the hotel's own timezone.      `date.today()` is the *s, Today's calendar date in the hotel's own timezone.      `date.today()` is the *s (+3 more)

### Community 337 - "Community 337"
Cohesion: 0.35
Nodes (10): _canonical_identity(), _enabled(), _identity_contains(), _load_local_evidence(), PostgresTargetSafetyError, Fail-closed safety guard for PostgreSQL tests that mutate schema or data.  Remot, Return ``dsn`` only when provider evidence proves a disposable QA target.      E, The PostgreSQL test target cannot be proven isolated and disposable. (+2 more)

### Community 338 - "Community 338"
Cohesion: 0.55
Nodes (9): _guest(), _reservation(), _seed_hotel(), _slots(), test_active_rejection_never_leaves_guest_unassigned_when_it_is_the_only_room(), test_last_completed_room_and_active_rejections_are_loaded_in_one_batch_query(), test_last_completed_room_signal_is_applied_by_cp_sat_and_greedy(), test_previous_completed_room_signal_requires_the_new_reservation_category() (+1 more)

### Community 339 - "Community 339"
Cohesion: 0.56
Nodes (10): _build_client(), _cleanup_client(), _override_auth(), test_allocation_policy_api_can_review_and_apply_suggestion(), test_allocation_policy_api_exposes_active_policy_and_versions(), test_allocation_policy_api_exposes_latest_run_details(), test_allocation_policy_api_suggestions_are_scoped_and_manager_has_no_access(), test_allocation_policy_feedback_draft_endpoint_creates_learning_suggestion() (+2 more)

### Community 340 - "Community 340"
Cohesion: 0.29
Nodes (9): PostgreSQL regressions for allocation freshness and room-lock serialization.  Th, A competing committed booking between solve and apply must fail closed., Creation waits for allocation's room lock and then observes its booking., _run_allocation(), _seed_allocation_case(), test_postgres_acceptance_rejects_stale_policy_or_fx_configuration(), test_postgres_autoapply_rejects_room_taken_after_solver_snapshot(), test_postgres_autoapply_serializes_with_concurrent_reservation_creation() (+1 more)

### Community 341 - "Community 341"
Cohesion: 0.24
Nodes (4): _Client, _Response, test_provider_chat_uses_curated_hotel_context_and_controlled_message(), test_provider_receives_only_curated_hotel_analytics_payload()

### Community 342 - "Community 342"
Cohesion: 0.35
Nodes (7): FakeJwkClient, test_apple_token_rejects_invalid_signature(), test_apple_token_rejects_nonce_mismatch(), test_apple_token_rejects_wrong_issuer_audience_or_expiry(), test_valid_apple_token_is_verified(), _token(), _verify()

### Community 343 - "Community 343"
Cohesion: 0.38
Nodes (10): _create_payload(), _reservation(), _seed_guest_inventory(), _seed_hotel(), test_adding_restriction_marks_only_future_active_reservations_for_review(), test_receptionist_cannot_override_until_canonical_permission_is_granted(), test_reservation_create_revalidates_after_quote_and_requires_exact_authorized_override(), test_reservation_update_revalidates_and_legacy_tag_resolution_cannot_bypass() (+2 more)

### Community 344 - "Community 344"
Cohesion: 0.18
Nodes (3): The rate calendar's "Hoy" must follow the hotel's timezone, not the server's.  R, Run the process in UTC like Render does, so a regression back to     `date.today, utc_server_clock()

### Community 345 - "Community 345"
Cohesion: 0.40
Nodes (10): _approve(), _seed(), _shortage_case(), test_claim_or_replacement_remains_pending_until_physical_receipt(), test_excess_is_pending_identification_until_stock_acceptance_or_return(), test_excess_return_to_laundry_is_only_closed_after_handover(), test_missing_linen_resolution_outcomes_keep_custody_and_ledger_consistent(), test_retirement_is_audited_idempotent_and_only_from_hotel_location() (+2 more)

### Community 346 - "Community 346"
Cohesion: 0.31
Nodes (10): Same per-location bug as stock_service: an 'out' at location B must be     valid, Same per-location bug as stock_service: an 'out' at location B must be     valid, _seed_hotels(), test_linen_minimums_are_location_specific_and_allow_zero(), test_linen_opening_count_batch_is_atomic_and_only_applies_before_location_history(), test_linen_outbound_movement_is_checked_against_its_own_location_not_hotel_wide_total(), test_linen_summary_marks_zero_balance_as_having_history(), test_linen_summary_returns_every_active_item_balance_in_one_call_hotel_scoped() (+2 more)

### Community 347 - "Community 347"
Cohesion: 0.31
Nodes (9): _complete_onboarding_setup(), API coverage for the expanded onboarding wizard., _register_owner(), test_complete_nine_step_flow_works(), test_each_step_persists(), test_idempotent_step_updates_do_not_duplicate_records(), test_invalid_data_blocks_advancement(), test_new_hotel_starts_with_cash_only() (+1 more)

### Community 348 - "Community 348"
Cohesion: 0.25
Nodes (4): _create_task_context(), MemoryObjectStorage, test_task_photo_is_private_tenant_scoped_and_integrity_checked(), test_task_photo_timestamp_uses_local_business_date()

### Community 349 - "Community 349"
Cohesion: 0.24
Nodes (9): _booking_cancel_payload(), PostgreSQL regression for OTA cancellation racing with check-in., A modification waits for an extension's reservation lock before room selection., A stale cross-tenant mapping cannot make cancellation mutate another hotel's sta, Cancellation waits for check-in's reservation lock, then requires review., test_ota_cancellation_does_not_follow_cross_hotel_reservation_mapping(), test_ota_cancellation_waits_for_checkin_and_uses_committed_status(), test_ota_modification_locks_reservation_before_room_after_extension() (+1 more)

### Community 350 - "Community 350"
Cohesion: 0.53
Nodes (10): _create_minimal_schema(), _load_migration(), _manual_reference_index_sql(), SQLite regression coverage for the reversible payment-correction migration., _run(), test_payment_correction_downgrade_preserves_schema_when_cancelled_duplicates_exist(), test_payment_correction_migration_refuses_to_drop_existing_audit_history(), test_payment_correction_migration_round_trips_when_history_is_empty() (+2 more)

### Community 351 - "Community 351"
Cohesion: 0.22
Nodes (4): authed_client(), client_with_db(), get_auth_context_target(), get_db_override_target()

### Community 352 - "Community 352"
Cohesion: 0.36
Nodes (10): _completed_transaction(), _create_sample_reservation(), test_date_change_with_payments_requires_manager_and_preserves_history(), test_date_change_without_payments_cancels_and_recreates(), test_extension_rejects_checkout_not_after_current_checkout_in_spanish(), test_extension_rejects_refund_as_immediate_payment_without_mutating_reservation(), test_extension_requires_payment_or_link_action(), test_no_show_can_be_marked_without_auto_charge() (+2 more)

### Community 353 - "Community 353"
Cohesion: 0.18
Nodes (4): Tests for reservation creation logic., Tests for reservation creation logic., Tests for reservation creation logic., TestReservationCreation

### Community 354 - "Community 354"
Cohesion: 0.18
Nodes (6): Should fail for non-existent guest., Tests for reservation state machine transitions., Tests for reservation state machine transitions., Tests for reservation state machine transitions., Tests for reservation state machine transitions., TestStateTransitions

### Community 355 - "Community 355"
Cohesion: 0.29
Nodes (6): _context(), _hotel_today(), Regression tests for tenant-scoped, per-role reservation visibility., _reserve(), test_in_house_guest_remains_visible_when_check_in_predates_window(), test_visibility_window_filters_far_future_and_null_is_unlimited()

### Community 356 - "Community 356"
Cohesion: 0.31
Nodes (10): _assert_manual_reference_keys_unique(), downgrade(), _install_tenant_rls(), _manual_reference_index_exists(), Add auditable, idempotent payment corrections.  Revision ID: 20261024_atomic_pay, Fail before DDL if existing rows cannot satisfy the target unique index., Keep correction history isolated even for direct SQL access., _remove_tenant_rls() (+2 more)

### Community 357 - "Community 357"
Cohesion: 0.49
Nodes (9): changed_paths(), git(), is_release_relevant_path(), main(), Fail closed: only the three generated evidence files are non-runtime.      A rel, ReleaseEvidenceError, resolve_commit(), select_summary() (+1 more)

### Community 358 - "Community 358"
Cohesion: 0.38
Nodes (9): _enum_value(), _event_to_read(), _group_to_read(), list_movement_groups(), MovementEventRead, MovementGroupRead, _not_found_or_bad_request(), read_movement_group() (+1 more)

### Community 359 - "Community 359"
Cohesion: 0.33
Nodes (10): approve_temporary_action_grant(), create_temporary_action_grant(), deny_temporary_action_grant(), _raise_temporary_grant_http_error(), Ask for one exceptional permission without changing the requester's role., read_active_temporary_action_grants(), read_pending_temporary_action_grants(), revoke_temporary_action_grant() (+2 more)

### Community 360 - "Community 360"
Cohesion: 0.36
Nodes (9): _attach_actor_names(), audit_timeline(), _build_audit_timeline_csv(), _current_user(), export_audit_timeline(), recent_security_events(), _safe_resource_id(), security_overview() (+1 more)

### Community 361 - "Community 361"
Cohesion: 0.31
Nodes (10): _assert_assignable_role(), _assert_manageable_membership(), _assert_manageable_role(), invite_user(), list_users(), _membership_user_info(), resend_invitation(), revoke_user() (+2 more)

### Community 362 - "Community 362"
Cohesion: 0.20
Nodes (9): StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, StaticFiles that returns 404 on invalid filenames (e.g., containing wildcards on, SafeStaticFiles (+1 more)

### Community 363 - "Community 363"
Cohesion: 0.20
Nodes (8): BookingRead, ReservationRead, BookingCancellationResponse, CancellationReviewDecisionRequest, CancellationReviewRead, CancellationReviewResolutionResponse, Transport contracts for manual reservation cancellation review., ReservationCancellationResponse

### Community 364 - "Community 364"
Cohesion: 0.31
Nodes (9): _cassandra_probe(), _close_clients(), _enable(), Live smoke tests for the optional Mongo, Neo4j, and Cassandra projections.  Each, Avoid reusing a client created by another test or stale .env flags., reset_projection_clients(), test_cassandra_bootstraps_missing_keyspace_and_lands_room_event(), test_mongo_audit_projection_lands_document() (+1 more)

### Community 365 - "Community 365"
Cohesion: 0.20
Nodes (5): Request and read contracts for one group collection with child allocations., ReservationGroupPaymentAllocationRead, ReservationGroupPaymentAllocationRequest, ReservationGroupPaymentCreate, ReservationGroupPaymentRead

### Community 366 - "Community 366"
Cohesion: 0.20
Nodes (10): consume_invitation(), find_by_token(), hash_invitation_token(), is_expired(), issue_invitation(), Atomically transition a pending invitation to accepted exactly once., Return a naive UTC timestamp, matching the current SQLAlchemy models., Hash a high-entropy bearer token before it is persisted. (+2 more)

### Community 367 - "Community 367"
Cohesion: 0.29
Nodes (9): ensure_active_owner(), _lock_active_owner_memberships(), Atomic invariants and lifecycle operations for hotel memberships., Lock the current owner set for the duration of the caller's transaction., Require at least one active owner while holding the owner-row lock., Validate a role/status mutation before changing the membership row.      The own, Transfer the single billing/property owner inside one transaction., transfer_primary_owner() (+1 more)

### Community 368 - "Community 368"
Cohesion: 0.24
Nodes (3): BodyLimitMiddleware, Tope global de tamaño de cuerpo como middleware ASGI puro (hallazgo N13 del info, _TooLarge

### Community 369 - "Community 369"
Cohesion: 0.20
Nodes (10): build_beat_schedule(), Return no scheduled provider/network work for a closed sandbox.      `notificati, Return a Redis endpoint identity without exposing URL credentials., Return a Redis endpoint identity without exposing URL credentials., Allow only internal outbox recovery in a closed sandbox with Redis wired.      T, Allow only internal outbox recovery in a closed sandbox with Redis wired.      T, Return provider work or only safe internal replay for a closed sandbox.      `no, Return provider work or only safe internal replay for a closed sandbox.      `no (+2 more)

### Community 370 - "Community 370"
Cohesion: 0.31
Nodes (9): _empty_totals(), _positive_count(), _process_pending_revocations(), Durable, tenant-scoped recovery for canceled Mercado Pago checkout links., Drain a small, fair batch after the SQL-only scheduled hotel jobs., Rotate two positions every five-minute slot for predictable fairness., Enumerate every hotel regardless of subscription, rotating visits by cycle., _rotated_hotel_ids() (+1 more)

### Community 371 - "Community 371"
Cohesion: 0.20
Nodes (10): _ensure_explicit_zero_tax_policy(), hotel_config(), Create sample room categories for hotel 1., Minimal categories for a second hotel to verify isolation., Create sample room categories for hotel 1., Minimal categories for a second hotel to verify isolation., Create default hotel configuration., Create default hotel configuration. (+2 more)

### Community 373 - "Community 373"
Cohesion: 0.38
Nodes (9): _evaluate(), test_cancellation_after_cutoff_requires_approval_for_saved_percentage(), test_cancellation_inside_saved_free_window_has_no_penalty(), test_cutoff_subtracts_elapsed_hours_across_daylight_saving_transition(), test_fixed_penalty_uses_saved_currency(), test_invalid_policy_values_fail_closed_to_manager_review(), test_missing_checkin_time_requires_hotel_configuration(), test_missing_snapshot_requires_manager_review_without_using_current_policy() (+1 more)

### Community 374 - "Community 374"
Cohesion: 0.20
Nodes (9): PostgreSQL regressions for the check-in room row lock and ORM identity map., A moved reservation is refreshed before check-in; a busy room returns a conflict, Checkout uses PostgreSQL NOWAIT while holding the reservation lock., A stale eagerly loaded Room must not pass check-in after another commit., Deferred billing permits checkout without turning the balance into a payment., test_checkin_refreshes_concurrent_room_move_and_fails_fast_on_room_lock(), test_checkin_room_lock_refreshes_room_loaded_before_competing_status_change(), test_checkout_allows_deferred_company_balance_without_financial_mutation_postgres() (+1 more)

### Community 375 - "Community 375"
Cohesion: 0.42
Nodes (9): _legacy_deferred_reservation(), _payment(), test_deferred_company_analytics_keeps_occupied_night_without_lodging_revenue(), test_deferred_company_reports_hide_base_money_but_keep_occupancy_and_extra_payment(), test_deferred_reservation_financial_summary_exposes_only_selected_night_extra(), test_deferred_reservation_group_masks_legacy_group_total(), test_deferred_reservation_read_and_list_mask_legacy_lodging_money(), test_paid_total_adjustment_cannot_restore_a_deferred_lodging_amount() (+1 more)

### Community 376 - "Community 376"
Cohesion: 0.31
Nodes (7): _login(), Public pricing is owner-editable from the master-admin console.  Reuses the mast, test_a_plan_dropped_from_the_payload_disappears(), test_negative_price_is_rejected(), test_owner_can_read_captured_leads(), test_owner_sets_a_price_and_the_public_endpoint_serves_it(), test_saving_pricing_writes_an_audit_event()

### Community 377 - "Community 377"
Cohesion: 0.20
Nodes (9): Regression coverage for portable Graphify artifact normalization., A second normalizer run must leave already-portable artifacts unchanged., Embedded worktree paths must become repository-relative instructions., A generated-instruction symlink must not allow writes outside the repository., A symlinked instruction directory must not allow external files to be rewritten., test_does_not_follow_instruction_directory_symlink_outside_generated_directory(), test_does_not_follow_instruction_symlink_outside_generated_directory(), test_is_idempotent_after_generated_paths_are_normalized() (+1 more)

### Community 378 - "Community 378"
Cohesion: 0.29
Nodes (5): FakeConnection, FakeEngine, test_repair_adds_missing_cash_handoff_schema_objects(), test_repair_refuses_non_postgres_targets(), test_schema_report_lists_only_missing_model_tables()

### Community 379 - "Community 379"
Cohesion: 0.38
Nodes (9): _reservation(), test_confirmation_is_accepted_and_second_click_is_deduplicated(), test_invalid_recipient_is_rejected_before_provider(), test_local_example_test_address_is_accepted_but_never_forwarded(), test_production_rejects_example_test_recipient(), test_provider_failure_is_visible_and_explicit_resend_creates_attempt(), test_synthetic_email_does_not_expand_reservation_tenant_scope(), test_test_mode_never_sends_example_test_even_if_provider_flags_are_enabled() (+1 more)

### Community 380 - "Community 380"
Cohesion: 0.64
Nodes (9): _build_client(), _cleanup_client(), _override_auth(), _seed_operational_state(), test_pending_actions_endpoint_is_hotel_scoped(), test_pending_actions_endpoint_surfaces_payment_errors_as_http_500(), test_reservation_operations_resolution_endpoints_close_followups(), test_reservation_operations_summary_endpoint_exposes_pending_operational_actions() (+1 more)

### Community 381 - "Community 381"
Cohesion: 0.60
Nodes (9): _client_with_db(), _override_auth(), _seed_group(), test_company_group_revert_denies_reception_even_with_individual_company_manage_override(), test_explicit_receptionist_grant_can_revert_group(), test_housekeeping_cannot_read_or_revert_room_movement_group(), test_receptionist_can_read_but_cannot_revert_room_movement_group(), test_revert_movement_group_marks_reservations_protected() (+1 more)

### Community 382 - "Community 382"
Cohesion: 0.22
Nodes (4): _make_period(), PricePeriod is NOT used for dates outside its range., Tier-2: active PricePeriod used when no DailyRate exists., TestResolveRateCalendar

### Community 383 - "Community 383"
Cohesion: 0.51
Nodes (9): _ensure_hotel(), _reservation(), _surcharge(), test_fixed_surcharge_applies_to_transaction_gross_and_fee(), test_inactive_surcharge_is_noop(), test_payment_link_requested_amount_includes_surcharge(), test_payment_link_webhook_base_amount_can_be_recovered_from_final_amount(), test_percentage_surcharge_applies_to_transaction_gross_and_fee() (+1 more)

### Community 384 - "Community 384"
Cohesion: 0.38
Nodes (8): _hotel_id(), _race_two_sessions(), Two-session idempotency regressions for inbound payment and OTA webhooks.  These, Hold the first real PostgreSQL lock until the second session is waiting., _seed_payment_target(), test_distinct_payment_events_share_one_payment_and_transaction_under_postgres_lock(), test_same_ota_reservation_is_materialized_once_under_two_postgres_sessions(), test_same_payment_webhook_is_idempotent_under_two_postgres_sessions()

### Community 385 - "Community 385"
Cohesion: 0.53
Nodes (8): _headers(), _issue_key(), _seed_hotel(), test_whatsapp_availability_uses_api_key_hotel_scope(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_cross_hotel_isolation_for_create_and_payment_link(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), _whatsapp_quote()

### Community 386 - "Community 386"
Cohesion: 0.31
Nodes (9): _create_linen_tables(), downgrade(), _drop_kind_column(), _finalize_laundry_vendor_columns(), _migrate_linen_data(), _migrate_linen_data_back(), linen (ropa blanca) split into its own physical tables  Revision ID: 20260727_li, Reverse of _migrate_linen_data: every linen_items row moves back into     stock_ (+1 more)

### Community 387 - "Community 387"
Cohesion: 0.29
Nodes (9): downgrade(), _insert_default_rows(), _insert_permission_rows(), _install_rls(), Add guest room-rejection lifecycle and its resolution permission.  Revision ID:, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls() (+1 more)

### Community 388 - "Community 388"
Cohesion: 0.40
Nodes (9): _create_and_secure_retention_holds(), _cron_is_required(), downgrade(), _downgrade_sqlite(), _install_purge_function(), Honor auditable legal holds in public-form retention.  Revision ID: 20260926_leg, _reschedule_purge_job(), upgrade() (+1 more)

### Community 389 - "Community 389"
Cohesion: 0.42
Nodes (8): _load_manifest(), main(), ManifestContinuityError, _provider_subject(), Safe error that never prints provider values., Allow only a newer observation timestamp between provider snapshots., _timestamp(), verify_manifest_continuity()

### Community 390 - "Community 390"
Cohesion: 0.44
Nodes (8): _catalog(), initialize(), _json_bytes(), main(), OperationalQAError, _utc_now(), validate(), _write()

### Community 391 - "Community 391"
Cohesion: 0.22
Nodes (6): main(), ProviderClients, Small GET-only API client with bounded retries and redacted failures., ReadOnlyJsonApi, _required_env(), VerificationConfig

### Community 392 - "Community 392"
Cohesion: 0.22
Nodes (4): backendURL, ownerCredentials, receptionistCredentials, TestSession

### Community 393 - "Community 393"
Cohesion: 0.31
Nodes (6): jsonResponse(), permissionAdminReadStepUpRequired(), session, stepUpRequired(), tick(), waitFor()

### Community 394 - "Community 394"
Cohesion: 0.28
Nodes (8): RateLimitEvent, Persistent rate-limit events for security-sensitive endpoints., check_mfa_attempt(), mfa_attempt_key(), Use one OTP bucket and one reauthentication bucket per account.      Surface-spe, Record and commit one persistent account proof attempt before checking it., Clear the shared account bucket after that category of proof succeeds., reset_mfa_attempts()

### Community 395 - "Community 395"
Cohesion: 0.36
Nodes (8): issue_provider_evidence_token(), load_provider_evidence_private_key(), main(), Load the producer-only signer from PEM or base64 raw seed bytes., Create a provider-bound capability using the producer-only signer., _required(), _safe_output_path(), write_private_token()

### Community 396 - "Community 396"
Cohesion: 0.33
Nodes (8): CashHandoffSchemaRepairError, main(), missing_model_tables(), Repair known legacy PostgreSQL schema drift before starting the API.  The manage, Raised when the safe repair cannot run against the configured database., Apply the additive cash-handoff repair in one PostgreSQL transaction., Return model tables absent from a PostgreSQL database without changing it., repair_cash_handoff_schema()

### Community 397 - "Community 397"
Cohesion: 0.36
Nodes (8): _pending_proposal_query(), Run one SQL-backed pass, retrying only transient lock contention., Reoptimize once per hotel and coalesce concurrent same-process triggers.      Th, _request_allocation_proposal(), request_reservation_created_allocation(), reservation_overlaps_allocation_horizon(), _run_reoptimization_once(), trigger_reoptimization_bg()

### Community 398 - "Community 398"
Cohesion: 0.47
Nodes (8): build_company_terms_snapshot(), company_terms_from_profile(), _decimal_text(), effective_company_terms(), get_company_terms_review_state(), _parse_pricing_snapshot(), _reservation_economics(), terms_fingerprint()

### Community 399 - "Community 399"
Cohesion: 0.31
Nodes (3): GemmaServiceError, Raised when a Gemma request cannot be completed safely., Raised when a Gemma request cannot be completed safely.

### Community 400 - "Community 400"
Cohesion: 0.33
Nodes (8): _amount(), generate_payment_receipt_pdf(), _local_created_at(), _pdf_text(), _rate(), Generate a downloadable PDF from the persisted payment receipt snapshot., Keep core-font text safe while retaining Spanish Latin-1 characters., Render one page from ``get_payment_receipt_data`` output.      The function acce

### Community 401 - "Community 401"
Cohesion: 0.50
Nodes (8): _aggregate_inventory_rules(), _build_direct_prices(), _build_missing_channel(), _build_ota_prices(), _default_restrictions(), get_daily_calendar(), _select_ota_price_rule(), _select_rate_plan_price()

### Community 402 - "Community 402"
Cohesion: 0.22
Nodes (9): push_availability_update(), _push_to_booking(), _push_to_expedia(), Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Booking.com OC API.          In production, this wou, Send availability update to Expedia EQC API.          In production, this would, Send availability update to Expedia EQC API.          In production, this would, Push availability updates to all enabled OTAs for a given category and date rang (+1 more)

### Community 403 - "Community 403"
Cohesion: 0.47
Nodes (8): _context(), _response(), test_booking_adapter_acknowledges_queue_and_keeps_v1_outbound_limits_explicit(), test_booking_adapter_does_not_treat_failed_pull_as_empty_queue(), test_booking_adapter_normalizes_xml_reservations_and_deduplicates(), test_booking_adapter_posts_documented_availability_and_keeps_token_out_of_evidence(), test_booking_adapter_requires_token_and_property_before_transport(), test_booking_adapter_surfaces_retryable_provider_outage()

### Community 404 - "Community 404"
Cohesion: 0.64
Nodes (8): _client_with_db(), _override_auth(), _seed_reservation(), test_company_document_cannot_be_attached_to_unlinked_reservation(), test_company_documents_api_cross_hotel_isolation(), test_company_documents_api_crud_and_status_flow(), test_receptionist_cannot_manage_company_by_default(), test_uploaded_company_voucher_is_private_signature_aware_and_tenant_scoped()

### Community 405 - "Community 405"
Cohesion: 0.39
Nodes (8): Reservation-level review for changes to mutable company configuration., _seed_company_reservation(), test_company_terms_change_is_reviewed_without_silently_rewriting_booking(), test_company_terms_review_does_not_disclose_reservation_across_hotels(), test_company_terms_review_rejects_closed_reservations_without_mutation(), test_legacy_reservation_without_snapshot_cannot_claim_to_keep_unknown_terms(), test_manager_accepts_current_terms_without_repricing_and_retry_is_idempotent(), test_stale_company_config_requires_manager_to_reload_before_deciding()

### Community 406 - "Community 406"
Cohesion: 0.44
Nodes (8): _create_remitos(), _load_migration(), test_day2_downgrade_refuses_to_discard_persisted_operational_data(), test_migration_refuses_tab_or_newline_duplicates_before_unique_constraint(), test_migration_refuses_uniqueness_until_remito_duplicates_are_resolved(), test_remito_preflight_blocks_single_legacy_value_with_outer_whitespace(), test_remito_preflight_is_empty_when_no_duplicate_exists(), test_remito_preflight_reports_ids_and_trimmed_duplicates()

### Community 407 - "Community 407"
Cohesion: 0.39
Nodes (8): client_with_db(), create_hotel_with_membership(), get_db_override_target(), test_reservations_list_isolated_by_hotel(), test_reset_endpoint_allows_testing_env(), test_room_cap_enforced(), test_rooms_list_isolated_by_hotel(), test_staff_cap_enforced_for_pending_invites_and_scoped_by_hotel()

### Community 408 - "Community 408"
Cohesion: 0.50
Nodes (8): _auth(), _client(), API-level coverage: inbox scoping, push subscription CRUD, preference CRUD, and, test_daily_report_schedule_is_owner_co_owner_only(), test_inbox_is_tenant_and_recipient_scoped(), test_mark_read_is_scoped_to_recipient(), test_preferences_crud(), test_push_subscription_register_and_unregister()

### Community 409 - "Community 409"
Cohesion: 0.50
Nodes (8): _outbox_event_types(), _owner(), Integration coverage: the real domain-event call sites (reservation lifecycle, c, test_checkin_checkout_enqueue_notifications(), test_guest_restriction_lifecycle_enqueues_notifications(), test_low_stock_movement_enqueues_notification(), test_no_show_enqueues_notification(), test_reservation_lifecycle_enqueues_notifications()

### Community 410 - "Community 410"
Cohesion: 0.22
Nodes (9): A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered, A payment state change is a money-moving event and must record WHO     triggered (+1 more)

### Community 411 - "Community 411"
Cohesion: 0.22
Nodes (8): A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl, A gateway webhook has no human actor -- it must stay None, never         silentl

### Community 412 - "Community 412"
Cohesion: 0.36
Nodes (6): _add_event(), test_missing_or_zero_cursor_requires_full_refetch(), test_recovery_collapses_published_and_pending_domains_without_payload(), test_recovery_is_tenant_scoped(), test_recovery_marks_limit_overflow_for_full_refetch(), test_stale_cursor_requires_full_refetch()

### Community 413 - "Community 413"
Cohesion: 0.25
Nodes (2): FakeRedis, test_availability_key_shape_and_serialization()

### Community 414 - "Community 414"
Cohesion: 0.22
Nodes (8): A legacy per-hotel setting cannot bypass the full-payment rule., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in., Cannot checkout a FULLY_PAID reservation that was never checked in.

### Community 415 - "Community 415"
Cohesion: 0.22
Nodes (8): Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, The default full-payment policy blocks check-in without payment., Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se, Calling perform_checkout twice on the same reservation raises CheckInError on se

### Community 416 - "Community 416"
Cohesion: 0.22
Nodes (5): Two DailyRates for the same hotel+category+date raise IntegrityError., Same date but different categories should NOT conflict., Same category code but different hotels: no constraint violation., DailyRate stores and retrieves price as float without data loss., TestDailyRateModelConstraints

### Community 417 - "Community 417"
Cohesion: 0.22
Nodes (7): When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., When hotel accepts overbooking, caller creates reservation with is_wait_listed=T, When allow_overbooking=True the caller sets is_wait_listed=True and room_id=None, HotelConfiguration.allow_overbooking field must exist and be togglable., TestWaitlistCreation

### Community 418 - "Community 418"
Cohesion: 0.31
Nodes (8): _is_example_test_address(), is_local_synthetic_reservation_email(), local_synthetic_email_addresses_enabled(), normalize_reservation_email(), Validation helpers for reservation communication email addresses., Allow reserved synthetic addresses only in isolated local/test modes., Validate and normalize an email, narrowly allowing local ``example.test``., Return whether a validated recipient belongs to the local reserved domain.

### Community 419 - "Community 419"
Cohesion: 0.42
Nodes (8): _columns(), _create_index_if_missing(), downgrade(), _drop_index_if_present(), _indexes(), Operational audit fields, daily cash indexes, and audit read permission., _seed_audit_permission(), upgrade()

### Community 420 - "Community 420"
Cohesion: 0.50
Nodes (8): _backfill_external_ota_credits(), downgrade(), _has_columns(), Backfill legacy OTA credits and operational role defaults.  This data migration, _set_global_role_defaults(), _set_housekeeping_whatsapp_defaults(), _set_manager_operational_defaults(), upgrade()

### Community 421 - "Community 421"
Cohesion: 0.33
Nodes (8): _assert_no_duplicate_remitos(), downgrade(), _guard_day2_downgrade_data(), _install_rls(), Day 2 feedback: cash expenses, group collections, rate drafts, fiscal profile, a, Refuse rollback when it would discard operational data or session state., _remove_rls(), upgrade()

### Community 422 - "Community 422"
Cohesion: 0.50
Nodes (7): _claude(), _codex(), _expected(), _instructions(), main(), _roles(), _toml_string()

### Community 423 - "Community 423"
Cohesion: 0.25
Nodes (5): AppleAuthorization, AppleSignInResult, CLIENT_ID, REDIRECT_URI, Window

### Community 424 - "Community 424"
Cohesion: 0.25
Nodes (7): Activity, DashboardStats, mockActivities, mockReservations, mockRooms, Reservation, Room

### Community 425 - "Community 425"
Cohesion: 0.29
Nodes (5): flattenKeys(), frontendRoot, loadKeys(), pluralSuffixes, sourceRoot

### Community 426 - "Community 426"
Cohesion: 0.36
Nodes (6): MARKETING_ROUTES, marketingHtmlPlugin(), renderRouteHtml(), replaceTag(), indexHtml, vercel

### Community 427 - "Community 427"
Cohesion: 0.50
Nodes (7): evaluate_hotel_write_access(), get_policy_payload(), _parse_hotel_ids(), _parse_user_ids(), _policy_table(), update_policy(), _utcnow()

### Community 428 - "Community 428"
Cohesion: 0.25
Nodes (4): bubbleStyles, modeLabel, runtimeLabel, suggestedPrompts

### Community 429 - "Community 429"
Cohesion: 0.25
Nodes (3): measured(), Mide, sobre PostgreSQL real, el costo de cuatro rutas calientes que la lectura c, Ejecuta ``fn`` ``repeat`` veces en una sesión nueva y devuelve sentencias/commit

### Community 430 - "Community 430"
Cohesion: 0.39
Nodes (7): _currency(), _decimal_amount(), evaluate_cancellation_policy(), _parse_hotel_time(), Pure cancellation-policy evaluation from the immutable booking snapshot., Calculate a proposed cancellation penalty without applying it.      Missing hist, _review()

### Community 431 - "Community 431"
Cohesion: 0.25
Nodes (8): Prefix formula-like text so spreadsheet software treats it as text., Prefix formula-like text so spreadsheet software treats it as text., Apply formula protection consistently to every text cell in a CSV row., Apply formula protection consistently to every text cell in a CSV row., Apply formula protection consistently to every text cell in a CSV row., Prefix formula-like text so spreadsheet software treats it as text., spreadsheet_safe_row(), spreadsheet_safe_value()

### Community 432 - "Community 432"
Cohesion: 0.46
Nodes (6): _aggregate_rows(), build_financial_report(), _hotel_bounds(), _local_day(), _money(), _validate_report_window()

### Community 433 - "Community 433"
Cohesion: 0.25
Nodes (7): Notify an existing staff member after their role change is committed., Send a best-effort staff access notice without logging provider data., Notify an invitee after the hotel membership and invitation are committed., send_staff_invitation_email(), _send_staff_notice(), send_staff_role_changed_email(), send_staff_welcome_email()

### Community 434 - "Community 434"
Cohesion: 0.25
Nodes (8): get_timezone_catalog(), is_valid_timezone(), Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return a stable, sorted catalog of supported IANA timezone names.      The set i, Return True when the timezone exists in the supported catalog., Return True when the timezone exists in the supported catalog., Return True when the timezone exists in the supported catalog.

### Community 435 - "Community 435"
Cohesion: 0.57
Nodes (7): _guest(), _hotel(), test_audit_failure_does_not_raise_from_decorated_function(), test_audit_log_has_correct_action_enum_value(), test_audit_log_uses_correct_hotel_id_isolation(), test_modifying_guest_creates_audit_log_with_before_after(), _user()

### Community 436 - "Community 436"
Cohesion: 0.32
Nodes (3): FakeInspector, _load_migration(), test_repair_migration_adds_missing_successor_column_and_constraints()

### Community 437 - "Community 437"
Cohesion: 0.50
Nodes (7): _company(), test_company_base_price_applies_as_reservation_default_but_overridable(), test_company_document_signature_status_flow(), test_company_documents_are_hotel_scoped(), test_corporate_requirements_do_not_implicitly_lock_allocation(), test_corporate_reservation_is_allocation_locked(), _user()

### Community 438 - "Community 438"
Cohesion: 0.46
Nodes (6): SQLite upgrade coverage for company nightly rate cutover and rollback guard., _run_alembic(), _seed_legacy_company(), test_company_nightly_rate_cutover_backfill_roundtrip_is_current_date_only(), test_company_nightly_rate_downgrade_refuses_to_discard_charge_snapshots(), test_company_nightly_rate_downgrade_refuses_to_discard_user_history()

### Community 439 - "Community 439"
Cohesion: 0.43
Nodes (7): _load_data_migration(), _load_migration(), SQLite contract test for the new manual-payment/check-in-policy migration., A payment committed after candidate discovery must be in the backfill snapshot., test_migration_backfills_default_policy_and_is_idempotent(), test_migration_separates_legacy_ota_credit_and_requires_reconfirmation(), test_ota_backfill_locks_row_before_recomputing_completed_ledger()

### Community 440 - "Community 440"
Cohesion: 0.46
Nodes (5): _guest(), _hotel(), test_audit_projection_document_shape_from_decorator(), test_guest_update_writes_postgres_audit_and_mongo_off_does_not_raise(), _user()

### Community 441 - "Community 441"
Cohesion: 0.25
Nodes (4): _assign_hotel(), Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1)., Assign hotel scope to reservation (hotel_id column provided by A1).

### Community 442 - "Community 442"
Cohesion: 0.25
Nodes (6): Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., Multi-hotel safety: scope payments and methods by hotel_id., TestHotelIsolation

### Community 443 - "Community 443"
Cohesion: 0.25
Nodes (7): Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation., Cannot pay for a cancelled reservation.

### Community 444 - "Community 444"
Cohesion: 0.25
Nodes (7): Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method., Cannot use a disabled payment method.

### Community 445 - "Community 445"
Cohesion: 0.25
Nodes (7): Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials., Failed gateway payment should not update reservation financials.

### Community 446 - "Community 446"
Cohesion: 0.25
Nodes (7): A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t, A refund can never exceed what was actually collected in the ledger --         t

### Community 447 - "Community 447"
Cohesion: 0.25
Nodes (1): One operator-entered collection stays idempotent across grouped reservations.

### Community 448 - "Community 448"
Cohesion: 0.43
Nodes (7): v72 §16.2: reportable_origin derivation from channel_code + company_id + source., _res(), test_company_channel_is_empresa(), test_company_id_overrides_channel(), test_origin_from_channel(), test_ota_source_fallback_when_channel_generic(), test_unknown_channel_defaults_to_manual_reception()

### Community 449 - "Community 449"
Cohesion: 0.50
Nodes (6): _delete_audit(), _seed_category(), test_price_period_delete_soft_deletes_hides_and_audits(), test_reservation_delete_soft_deletes_hides_and_audits(), test_room_delete_lists_only_active_blocking_reservations_and_allows_delete_after_move(), test_room_delete_soft_deletes_hides_and_audits()

### Community 450 - "Community 450"
Cohesion: 0.25
Nodes (3): C1: after_begin listener reapplies transaction-scoped RLS tenant context.  ``set, Most sessions never call set_tenant_*; the listener must not touch them., test_sqlite_commit_with_no_tenant_context_is_a_clean_noop()

### Community 451 - "Community 451"
Cohesion: 0.25
Nodes (7): Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False)., Guest who has NOT accepted terms is blocked (terms_accepted=False).

### Community 452 - "Community 452"
Cohesion: 0.25
Nodes (7): When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error., When require_document_for_checkin=False, missing document is not an error.

### Community 453 - "Community 453"
Cohesion: 0.25
Nodes (7): When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error., When require_terms_acceptance=False, missing terms is not an error.

### Community 454 - "Community 454"
Cohesion: 0.25
Nodes (4): V72 §13 — Daily Rate Management tests.  Tests cover:   - get_price_for_date: Dai, Applying a second period to overlapping dates updates those dates., No duplicate rows after two overlapping period applies (upsert semantics)., TestPricePeriodOverlap

### Community 455 - "Community 455"
Cohesion: 0.25
Nodes (5): When allow_overbooking is False, creating a reservation with no available rooms, Fill the only Standard room then try to auto-assign — service should raise., Explicitly requesting an already-occupied room raises ReservationError., Six physical Twin rooms hold six overlapping stays; the seventh is         rejec, TestOverbookingBlocked

### Community 456 - "Community 456"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 457 - "Community 457"
Cohesion: 0.46
Nodes (7): downgrade(), _existing_enum_labels(), Align allocation enum storage with the model values.  The original allocation mi, _rename_postgres_enum_values(), _repair_sqlite(), _sqlite_rebuild_constraints(), upgrade()

### Community 458 - "Community 458"
Cohesion: 0.36
Nodes (6): _add_constraint_if_missing(), _has_fk(), _has_unique(), Repair cash handoff columns that were absent from an already-stamped schema.  So, Run a constraint-adding ALTER TABLE, tolerating it already existing.      The in, upgrade()

### Community 459 - "Community 459"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add notification backend: notifications, push_subscriptions, notification_prefer, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before dropping its table., _remove_rls(), upgrade()

### Community 460 - "Community 460"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add promotions table (versioned, typed conditions) and migrate payment_surcharge, Install the PostgreSQL tenant policy for promotions; no-op elsewhere., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 461 - "Community 461"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), Add missing tenant RLS policies to existing hotel-scoped tables.  Revision ID: 2, Install the PostgreSQL tenant policy; no-op on other dialects., Remove the PostgreSQL tenant policy before restoring the prior state., _remove_rls(), upgrade()

### Community 462 - "Community 462"
Cohesion: 0.36
Nodes (7): _assert_downgrade_lossless(), downgrade(), _install_rls(), Add tenant-scoped custom hotel roles and custom visibility-window codes., Refuse rollback while custom role state cannot be represented by built-ins., _remove_rls(), upgrade()

### Community 463 - "Community 463"
Cohesion: 0.32
Nodes (7): downgrade(), _install_rls(), add role visibility windows  Revision ID: 3bc5882f756d Revises: 20260828_permiss, Install the PostgreSQL tenant policy; no-op on SQLite., Remove the PostgreSQL tenant policy before dropping the table., _remove_rls(), upgrade()

### Community 464 - "Community 464"
Cohesion: 0.46
Nodes (7): _alter_user_column(), downgrade(), Allow system actors in hotel audit events.  Revision ID: 70014cb60e2c Revises: 2, _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade(), _user_fk()

### Community 465 - "Community 465"
Cohesion: 0.46
Nodes (7): downgrade(), _hotel_fk(), Prevent hotel deletion from cascading into audit_logs.  Replaces the audit_logs., _replace_fk(), _replace_postgresql_fk(), _replace_sqlite_fk(), upgrade()

### Community 466 - "Community 466"
Cohesion: 0.39
Nodes (7): downgrade(), _ensure_subscription_composite_target(), _has_unique(), _install_rls(), add subscription adjustment ledger  Revision ID: e6aadf684343 Revises: 0f85dca5b, _remove_rls(), upgrade()

### Community 467 - "Community 467"
Cohesion: 0.29
Nodes (3): LoggingTelemetry, Minimal telemetry port; the application is provider-neutral by default., Telemetry

### Community 468 - "Community 468"
Cohesion: 0.29
Nodes (6): _InvitationAccessLogFilter, Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs., Keep invitation and OTA webhook capabilities out of access logs.

### Community 469 - "Community 469"
Cohesion: 0.29
Nodes (3): backendURL, receptionistCredentials, TestSession

### Community 470 - "Community 470"
Cohesion: 0.33
Nodes (3): JobDispatcher, _FakeDispatcher, test_dispatch_once_is_postgres_dedupe_contract()

### Community 471 - "Community 471"
Cohesion: 0.57
Nodes (6): command(), fenced(), frontend_routes(), heading(), main(), write()

### Community 472 - "Community 472"
Cohesion: 0.48
Nodes (6): main(), _peak_resident_bytes(), _percentile(), Measure allocation solver time and process memory on synthetic hotel data.  Run, _resident_bytes(), _scenario()

### Community 473 - "Community 473"
Cohesion: 0.52
Nodes (5): main(), RealtimeMetrics, _run(), run_load(), validate_target()

### Community 474 - "Community 474"
Cohesion: 0.33
Nodes (4): chat_completions(), ChatCompletionRequest, ChatMessage, _extract_latest_user_message()

### Community 475 - "Community 475"
Cohesion: 0.38
Nodes (6): list_missing_follow_ups(), Neutral operational follow-up for declared laundry remito shortages.  This servi, Return operational details only; deliberately omit all price fields., Return operational details only; deliberately omit all price fields., _serialize_follow_up(), update_missing_follow_up()

### Community 476 - "Community 476"
Cohesion: 0.48
Nodes (5): _register_owner(), test_initial_state_is_empty(), test_multihotel_isolation_owner_state(), test_onboarding_flow_complete(), test_permissions_headers_applied_to_config()

### Community 477 - "Community 477"
Cohesion: 0.48
Nodes (6): _create_receptionist_user(), _open_cash_session(), Front desk can read reservation finances and record payments., _receptionist_context(), test_financial_summary_requires_reservation_read_not_cash_operation(), test_receptionist_can_view_and_make_reservation_payments()

### Community 478 - "Community 478"
Cohesion: 0.48
Nodes (5): _seed_product_with_compatibilities(), test_build_slots_from_db_respects_policy_when_fallback_is_disabled(), test_build_slots_from_db_uses_sellable_product_compatibility_priorities(), test_run_persisted_allocation_respects_published_policy_that_disables_fallback(), test_run_persisted_allocation_uses_upgrade_compatibility_when_exact_inventory_is_unavailable()

### Community 479 - "Community 479"
Cohesion: 0.57
Nodes (6): _create_minimal_schema(), _load_migration(), SQLite regression coverage for auditable cash-movement voids., _run(), test_cash_movement_void_migration_refuses_to_drop_void_history(), test_cash_movement_void_migration_round_trips_without_history()

### Community 481 - "Community 481"
Cohesion: 0.33
Nodes (1): TestCheckIn

### Community 482 - "Community 482"
Cohesion: 0.29
Nodes (3): api_client(), API tests for /api/connections/{provider}/connect. Focus on JSON serialization o, Provide a TestClient wired to an in-memory database.

### Community 483 - "Community 483"
Cohesion: 0.33
Nodes (2): _context(), test_generic_room_status_patch_projects_event_and_reallocates()

### Community 485 - "Community 485"
Cohesion: 0.43
Nodes (5): _build_signature(), This bool-returning shim delegates to the SAME raising validator every     real, test_validate_mercadopago_webhook_signature_accepts_valid_manifest_signature(), test_validate_mercadopago_webhook_signature_rejects_expired_timestamp(), test_validate_mercadopago_webhook_signature_rejects_tampered_data_id()

### Community 486 - "Community 486"
Cohesion: 0.43
Nodes (4): _reservation(), test_payment_link_webhook_uses_the_saved_fixed_surcharge_quote(), test_quote_chooses_maximum_tender_without_exceeding_balance_and_returns_cash_suggestion(), test_signed_payment_quote_keeps_previewed_fx_and_surcharge_when_rate_changes()

### Community 487 - "Community 487"
Cohesion: 0.71
Nodes (6): _build_client(), _cleanup(), _override_auth(), test_promotion_crud_lifecycle_and_versioning(), test_promotions_are_tenant_isolated_across_hotels(), test_simulate_endpoint_returns_full_breakdown_without_persisting()

### Community 488 - "Community 488"
Cohesion: 0.48
Nodes (6): Tests for the reservation global search filter (B1 header search).  Search is a, _reservation(), test_search_does_not_leak_across_hotels(), test_search_matches_confirmation_code(), test_search_matches_guest_last_name_case_insensitive(), test_search_no_match_returns_empty()

### Community 490 - "Community 490"
Cohesion: 0.29
Nodes (3): Editing a room category into a duplicate code or name must answer 409.  `room_ca, Same failure mode one section below on the same settings page: renaming a     ro, test_duplicate_room_number_returns_409()

### Community 491 - "Community 491"
Cohesion: 0.43
Nodes (4): RecordingMailer, test_staff_notices_report_unavailable_or_failed_delivery_without_provider_details(), test_staff_role_notice_names_the_hotel_and_both_roles(), test_staff_welcome_notice_contains_access_details_without_capabilities()

### Community 492 - "Community 492"
Cohesion: 0.33
Nodes (2): _Session, test_subscription_session_closes_before_asgi_work()

### Community 493 - "Community 493"
Cohesion: 0.29
Nodes (4): PricePeriod can be created and queried., A 30-day period (Dec 1–30 inclusive) generates exactly 30 DailyRates., Creating an inactive PricePeriod does not create DailyRate rows         (rows on, TestPricePeriodModel

### Community 494 - "Community 494"
Cohesion: 0.48
Nodes (5): _seed_waitlist_base(), test_waitlist_cross_hotel_isolation(), test_waitlist_entry_has_no_room_and_cannot_request_payment_link(), test_waitlist_promotion_rejects_entry_changed_after_suggestion(), test_waitlist_suggestion_is_feasibility_only_and_does_not_promote()

### Community 495 - "Community 495"
Cohesion: 0.48
Nodes (5): _analytics_enum(), analytics r1 base schema  Revision ID: 20260424_analytics_r1_base Revises: 20260, _reservation_status_enum_new(), _reservation_status_enum_old(), upgrade()

### Community 496 - "Community 496"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align billing-adjustment enum storage with the runtime enum values.  The allocat, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 497 - "Community 497"
Cohesion: 0.52
Nodes (6): _constraint(), downgrade(), Align room-movement enum storage with the runtime enum values.  The original all, _rename_postgres_values(), _repair_sqlite(), upgrade()

### Community 498 - "Community 498"
Cohesion: 0.52
Nodes (6): _backfill_authoritative_values(), _columns(), _decode(), downgrade(), Make hotel configuration columns the authority and retire dead scaffolding.  Dea, upgrade()

### Community 499 - "Community 499"
Cohesion: 0.57
Nodes (6): downgrade(), _drop_index_if_present(), _ensure_index(), _index_map(), Add query-shape indexes and remove redundant model drift.  The ORM is the primar, upgrade()

### Community 500 - "Community 500"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add tenant-scoped operational tasks and shift handoffs  Revision ID: 20260910_op, _remove_rls(), upgrade()

### Community 501 - "Community 501"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), add auditable reservation guest email deliveries  Revision ID: 20260910_reservat, _remove_rls(), upgrade()

### Community 502 - "Community 502"
Cohesion: 0.43
Nodes (6): downgrade(), _enum(), _install_rls(), Add tenant-scoped WhatsApp CRM W0/W1 tables and RLS.  Revision ID: 20260911_what, _remove_rls(), upgrade()

### Community 503 - "Community 503"
Cohesion: 0.48
Nodes (6): downgrade(), _enum_labels(), _quote_identifier(), Normalize the remaining PostgreSQL enum labels used by OTA models.  Revision ID:, _rename_enum_labels(), upgrade()

### Community 504 - "Community 504"
Cohesion: 0.43
Nodes (5): _enable_tenant_rls(), _has_fk(), _has_unique(), Harden company nightly charge tenant keys and row level security., upgrade()

### Community 505 - "Community 505"
Cohesion: 0.43
Nodes (6): downgrade(), _install_tenant_rls(), Add tenant-scoped per-guest arrival records and hotel status policy.  Revision I, _remove_tenant_rls(), _status_check(), upgrade()

### Community 506 - "Community 506"
Cohesion: 0.43
Nodes (6): downgrade(), _event_id_type(), _install_rls(), Add durable ids, cursor and retry state to the realtime outbox.  The migration i, _remove_rls(), upgrade()

### Community 507 - "Community 507"
Cohesion: 0.80
Nodes (5): build_sql(), _literal(), load_env(), main(), SharedSandboxBootstrapError

### Community 508 - "Community 508"
Cohesion: 0.47
Nodes (5): graphify_command_error(), inline_list(), main(), Parse the simple unquoted frontmatter lists used by context packs., Reject context commands that the installed Graphify CLI cannot route.

### Community 509 - "Community 509"
Cohesion: 0.53
Nodes (5): _ensure_wide_version_table(), get_url(), Alembic creates alembic_version with version_num VARCHAR(32) by default.     Som, run_migrations_offline(), run_migrations_online()

### Community 510 - "Community 510"
Cohesion: 0.40
Nodes (3): credentials, parseMoney(), readStat()

### Community 511 - "Community 511"
Cohesion: 0.33
Nodes (5): LaundryRemito, LaundryRemitoLine, LaundryVendor, LaundryVendorPrice, Laundry vendor, pricing and remito (delivery note) models.  An outsourced laundr

### Community 512 - "Community 512"
Cohesion: 0.33
Nodes (4): advance_business_clock(), Business-date read and controlled one-day advancement for local simulation., Advance exactly one business day and append a real-time audit event.      SQLite, Advance exactly one business day and append a real-time audit event.      SQLite

### Community 513 - "Community 513"
Cohesion: 0.40
Nodes (6): _model_event_payload(), _model_hotel_id(), queue_model_changes(), Collect safe domain signals from ORM writes before a transaction ends., Collect safe domain signals from ORM writes before a transaction ends., _scalar_event_value()

### Community 514 - "Community 514"
Cohesion: 0.33
Nodes (6): _outbox_backoff_seconds(), publish_pending_domain_events(), Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th, Exponential backoff for outbox replay: base, 2x, 4x, ... per attempt., Drain durable outbox rows for one tenant onto Redis/Valkey.      Used both by th

### Community 515 - "Community 515"
Cohesion: 0.60
Nodes (5): build_controlled_proposal(), _dedupe_preserve_order(), _detect_channel(), GemmaProposalPreview, GemmaSuggestedAction

### Community 516 - "Community 516"
Cohesion: 0.60
Nodes (5): _enum_value(), project_company_link(), project_reservation_assignment(), project_room_movement(), _run_write()

### Community 517 - "Community 517"
Cohesion: 0.33
Nodes (6): hotel_local_date_bounds(), normalize_timezone(), Trim whitespace and validate the timezone name., Trim whitespace and validate the timezone name., Trim whitespace and validate the timezone name., Return a half-open UTC range for inclusive hotel-local dates.      Transaction t

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
Cohesion: 0.53
Nodes (5): _alembic(), _assert_migrated(), Data-contract regression for the payment-link execution-mode migration., _seed_legacy_links(), test_payment_link_migration_backfills_provider_history_and_reupgrades()

### Community 523 - "Community 523"
Cohesion: 0.60
Nodes (5): _f003_environment(), test_f003_seed_accepts_only_dedicated_local_fixture_target(), test_f003_seed_rejects_database_outside_its_dedicated_namespace(), test_f003_seed_rejects_sqlite_even_with_opt_in(), test_f003_seed_requires_explicit_opt_in()

### Community 524 - "Community 524"
Cohesion: 0.53
Nodes (5): _create_referenced_tables(), _load_migration(), SQLite migration coverage for the fixed housekeeping checklist schema., _run(), test_housekeeping_checklist_migration_creates_constrained_tenant_tables_and_guards_downgrade()

### Community 525 - "Community 525"
Cohesion: 0.53
Nodes (5): _assert_backfill(), Data migration guard for separating housekeeping state from room status., _run_alembic(), test_housekeeping_board_permission_migration_seeds_only_intended_roles(), test_housekeeping_status_migration_backfills_and_reverses_cleanly()

### Community 526 - "Community 526"
Cohesion: 0.73
Nodes (5): _manual_payload(), _seed_hotel(), test_foreign_currency_ota_prepayment_is_reported_without_reducing_local_balance(), test_legacy_api_omission_defaults_external_payment_to_reservation_currency(), test_same_currency_ota_prepayment_keeps_existing_balance_credit_behavior()

### Community 527 - "Community 527"
Cohesion: 0.33
Nodes (4): Critical test: Simulates simultaneous booking from OTA and direct.     Verifies, Scenario: Only 1 room of category SUITE_P (room 406, 407, 408).         Book 2 o, Non-overlapping OTA booking should succeed even with 1 room., TestOTARaceCondition

### Community 528 - "Community 528"
Cohesion: 0.33
Nodes (6): ensure_category_pricing_table(), Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata)., Create CategoryPricing table for tests (not included in Base metadata).

### Community 529 - "Community 529"
Cohesion: 0.33
Nodes (5): Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING., Paying LESS than the deposit threshold should keep status as PENDING.

### Community 531 - "Community 531"
Cohesion: 0.60
Nodes (5): _job_block(), _load_workflow(), Contracts for opting provider-bound PR evidence checks in by label., test_provider_evidence_gates_are_opt_in_and_respond_to_label_changes(), test_regular_pr_backend_frontend_and_e2e_checks_remain_enabled()

### Community 532 - "Community 532"
Cohesion: 0.53
Nodes (5): Tests for operator-created reservation consumption charges., _reservation(), test_add_reservation_charge_updates_operational_financial_summary(), test_reservation_charge_rejects_other_hotel_and_checked_out_reservations(), test_reservation_charge_uses_reservation_currency_and_rejects_mismatch()

### Community 533 - "Community 533"
Cohesion: 0.53
Nodes (5): _group_payloads(), Atomic multi-room reservation grouping and aggregate balance contracts., test_create_four_room_company_group_and_aggregate_summary(), test_group_rejects_inconsistent_company_and_manual_totals(), test_group_rejects_room_count_outside_bounds()

### Community 534 - "Community 534"
Cohesion: 0.33
Nodes (5): Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in., Should fail when check-out is before check-in.

### Community 535 - "Community 535"
Cohesion: 0.33
Nodes (5): Cannot book the same room for overlapping dates., Cannot book the same room for overlapping dates., Cannot book the same room for overlapping dates., Should fail when room doesn't match the requested category., Cannot book the same room for overlapping dates.

### Community 536 - "Community 536"
Cohesion: 0.33
Nodes (4): Tests for confirmation code generation., Tests for confirmation code generation., Tests for confirmation code generation., TestConfirmationCode

### Community 537 - "Community 537"
Cohesion: 0.33
Nodes (6): _create_rooms_with_soft_deleted_tail(), Create the reported 42-room case, leaving three soft-deleted rows active., Create the reported 42-room case, leaving three soft-deleted rows active., Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, Removing 3 of 42 rooms leaves 39 usable rooms against the Pro cap of 40.      Th, test_soft_deleted_rooms_are_excluded_from_every_room_count_surface()

### Community 538 - "Community 538"
Cohesion: 0.33
Nodes (6): Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, Preview QA already requires a strong MASTER_ADMIN_PASSWORD/EMAIL, but     produc, test_validate_runtime_security_rejects_weak_master_admin_password_in_production()

### Community 539 - "Community 539"
Cohesion: 0.53
Nodes (4): test_env_file_requires_owner_only_permissions(), test_sql_creates_primary_switch_membership_and_isolated_owner(), test_sql_is_guarded_tagged_and_never_contains_plaintext_passwords(), _values()

### Community 540 - "Community 540"
Cohesion: 0.53
Nodes (5): _migrate(), Every foreign key in a migrated SQLite database needs a unique parent key.  SQLi, test_cash_close_reports_accepts_writes_with_foreign_keys_enforced(), test_every_foreign_key_in_a_migrated_sqlite_database_has_a_unique_parent_key(), _unique_column_sets()

### Community 541 - "Community 541"
Cohesion: 0.73
Nodes (5): _plan_values(), _run_alembic(), test_price_migration_downgrade_preserves_admin_edit_with_same_published_price(), test_price_migration_downgrade_restores_preexisting_currency_and_period(), test_publishes_approved_prices_without_overwriting_admin_values()

### Community 542 - "Community 542"
Cohesion: 0.33
Nodes (6): opened_cash_register(), Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja., Payment-gate scenarios start with an explicitly opened caja.

### Community 543 - "Community 543"
Cohesion: 0.40
Nodes (3): _pg_enum(), vouchers, refund_requests, and pending_operational_actions  Implements the three, upgrade()

### Community 544 - "Community 544"
Cohesion: 0.47
Nodes (5): _add_successor_reference(), downgrade(), _drop_successor_reference(), Add zero-balance cash rotation and custody handoffs., upgrade()

### Community 545 - "Community 545"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Harden core hotel-scoped relationships with tenant-leading keys.  The applicatio, upgrade()

### Community 546 - "Community 546"
Cohesion: 0.47
Nodes (4): _has_fk(), _has_unique(), Complete tenant-leading foreign keys outside the core booking domain.  The core, upgrade()

### Community 547 - "Community 547"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), seed section visibility permissions and their role defaults  Revision ID: 202608, upgrade()

### Community 548 - "Community 548"
Cohesion: 0.60
Nodes (5): downgrade(), _has_column(), _has_table(), Fold legacy category pricing into seasonal price periods., upgrade()

### Community 549 - "Community 549"
Cohesion: 0.60
Nodes (5): downgrade(), Align section defaults and remove the self-session catalog permission.  Revision, _restore_session_permission(), _set_role_default(), upgrade()

### Community 550 - "Community 550"
Cohesion: 0.47
Nodes (5): downgrade(), Tighten housekeeping's default access to occupancy planning.  Revision ID: 20260, Set one global default without creating duplicate rows on reruns., _set_role_default(), upgrade()

### Community 551 - "Community 551"
Cohesion: 0.47
Nodes (4): _insert_default_rows(), _insert_permission_rows(), Add nested authorization tiers for reservation room moves.  Revision ID: 2026083, upgrade()

### Community 552 - "Community 552"
Cohesion: 0.53
Nodes (5): downgrade(), _has_columns(), _indexes(), Add check-in policy, manual receipt references, and auditable refunds., upgrade()

### Community 553 - "Community 553"
Cohesion: 0.47
Nodes (5): downgrade(), _install_rls(), Add tenant-scoped groups for multi-room reservations., _remove_rls(), upgrade()

### Community 554 - "Community 554"
Cohesion: 0.47
Nodes (4): _existing_table_matches(), _install_tenant_rls(), Persist the local synthetic hotel business date.  Revision ID: 20261017_local_bu, upgrade()

### Community 555 - "Community 555"
Cohesion: 0.47
Nodes (4): _add_group_batch_columns_and_check(), _add_transaction_columns_and_check(), Persist cash received, change, and explicitly retained tip separately.  Revision, upgrade()

### Community 556 - "Community 556"
Cohesion: 0.47
Nodes (5): downgrade(), _install_tenant_rls(), Snapshot corporate terms per reservation and audit manager review.  Revision ID:, _remove_tenant_rls(), upgrade()

### Community 557 - "Community 557"
Cohesion: 0.47
Nodes (5): downgrade(), _install_tenant_rls(), Track laundry remito discrepancies and explicit linen retirements.  Revision ID:, _remove_tenant_rls(), upgrade()

### Community 558 - "Community 558"
Cohesion: 0.47
Nodes (5): downgrade(), _install_tenant_rls(), Add audited cancellation review queue and approval permission.  Revision ID: 202, _remove_tenant_rls(), upgrade()

### Community 559 - "Community 559"
Cohesion: 0.47
Nodes (5): downgrade(), _install_tenant_rls(), Persist general stock counts and require audited approval before adjustment.  Re, _remove_tenant_rls(), upgrade()

### Community 560 - "Community 560"
Cohesion: 0.40
Nodes (4): downgrade(), sync_model_drift_missing_columns  Revision ID: 3eaf48a79290 Revises: 20260419_on, Restore the legacy index even if a later downgrade already did so., _restore_reservations_hotel_index()

### Community 561 - "Community 561"
Cohesion: 0.47
Nodes (5): downgrade(), _install_rls(), linen location par levels  Revision ID: 41d66acfb13a Revises: 015f7e36b9cd Creat, _remove_rls(), upgrade()

### Community 562 - "Community 562"
Cohesion: 0.47
Nodes (4): ota allocation foundation  Revision ID: dee1bd0660f6 Revises: 20260408_payment_l, _seed_ota_providers(), upgrade(), _utcnow()

### Community 563 - "Community 563"
Cohesion: 0.60
Nodes (5): downgrade(), _policy_name(), _quoted_table(), master admin rls bypass  Adds a session-scoped bypass to the tenant-isolation RL, upgrade()

### Community 564 - "Community 564"
Cohesion: 0.80
Nodes (4): _archive_historical(), _build_cases(), main(), _write_json()

### Community 565 - "Community 565"
Cohesion: 0.40
Nodes (5): get_interface_language(), Expose only the selected UI language to authenticated hotel members., Expose only the selected UI language to authenticated hotel members., Expose only the selected UI language to authenticated hotel members., Expose only the selected UI language to authenticated hotel members.

### Community 566 - "Community 566"
Cohesion: 0.40
Nodes (3): Count response bytes after compression without buffering body content., Count response bytes after compression without buffering body content., ResponseBodySizeTelemetryMiddleware

### Community 567 - "Community 567"
Cohesion: 0.50
Nodes (3): localIsoDate(), openReservationForm(), receptionist

### Community 568 - "Community 568"
Cohesion: 0.40
Nodes (3): MasterBillingPolicy, MasterStripeSettings, MasterSystemEmailConnection

### Community 569 - "Community 569"
Cohesion: 0.40
Nodes (4): ConnectionCreate, ConnectionRead, Pydantic schemas for external provider connections. Ensures credentials/settings, Payload to establish/update a provider connection.

### Community 570 - "Community 570"
Cohesion: 0.40
Nodes (3): GuestRoomAvoidanceRead, GuestRoomAvoidanceResolveRequest, Pydantic schemas for a guest's room-rejection lifecycle.

### Community 571 - "Community 571"
Cohesion: 0.40
Nodes (1): HotelIdentityPayload

### Community 572 - "Community 572"
Cohesion: 0.40
Nodes (3): PaymentSurchargeQuoteRead, PaymentSurchargeQuoteRequest, Validated payment-surcharge quote contracts.

### Community 573 - "Community 573"
Cohesion: 0.60
Nodes (4): login(), Closed-loop load test: N virtual users, each loops over a request mix with think, run(), vu()

### Community 574 - "Community 574"
Cohesion: 0.50
Nodes (3): _prepare_environment(), Seed a demo hotel that looks like a real one, for marketing screenshots.  The E2, seed()

### Community 575 - "Community 575"
Cohesion: 0.60
Nodes (4): flush(), handle(), main(), pipe()

### Community 576 - "Community 576"
Cohesion: 0.40
Nodes (5): dolarapi_rates_enabled(), DolarApiRatesDisabled, Raised when public DolarAPI market-data reads are disabled., Allow only public DolarAPI quote reads, independently of integrations.      This, require_dolarapi_rates()

### Community 577 - "Community 577"
Cohesion: 0.40
Nodes (3): duplicate_laundry_remitos(), Read-only duplicate detection shared by migration and operator tooling., Return normalized duplicate remito groups, including every row id.      Service

### Community 578 - "Community 578"
Cohesion: 0.70
Nodes (4): _canonical_hash(), create_reservation_group_payment(), get_group_payment_batch(), _read_batch()

### Community 579 - "Community 579"
Cohesion: 0.60
Nodes (4): create_category(), create_room(), upsert_categories(), upsert_rooms()

### Community 580 - "Community 580"
Cohesion: 0.40
Nodes (3): find_user_by_email(), Exact, case-insensitive lookup helpers for user identity fields., Find an exact email match without treating SQL wildcard characters specially.

### Community 581 - "Community 581"
Cohesion: 0.70
Nodes (4): _claim_request(), _process_hotel_request(), process_recalculation_requests(), _session()

### Community 582 - "Community 582"
Cohesion: 0.50
Nodes (3): _override_auth(), GET /api/bookings/price-quote is the only endpoint of app/api/bookings.py that t, test_receptionist_can_get_price_quote()

### Community 583 - "Community 583"
Cohesion: 0.60
Nodes (4): Alembic round-trip for the additive local business-clock table., _run_alembic(), test_local_business_clock_migration_adds_and_drops_only_its_table(), test_local_business_clock_migration_adopts_existing_bootstrap_table()

### Community 584 - "Community 584"
Cohesion: 0.60
Nodes (4): _load_migration(), SQLite migration coverage for separate cash tender, change, and tip amounts., _run(), test_cash_tender_change_migration_preserves_legacy_rows_and_validates_pairs()

### Community 585 - "Community 585"
Cohesion: 0.70
Nodes (4): _client_with_db(), _override_auth(), _seed_blocked_reservation(), test_unauthorized_role_cannot_override()

### Community 586 - "Community 586"
Cohesion: 0.40
Nodes (1): TestGuestValidation

### Community 587 - "Community 587"
Cohesion: 0.60
Nodes (4): _assert_columns(), SQLite round-trip for company extension request fields., _run_alembic(), test_company_extension_request_migration_upgrade_downgrade_upgrade()

### Community 588 - "Community 588"
Cohesion: 0.60
Nodes (4): _load_migration(), SQLite migration coverage for configurable USD conversion sides., _side_columns(), test_fx_conversion_side_migration_backfills_defaults_and_round_trips_safely()

### Community 589 - "Community 589"
Cohesion: 0.60
Nodes (4): _alembic(), _load_migration(), test_guest_room_avoidance_migration_is_reversible_on_sqlite_and_seeds_defaults(), test_guest_room_avoidance_migration_owns_reversible_postgresql_rls()

### Community 590 - "Community 590"
Cohesion: 0.40
Nodes (3): PostgreSQL tenant and concurrent item completion regressions., Checkout, checklist creation, and room audit share the caller transaction., test_postgres_checkout_checklist_and_room_audit_roll_back_atomically()

### Community 591 - "Community 591"
Cohesion: 0.60
Nodes (4): _assert_schema(), SQLite migration round-trip for bounded manual reservation rates., _run_alembic(), test_manual_rate_policy_migration_upgrade_downgrade_upgrade()

### Community 592 - "Community 592"
Cohesion: 0.60
Nodes (4): _pending_push(), PostgreSQL-backed delivery-state regression coverage for Web Push., test_permanently_unavailable_push_is_terminal_on_postgres(), test_transient_push_error_keeps_retry_on_postgres()

### Community 593 - "Community 593"
Cohesion: 0.70
Nodes (4): _complete_setup(), test_can_finish_blocks_on_each_missing_gate(), test_can_finish_unlocks_when_required_gates_close(), test_finish_onboarding_succeeds_when_all_gates_are_closed()

### Community 595 - "Community 595"
Cohesion: 0.40
Nodes (5): A public webhook endpoint must fail closed without a configured secret., A public webhook endpoint must fail closed without a configured secret., A public webhook endpoint must fail closed without a configured secret., A public webhook endpoint must fail closed without a configured secret., test_mercadopago_webhook_signature_rejects_when_secret_is_unconfigured()

### Community 596 - "Community 596"
Cohesion: 0.70
Nodes (4): _load(), test_formal_catalog_has_exact_v2_matrix_without_observations(), test_historical_observations_are_archived_and_non_certifiable(), test_operational_catalog_cannot_look_like_formal_release_evidence()

### Community 597 - "Community 597"
Cohesion: 0.70
Nodes (4): manifest(), test_release_manifest_accepts_exact_sha_bound_artifacts(), test_release_manifest_rejects_mismatched_sha_and_mutable_tag(), test_release_manifest_rejects_wrong_environment_and_digest()

### Community 598 - "Community 598"
Cohesion: 0.60
Nodes (4): _load_migration(), SQLite coverage for the reversible cancellation-policy snapshot column., _run(), test_cancellation_policy_snapshot_migration_is_nullable_reversible_and_does_not_backfill()

### Community 599 - "Community 599"
Cohesion: 0.40
Nodes (5): Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke, Room.status is a persisted column, not derived from reservations --     a checke, test_move_reservation_room_updates_room_status_for_checked_in_reservation()

### Community 600 - "Community 600"
Cohesion: 0.60
Nodes (4): _assert_permission_defaults(), SQLite round-trip for the configurable reservation price permission., _run_alembic(), test_reservation_rate_adjust_permission_migration_upgrade_downgrade_upgrade()

### Community 601 - "Community 601"
Cohesion: 0.40
Nodes (4): B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto, B4: manual tarifa on a direct reservation with no company_id -- the         auto

### Community 602 - "Community 602"
Cohesion: 0.40
Nodes (4): Reserve a specific room., Reserve a specific room., Reserve a specific room., Reserve a specific room.

### Community 603 - "Community 603"
Cohesion: 0.40
Nodes (4): Should fail for non-existent guest., Should fail for non-existent guest., Should fail for non-existent guest., Should fail for non-existent guest.

### Community 604 - "Community 604"
Cohesion: 0.40
Nodes (4): Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category., Should fail when room doesn't match the requested category.

### Community 606 - "Community 606"
Cohesion: 0.40
Nodes (5): Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., Partial integration env vars should not block production startup., test_validate_runtime_security_ignores_incomplete_optional_integrations()

### Community 607 - "Community 607"
Cohesion: 0.40
Nodes (5): OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, OAuth redirect URIs are only validated when the corresponding service credential, test_validate_runtime_security_rejects_localhost_redirect_when_service_configured()

### Community 608 - "Community 608"
Cohesion: 0.40
Nodes (5): MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., MERCADOPAGO_WEBHOOK_SECRET is required only when MP_ACCESS_TOKEN is set., test_validate_runtime_security_rejects_missing_mp_webhook_when_mp_configured()

### Community 609 - "Community 609"
Cohesion: 0.60
Nodes (4): _alembic(), _assert_revision_schema(), SQLite migration round-trip for audited, hotel-scoped stock count sessions., test_stock_count_migration_backfills_safe_defaults_and_round_trips()

### Community 610 - "Community 610"
Cohesion: 0.60
Nodes (4): _assert_transfer_schema(), SQLite migration round-trip for linked stock transfer movements., _run_alembic(), test_stock_transfer_migration_upgrade_downgrade_upgrade()

### Community 612 - "Community 612"
Cohesion: 0.70
Nodes (4): _seed_whatsapp_hotel(), test_whatsapp_create_reservation_sets_channel_code_whatsapp(), test_whatsapp_generate_payment_link_sets_sent_via_whatsapp(), test_whatsapp_service_rejects_cross_hotel_reservation_payment_link()

### Community 613 - "Community 613"
Cohesion: 0.60
Nodes (4): downgrade(), _fk_names(), launch security hardening  Revision ID: 20260408_launch_security_hardening Revis, upgrade()

### Community 614 - "Community 614"
Cohesion: 0.50
Nodes (3): _audit_action_enum(), audit_log table and transaction.hotel_id FK  Adds the tenant-scoped audit_logs t, upgrade()

### Community 615 - "Community 615"
Cohesion: 0.60
Nodes (4): _constraint(), downgrade(), Allow downward stock adjustments.  Previously "adjustment" stock movements could, upgrade()

### Community 616 - "Community 616"
Cohesion: 0.50
Nodes (3): _backfill_primary_owners(), Add an explicit per-hotel Primary Owner membership.  Revision ID: 20260820_prima, upgrade()

### Community 617 - "Community 617"
Cohesion: 0.50
Nodes (3): _has_unique_hotel_id_id(), SQLite: give shift_handoffs' composite FK a unique parent key.  ``shift_handoffs, upgrade()

### Community 618 - "Community 618"
Cohesion: 0.50
Nodes (3): _columns(), Add hotel-scoped staff aliases and password-login capability state.  Revision ID, upgrade()

### Community 619 - "Community 619"
Cohesion: 0.60
Nodes (4): downgrade(), _install_purge_function(), Backfill the public inquiry retention clock and update the purge function.  Revi, upgrade()

### Community 620 - "Community 620"
Cohesion: 0.50
Nodes (3): _enable_tenant_rls(), Persist fixed post-checkout housekeeping checklists.  Revision ID: 20261023_hous, upgrade()

### Community 621 - "Community 621"
Cohesion: 0.60
Nodes (4): _check_clause(), downgrade(), repair sqlite reservation status enum pre_check_in  PostgreSQL got `pre_check_in, upgrade()

### Community 622 - "Community 622"
Cohesion: 0.60
Nodes (4): downgrade(), _has_column(), extend payment link tests states  Revision ID: d4f8c21e7b10 Revises: b7c1f0a8f9d, upgrade()

### Community 623 - "Community 623"
Cohesion: 0.50
Nodes (3): Add durable job dedupe and worker heartbeat metadata., _rls(), upgrade()

### Community 624 - "Community 624"
Cohesion: 0.83
Nodes (3): _compare_dirs(), main(), _skill_dirs()

### Community 625 - "Community 625"
Cohesion: 0.83
Nodes (3): main(), run(), validate_json()

### Community 626 - "Community 626"
Cohesion: 0.83
Nodes (3): main(), _non_empty(), validate_manifest()

### Community 627 - "Community 627"
Cohesion: 0.50
Nodes (2): receptionist, waitlistEntry

### Community 628 - "Community 628"
Cohesion: 0.50
Nodes (3): active_rooms(), Shared room query scopes., Return the rooms that currently exist for operational use.      Soft-deleted roo

### Community 629 - "Community 629"
Cohesion: 0.50
Nodes (4): get_country_catalog(), Return the curated country -> timezone catalog as {code, name, timezone} dicts., Return the curated country -> timezone catalog as {code, name, timezone} dicts., Return the curated country -> timezone catalog as {code, name, timezone} dicts.

### Community 630 - "Community 630"
Cohesion: 0.67
Nodes (3): GET /api/reservations/{id}/operations-summary and     GET /api/reservations/acti, _receptionist_context(), test_receptionist_can_view_operations_summary_and_pending_actions()

### Community 631 - "Community 631"
Cohesion: 0.50
Nodes (4): RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, RegisterRequest.email was a plain str with no format validation, so     garbage, test_register_rejects_malformed_email()

### Community 632 - "Community 632"
Cohesion: 0.50
Nodes (4): .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, .test" is an RFC 2606 reserved TLD email-validator blocks as     special-use by, test_register_rejects_reserved_test_tld_outside_test_mode()

### Community 633 - "Community 633"
Cohesion: 0.50
Nodes (4): The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, The isolated Playwright E2E backend boots with APP_ENV=test and its     specs re, test_register_accepts_reserved_test_tld_in_test_mode()

### Community 634 - "Community 634"
Cohesion: 0.50
Nodes (4): A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j, A guest self-registering must never end up with User.role="platform_admin"     j, test_self_registration_cannot_grant_platform_admin_role()

### Community 635 - "Community 635"
Cohesion: 0.50
Nodes (4): opened_cash_register(), Operational tests must prepare the caja before collecting cash., Operational tests must prepare the caja before collecting cash., Operational tests must prepare the caja before collecting cash.

### Community 637 - "Community 637"
Cohesion: 0.67
Nodes (3): Authorization and API contract checks for FX-credit cash refunds., _step_up_header(), test_credit_refund_requires_refund_permission_step_up_and_cash_session()

### Community 638 - "Community 638"
Cohesion: 0.83
Nodes (3): _load_migration(), _market_columns(), test_fx_direction_market_migration_preserves_global_market_and_guards_downgrade()

### Community 639 - "Community 639"
Cohesion: 0.67
Nodes (3): _load_migration(), SQLite migration coverage for separate FX rounding-credit ledger fields., test_credit_ledger_migration_preserves_old_rows_and_constrains_credit_refunds()

### Community 640 - "Community 640"
Cohesion: 0.50
Nodes (1): PostgreSQL regressions for exact non-cash FX settlement amounts.

### Community 641 - "Community 641"
Cohesion: 0.67
Nodes (3): _load_migration(), SQLite coverage for the persisted foreign-payment FX rounding policy., test_fx_rounding_policy_migration_defaults_existing_hotels_and_checks_allowed_policies()

### Community 642 - "Community 642"
Cohesion: 0.83
Nodes (3): _guest_with_companion(), test_decorator_mongo_projection_excludes_guest_pii(), test_direct_guest_and_companion_audits_exclude_pii()

### Community 644 - "Community 644"
Cohesion: 0.83
Nodes (3): _load_migration(), _run_migration(), test_migration_backfills_existing_accounts_and_retains_alias_on_rollback()

### Community 645 - "Community 645"
Cohesion: 0.50
Nodes (1): Regression: provider-supplied OAuth error text must not break out of the inline

### Community 646 - "Community 646"
Cohesion: 0.83
Nodes (3): _seed_hotels(), test_laundry_batch_lifecycle_is_hotel_scoped(), test_laundry_invalid_status_transition_is_rejected()

### Community 647 - "Community 647"
Cohesion: 0.67
Nodes (3): _alembic(), Regression coverage for the additive movement-group permission migration., test_migration_seeds_dedicated_permission_and_safe_role_defaults()

### Community 648 - "Community 648"
Cohesion: 0.67
Nodes (3): _hotel_with_pending_in_app_notification(), notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY tenant t, test_process_outbox_delivers_across_every_active_hotel()

### Community 650 - "Community 650"
Cohesion: 0.50
Nodes (1): TestBookingWebhook

### Community 651 - "Community 651"
Cohesion: 0.67
Nodes (3): _load_migration(), SQLite coverage for the legacy payment-link revocation backfill., test_migration_queues_only_legacy_open_mp_links_for_cancelled_reservations()

### Community 652 - "Community 652"
Cohesion: 0.50
Nodes (1): PostgreSQL coverage for exclusive provider-revocation work claims.

### Community 653 - "Community 653"
Cohesion: 0.50
Nodes (4): Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, Guessing the 6-digit verification code must itself be throttled, not     just re, test_verify_email_code_guessing_is_rate_limited()

### Community 654 - "Community 654"
Cohesion: 0.50
Nodes (4): validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th, validate-reset (no-op check) and reset-password (consumes the code)     guess th, test_reset_password_code_guessing_is_rate_limited_and_shared_with_validate()

### Community 655 - "Community 655"
Cohesion: 0.50
Nodes (4): Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun, Registration had no throttle at all: an attacker could farm unlimited     accoun, test_register_is_rate_limited_by_source()

### Community 656 - "Community 656"
Cohesion: 0.50
Nodes (4): Concurrent attempts share the same budget instead of racing on a pre-count., Concurrent attempts share the same budget instead of racing on a pre-count., Concurrent attempts share the same budget instead of racing on a pre-count., test_concurrent_db_requests_record_each_attempt_before_deciding()

### Community 657 - "Community 657"
Cohesion: 0.83
Nodes (3): _seed_hotel(), test_promotion_reduces_reservation_total_amount(), test_reservation_pricing_snapshot_is_unaffected_by_later_promotion_edit_or_deactivation()

### Community 658 - "Community 658"
Cohesion: 0.50
Nodes (3): Create a standard reservation and verify computed fields., Create a standard reservation and verify computed fields., Create a standard reservation and verify computed fields.

### Community 659 - "Community 659"
Cohesion: 0.50
Nodes (4): A tariff revision change invalidates the quote before any write., A tariff revision change invalidates the quote before any write., A tariff revision change invalidates the quote before any write., test_forward_stale_tariff_quote_cannot_persist_reservation()

### Community 660 - "Community 660"
Cohesion: 0.50
Nodes (3): PostgreSQL locking regression for stock-count confirmation., An in-flight movement cannot slip between stale-check and adjustment., test_confirmation_waits_for_inflight_movement_then_requires_recount()

### Community 661 - "Community 661"
Cohesion: 0.50
Nodes (1): PostgreSQL-backed contract checks for stock movement idempotency.

### Community 662 - "Community 662"
Cohesion: 0.67
Nodes (3): _index_names(), Focused regression tests for the TECH-0063 OLTP audit fixes., test_hot_path_composite_indexes_exist_in_models()

### Community 663 - "Community 663"
Cohesion: 0.50
Nodes (1): add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082

### Community 664 - "Community 664"
Cohesion: 0.50
Nodes (1): add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c

### Community 665 - "Community 665"
Cohesion: 0.50
Nodes (1): add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2

### Community 666 - "Community 666"
Cohesion: 0.50
Nodes (1): add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em

### Community 667 - "Community 667"
Cohesion: 0.50
Nodes (1): reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif

### Community 668 - "Community 668"
Cohesion: 0.50
Nodes (1): ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026

### Community 669 - "Community 669"
Cohesion: 0.50
Nodes (1): ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026

### Community 670 - "Community 670"
Cohesion: 0.50
Nodes (1): extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard

### Community 671 - "Community 671"
Cohesion: 0.50
Nodes (1): add trial and comped fields to subscriptions  Revision ID: 20260419_subscription

### Community 672 - "Community 672"
Cohesion: 0.50
Nodes (1): master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a

### Community 673 - "Community 673"
Cohesion: 0.50
Nodes (1): master admin system owner mail and stripe settings  Revision ID: 20260421_master

### Community 674 - "Community 674"
Cohesion: 0.50
Nodes (1): v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin

### Community 675 - "Community 675"
Cohesion: 0.50
Nodes (1): v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_

### Community 676 - "Community 676"
Cohesion: 0.50
Nodes (1): v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus

### Community 677 - "Community 677"
Cohesion: 0.50
Nodes (1): v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume

### Community 678 - "Community 678"
Cohesion: 0.50
Nodes (1): v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_

### Community 679 - "Community 679"
Cohesion: 0.50
Nodes (1): Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open

### Community 680 - "Community 680"
Cohesion: 0.50
Nodes (1): laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026

### Community 681 - "Community 681"
Cohesion: 0.50
Nodes (1): Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay

### Community 682 - "Community 682"
Cohesion: 0.50
Nodes (1): permission matrix, role boundaries, and security audit log  Revision ID: 2026061

### Community 683 - "Community 683"
Cohesion: 0.50
Nodes (1): Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614

### Community 684 - "Community 684"
Cohesion: 0.50
Nodes (1): Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2

### Community 685 - "Community 685"
Cohesion: 0.50
Nodes (1): v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2

### Community 686 - "Community 686"
Cohesion: 0.50
Nodes (1): v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc

### Community 687 - "Community 687"
Cohesion: 0.50
Nodes (1): drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i

### Community 688 - "Community 688"
Cohesion: 0.50
Nodes (1): Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_

### Community 689 - "Community 689"
Cohesion: 0.50
Nodes (1): v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo

### Community 690 - "Community 690"
Cohesion: 0.50
Nodes (1): add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).

### Community 691 - "Community 691"
Cohesion: 0.50
Nodes (1): reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res

### Community 692 - "Community 692"
Cohesion: 0.50
Nodes (1): soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:

### Community 693 - "Community 693"
Cohesion: 0.50
Nodes (1): repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi

### Community 694 - "Community 694"
Cohesion: 0.50
Nodes (1): Store private transfer-proof bytes separately from searchable metadata.

### Community 695 - "Community 695"
Cohesion: 0.50
Nodes (1): Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs

### Community 696 - "Community 696"
Cohesion: 0.50
Nodes (1): Add transactions.created_by_user_id for payment audit trail.  Transaction had cr

### Community 697 - "Community 697"
Cohesion: 0.50
Nodes (1): repair: create hotel_memberships table (was never migrated)  Revision ID: 202607

### Community 698 - "Community 698"
Cohesion: 0.50
Nodes (1): Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing

### Community 699 - "Community 699"
Cohesion: 0.50
Nodes (1): Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID

### Community 700 - "Community 700"
Cohesion: 0.50
Nodes (1): add permission metadata and optimistic override versions  Revision ID: 20260820_

### Community 701 - "Community 701"
Cohesion: 0.50
Nodes (1): Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the

### Community 702 - "Community 702"
Cohesion: 0.50
Nodes (1): Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_

### Community 703 - "Community 703"
Cohesion: 0.50
Nodes (1): add Apple subject and first-authorization display name  Revision ID: 20260821_ap

### Community 704 - "Community 704"
Cohesion: 0.50
Nodes (1): Add soft-delete metadata to guests and payments for TECH-0110.  The columns are

### Community 705 - "Community 705"
Cohesion: 0.50
Nodes (1): Grant receptionist the same-category room move default.  Phase A narrowed reserv

### Community 706 - "Community 706"
Cohesion: 0.50
Nodes (1): Persist short-lived MFA step-up ticket use to prevent cross-worker replay.

### Community 707 - "Community 707"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reverting room-movement groups.  Revision ID: 202

### Community 708 - "Community 708"
Cohesion: 0.50
Nodes (1): Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026

### Community 709 - "Community 709"
Cohesion: 0.50
Nodes (1): Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv

### Community 710 - "Community 710"
Cohesion: 0.50
Nodes (1): Configure official or blue USD quotes by conversion direction.  Revision ID: 202

### Community 711 - "Community 711"
Cohesion: 0.50
Nodes (1): Store external OTA payment amounts in their source currency.  Revision ID: 20261

### Community 712 - "Community 712"
Cohesion: 0.50
Nodes (1): Record FX rounding credit and manual credit refunds separately.  Revision ID: 20

### Community 713 - "Community 713"
Cohesion: 0.50
Nodes (1): Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_

### Community 714 - "Community 714"
Cohesion: 0.50
Nodes (1): Track Mercado Pago checkout revocation separately from local cancellation.  Revi

### Community 715 - "Community 715"
Cohesion: 0.50
Nodes (1): Track auditable voids for open-session cash corrections.  Revision ID: 20261024_

### Community 716 - "Community 716"
Cohesion: 0.50
Nodes (1): Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:

### Community 717 - "Community 717"
Cohesion: 0.50
Nodes (1): Add a dedicated permission for reading company vouchers and signatures.  Revisio

### Community 718 - "Community 718"
Cohesion: 0.50
Nodes (1): merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R

### Community 719 - "Community 719"
Cohesion: 0.50
Nodes (1): bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr

### Community 720 - "Community 720"
Cohesion: 0.50
Nodes (1): merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f

### Community 721 - "Community 721"
Cohesion: 0.50
Nodes (1): repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist

### Community 722 - "Community 722"
Cohesion: 0.50
Nodes (1): persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_

### Community 723 - "Community 723"
Cohesion: 0.50
Nodes (1): add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio

### Community 724 - "Community 724"
Cohesion: 0.50
Nodes (1): guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date

### Community 725 - "Community 725"
Cohesion: 0.50
Nodes (1): ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d

### Community 726 - "Community 726"
Cohesion: 0.50
Nodes (1): track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca

### Community 727 - "Community 727"
Cohesion: 0.50
Nodes (1): add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D

### Community 728 - "Community 728"
Cohesion: 0.50
Nodes (1): baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7

### Community 729 - "Community 729"
Cohesion: 0.50
Nodes (1): reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202

### Community 730 - "Community 730"
Cohesion: 0.50
Nodes (1): repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3

### Community 731 - "Community 731"
Cohesion: 1.00
Nodes (2): graphify_state(), main()

### Community 732 - "Community 732"
Cohesion: 0.67
Nodes (3): FxConversionQuoteRead, get_conversion_quote(), Return the configured official/blue conversion for any supported pair.

### Community 734 - "Community 734"
Cohesion: 0.67
Nodes (1): frontendRoot

### Community 735 - "Community 735"
Cohesion: 0.67
Nodes (3): Metadata returned by the server-side Embedded Signup exchange., Metadata returned by the server-side Embedded Signup exchange., WhatsAppChannelComplete

### Community 736 - "Community 736"
Cohesion: 0.67
Nodes (3): Normalize UTC timestamps for legacy ``DateTime`` columns without TZ., Normalize UTC timestamps for legacy ``DateTime`` columns without TZ., utc_naive()

### Community 738 - "Community 738"
Cohesion: 0.67
Nodes (1): FakeResponse

### Community 739 - "Community 739"
Cohesion: 0.67
Nodes (1): Regression coverage for the additive company-document read permission.

### Community 741 - "Community 741"
Cohesion: 0.67
Nodes (2): Verify the hotel has exactly 38 rooms., Verify the hotel has exactly 38 rooms.

### Community 742 - "Community 742"
Cohesion: 0.67
Nodes (2): Same room_number can exist in different hotels without conflict., Same room_number can exist in different hotels without conflict.

### Community 743 - "Community 743"
Cohesion: 0.67
Nodes (2): Verify room string representation., Verify room string representation.

### Community 744 - "Community 744"
Cohesion: 0.67
Nodes (1): Real PostgreSQL concurrency coverage for payment-link test callbacks.

### Community 745 - "Community 745"
Cohesion: 0.67
Nodes (1): PostgreSQL regressions for fail-fast room movement locks.

### Community 746 - "Community 746"
Cohesion: 0.67
Nodes (1): PostgreSQL regression for atomic audit persistence on legacy booking delete.

### Community 748 - "Community 748"
Cohesion: 0.67
Nodes (1): PostgreSQL regression for waitlist suggestion freshness under row locks.

### Community 750 - "Community 750"
Cohesion: 1.00
Nodes (1): Defensive datastore clients for optional infrastructure.

### Community 751 - "Community 751"
Cohesion: 1.00
Nodes (1): Application decorators.

### Community 752 - "Community 752"
Cohesion: 1.00
Nodes (1): Dependency injection helpers (auth, etc.).

### Community 754 - "Community 754"
Cohesion: 1.00
Nodes (1): Email provider abstraction for platform transactional mail.

### Community 755 - "Community 755"
Cohesion: 1.00
Nodes (1): Master admin panel backend package.

### Community 772 - "Community 772"
Cohesion: 1.00
Nodes (1): An immutable view of the effective fields in a reservation PATCH.

### Community 773 - "Community 773"
Cohesion: 1.00
Nodes (1): Return operational fields blocked for a terminal reservation.          The two P

### Community 774 - "Community 774"
Cohesion: 1.00
Nodes (1): Classify a validated PATCH payload without changing the reservation.

### Community 777 - "Community 777"
Cohesion: 1.00
Nodes (1): A moved reservation is refreshed before check-in; a busy room returns a conflict

### Community 778 - "Community 778"
Cohesion: 1.00
Nodes (1): A moved reservation is refreshed before check-in; a busy room returns a conflict

### Community 779 - "Community 779"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 780 - "Community 780"
Cohesion: 1.00
Nodes (1): Checkout uses PostgreSQL NOWAIT while holding the reservation lock.

### Community 781 - "Community 781"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 782 - "Community 782"
Cohesion: 1.00
Nodes (1): A stale eagerly loaded Room must not pass check-in after another commit.

### Community 783 - "Community 783"
Cohesion: 1.00
Nodes (1): Replace requests at the adapter boundary; never permit a real request.

### Community 784 - "Community 784"
Cohesion: 1.00
Nodes (1): Replace requests at the adapter boundary; never permit a real request.

### Community 785 - "Community 785"
Cohesion: 1.00
Nodes (1): Observe the exact PostgreSQL lock dependency, without SQL-text filters.

### Community 786 - "Community 786"
Cohesion: 1.00
Nodes (1): Observe the exact PostgreSQL lock dependency, without SQL-text filters.

### Community 787 - "Community 787"
Cohesion: 1.00
Nodes (1): Hold the first real PostgreSQL lock until the second session is waiting.

## Knowledge Gaps
- **2699 isolated node(s):** `hotel check-in checkout times  Revision ID: 015f7e36b9cd Revises: 20260930_house`, `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`, `add temporary action grants  Revision ID: 0f85dca5b98b Revises: 20260820_user_se`, `Install the PostgreSQL tenant policy; no-op on other dialects.`, `Remove the PostgreSQL tenant policy before dropping the table.` (+2694 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 97`** (1 nodes): `BookingAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 214`** (2 nodes): `OnboardingState`, `Onboarding state scoped by hotel. Tracks completion of setup steps and stores dr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 239`** (2 nodes): `HotelConfigUpdate`, `_normalize_currency()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 255`** (1 nodes): `DespegarAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 256`** (1 nodes): `ExpediaAdapter`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 413`** (2 nodes): `FakeRedis`, `test_availability_key_shape_and_serialization()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 447`** (1 nodes): `One operator-entered collection stays idempotent across grouped reservations.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 481`** (1 nodes): `TestCheckIn`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 483`** (2 nodes): `_context()`, `test_generic_room_status_patch_projects_event_and_reallocates()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 492`** (2 nodes): `_Session`, `test_subscription_session_closes_before_asgi_work()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 571`** (1 nodes): `HotelIdentityPayload`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 586`** (1 nodes): `TestGuestValidation`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 627`** (2 nodes): `receptionist`, `waitlistEntry`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 640`** (1 nodes): `PostgreSQL regressions for exact non-cash FX settlement amounts.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 645`** (1 nodes): `Regression: provider-supplied OAuth error text must not break out of the inline`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 650`** (1 nodes): `TestBookingWebhook`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 652`** (1 nodes): `PostgreSQL coverage for exclusive provider-revocation work claims.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 661`** (1 nodes): `PostgreSQL-backed contract checks for stock movement idempotency.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 663`** (1 nodes): `add user TOTP MFA and recovery codes  Revision ID: 0c66ee6f32fa Revises: 2026082`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 664`** (1 nodes): `add hotel scope to core tables  Revision ID: 20260404_add_hotel_scope Revises: c`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 665`** (1 nodes): `add subscription v2 tables  Revision ID: 20260407_subscription_tables Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 666`** (1 nodes): `add sender metadata to payment link tests  Revision ID: 20260408_payment_link_em`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 667`** (1 nodes): `reservation financial lifecycle  Revision ID: 20260410_reservation_financial_lif`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 668`** (1 nodes): `ai assistant sessions  Revision ID: 20260411_ai_assistant_sessions Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 669`** (1 nodes): `ai assistant insights  Revision ID: 20260412_ai_assistant_insights Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 670`** (1 nodes): `extend onboarding state for wizard flow  Revision ID: 20260419_onboarding_wizard`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 671`** (1 nodes): `add trial and comped fields to subscriptions  Revision ID: 20260419_subscription`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 672`** (1 nodes): `master admin panel  Revision ID: 20260421_master_admin_panel Revises: 9c0d2f3e1a`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 673`** (1 nodes): `master admin system owner mail and stripe settings  Revision ID: 20260421_master`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 674`** (1 nodes): `v72 gaps phase 1: Numeric precision, room score/accessibility, guest dedup+ratin`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 675`** (1 nodes): `v72 gaps phase 2: guest search indexes, OTA dedup constraint, updated guest_tag_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 676`** (1 nodes): `v72 gaps phase 3: room_movement_groups table, BillingAdjustment/ReservationAdjus`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 677`** (1 nodes): `v72 gaps phase 4: PRE_CHECK_IN state, RoomMoveEvent audit fields, company_docume`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 678`** (1 nodes): `v72 gaps phase 5: optimistic locking on reservations  Revision ID: 20260612_v72_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 679`** (1 nodes): `Add one-open-cash-session partial unique index.  Revision ID: 20260613_cash_open`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 680`** (1 nodes): `laundry and stock foundations  Revision ID: 20260613_laundry_stock Revises: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 681`** (1 nodes): `Add transaction idempotency key for gateway payments.  Revision ID: 20260613_pay`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 682`** (1 nodes): `permission matrix, role boundaries, and security audit log  Revision ID: 2026061`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 683`** (1 nodes): `Add PostgreSQL trigram indexes for guest search hot path.  Revision ID: 20260614`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 684`** (1 nodes): `Add daily rates and price periods.  Revision ID: 20260624_daily_rates Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 685`** (1 nodes): `v72 fx rate snapshots table.  Revision ID: 20260624_fx_rate_snapshots Revises: 2`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 686`** (1 nodes): `v72 section 12.3 - payment_surcharges table.  Revision ID: 20260624_payment_surc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 687`** (1 nodes): `drop orphan payment_surcharge_configs table (R5b).  main carries TWO surcharge i`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 688`** (1 nodes): `Add configurable public API rate limit per hotel.  Revision ID: 20260625_public_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 689`** (1 nodes): `v72 §16.2: add 'company' value to reservation_channel_code_enum.  Adds the corpo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 690`** (1 nodes): `add reservations.settlement_due_date for corporate deferred billing (R5b §3.5).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 691`** (1 nodes): `reservation waitlist flags (BRM v72 §9).  Add denormalized waitlist flags to res`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 692`** (1 nodes): `soft delete audited domain records.  Revision ID: 20260625_soft_delete Revises:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 693`** (1 nodes): `repair: ensure uq_reservation_hotel_id_id exists before payment_links FK  Revisi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 694`** (1 nodes): `Store private transfer-proof bytes separately from searchable metadata.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 695`** (1 nodes): `Add private bank-transfer proof workflow.  Revision ID: 20260724_payment_proofs`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 696`** (1 nodes): `Add transactions.created_by_user_id for payment audit trail.  Transaction had cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 697`** (1 nodes): `repair: create hotel_memberships table (was never migrated)  Revision ID: 202607`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 698`** (1 nodes): `Add quoted_amount_ars/quoted_amount_usd to reservations (dual manual OTA pricing`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 699`** (1 nodes): `Add first-name indexes for the tenant-scoped guest search hot path.  Revision ID`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 700`** (1 nodes): `add permission metadata and optimistic override versions  Revision ID: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 701`** (1 nodes): `Add tenant-scoped indexes for TECH-0063 OLTP hot paths.  The indexes mirror the`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 702`** (1 nodes): `Add normal-user server-side sessions for TECH-0021.  Revision ID: 20260820_user_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 703`** (1 nodes): `add Apple subject and first-authorization display name  Revision ID: 20260821_ap`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 704`** (1 nodes): `Add soft-delete metadata to guests and payments for TECH-0110.  The columns are`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 705`** (1 nodes): `Grant receptionist the same-category room move default.  Phase A narrowed reserv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 706`** (1 nodes): `Persist short-lived MFA step-up ticket use to prevent cross-worker replay.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 707`** (1 nodes): `Add a dedicated permission for reverting room-movement groups.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 708`** (1 nodes): `Expand public inquiries with a last-updated retention anchor.  Revision ID: 2026`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 709`** (1 nodes): `Add direction-specific USD conversion rate sides.  Revision ID: 20261016_fx_conv`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 710`** (1 nodes): `Configure official or blue USD quotes by conversion direction.  Revision ID: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 711`** (1 nodes): `Store external OTA payment amounts in their source currency.  Revision ID: 20261`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 712`** (1 nodes): `Record FX rounding credit and manual credit refunds separately.  Revision ID: 20`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 713`** (1 nodes): `Persist each hotel's foreign-payment FX rounding policy.  Revision ID: 20261022_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 714`** (1 nodes): `Track Mercado Pago checkout revocation separately from local cancellation.  Revi`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 715`** (1 nodes): `Track auditable voids for open-session cash corrections.  Revision ID: 20261024_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 716`** (1 nodes): `Coalesce pending automatic room-optimization proposals per hotel.  Revision ID:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 717`** (1 nodes): `Add a dedicated permission for reading company vouchers and signatures.  Revisio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 718`** (1 nodes): `merge stock kind fix and laundry vendor settlements  Revision ID: 513720cf2551 R`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 719`** (1 nodes): `bind users to Google subject  Revision ID: 5e86f1b9ccbb Revises: 0c66ee6f32fa Cr`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 720`** (1 nodes): `merge linen split and reservation quoted dual amounts  Revision ID: 6feb3dd16d0f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 721`** (1 nodes): `repair: ensure uq_stock_items_hotel_id_id / uq_stock_locations_hotel_id_id exist`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 722`** (1 nodes): `persist staff invitation lifecycle  Revision ID: 8b5d07cc381b Revises: 20260820_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 723`** (1 nodes): `add integration catalog  Revision ID: 9b0becb6c658 Revises: 20260407_subscriptio`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 724`** (1 nodes): `guest legal profile  Revision ID: 9c0d2f3e1a44 Revises: 3eaf48a79290 Create Date`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 725`** (1 nodes): `ota hardening: hotel-scoped mappings and webhook credentials  Revision ID: a7f3d`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 726`** (1 nodes): `track cash business timestamps  Revision ID: aa2eb9bde9e5 Revises: 20261017_loca`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 727`** (1 nodes): `add payment link tests  Revision ID: b7c1f0a8f9d2 Revises: 9b0becb6c658 Create D`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 728`** (1 nodes): `baseline  Revision ID: cb9001557529 Revises:  Create Date: 2026-03-31 19:04:53.7`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 729`** (1 nodes): `reservation cancellation policy snapshot  Revision ID: ebaf9d3d2baa Revises: 202`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 730`** (1 nodes): `repair audit_logs stray legacy columns  Revision ID: ebd2db08c7d0 Revises: 6feb3`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 731`** (2 nodes): `graphify_state()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 734`** (1 nodes): `frontendRoot`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 738`** (1 nodes): `FakeResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 739`** (1 nodes): `Regression coverage for the additive company-document read permission.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 741`** (2 nodes): `Verify the hotel has exactly 38 rooms.`, `Verify the hotel has exactly 38 rooms.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 742`** (2 nodes): `Same room_number can exist in different hotels without conflict.`, `Same room_number can exist in different hotels without conflict.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 743`** (2 nodes): `Verify room string representation.`, `Verify room string representation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 744`** (1 nodes): `Real PostgreSQL concurrency coverage for payment-link test callbacks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 745`** (1 nodes): `PostgreSQL regressions for fail-fast room movement locks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 746`** (1 nodes): `PostgreSQL regression for atomic audit persistence on legacy booking delete.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 748`** (1 nodes): `PostgreSQL regression for waitlist suggestion freshness under row locks.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 750`** (1 nodes): `Defensive datastore clients for optional infrastructure.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 751`** (1 nodes): `Application decorators.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 752`** (1 nodes): `Dependency injection helpers (auth, etc.).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 754`** (1 nodes): `Email provider abstraction for platform transactional mail.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 755`** (1 nodes): `Master admin panel backend package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 772`** (1 nodes): `An immutable view of the effective fields in a reservation PATCH.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 773`** (1 nodes): `Return operational fields blocked for a terminal reservation.          The two P`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 774`** (1 nodes): `Classify a validated PATCH payload without changing the reservation.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 777`** (1 nodes): `A moved reservation is refreshed before check-in; a busy room returns a conflict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 778`** (1 nodes): `A moved reservation is refreshed before check-in; a busy room returns a conflict`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 779`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 780`** (1 nodes): `Checkout uses PostgreSQL NOWAIT while holding the reservation lock.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 781`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 782`** (1 nodes): `A stale eagerly loaded Room must not pass check-in after another commit.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 783`** (1 nodes): `Replace requests at the adapter boundary; never permit a real request.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 784`** (1 nodes): `Replace requests at the adapter boundary; never permit a real request.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 785`** (1 nodes): `Observe the exact PostgreSQL lock dependency, without SQL-text filters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 786`** (1 nodes): `Observe the exact PostgreSQL lock dependency, without SQL-text filters.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 787`** (1 nodes): `Hold the first real PostgreSQL lock until the second session is waiting.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Base` connect `Community 15` to `Community 509`, `Community 11`, `Community 192`, `Community 9`, `Community 286`, `Community 105`, `Community 568`, `Community 140`, `Community 120`, `Community 31`, `Community 227`, `Community 61`, `Community 115`, `Community 29`, `Community 50`, `Community 25`, `Community 6`, `Community 0`, `Community 121`, `Community 20`, `Community 238`, `Community 10`, `Community 8`, `Community 4`, `Community 271`, `Community 228`, `Community 17`, `Community 93`, `Community 12`, `Community 58`, `Community 23`, `Community 7`, `Community 19`, `Community 16`, `Community 35`, `Community 80`, `Community 28`, `Community 223`, `Community 41`, `Community 511`, `Community 56`, `Community 178`, `Community 62`, `Community 214`, `Community 76`, `Community 21`, `Community 32`, `Community 24`, `Community 166`, `Community 155`, `Community 3`, `Community 14`, `Community 237`, `Community 72`, `Community 202`, `Community 39`, `Community 394`, `Community 122`, `Community 1`, `Community 26`, `Community 167`, `Community 89`, `Community 429`, `Community 396`?**
  _High betweenness centrality (0.105) - this node is a cross-community bridge._
- **Why does `HotelConfiguration` connect `Community 4` to `Community 10`, `Community 0`, `Community 8`, `Community 2`, `Community 209`, `Community 565`, `Community 6`, `Community 19`, `Community 38`, `Community 27`, `Community 21`, `Community 7`, `Community 140`, `Community 9`, `Community 15`, `Community 429`, `Community 61`, `Community 29`, `Community 50`, `Community 25`, `Community 3`, `Community 155`, `Community 122`, `Community 24`, `Community 34`, `Community 41`, `Community 367`, `Community 62`, `Community 149`, `Community 32`, `Community 73`, `Community 26`, `Community 17`, `Community 238`, `Community 336`, `Community 736`, `Community 629`, `Community 434`, `Community 517`, `Community 402`, `Community 370`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Why does `Reservation` connect `Community 0` to `Community 10`, `Community 8`, `Community 93`, `Community 4`, `Community 21`, `Community 61`, `Community 76`, `Community 23`, `Community 15`, `Community 29`, `Community 6`, `Community 50`, `Community 58`, `Community 149`, `Community 66`, `Community 103`, `Community 24`, `Community 32`, `Community 166`, `Community 81`, `Community 122`, `Community 43`, `Community 31`, `Community 16`, `Community 257`, `Community 155`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Are the 1402 inferred relationships involving `Reservation` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Reservation` has 1402 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1355 inferred relationships involving `HotelConfiguration` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`HotelConfiguration` has 1355 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1286 inferred relationships involving `ReservationStatusEnum` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`ReservationStatusEnum` has 1286 INFERRED edges - model-reasoned connections that need verification._
- **Are the 1021 inferred relationships involving `Room` (e.g. with `FastAPI routes for Booking management (thin layer over Reservation). Provides ba` and `Ensure computed fields land in the response.`) actually correct?**
  _`Room` has 1021 INFERRED edges - model-reasoned connections that need verification._