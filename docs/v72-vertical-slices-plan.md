# v72 Vertical Slices Plan

Source read before writing: `docs/business-requirements-master-v72.md` including the v72 "Auditoria masiva" summary section, `docs/data-foundations/v72-traceability-matrix.md`, `docs/data-foundations/transactions-vs-payments.md`, all Alembic filenames, HEAD migration `alembic/versions/20260612_v72_gaps_phase6_payment_tables.py`, recent migrations `20260612_v72_gaps_phase5.py`, `20260612_v72_gaps_phase4.py`, `20260612_v72_gaps_phase3.py`, plus schema migrations `20260612_v72_gaps_phase1.py` and `20260612_v72_gaps_phase2.py`. I listed `app/`, read router/service/model files, listed `frontend/`, and confirmed `web/` is MISSING.

## 1. Inventory

| V72 domain | Model | Migration | Service | Router | Tests | UI |
|---|---|---|---|---|---|---|
| Hotel config | `app/models/hotel_config.py`; `app/models/hotel_membership.py` | baseline, `20260404_add_hotel_scope.py`, onboarding/config migrations | `app/services/hotel_service.py`, `app/services/onboarding_service.py` | `app/api/config.py`, `app/api/onboarding.py` | `tests/test_config_permissions.py`, `tests/test_onboarding_flow.py`, `tests/test_onboarding_wizard.py` | `frontend/src/views/protected/SettingsHotelPage.tsx`, `frontend/src/views/onboarding/OnboardingWizard.tsx` |
| Users/roles | `app/models/user.py`, `app/models/hotel_membership.py` | baseline, `20260404_add_hotel_scope.py` | PARTIAL: `app/services/security.py`, `app/services/hotel_service.py`; no configurable permission matrix service | `app/api/auth.py`, `app/api/users.py`, `app/api/invitations.py` | `tests/test_auth_security.py`, `tests/test_invitations.py`, `tests/test_runtime_security.py` | `frontend/src/views/protected/SettingsUsersPage.tsx`, public auth pages |
| Guests | `app/models/guest.py` | `20260612_v72_gaps_phase1.py`, `20260612_v72_gaps_phase2.py`, `9c0d2f3e1a44_guest_legal_profile.py` | PARTIAL: `app/services/guest_profile.py`, `app/services/jurisdiction_profile.py`; no full guest profile/tag CRUD service observed | `app/api/guests.py` | `tests/test_business_requirements_db.py`, `tests/test_checkin.py` | PARTIAL: `frontend/src/views/protected/GuestsPage.tsx` |
| Companies | `app/models/company.py`, `app/models/company_document.py` | baseline, `20260612_v72_gaps_phase2.py`, `20260612_v72_gaps_phase4.py` | PARTIAL: company CRUD lives in `app/services/analytics_service.py`; no dedicated company document workflow service observed | `app/api/companies.py` | `tests/test_commercial_api.py`, `tests/test_commercial_service.py`, `tests/test_business_requirements_db.py` | MISSING dedicated company UI |
| Rooms/categories/rates | `app/models/room.py`, `app/models/pricing.py`, `app/models/commercial.py` | baseline, `20260612_v72_gaps_phase1.py`, `20260612_v72_gaps_phase3.py` | `app/services/reservation_service.py`, `app/services/commercial_service.py`, `app/services/pricing_policy_service.py`, `app/services/rate_calendar_service.py` | `app/api/rooms.py`, `app/api/commercial.py`, `app/api/rate_calendar.py` | `tests/test_rate_calendar_service.py`, `tests/test_rate_calendar_api.py`, `tests/test_pricing_policy_service.py`, `tests/test_business_requirements_db.py` | `frontend/src/views/protected/RoomsPage.tsx`, `frontend/src/views/protected/RateCalendarPage.tsx` |
| Inventory/availability | `app/models/reservation.py`, `app/models/room.py`, `app/models/room_block.py`, OTA inventory models in `app/models/ota.py`/`ota_core.py` | `20260612_v72_gaps_phase2.py`, `dee1bd0660f6_ota_allocation_foundation.py` | PARTIAL: `app/services/reservation_service.py` (`check_room_availability`, `find_available_rooms`) does not consult `room_blocks`; `app/services/rate_calendar_service.py` covers rate/inventory calendar | `app/api/rooms.py`, `app/api/bookings.py`, `app/api/rate_calendar.py` | `tests/test_multi_hotel_isolation_contracts.py`, `tests/test_rate_calendar_api.py` | PARTIAL: reservation/rooms/rate calendar pages; no separate block management UI |
| Reservations + modifications + assignments | `app/models/reservation.py`, `app/models/operations.py`, `app/models/allocation.py`, `app/models/waitlist.py` | baseline, `20260612_v72_gaps_phase1.py`, `phase3.py`, `phase4.py`, `phase5.py`, `dee1bd0660f6_ota_allocation_foundation.py` | `app/services/reservation_service.py`, `app/services/reservation_operations_service.py`, `app/services/reservation_action_service.py`, `app/services/allocation_engine.py`, `app/services/allocation_runtime_service.py`, `app/services/allocation_policy_service.py` | `app/api/reservations.py`, `app/api/bookings.py`, `app/api/allocation_policy.py` | `tests/test_reservation_service.py`, `tests/test_reservation_operations_service.py`, `tests/test_allocation_engine.py`, `tests/test_allocation_policy_service.py` | PARTIAL: `frontend/src/views/protected/ReservationsPage.tsx`; no full assignment group/revert UI |
| Stays | PARTIAL: represented by `app/models/reservation.py` actual check-in/out and room move history; no separate Stay model | baseline, `20260612_v72_gaps_phase4.py` | PARTIAL: `app/services/checkin_service.py`, `app/services/reservation_operations_service.py` | `app/api/checkin.py`, `app/api/reservations.py` | `tests/test_checkin.py`, `tests/test_reservation_operations_service.py` | PARTIAL: Reservations page only |
| Check-in/out | `app/models/reservation.py`, `app/models/guest.py`, `app/models/room.py` | baseline, `20260612_v72_gaps_phase4.py` | `app/services/checkin_service.py` | `app/api/checkin.py`, legacy booking endpoints in `app/api/bookings.py` | `tests/test_checkin.py`, `tests/test_checkin_security.py` | PARTIAL: no dedicated check-in wizard observed |
| Payments/deposits/MercadoPago/refunds | `app/models/transaction.py`, `app/models/payment_config.py`, `app/models/payment_link_test.py`, `app/models/refund.py`, `app/models/voucher.py`; MISSING models for new `payments`, `payment_links`, `payment_webhook_events` tables | `20260410_reservation_financial_lifecycle.py`, `20260612_vouchers_refunds_pending_actions.py`, `20260612_v72_gaps_phase1.py`, `20260612_v72_gaps_phase6_payment_tables.py` | PARTIAL: `app/services/payment_service.py` writes `transactions`; `app/services/payment_link_test_service.py` is test-link only; no production PaymentLink/Payment webhook service observed | `app/api/payments.py`, `app/api/payment_link_tests.py` | `tests/test_payment_service.py`, `tests/test_mercadopago_webhook_signature.py`, `tests/smoke/test_payment_failures.py` | PARTIAL: `frontend/src/views/protected/SettingsTestsPage.tsx`; no production reservation payment-link UI |
| Cash sessions/arqueo | `app/models/cash_register.py` | `20260612_v72_gaps_phase1.py` | MISSING cash register service | MISSING cash register router | `tests/test_business_requirements_db.py`, `tests/test_multi_tenancy_isolation.py` only schema/isolation | MISSING |
| Analytics/reports | `app/models/analytics.py` | `20260424_analytics_r1_base.py` | `app/services/analytics_service.py`, `app/services/analytics_facts.py`, `app/services/analytics_exports.py`, `app/services/analytics_insights.py` | `app/api/analytics.py`, `app/api/reports.py`, `app/api/room_state_events.py` | `tests/test_analytics_*.py`, `tests/test_rate_calendar_api.py` | `frontend/src/views/protected/analytics/AnalyticsPages.tsx`, dashboard |
| Audit | `app/models/audit_log.py`, `app/models/analytics.py` (`HotelAuditEvent`), movement/status models in `app/models/operations.py` | `20260612_audit_log_and_transaction_fk.py`, `20260424_analytics_r1_base.py`, `20260612_v72_gaps_phase3.py`, `phase4.py` | PARTIAL: `app/services/analytics_service.py` has audit helpers; status/move history inserted in reservation services; no central audit service | PARTIAL: master admin audit in `app/master_admin/router.py`; no hotel audit router observed | `tests/test_audit_log_model.py`, analytics audit tests | PARTIAL: `frontend/src/master_admin/pages/AuditPage.tsx`; no hotel operator audit UI |
| Housekeeping | PARTIAL: `app/models/room.py` room status, `app/models/analytics.py` `RoomStateEvent` | `20260424_analytics_r1_base.py` | PARTIAL: room status logic in `app/api/rooms.py`, room state helpers in `app/services/analytics_service.py` | `app/api/rooms.py`, `app/api/room_state_events.py` | `tests/test_multi_hotel_isolation_contracts.py`, `tests/test_analytics_block1_schema.py` | PARTIAL: no dedicated housekeeping page; room/status UI only |
| Laundry | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| Stock | MISSING | MISSING | MISSING | MISSING | MISSING | MISSING |
| OTA integrations | `app/models/ota.py`, `app/models/ota_core.py`, `app/models/integration.py`, `app/models/connection.py` | `dee1bd0660f6_ota_allocation_foundation.py`, `a7f3d2c1b9e8_ota_hardening.py`, `9b0becb6c658_add_integration_catalog.py`, `20260612_v72_gaps_phase2.py` | `app/services/ota_service.py`, `app/services/ota/orchestrator.py`, adapters under `app/services/ota/adapters/`, `app/services/integration_service.py` | `app/api/ota_webhooks.py`, `app/api/integrations.py`, `app/api/connections.py` | `tests/test_ota_*.py`, `tests/test_connections.py`, `tests/test_integration_crypto_hardening.py` | PARTIAL: `frontend/src/views/protected/SettingsConnectionsPage.tsx` |
| API keys | `app/models/hotel_api_key.py` | `20260612_v72_gaps_phase1.py` | MISSING API key issue/verify/rate-limit service | MISSING hotel API key router/public API router | `tests/test_business_requirements_db.py`, `tests/test_multi_tenancy_isolation.py` schema/isolation only | MISSING |
| WhatsApp bot hooks | PARTIAL: `HotelAPIKey` purpose, `ReservationChannelCodeEnum.WHATSAPP`, integration catalog entry | `20260612_v72_gaps_phase1.py`, `20260424_analytics_r1_base.py`, `9b0becb6c658_add_integration_catalog.py` | MISSING WhatsApp/public booking service | MISSING public WhatsApp bot router | analytics fixtures only | MISSING |

