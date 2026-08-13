# Hotel Chipre PMS mobile-first operations implementation

Source specification: `/Users/maximopaulos/.codex/attachments/136f323c-4027-43a7-b47d-b7e2494ab847/pasted-text-1.txt`.

Baseline: `541abcbf89d98d9c7db71a547e69620b2c442818` on `main`.

## Global constraints

- Keep one responsive web application and preserve the desktop experience.
- Mobile operational flows must work from 320 to 430 CSS pixels without page-level horizontal overflow; complex grids require a mobile alternative.
- Interactive targets are at least 44 by 44 CSS pixels and visible flows cover loading, empty, error, denied, offline, keyboard, focus, safe-area and orientation states.
- Backend authorization is authoritative. Missing read permission hides navigation, blocks direct routes and returns `403` without partial data.
- Only `owner` can administer permissions. This capability is non-delegable and no actor can elevate itself.
- Default permissions are role-based and the owner can set hotel-role overrides plus individual employee overrides, subject to non-configurable security invariants.
- An active guest lodging prohibition blocks reservation creation unless the actor has the explicit override permission and records a reason. Existing reservations enter review and check-in remains blocked.
- Promotions are typed, versioned, auditable, snapshot into quotes/reservations and never execute arbitrary formulas or scripts.
- Monetary values use `Numeric`/`Decimal`, never `Float` for new or migrated money paths.
- Stock and linen/laundry remain separate tenant-scoped domains. A movement cannot consume quantity from another location.
- PWA caches only the shell and static assets. Sensitive API responses and critical writes are never persisted or queued offline.
- Notifications are tenant-scoped, permission-filtered, deduplicated and auditable. Lock-screen summaries may contain guest name, room, event and amount only when the recipient can read those fields; never documents, contact data, notes, credentials or payment secrets.
- QA never completes real payments or sends real email, webhooks or OTA effects. External channels use local sinks/synthetic devices until an explicitly authorized pilot.
- Migrations are expand-contract, reversible where safe, have one linear Alembic head, and must work on SQLite tests and PostgreSQL semantics.
- Each task includes focused automated coverage; final acceptance requires the full backend suite, frontend lint/typecheck/build, clean migration dry-run, mobile Playwright matrix and evidence tied to the exact `code_sha`.

## Task 1: RBAC foundation and guest lodging prohibitions

Implement the P0 backend contract and migrations.

- Split broad permission keys into read/write/action permissions for guests, prohibitions, reservations, rooms, check-in/out, stock, laundry, rates, promotions and hotel settings while preserving safe existing access through an explicit migration/backfill.
- Make permission administration owner-only and non-delegable. Add per-user overrides in addition to existing hotel-role overrides, with resolution order individual override, hotel-role override, role default, deny; security invariants always win.
- Add APIs for permission catalog, role overrides, individual overrides, effective-permission preview and restoring defaults. Audit before/after values and clear effective-permission caches after changes.
- Add `GuestRestriction` as a hotel-scoped, auditable lodging prohibition with active/resolved status, reason, optional detail/validity, creator/resolver and timestamps. Backfill active `prohibido_alojar` tags without destructive removal.
- Enforce active prohibitions centrally in reservation quote/create/update, internal bookings, public booking, WhatsApp and waitlist promotion. Return `409` with stable code `GUEST_PROHIBITED` internally; external/public responses must not reveal the reason.
- Allow an override only with `reservation:prohibition_override`, the restriction identifier and a non-empty reason. Store the override snapshot/audit event.
- OTA inbound records that match a prohibited guest remain idempotently ingested as manual-review/no-auto-allocation and raise a domain event rather than being silently rejected.
- Adding a prohibition to a guest with future reservations marks those reservations for manual review without cancelling them. Check-in revalidates the prohibition and requires the explicit override path.
- Consolidate or harden legacy `/api/bookings` paths so they cannot bypass effective permissions, manual-rate controls or prohibition enforcement.
- Cover multi-hotel isolation, concurrent create/prohibit, owner-only permission administration, receptionist grant/revoke, direct API denial, public non-disclosure and migration upgrade/downgrade.

## Task 2: Mobile permission and guest-restriction experience

Implement the frontend contract for Task 1.

- Introduce route metadata and an authorization boundary that hides unauthorized navigation, blocks direct routes and renders a clear no-access state without firing protected queries.
- Update reservation drawers and actions to render only effective permitted operations.
- Rebuild Settings Permissions as mobile accordions by module with role selector, employee exceptions, effective source, immutable-lock explanation, preview and restore-default actions. Only owners can open it.
- Show active lodging restrictions in guest search/detail and reservation selection without exposing detail to actors lacking prohibition-read permission.
- Add create/resolve prohibition UI and the audited reservation-override confirmation flow, including mandatory reason and safe error handling.
- Test permission revocation in the active tab and cross-tab, direct deep links, keyboard/focus and 320-430 px layouts.

## Task 3: Canonical pricing, promotions and payment adjustments backend

- Implement the canonical order: nightly base, authorized manual override, nightly promotions, hotel taxes/fees, currency conversion snapshot, payment-method adjustment, currency rounding.
- Add versioned hotel-scoped promotion rules with typed conditions for booking/stay dates, min/max nights, weekdays, category/room, channel, guest/company/tag, payment currency and payment method.
- Support fixed/percentage benefits, whole-stay or from-night-N scope, priority and explicit stackability. Never allow a negative final amount.
- Add simulation and CRUD APIs; snapshots must preserve rule versions and nightly calculations when later rules change.
- Replace payment surcharge money/percent paths with Decimal-safe editable/reactivatable payment adjustments, validate enabled methods/currency/ranges and prevent double application with legacy payment-specific nightly pricing.
- Cover overlapping rules, currency rounding, disabled/reactivated adjustments, quote/edit behavior, snapshots, tenant isolation and migration round trips.