## 2. Vertical Slices

### SLICE-01
- slice_id: SLICE-01
- name: Permission Matrix and Role Boundaries
- scope: Replace hard-coded role checks for V72-sensitive actions with permission-aware checks while preserving current roles. Cover guest edits/tags, company creation, overbooking, room block/unblock, no-show, check-in override, payments, and admin-only configuration.
- files_to_create: `app/models/permission.py`, `app/schemas/permission.py`, `app/services/permission_service.py`, `app/api/permissions.py`, `tests/test_permission_service.py`, `tests/test_permissions_api.py`, `frontend/src/api/permissions.ts`, `frontend/src/hooks/usePermissions.ts`
- files_to_modify: `app/dependencies/auth.py`, `app/api/users.py`, `app/api/guests.py`, `app/api/companies.py`, `app/api/reservations.py`, `app/api/rooms.py`, `app/api/checkin.py`, `app/main.py`, `frontend/src/views/protected/SettingsSecurityPage.tsx`
- v72_sections_covered: `1. Regla global de obligatoriedad`, `2.2 Correccion de datos`, `2.6 Rating y tags`, `2.7 Prohibido alojar`, `3.2`, `9.1`, `14.1`, `17 Sprint 1 roles/permisos`, v72 audit summary permissions/security
- acceptance_criteria: `test_default_permissions_seeded_for_owner_manager_reception_housekeeping`, `test_permission_override_allows_receptionist_guest_edit`, `test_housekeeping_cannot_create_reservation_by_default`, `test_permission_denied_is_audited`, Playwright `settings-security-permissions.spec.ts`
- complexity: L
- depends_on: []

### SLICE-02
- slice_id: SLICE-02
- name: Guest Profile, Tags, and Check-in Override
- scope: Complete guest CRUD/search/profile/tag workflows and implement audited superior override for `prohibido_alojar` check-in blocks. Keep no manual merge in V1 and rely on document dedup.
- files_to_create: `app/services/guest_service.py`, `app/schemas/guest_tag.py`, `tests/test_guest_service.py`, `tests/test_guest_api_profile.py`, `frontend/src/api/guestTags.ts`, `frontend/src/hooks/useGuestTags.ts`, `frontend/e2e/guest-profile.spec.ts`
- files_to_modify: `app/api/guests.py`, `app/api/checkin.py`, `app/services/checkin_service.py`, `app/models/guest.py`, `frontend/src/views/protected/GuestsPage.tsx`
- v72_sections_covered: `2.1-2.7 Huespedes`, `7.3-7.4 agregar huespedes posteriores`, v72 audit summary guests/security/UX
- acceptance_criteria: `test_guest_search_matches_document_phone_email_name`, `test_guest_quick_profile_returns_last_five_stays_and_tags`, `test_prohibido_alojar_blocks_checkin_without_override`, `test_authorized_override_allows_checkin_and_writes_audit`, Playwright `guest-profile-tags-and-checkin-override.spec.ts`
- complexity: L
- depends_on: [SLICE-01]

### SLICE-03
- slice_id: SLICE-03
- name: Corporate Reservations and Documents
- scope: Make companies operational for V1: commercial fields, deferred payment flags, vouchers/documents, signature status, and manual-only assignment for corporate reservations.
- files_to_create: `app/services/company_document_service.py`, `app/api/company_documents.py`, `app/schemas/company_document.py`, `tests/test_company_documents_service.py`, `tests/test_company_documents_api.py`, `frontend/src/api/companies.ts`, `frontend/src/views/protected/CompaniesPage.tsx`, `frontend/e2e/company-documents.spec.ts`
- files_to_modify: `app/api/companies.py`, `app/services/analytics_service.py`, `app/api/reservations.py`, `app/services/reservation_service.py`, `app/main.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`
- v72_sections_covered: `3.1-3.7 Reservas de empresa`, `8.1 asignacion`, `17 Sprint 1 empresas basico`
- acceptance_criteria: `test_receptionist_cannot_create_company_by_default`, `test_company_base_price_applies_as_reservation_default_but_can_override`, `test_company_document_signature_status_flow`, `test_corporate_reservation_is_allocation_locked`, Playwright `companies-documents.spec.ts`
- complexity: M
- depends_on: [SLICE-01]