## Task 4: Mobile rates, promotions and hotel configuration

- Replace the mobile rate grid with range/category/day editing and a per-day card view while preserving the desktop grid.
- Build a no-code promotion editor and simulator for every Task 3 condition, benefit, scope, priority and stackability field.
- Show the complete nightly price, promotion, FX and payment-adjustment breakdown before confirmation.
- Reorganize hotel settings into General, Reservations, Guests, Rooms/check-in, Pricing/payments, Stock/laundry, Alerts/reports, Integrations, Users/permissions and Security.
- Replace raw JSON configuration inputs with typed mobile forms, save feedback, impact previews and audit history.

## Task 5: Stock and laundry integrity and mobile data APIs

- Enforce non-negative balance per item and location for stock and linen, including concurrent/retried movements.
- Make legacy laundry mutation endpoints read-only after verified compatibility/backfill; keep stock and linen schemas, permissions, queries and reports isolated.
- Add paginated aggregate summary/history endpoints to replace frontend N+1 requests.
- Split permissions into read, movement, adjustment/admin and vendor/remito/price operations with the agreed role defaults.
- Cover cross-hotel equal IDs, per-location balances, idempotent retries, legacy write denial and stock/linen non-mixing.

## Task 6: Mobile stock and laundry workflows

- Stock mobile tabs: summary, entry/exit/transfer, adjustment, alerts and history.
- Laundry mobile tabs: clean availability, outbound remito, return/discrepancy, vendor/prices and history.
- Use the aggregate APIs, pagination, optimistic feedback only where idempotent, and clear empty/error/offline states.
- Preserve desktop workflows and add full owner/manager/housekeeping responsive journeys.

## Task 7: Mobile shell, accessibility, PWA and performance

- Add role-aware bottom navigation: owner/co-owner/manager/reception use Planilla, Reservations, Guests, Rooms, More; housekeeping uses Planilla, Rooms, Laundry, Alerts, More. Remove destinations when permission is absent.
- Add visible notification access, hotel selector and global search; provide contextual sticky primary actions.
- Add manifest, optimized icons, standalone mode, install education and a small service worker that caches only versioned static assets.
- Implement safe areas, virtual-keyboard behavior, focus trap/return, Escape, background scroll lock, reduced motion and responsive master-admin navigation.
- Give planilla, permissions, rates and other table-heavy screens a card/day/task mobile alternative.
- Enforce bundle budgets: initial JS at most 130 KB gzip, CSS at most 15 KB gzip and each route chunk at most 60 KB gzip. Add budget/Web Vitals checks and optimize existing large image/font delivery.

## Task 8: Notification, web-push, email and daily-report backend

- Add tenant-scoped `Notification`, `PushSubscription`, `NotificationPreference`, `NotificationOutbox` and `DailyReportSchedule` models with expand-contract migrations.
- Convert domain changes into semantic events for reservations, guest prohibitions, check-in/out, room status/blocks, payment/cash failures, low stock, laundry discrepancies, rates/promotions/config/permissions and integration/OTA failures.
- Build in-app records and channel outbox entries with recipient permission filtering, unique event/channel/recipient dedupe, bounded retries, expiry, redacted logs and kill switches.
- Add inbox/read-state, preference, subscription and schedule APIs. Deep links revalidate authentication, hotel membership and entity permissions.
- Use standards-based Web Push behind `WEB_PUSH_ENABLED`; store endpoints/keys as sensitive data and remove expired subscriptions. Use existing email adapters behind `NOTIFICATION_EMAIL_ENABLED` and local sinks in QA.
- Generate a 07:00 hotel-timezone daily report for owner and manager by default, configurable by owner for time, recipients, channels and sections.
- Test DST/timezones, duplicate events, permission changes, expired subscriptions, retry/idempotency, redaction, multi-hotel isolation and external-effects fail-closed behavior.

## Task 9: Notification center, PWA push and report settings frontend

- Add a permission-filtered notification center, unread badge, read state, severity filters and secure deep-link handling.
- Add explicit install/subscribe flows; on iOS explain Home Screen installation before requesting permission from a direct user gesture.
- Render operational lock-screen summaries only from the backend-safe payload and fall back to generic text when fields are not permitted.
- Add owner-facing channel/event/role preferences, quiet hours and daily-report schedule/recipient/section forms.
- Add offline, denied-permission, expired-subscription and delivery-error states without blocking core hotel operations.

## Task 10: Full mobile E2E, performance, documentation and release gate

- Expand the catalog to every app route and owner, co-owner, manager, reception, housekeeping and master-admin using separate authenticated identities.
- Run the complete mobile business lifecycle: guest/restriction, quote/reservation/override, payment fixture, check-in, consumption/move/extend, checkout, cleaning/available, reports/analytics.
- Cover room blocks, stock/laundry isolation, rates/promotions/currency/payment adjustments, settings, permission grant/revoke, notifications, install, deep links, email sink and daily reports.
- Run Chromium Android and WebKit iPhone SE/15/15 Pro Max at portrait/landscape, virtual keyboard, slow network and offline shell; validate a real mirrored iPhone.
- Add accessibility and performance gates, realistic large-data profiles, reload persistence and cross-hotel cache isolation.
- Update OpenAPI/inventories, Graphify, decision log, configuration/deployment documentation and QA evidence templates.
- Run full validation and produce evidence tied to exact `code_sha`; certified release still requires current provider-bound `summary.json`, `validated-preview-manifest.json` and `attestation.json`.