### SLICE-04
- slice_id: SLICE-04
- name: Room Blocks, Availability, and Housekeeping
- scope: Add service/router/UI for date-ranged and indefinite room blocks, integrate active blocks into availability and allocation, and make housekeeping room-state actions role-safe.
- files_to_create: `app/services/room_block_service.py`, `app/api/room_blocks.py`, `app/schemas/room_block.py`, `tests/test_room_block_service.py`, `tests/test_room_blocks_api.py`, `frontend/src/api/roomBlocks.ts`, `frontend/src/hooks/useRoomBlocks.ts`, `frontend/e2e/room-blocks.spec.ts`
- files_to_modify: `app/services/reservation_service.py`, `app/services/allocation_engine.py`, `app/services/allocation_runtime_service.py`, `app/api/rooms.py`, `app/main.py`, `frontend/src/views/protected/RoomsPage.tsx`
- v72_sections_covered: `4 Habitaciones`, `13 Calendario`, `14 Bloqueos y mantenimiento`, `17 Sprint 1 habitaciones/calendario/disponibilidad`
- acceptance_criteria: `test_active_room_block_excludes_room_from_availability`, `test_indefinite_block_excludes_future_dates_until_resolved`, `test_block_with_conflicting_protected_reservation_requires_manual_resolution`, `test_unblock_triggers_reallocation_run`, Playwright `rooms-blocks-housekeeping.spec.ts`
- complexity: L
- depends_on: [SLICE-01]

### SLICE-05
- slice_id: SLICE-05
- name: Allocation Engine V72 Rules
- scope: Align the solver with V72 hard rules: mobility restriction lowest floor, room score as tiebreaker only, protected/manual/corporate/in-progress reservations immovable, movement groups, and audited group revert.
- files_to_create: `app/services/room_movement_group_service.py`, `app/api/room_movement_groups.py`, `app/schemas/room_movement_group.py`, `tests/test_allocation_v72_rules.py`, `tests/test_room_movement_groups_api.py`, `frontend/src/api/allocationRuns.ts`, `frontend/e2e/allocation-movement-groups.spec.ts`
- files_to_modify: `app/services/allocation_engine.py`, `app/services/allocation_runtime_service.py`, `app/services/reservation_operations_service.py`, `app/models/operations.py`, `app/api/reservations.py`, `app/main.py`, `frontend/src/views/protected/ReservationsPage.tsx`
- v72_sections_covered: `5.1-5.6 Motor de reservas`, `6 Restriccion motriz`, `8.2 cambio habitacion`, `8.6 extension con futura vendida`
- acceptance_criteria: `test_mobility_restriction_prefers_lowest_compatible_floor`, `test_score_only_breaks_equivalent_room_tie`, `test_solver_does_not_move_corporate_manual_or_pre_checkin_reservations`, `test_allocation_run_creates_movement_group_and_events`, `test_revert_movement_group_marks_reservations_protected`, Playwright `allocation-runs-revert.spec.ts`
- complexity: L
- depends_on: [SLICE-03, SLICE-04]

### SLICE-06
- slice_id: SLICE-06
- name: Reservation Lifecycle, Waitlist, No-show, and Extensions
- scope: Complete V72 reservation operations: manual/phone/OTA creation, waitlist without payment links, no-show marking, add later guests, date changes with/without payments, extensions with immediate payment/link action, and optimistic locking.
- files_to_create: `app/services/waitlist_service.py`, `app/api/waitlist.py`, `app/schemas/waitlist.py`, `tests/test_waitlist_service.py`, `tests/test_reservation_lifecycle_v72.py`, `frontend/src/api/waitlist.ts`, `frontend/src/views/protected/WaitlistPage.tsx`, `frontend/e2e/reservation-lifecycle.spec.ts`
- files_to_modify: `app/api/reservations.py`, `app/services/reservation_service.py`, `app/services/reservation_operations_service.py`, `app/schemas/reservation.py`, `app/main.py`, `frontend/src/views/protected/ReservationsPage.tsx`, `frontend/src/router.tsx`
- v72_sections_covered: `7 Check-in/check-out y huespedes`, `8 Reservas cambios y extensiones`, `9 Overbooking y lista de espera`, `10 OTA manual`, `11 Reserva telefonica/manual`, `13 Calendario`
- acceptance_criteria: `test_waitlist_entry_has_no_room_and_cannot_request_payment_link`, `test_no_show_can_be_marked_without_auto_charge`, `test_date_change_without_payments_cancels_and_recreates`, `test_date_change_with_payments_requires_manager_and_preserves_history`, `test_extension_requires_payment_or_link_action`, Playwright `waitlist-and-reservation-edits.spec.ts`
- complexity: L
- depends_on: [SLICE-01, SLICE-04]

### SLICE-07
- slice_id: SLICE-07
- name: Production Payments, Links, Webhooks, Refunds
- scope: Implement production `payment_links`, `payments`, and `payment_webhook_events` model/service/router stack and converge it with `transactions` as canonical ledger. Keep MercadoPago webhook signature validation and idempotency explicit.
- files_to_create: `app/models/payment.py`, `app/models/payment_link.py`, `app/models/payment_webhook_event.py`, `app/schemas/payment_link.py`, `app/services/payment_link_service.py`, `app/services/payment_webhook_service.py`, `app/api/payment_links.py`, `tests/test_payment_link_service.py`, `tests/test_payment_webhook_service.py`, `tests/test_payment_links_api.py`, `frontend/src/api/paymentLinks.ts`, `frontend/src/hooks/usePaymentLinks.ts`, `frontend/e2e/reservation-payment-links.spec.ts`
- files_to_modify: `app/models/__init__.py`, `app/services/payment_service.py`, `app/api/payments.py`, `app/api/payment_link_tests.py`, `app/main.py`, `frontend/src/views/protected/ReservationsPage.tsx`, `frontend/src/api/payments.ts`
- v72_sections_covered: `7.1 pago completo antes de check-in`, `8.5 extension pago/link`, `12 Pagos y links`, `15 Emails y Gmail`, `17 Sprint 1 pagos manuales/links/MercadoPago/PayPal`, `transactions-vs-payments.md`
- acceptance_criteria: `test_create_payment_link_persists_link_without_transaction`, `test_gateway_webhook_is_idempotent_by_provider_webhook_id`, `test_completed_gateway_payment_creates_one_transaction`, `test_balance_due_uses_transactions_not_payments`, `test_refund_request_gateway_voucher_manual_paths`, Playwright `reservation-payment-link-flow.spec.ts`
- complexity: L
- depends_on: [SLICE-01]

### SLICE-08
- slice_id: SLICE-08
- name: Cash Register and Arqueo
- scope: Add operational cash sessions, movements, expected balance calculation from confirmed cash transactions, close report, difference approval, and race-safe one-open-session rule.
- files_to_create: `app/services/cash_register_service.py`, `app/api/cash_register.py`, `app/schemas/cash_register.py`, `tests/test_cash_register_service.py`, `tests/test_cash_register_api.py`, `frontend/src/api/cashRegister.ts`, `frontend/src/hooks/useCashRegister.ts`, `frontend/src/views/protected/CashRegisterPage.tsx`, `frontend/e2e/cash-register.spec.ts`
- files_to_modify: `app/services/payment_service.py`, `app/main.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`
- v72_sections_covered: `17 Sprint 1 caja basica`, v72 audit summary caja/arqueo/reportes, `transactions-vs-payments.md`
- acceptance_criteria: `test_only_one_open_cash_session_per_hotel_is_allowed`, `test_cash_payment_creates_cash_movement_in_open_session`, `test_close_report_expected_balance_uses_confirmed_cash_transactions`, `test_close_with_difference_requires_approval_permission`, Playwright `cash-session-close.spec.ts`
- complexity: M
- depends_on: [SLICE-07]

### SLICE-09
- slice_id: SLICE-09
- name: Public Hotel API Keys and Booking Engine Hooks
- scope: Build hotel-scoped API key issuance/verification, public availability/rate/category/reservation/link endpoints, rate limiting by hotel/key, and clear separation from staff JWT auth.
- files_to_create: `app/services/hotel_api_key_service.py`, `app/dependencies/api_key_auth.py`, `app/schemas/hotel_api_key.py`, `app/api/hotel_api_keys.py`, `app/api/public_booking.py`, `tests/test_hotel_api_key_service.py`, `tests/test_public_booking_api.py`, `frontend/src/api/apiKeys.ts`, `frontend/src/views/protected/SettingsApiKeysPage.tsx`, `frontend/e2e/api-keys.spec.ts`
- files_to_modify: `app/main.py`, `app/services/rate_calendar_service.py`, `app/services/reservation_service.py`, `app/services/payment_link_service.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`
- v72_sections_covered: `16 API publica del hotel`, `16.2 Web propia / booking engine`, `17 Sprint 1 API base`
- acceptance_criteria: `test_api_key_secret_is_only_returned_once_and_hash_is_stored`, `test_public_availability_requires_active_api_key`, `test_public_reservation_is_scoped_to_key_hotel`, `test_public_api_rate_limit_is_per_hotel_key`, Playwright `settings-api-keys.spec.ts`
- complexity: L
- depends_on: [SLICE-04, SLICE-07]

### SLICE-10
- slice_id: SLICE-10
- name: WhatsApp Bot Hooks
- scope: Add WhatsApp-specific public hook endpoints for availability, prices, options, reservation creation, payment link generation, and payment confirmation callback handling through explicit API-key auth.
- files_to_create: `app/services/whatsapp_booking_service.py`, `app/api/whatsapp_hooks.py`, `app/schemas/whatsapp_hooks.py`, `tests/test_whatsapp_hooks_api.py`, `tests/test_whatsapp_booking_service.py`, `frontend/src/views/protected/SettingsWhatsAppPage.tsx`, `frontend/e2e/whatsapp-settings.spec.ts`
- files_to_modify: `app/main.py`, `app/services/hotel_api_key_service.py`, `app/services/reservation_service.py`, `app/services/payment_link_service.py`, `app/services/payment_webhook_service.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`, `frontend/src/views/protected/SettingsConnectionsPage.tsx`
- v72_sections_covered: `16.1 WhatsApp bot`, `16.2 origenes`, `17 Sprint 1 API base WhatsApp/web propia`
- acceptance_criteria: `test_whatsapp_availability_uses_api_key_hotel_scope`, `test_whatsapp_create_reservation_sets_channel_code_whatsapp`, `test_whatsapp_generate_payment_link_sets_sent_via_whatsapp`, `test_whatsapp_payment_confirmation_is_idempotent`, Playwright `whatsapp-hook-config.spec.ts`
- complexity: M
- depends_on: [SLICE-09]

### SLICE-11
- slice_id: SLICE-11
- name: Reports and Operational Alerts
- scope: Fill daily/nightly reports and alerts for pending payment, late arrivals, available-with-review, maintenance/room/cash signals, and exports aligned with analytics facts.
- files_to_create: `app/services/operational_report_service.py`, `app/schemas/reports.py`, `tests/test_operational_reports.py`, `frontend/src/api/reports.ts`, `frontend/src/views/protected/ReportsPage.tsx`, `frontend/e2e/reports-alerts.spec.ts`
- files_to_modify: `app/api/reports.py`, `app/services/analytics_facts.py`, `app/services/hotel_outbound_email_service.py`, `app/main.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`, `frontend/src/views/protected/DashboardPage.tsx`
- v72_sections_covered: `13 Calendario/planilla`, `15 Emails y Gmail`, `17 Sprint 1 reportes basicos`, v72 audit summary reportes/UX
- acceptance_criteria: `test_daily_report_includes_pending_payment_late_arrivals_and_room_blocks`, `test_available_with_review_today_sends_immediate_alert`, `test_nightly_report_uses_hotel_gmail_identity`, Playwright `reports-dashboard-alerts.spec.ts`
- complexity: M
- depends_on: [SLICE-04, SLICE-07, SLICE-08]

### SLICE-12
- slice_id: SLICE-12
- name: OTA Manual and Integration Hardening
- scope: Complete manual OTA reservation dedup/update/audit, internal release of no-guarantee OTA reservations, and webhook security boundaries without relying on live channel manager sync.
- files_to_create: `app/services/ota_manual_service.py`, `app/schemas/ota_manual.py`, `tests/test_ota_manual_service.py`, `frontend/e2e/ota-manual-reservations.spec.ts`
- files_to_modify: `app/api/reservations.py`, `app/api/ota_webhooks.py`, `app/services/ota_service.py`, `app/services/reservation_action_service.py`, `app/services/reservation_service.py`, `frontend/src/views/protected/ReservationsPage.tsx`, `frontend/src/views/protected/SettingsConnectionsPage.tsx`
- v72_sections_covered: `10 OTA manual y duplicados`, `13.2 OTA sin pago`, `17 Sprint 1 carga manual OTA`, `Sprint 1 NO necesita Channel Manager real`
- acceptance_criteria: `test_manual_ota_requires_channel_and_external_id`, `test_duplicate_channel_external_id_updates_existing_reservation_and_audits`, `test_no_guarantee_ota_internal_release_does_not_call_provider_cancel`, `test_deprecated_ota_webhook_routes_return_410`, Playwright `manual-ota-reservation.spec.ts`
- complexity: M
- depends_on: [SLICE-01, SLICE-06]

### SLICE-13
- slice_id: SLICE-13
- name: Laundry and Stock Foundations
- scope: Add minimal V72 operational foundations for laundry and stock because both are entirely missing today. Keep scope to inventory records, movements, and room/stay linkage without procurement or accounting expansion.
- files_to_create: `app/models/laundry.py`, `app/models/stock.py`, `app/schemas/laundry.py`, `app/schemas/stock.py`, `app/services/laundry_service.py`, `app/services/stock_service.py`, `app/api/laundry.py`, `app/api/stock.py`, `alembic/versions/<new>_v72_laundry_stock.py`, `tests/test_laundry_service.py`, `tests/test_stock_service.py`, `frontend/src/views/protected/LaundryPage.tsx`, `frontend/src/views/protected/StockPage.tsx`
- files_to_modify: `app/models/__init__.py`, `app/main.py`, `frontend/src/router.tsx`, `frontend/src/ui/AppShell.tsx`
- v72_sections_covered: v72 domain list from task, v72 audit summary operations/data/QA; no detailed numbered BRM laundry/stock section observed in `business-requirements-master-v72.md`
- acceptance_criteria: `test_laundry_batch_lifecycle_is_hotel_scoped`, `test_stock_item_and_movement_are_hotel_scoped`, `test_stock_movement_requires_positive_quantity`, Playwright `laundry-stock-foundation.spec.ts`
- complexity: M
- depends_on: [SLICE-01]

## 3. Wave Plan

Wave 1 can run fully in parallel as isolated git worktrees:
- SLICE-01 writes permission/auth/users/security files.
- SLICE-07 writes payment link/payment webhook files and payment service/router.
- SLICE-13 writes new laundry/stock files plus `app/models/__init__.py`, `app/main.py`, and frontend navigation.

Disjoint file-set confirmation: SLICE-01 and SLICE-07 are disjoint except both may later affect secured routers, but Wave 1 scope keeps SLICE-01 changes to auth/permissions and existing routers, while SLICE-07 owns payment files. SLICE-13 conflicts with any other slice that edits `app/main.py`, `app/models/__init__.py`, `frontend/src/router.tsx`, or `frontend/src/ui/AppShell.tsx`; run it in a separate worktree but merge after route-registration edits are reconciled, or defer navigation registration to one integration commit. For strict no-conflict parallelism, run SLICE-13 without frontend/router registration until integration.

Wave 2 depends only on Wave 1:
- SLICE-02 depends on SLICE-01.
- SLICE-03 depends on SLICE-01.
- SLICE-04 depends on SLICE-01.
- SLICE-08 depends on SLICE-07.

Disjoint file-set confirmation: SLICE-02 owns guest/check-in profile files; SLICE-03 owns companies/documents; SLICE-04 owns room blocks/availability/rooms; SLICE-08 owns cash register/payment cash integration. Conflicts: SLICE-02 and SLICE-04 both may touch `app/api/checkin.py`/room status only lightly; SLICE-04 and SLICE-08 both edit `app/main.py` and frontend nav. Keep API router registration in one integration commit to avoid merge conflicts.

Wave 3 depends on Wave 2:
- SLICE-05 depends on SLICE-03 and SLICE-04.
- SLICE-06 depends on SLICE-01 and SLICE-04.
- SLICE-09 depends on SLICE-04 and SLICE-07.
- SLICE-12 depends on SLICE-01 and SLICE-06.

Disjoint file-set confirmation: SLICE-05 owns allocation/movement groups; SLICE-06 owns waitlist/lifecycle/reservation edits; SLICE-09 owns public API/API keys; SLICE-12 owns OTA manual hardening. Expected conflicts: SLICE-05, SLICE-06, and SLICE-12 all modify `app/api/reservations.py` and `app/services/reservation_service.py`; do not merge them in parallel without pre-splitting reservation router/service into focused modules or assigning a single integration owner.

Wave 4 depends on Wave 3:
- SLICE-10 depends on SLICE-09.
- SLICE-11 depends on SLICE-04, SLICE-07, and SLICE-08.

Disjoint file-set confirmation: SLICE-10 owns WhatsApp/public hook files; SLICE-11 owns reports/alerts. They are disjoint except `app/main.py`, frontend router/nav, and possibly `hotel_outbound_email_service.py` if WhatsApp notifications later use email/SMS fallbacks.

## 4. Requires Schema Change

| Requirement with no complete home in current HEAD schema | Suggested table/column | Estimated migration complexity |
|---|---|---|
| Configurable permission matrix beyond hard-coded roles | `permissions`, `role_permission_defaults`, `hotel_role_permission_overrides` | M |
| Audited override token/approval for `prohibido_alojar` check-in by superior | `guest_checkin_overrides` or generic `approval_tokens` with `entity_type`, `entity_id`, `approved_by_user_id`, `expires_at`, `used_at` | M |
| Full quick guest profile can be served from existing tables, but active alerts need lifecycle fields if tags are to be resolved/dismissed | Add `resolved_at`, `resolved_by_user_id` to `guest_tags` or create `guest_alert_events` | S |
| Reservation room history across stays exists as `room_move_events`, but a formal "stays" aggregate is absent | Optional `stays` table if product needs stay separate from reservation; otherwise no migration | M |
| Production `payments`, `payment_links`, `payment_webhook_events` tables exist in migration but no SQLAlchemy models observed | Add ORM model files matching existing HEAD tables; no DB migration if schema matches | S |
| Payment idempotency rule for `transactions` references `idempotency_key`, but `app/models/transaction.py` does not show `idempotency_key` | `transactions.idempotency_key`, unique `(hotel_id, reservation_id, idempotency_key)` where not null | M |
| Payment surcharge as line item/separate audit is not represented beyond config | `payment_link_surcharges` or `payment_links.surcharge_amount`, `base_amount`, `surcharge_config_id` | S |
| Cash one-open-session invariant is not DB-enforced | Partial unique index on `cash_sessions(hotel_id)` where `status='open'` | M, PostgreSQL-specific plus SQLite test workaround |
| Cash close concurrency/versioning | `cash_sessions.version`, optional `cash_close_reports.version` | S |
| Public API rate limiting by hotel/key has event table but no key-scoped counters | `api_key_rate_limit_events` or extend `rate_limit_events` with `hotel_id`, `api_key_id`, `route_key` | M |
| WhatsApp bot conversation/request audit | `whatsapp_bot_events` with request/response metadata, `hotel_id`, `api_key_id`, `reservation_id`, redacted payload | M |
| Laundry domain is entirely absent | `laundry_batches`, `laundry_items`, `laundry_movements` | M |
| Stock domain is entirely absent | `stock_items`, `stock_locations`, `stock_movements` | M |
| Room damage/observations mentioned in pending requirements are only generic notes | `room_damage_reports` or `room_observation_events` | M |
| Calendar "available with review" warning is not a durable state | `room_review_flags` or extend `room_state_events` with `available_with_review` event type | S |
| Morning/immediate alert recipients per hotel are not visible as schema | `hotel_alert_recipients`, `hotel_alert_rules` | M |
| Formal report schedules for daily/nightly emails are not visible | `report_schedules`, `report_delivery_events` | M |
| Company voucher/document files store `file_url`; no file storage metadata/checksum observed | Add `storage_key`, `content_type`, `sha256_hex`, `uploaded_by_user_id` to `company_documents` | S |
| Allocation movement group table exists, but `RoomMoveEvent` model/schema must include `movement_group_id` and audit fields if not already synchronized | Align `app/models/operations.py` with `20260612_v72_gaps_phase3.py` and `phase4.py`; no migration if already present in DB | S |

## 5. Risk Register

| Risk | Specific files/functions | Why it matters | Mitigation |
|---|---|---|---|
| Allocation solver concurrency | `app/api/reservations.py:508 recalculate_allocation`, `app/services/allocation_runtime_service.py:53 run_persisted_allocation`, `app/services/allocation_engine.py:461 apply_allocation_result` | Allocation applies multiple room changes without a hotel-level allocation lock or row locks for all affected reservations/rooms. Concurrent reservation creation can invalidate solver assumptions. | Add hotel-scoped allocation lock, select affected reservations `FOR UPDATE`, version-check reservations before apply, and test concurrent recalculate/create. |
| Allocation ignores active room blocks | `app/services/reservation_service.py:214 check_room_availability`, `app/services/reservation_service.py:250 find_available_rooms`, `app/services/allocation_engine.py:595 build_slots_from_db` | Schema has `room_blocks`, but availability and solver candidate rooms do not consult date-ranged blocks, so blocked rooms can be sold/assigned. | Centralize availability query with room-block exclusion and reuse it from reservation creation, rooms API, allocation, and public API. |
| Allocation hard rules incomplete | `app/services/allocation_engine.py:31 ReservationSlot`, `app/services/allocation_engine.py:589 is_locked`, `app/models/reservation.py` mobility fields | Current lock check covers checked-in/allocation_locked; V72 also protects pre-check-in/check-in started, corporate, manual/protected, and requires mobility lowest-floor preference and score as tiebreaker. | Extend slot fields and tests for each hard rule before changing objective weights. |
| Cash close race conditions | `app/models/cash_register.py`; MISSING `cash_register_service.py`/router | Schema permits multiple open sessions unless constrained by service/DB. Close expected balance can race with late cash movement insertion. | Add transactional close flow with `FOR UPDATE` session lock, one-open-session constraint, and movement cutoff at close timestamp. |
| Payment webhook idempotency | `alembic/versions/20260612_v72_gaps_phase6_payment_tables.py`, MISSING `PaymentWebhookEvent` model/service, `app/api/payment_link_tests.py:92 mercadopago_webhook` | HEAD schema has webhook uniqueness but production webhook service is missing. Test-link webhook is separate and can refresh records by reference but does not create canonical `Payment` then `Transaction`. | Implement production webhook service using unique `(hotel_id, provider, webhook_id)`, signature verification, provider payment lookup, and transaction idempotency. |
| Transactions/payments divergence | `app/services/payment_service.py:114 process_payment`, `docs/data-foundations/transactions-vs-payments.md` | Service only writes `transactions`; new `payments` and `payment_links` tables have no ORM/service, so gateway lifecycle cannot be audited per source-of-truth rule. | Add ORM and service convergence: link -> payment -> completed transaction, with balance computed only from confirmed transactions. |
| Multi-tenancy gap in unauthenticated connection endpoint | `app/api/connections.py:16 connect_provider` | Endpoint accepts provider payload with only DB dependency in observed signature, no `AuthContext`; likely can create/update provider connections without hotel membership enforcement unless service infers safely. | Require `require_roles("owner","co_owner")`, pass `context.hotel_id`, and add cross-hotel API tests. |
| Multi-tenancy gap in payment link test webhook | `app/api/payment_link_tests.py:92 mercadopago_webhook`, `app/services/payment_link_test_service.py:404 refresh_mercadopago_payment_link_test_by_reference` | Webhook is public by design; it accepts `hotel_id` query and external reference. Signature validation exists, but the production plan must avoid trusting caller-provided hotel_id without provider validation. | Resolve hotel from signed external reference/provider payload, then enforce reference+hotel match and idempotency. |
| Multi-tenancy gap in OTA webhooks | `app/api/ota_webhooks.py:37 booking_webhook`, `:43 expedia_webhook`, `:49 despegar_webhook` | Secret is path-based, no JWT by design. Risk is acceptable only if per-hotel webhook secret is high entropy and never logged; deprecated routes exist. | Keep deprecated routes returning `410`, rotate secrets, rate limit webhook paths, audit every accepted event. |
| Security-critical path: check-in role checks | `app/api/checkin.py:21 checkin`, `app/api/checkin.py:39 checkout`, `app/api/checkin.py:57 validate_guest` use `get_auth_context` not role/permission dependencies | Any active hotel member may attempt check-in/out. V72 allows receptionist/manager/owners but not housekeeping by default for some actions. | Replace with permission dependency after SLICE-01 and add denied role tests. |
| Security-critical path: housekeeping allowed to create reservations/move rooms | `app/api/reservations.py:73 create_new_reservation`, `:393 room_move`, `:509 recalculate_allocation` include `housekeeping`; `app/api/bookings.py` check-in/out also includes housekeeping | V72 default roles list uses limpieza/no for guest modifications and sensitive actions; current role set uses `housekeeping` broadly on operational reservation paths. | Tighten default permissions and use explicit permissions for housekeeping-only room state actions. |
| Security-critical path: no central audit service | `app/models/audit_log.py`, `app/services/analytics_service.py` audit helpers, scattered writes in `reservation_service.py`/`reservation_operations_service.py` | Critical overrides, permission denials, payment links, cash close, and room moves need consistent append-only audit. | Create central audit service used by permission, reservation, payment, cash, allocation, and public API services. |
| Permission model is hard-coded | `app/dependencies/auth.py:103 require_permission` only maps `config:manage`; routers mostly use `require_roles` | V72 requires configurable permissions per hotel; hard-coded role tuples cannot express overrides or audited bypass. | Implement SLICE-01 first and migrate routers gradually with tests. |
| Frontend coverage gaps | Missing UI for companies, cash register, API keys, WhatsApp hooks, waitlist, room blocks, check-in wizard, laundry, stock | Operators cannot exercise complete V72 flows even where schema exists. | Build UI per slice with Playwright coverage for the operational path, not just settings forms. |
